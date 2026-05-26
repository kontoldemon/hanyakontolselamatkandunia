"""
CloudSentinel Socket.io Live Streaming Module.
Phase 1: Self-hosted on DO Droplet alongside sensor.
Provides real-time event push to the War Room Dashboard via WebSocket.

Uses: python-socketio + aiohttp (async-native, matches our stack).
Phase 1 (DO): JWT-secured WebSocket with CORS whitelist.
Phase 2 (AWS): Migrate to App Runner with IAM auth.
"""

from __future__ import annotations

import asyncio
import json
import structlog
import urllib.parse
from collections import deque
from typing import Any

logger = structlog.get_logger("cloudsentinel.socketio")


class LiveStream:
    """
    Socket.io server for real-time event streaming.
    Runs alongside the sensor in the same asyncio event loop.

    Phase 1 (DO): JWT-secured WebSocket with CORS whitelist.
    Phase 2 (AWS): Migrate to App Runner with IAM auth.
    """

    # Default allowed origins for Phase 1
    DEFAULT_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://cloudsentinel.vercel.app",
        "https://cloudsentinel-dashboard.vercel.app",
    ]

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 3001,
        cors_origin: str | list[str] | None = None,
        auth_token: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.auth_token = auth_token

        # CORS: use provided origin or whitelist; never wildcard in production
        if cors_origin is None:
            self._cors_origins = self.DEFAULT_ALLOWED_ORIGINS
        elif isinstance(cors_origin, str) and cors_origin == "*":
            self._cors_origins = "*"
        else:
            self._cors_origins = cors_origin

        self._sio: Any = None
        self._app: Any = None
        self._runner: Any = None
        self._started: bool = False

        # Recent events buffer for new clients
        self._buffer: deque[dict[str, Any]] = deque(maxlen=1000)

        # Track authenticated clients
        self._auth_clients: set[str] = set()

    async def start(self) -> None:
        """Start the Socket.io + aiohttp server."""
        import socketio
        from aiohttp import web

        self._sio = socketio.AsyncServer(
            async_mode="aiohttp",
            cors_allowed_origins=self._cors_origins,
            logger=logger if logger.level <= logging.DEBUG else False,
        )
        self._app = web.Application()
        self._sio.attach(self._app)

        @self._sio.event
        async def connect(sid: str, environ: dict) -> None:
            # -- JWT / API Key authentication --
            if self.auth_token:
                auth_header = environ.get("HTTP_AUTHORIZATION", "")
                query_token = ""
                qs = environ.get("QUERY_STRING", "")
                params = urllib.parse.parse_qs(qs)
                query_token = params.get("token", [""])[0]

                provided = ""
                if auth_header.startswith("Bearer "):
                    provided = auth_header[7:]
                elif query_token:
                    provided = query_token

                if provided != self.auth_token:
                    logger.warning("Socket.io auth rejected for %s", sid)
                    await self._sio.disconnect(sid)
                    return

            self._auth_clients.add(sid)
            logger.info("Socket.io client connected: %s (authenticated)", sid)
            # Replay recent events
            for event in list(self._buffer)[-50:]:
                await self._sio.emit("cloudsentinel:event", event, to=sid)

        @self._sio.event
        async def disconnect(sid: str) -> None:
            self._auth_clients.discard(sid)
            logger.info("Socket.io client disconnected: %s", sid)

        @self._sio.event
        async def subscribe(sid: str, data: dict) -> None:
            """Client subscribes to specific event types (authenticated only)."""
            if self.auth_token and sid not in self._auth_clients:
                return
            event_types = data.get("types", [])
            logger.debug("Client %s subscribed to: %s", sid, event_types)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        self._started = True
        logger.info("Socket.io live stream on %s:%d", self.host, self.port)

    async def stop(self) -> None:
        """Stop the Socket.io server."""
        if self._runner:
            await self._runner.cleanup()
            self._started = False
            logger.info("Socket.io stopped")

    def emit(self, event: dict[str, Any]) -> None:
        """Emit an event to all connected WebSocket clients."""
        if not self._started or not self._sio:
            return

        # Clean sensitive fields for dashboard
        safe = dict(event)
        safe.pop("password", None)
        safe.pop("system", None)
        for k in list(safe):
            if k.startswith("log_"):
                del safe[k]
        # Buffer only sanitized events for replay.
        self._buffer.append(safe)

        # Emit asynchronously
        asyncio.create_task(self._sio.emit("cloudsentinel:event", safe))

    async def emit_coro(self, event: dict[str, Any]) -> None:
        """Coroutine version of emit."""
        if not self._started or not self._sio:
            return
        safe = dict(event)
        safe.pop("password", None)
        safe.pop("system", None)
        for k in list(safe):
            if k.startswith("log_"):
                del safe[k]
        self._buffer.append(safe)
        await self._sio.emit("cloudsentinel:event", safe)
