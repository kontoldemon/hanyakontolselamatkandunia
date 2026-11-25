"""Manual IP blocking route."""

from __future__ import annotations

import ipaddress
import json
import time
from typing import Any, Callable

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ...config import Settings
from ...geoip import is_public_ip

logger = structlog.get_logger("cloudsentinel.api.routers.blocks")


def build_blocks_router(
    settings: Settings,
    require_auth: Callable[..., Any],
    soar: Any,
    is_allowlisted: Callable[[str, list[str]], bool],
    manual_block_args: Callable[[str, str, str, str], list[str]],
    run_command: Callable[[list[str]], Any],
    spawn_unblock: Callable[[str, str, int, str], None],
    publish_block: Callable[..., Any],
) -> tuple[APIRouter, Callable[..., Any]]:
    router = APIRouter()

    @router.post("/admin/block-ip", dependencies=[Depends(require_auth)])
    async def manual_block_ip(body: dict[str, Any]) -> dict[str, Any]:
        ip = str(body.get("ip") or "").strip()
        reason = str(body.get("reason") or "manual-dashboard")[:120]
        ttl = int(body.get("ttl") or settings.soar.block_ttl or 3600)
        try:
            ipaddress.ip_address(ip)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid IP address") from exc
        if is_allowlisted(ip, settings.soar.allowlist):
            raise HTTPException(status_code=400, detail="IP is allowlisted")
        if not is_public_ip(ip):
            raise HTTPException(status_code=400, detail="Only public IPs can be blocked")

        started = time.time()
        firewall_path = settings.soar.firewall_path or "/sbin/iptables"
        check = manual_block_args(firewall_path, "-C", ip, reason)
        add = manual_block_args(firewall_path, "-I", ip, reason)

        action = ""
        if (
            soar is not None
            and getattr(soar, "eventgrid_enabled", False)
            and getattr(soar, "eventgrid_endpoint", "")
            and getattr(soar, "eventgrid_key", "")
        ):
            ok, error = await publish_block(
                endpoint=soar.eventgrid_endpoint,
                key=soar.eventgrid_key,
                ip=ip,
                ttl=ttl,
                reason=reason,
                risk_score=0,
                session_id="manual",
            )
            if ok:
                action = "eventgrid_published"
            else:
                logger.warning("manual_eventgrid_block_failed", ip=ip, error=error)

        redis_available = soar is not None and getattr(soar, "_redis", None) is not None
        if redis_available:
            payload = json.dumps(
                {
                    "ip": ip,
                    "action": "block",
                    "ttl": ttl,
                    "reason": reason,
                    "risk_score": 0,
                    "session_id": "manual",
                }
            )
            try:
                await soar._redis.publish("cloudsentinel:soar:blocks", payload)
                await soar._redis.set(f"soar:block:{ip}", "1", ex=ttl if ttl > 0 else None)
                if not action:
                    action = "event_published"
            except Exception as exc:
                logger.warning("manual_host_agent_publish_failed", ip=ip, error=str(exc))
                redis_available = False

        if not action and not redis_available:
            existing_code, _, _ = await run_command(check)
            if existing_code == 0:
                action = "already_blocked"
            else:
                code, _, stderr = await run_command(add)
                if code != 0:
                    raise HTTPException(
                        status_code=500,
                        detail=stderr[:200] or "Firewall block failed",
                    )
                action = "blocked"
                if ttl > 0:
                    spawn_unblock(ip, reason, ttl, firewall_path)

        try:
            from ...metrics import get_metrics

            metrics = get_metrics()
            metrics.record_block("manual_block")
            metrics.blocked_ips.add(ip)
            metrics.set_blocked_count(len(metrics.blocked_ips))
            metrics.set_mttb((time.time() - started) * 1000)
        except Exception:
            pass
        return {
            "ok": True,
            "ip": ip,
            "ttl": ttl,
            "reason": reason,
            "action": action,
            "mttb_ms": round((time.time() - started) * 1000, 3),
        }

    return router, manual_block_ip
