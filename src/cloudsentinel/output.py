"""
CloudSentinel ClickHouse output — batch writer (legacy module).

Prefer pipeline.ClickHouseForwarder for new code.
This module is retained for backward compatibility.
"""

from __future__ import annotations

import asyncio
try:
    from msgspec import json as _msgspec_json
    def _fast_dumps(obj, **kw):
        return _msgspec_json.encode(obj).decode("utf-8")
    _USE_MSGSPEC = True
except ImportError:
    import json as _json
    def _fast_dumps(obj, **kw):
        return _json.dumps(obj, **kw)
    _USE_MSGSPEC = False
import structlog
from collections import deque
from typing import Any
from urllib.parse import quote

logger = structlog.get_logger("cloudsentinel.output")


class ClickHouseOutput:
    """Async ClickHouse event writer using aiohttp. Batched writes with retry."""

    def __init__(
        self,
        url: str = "http://127.0.0.1:8123",
        database: str = "default",
        table: str = "cloudsentinel_events",
        batch_size: int = 20,
        flush_interval: float = 5.0,
        max_queue: int = 1000,
        timeout: float = 10.0,
        debug: bool = False,
    ) -> None:
        self.url = url.rstrip("/")
        self.database = database
        self.table = table
        self.batch_size = max(1, batch_size)
        self.flush_interval = max(0.1, flush_interval)
        self.max_queue = max(1, max_queue)
        self.timeout = timeout
        self.debug = debug

        self._queue: deque[dict[str, Any]] = deque()
        self._sending: bool = False
        self._stopped: bool = False
        self._flush_task: asyncio.Task | None = None
        self._session: Any = None

    async def start(self) -> None:
        import aiohttp
        self._session = aiohttp.ClientSession()
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("ClickHouse output started: %s/%s.%s", self.url, self.database, self.table)

    async def stop(self) -> None:
        self._stopped = True
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_now()
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("ClickHouse output stopped")

    def write(self, event: dict[str, Any]) -> None:
        if self._stopped:
            return
        event = dict(event)
        event.pop("system", None)
        for key in list(event):
            if key.startswith("log_"):
                del event[key]
        while len(self._queue) >= self.max_queue:
            self._queue.popleft()
        self._queue.append(event)
        if len(self._queue) >= self.batch_size:
            asyncio.create_task(self._flush_now())

    async def _flush_loop(self) -> None:
        while not self._stopped:
            await asyncio.sleep(self.flush_interval)
            await self._flush_now()

    async def _flush_now(self) -> None:
        if self._sending or not self._queue:
            return
        self._sending = True
        batch_size = min(len(self._queue), self.batch_size)
        batch = [self._queue.popleft() for _ in range(batch_size)]
        try:
            if self._session is None:
                import aiohttp
                self._session = aiohttp.ClientSession()
            query = f"INSERT INTO {self.database}.{self.table} FORMAT JSONEachRow"
            target = f"{self.url}/?query={quote(query)}"
            payload = "\n".join(
                _fast_dumps(e) for e in batch
            ).encode("utf-8") + b"\n"
            async with self._session.post(
                target,
                data=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                if 200 <= resp.status < 300:
                    if self.debug:
                        logger.debug("Wrote %d events to ClickHouse", len(batch))
                else:
                    text = await resp.text()
                    logger.error("ClickHouse HTTP %d: %s", resp.status, text[:200])
                    self._requeue_front(batch)
        except asyncio.TimeoutError:
            logger.error("ClickHouse timeout after %.1fs", self.timeout)
            self._requeue_front(batch)
        except Exception as exc:
            logger.error("ClickHouse write failed: %s", exc)
            self._requeue_front(batch)
        finally:
            self._sending = False

    def _requeue_front(self, batch: list[dict[str, Any]]) -> None:
        for event in reversed(batch):
            while len(self._queue) >= self.max_queue:
                self._queue.pop()
            self._queue.appendleft(event)
