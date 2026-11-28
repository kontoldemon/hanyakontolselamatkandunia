"""Health, readiness, and metrics routes."""

from __future__ import annotations

import time
from typing import Any, Callable

from fastapi import APIRouter, Depends, Response

from ...config import Settings
from ...pipeline import EventPipeline
from .. import queries
from ..block_state import count_active_blocks


def build_health_router(
    settings: Settings,
    pipeline: EventPipeline,
    require_auth: Callable[..., Any],
    clickhouse_health: Callable[[Settings], Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "hostname": settings.honeypot.hostname,
            "redis_connected": pipeline.connected,
            "pending_events": pipeline.pending_count,
        }

    @router.get("/readiness", dependencies=[Depends(require_auth)])
    async def readiness() -> dict[str, Any]:
        clickhouse_enabled = bool(getattr(settings.clickhouse, "enabled", False))
        clickhouse_ok = await clickhouse_health(settings)
        return {
            "ok": pipeline.connected or pipeline.pending_count >= 0,
            "redis_connected": pipeline.connected,
            "pending_events": pipeline.pending_count,
            "clickhouse_enabled": clickhouse_enabled,
            "clickhouse_ok": clickhouse_ok,
            "stream_enabled": bool(settings.stream.enabled),
            "stream_port": settings.stream.port if settings.stream.enabled else 0,
            "ssh_port": settings.honeypot.ssh_port,
            "deception_level": settings.deception.level,
            "deception_mode": settings.llm.deception_mode,
        }

    @router.get("/metrics")
    async def metrics_endpoint() -> Response:
        try:
            from ...metrics import get_metrics

            metrics = get_metrics()
            return Response(content=metrics.render(), media_type=metrics.content_type)
        except Exception:
            return Response(
                content="# CloudSentinel metrics unavailable\n",
                media_type="text/plain",
            )

    @router.get("/metrics/json", dependencies=[Depends(require_auth)])
    async def metrics_json() -> dict[str, Any]:
        try:
            from ...metrics import get_metrics

            metrics = get_metrics()
            mttb_value = metrics.mttb_ms or await queries.load_latest_mttb_async(settings)
            blocked_current = await count_active_blocks(
                settings.redis.url,
                len(metrics.blocked_ips),
            )
            return {
                "active_sessions": metrics.active_sessions,
                "mttb_ms": mttb_value,
                "total_connections": metrics.total_connections,
                "total_auth_failures": metrics.total_auth_failures,
                "total_auth_successes": metrics.total_auth_successes,
                "total_commands": metrics.total_commands,
                "total_blocks": metrics.total_blocks,
                "total_blocks_iptables": metrics.total_blocks_iptables,
                "blocked_ips_current": blocked_current,
                "uptime_seconds": time.time() - metrics.start_time,
            }
        except Exception:
            return {"error": "metrics unavailable"}

    return router
