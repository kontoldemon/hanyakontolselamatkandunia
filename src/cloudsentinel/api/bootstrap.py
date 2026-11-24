"""Admin API startup for the operator control plane."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog

from .. import tls
from ..admin_api import create_admin_app
from ..config import Settings
from ..pipeline import EventPipeline

logger = structlog.get_logger("cloudsentinel.api.bootstrap")


async def start_admin_api(
    settings: Settings,
    pipeline: EventPipeline,
    soar: Any = None,
    cert_path: str = "",
    key_path: str = "",
) -> None:
    admin_server = os.getenv("ADMIN_SERVER", "uvicorn").lower()
    if admin_server == "granian":
        try:
            import granian
            from granian.constants import Interfaces, Loops

            _USE_GRANIAN = True
        except ImportError:
            import uvicorn

            logger.warning("Granian requested but unavailable, falling back to uvicorn")
            _USE_GRANIAN = False
    else:
        import uvicorn

        _USE_GRANIAN = False

    app = create_admin_app(settings, pipeline, soar)

    tls_kwargs: dict[str, Any] = {}
    if cert_path and key_path and Path(cert_path).exists() and Path(key_path).exists():
        tls_kwargs = {"ssl_certfile": cert_path, "ssl_keyfile": key_path}
        logger.info("TLS enabled for admin API: %s", cert_path)
    elif settings.tls.enabled:
        # Auto-generate TLS cert if not provided
        gen_cert, gen_key = tls.generate_self_signed_cert(
            hostname=settings.honeypot.hostname,
            output_dir="var/lib/cloudsentinel/tls",
        )
        if gen_cert and gen_key:
            tls_kwargs = {"ssl_certfile": gen_cert, "ssl_keyfile": gen_key}
            logger.info("TLS auto-generated for admin API: %s", gen_cert)
    else:
        logger.warning("Admin API running without TLS - JWT tokens sent in plaintext")

    proto = "https" if tls_kwargs else "http"
    if _USE_GRANIAN:
        logger.info("Admin API (granian) listening on %s://%s:%s", proto, settings.admin.host, settings.admin.port)
        await granian.serve(
            app,
            host=settings.admin.host,
            port=settings.admin.port,
            interface=Interfaces.ASGI,
            loop=Loops.uvloop,
            ssl_certfile=tls_kwargs.get("ssl_certfile"),
            ssl_keyfile=tls_kwargs.get("ssl_keyfile"),
        )
    else:
        config = uvicorn.Config(
            app,
            host=settings.admin.host,
            port=settings.admin.port,
            log_level="info",
            loop="asyncio",
            **tls_kwargs,
        )
        server = uvicorn.Server(config)
        logger.info("Admin API (uvicorn) listening on %s://%s:%s", proto, settings.admin.host, settings.admin.port)
        await server.serve()
