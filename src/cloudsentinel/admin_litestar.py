"""
CloudSentinel Admin API -- Litestar Upgrade Path (v2.2+).

Litestar provides better async performance than FastAPI (uvloop-native, no
WSGI bridge), built-in OpenTelemetry integration, and pydantic v2 native.
This is an optional upgrade for production deployments.

To use: set ADMIN_BACKEND=litestar in .env
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.admin")


def create_litestar_app(
    settings: Any,
    pipeline: Any,
) -> Any:
    """Create a Litestar admin API application.

    This is a drop-in replacement for create_admin_app() in admin_api.py.
    API routes are identical -- no dashboard changes needed.

    Requires: pip install litestar[standard]
    """
    try:
        from litestar import Litestar, get, post
        from litestar.config.cors import CORSConfig
        from litestar.di import Provide
        from litestar.status_codes import HTTP_200_OK, HTTP_401_UNAUTHORIZED
    except ImportError:
        logger.warning("litestar not installed -- falling back to FastAPI")
        from .admin_api import create_admin_app
        return create_admin_app(settings, pipeline)

    from .metrics import get_metrics

    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": "2.1.0"}

    async def readiness() -> dict[str, Any]:
        connected = getattr(pipeline, "_connected", False)
        return {
            "status": "ready" if connected else "degraded",
            "redis_connected": connected,
            "clickhouse_enabled": settings.clickhouse.enabled,
            "stream_enabled": settings.stream.enabled,
        }

    async def stats() -> dict[str, Any]:
        metrics = get_metrics()
        return {
            "connections_total": metrics.connections_total,
            "connections_active": metrics.connections_active,
            "auth_failures": metrics.auth_failures,
            "commands_processed": metrics.commands_processed,
            "soar_blocks": metrics.soar_blocks,
            "uptime_seconds": metrics.uptime_seconds,
        }

    cors_config = CORSConfig(allow_origins=["*"], allow_methods=["GET"])

    app = Litestar(
        route_handlers=[healthz, readiness, stats],
        cors_config=cors_config,
        on_startup=[],
        on_shutdown=[],
    )

    logger.info("Litestar admin API created (v2.2 upgrade path)")
    return app
