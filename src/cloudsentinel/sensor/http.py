"""Attacker-facing HTTP honeypot runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from ..config import Settings
from ..pipeline import EventPipeline
from ..soar import SOAREngine

logger = structlog.get_logger("cloudsentinel.sensor.http")


async def start_http_honeypot(
    settings: Settings,
    pipeline: EventPipeline,
    soar: SOAREngine,
    stream: Any = None,
) -> None:
    try:
        import granian as _granian_http
        from granian.constants import Interfaces
        from granian.constants import Loops as GranianLoops
        _USE_GRANIAN_HTTP = True
    except ImportError:
        import uvicorn as _uvicorn_http
        _USE_GRANIAN_HTTP = False

    from ..http_server import create_http_honeypot

    app = create_http_honeypot(pipeline, soar, stream)
    http_port = getattr(settings.honeypot, "http_port", 8080)

    tls_kwargs: dict[str, Any] = {}
    if settings.honeypot.tls_enabled:
        cert = settings.honeypot.tls_cert_file
        key = settings.honeypot.tls_key_file
        if Path(cert).exists() and Path(key).exists():
            tls_kwargs = {"ssl_certfile": cert, "ssl_keyfile": key}
            logger.info("TLS enabled for HTTP honeypot: %s", cert)
        else:
            logger.warning("TLS cert/key not found, falling back to plain HTTP")

    proto = "https" if tls_kwargs else "http"
    if _USE_GRANIAN_HTTP:
        logger.info("HTTP honeypot (granian) listening on %s://%s:%s", proto, settings.honeypot.listen_host, http_port)
        await _granian_http.serve(
            app,
            host=settings.honeypot.listen_host,
            port=http_port,
            interface=Interfaces.ASGI,
            loop=GranianLoops.uvloop,
            ssl_certfile=tls_kwargs.get("ssl_certfile") if tls_kwargs else None,
            ssl_keyfile=tls_kwargs.get("ssl_keyfile") if tls_kwargs else None,
        )
    else:
        config = _uvicorn_http.Config(
            app,
            host=settings.honeypot.listen_host,
            port=http_port,
            log_level="warning",
            loop="asyncio",
            **tls_kwargs,
        )
        server = _uvicorn_http.Server(config)
        logger.info("HTTP honeypot (uvicorn) listening on %s://%s:%s", proto, settings.honeypot.listen_host, http_port)
        await server.serve()
