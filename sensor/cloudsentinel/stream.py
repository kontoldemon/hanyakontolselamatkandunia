"""
CloudSentinel Socket.io Live Streaming Module.
Phase 1: Self-hosted on DO Droplet alongside sensor.
Provides real-time event push to the War Room Dashboard via WebSocket.

Uses: python-socketio + aiohttp (async-native, matches our stack).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import Any

logger = logging.getLogger("cloudsentinel.socketio")


class LiveStream:
    """
    Socket.io server for real-time event streaming.
    Runs alongside the sensor in the same asyncio event loop.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 3001,
        cors_origin: str = "*",
    ) -> None:
        self.host = host
        self.port = port
        self.cors_origin = cors_origin
        self._sio: Any = None
        self._app: Any = None
        self._runner: Any = None
        self._started: bool = False

        # Recent events buffer for new clients
        self._buffer: deque[dict[str, Any]] = deque(maxlen=1000)

    async def start(self) -> None:
        """Start the Socket.io + aiohttp server."""
        import socketio
        from aiohttp import web

        self._sio = socketio.AsyncServer(
            async_mode="aiohttp",
            cors_allowed_origins=self.cors_origin,
            logger=logger if logger.level <= logging.DEBUG else False,
        )
        self._app = web.Application()
        self._sio.attach(self._app)

        @self._sio.event
        async def connect(sid: str, environ: dict) -> None:
            logger.info("Socket.io client connected: %s", sid)
            # Replay recent events
            for event in list(self._buffer)[-50:]:
                await self._sio.emit("cloudsentinel:event", event, to=sid)

        @self._sio.event
        async def disconnect(sid: str) -> None:
            logger.info("Socket.io client disconnected: %s", sid)

        @self._sio.event
        async def subscribe(sid: str, data: dict) -> None:
            """Client subscribes to specific event types."""
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
