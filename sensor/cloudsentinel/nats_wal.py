"""
CloudSentinel NATS JetStream WAL - Persistent event buffer.
Replaces file-based WAL with NATS JetStream for at-least-once delivery
with automatic replay on consumer reconnect.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import nats
from nats.js.api import ConsumerConfig, StorageType

logger = logging.getLogger("cloudsentinel.nats_wal")

NATS_URL = os.getenv("CLOUDSENTINEL_NATS_URL", "nats://localhost:4222")
NATS_STREAM = os.getenv("CLOUDSENTINEL_NATS_STREAM", "CLOUDSENTINEL_EVENTS")
NATS_SUBJECT = os.getenv("CLOUDSENTINEL_NATS_SUBJECT", "cloudsentinel.events.*")


@dataclass
class JetStreamWAL:
    """NATS JetStream-backed Write-Ahead Log with persistent storage."""

    url: str = NATS_URL
    stream_name: str = NATS_STREAM
    subject: str = NATS_SUBJECT
    _nc: Any = None
    _js: Any = None
    _connected: bool = False

    async def start(self) -> None:
        try:
            self._nc = await nats.connect(self.url)
            self._js = self._nc.jetstream()

            # Ensure stream exists (idempotent)
            try:
                await self._js.add_stream(
                    name=self.stream_name,
                    subjects=[self.subject],
                    storage=StorageType.FILE,
                    max_age=7 * 24 * 3600,  # 7 days retention
                    max_bytes=1024 * 1024 * 1024,  # 1 GB
                )
            except Exception:
                # Stream already exists
                pass

            self._connected = True
            logger.info("NATS JetStream WAL ready: %s", self.stream_name)
        except Exception as exc:
            logger.warning("NATS JetStream unavailable, falling back to file WAL: %s", exc)
            self._connected = False

    async def stop(self) -> None:
        if self._nc:
            await self._nc.drain()

    async def publish(self, event: dict[str, Any]) -> bool:
        """Publish event to JetStream with ack guarantee."""
        if not self._connected or not self._js:
            return False
        try:
            data = json.dumps(event, default=str).encode("utf-8")
            ack = await self._js.publish(
                f"cloudsentinel.events.{event.get('eventid', 'unknown')}",
                data,
            )
            return bool(ack)
        except Exception as exc:
            logger.debug("JetStream publish failed: %s", exc)
            return False

    async def replay(self, consumer_name: str, callback: Any) -> None:
        """Replay all buffered events since last ack."""
        if not self._connected or not self._js:
            return
        try:
            sub = await self._js.pull_subscribe(
                self.subject,
                consumer_name,
                config=ConsumerConfig(
                    ack_policy="explicit",
                    max_deliver=5,
                ),
            )
            while True:
                try:
                    msgs = await sub.fetch(100, timeout=5)
                    for msg in msgs:
                        try:
                            event = json.loads(msg.data.decode("utf-8"))
                            await callback(event)
                            await msg.ack()
                        except Exception as exc:
                            logger.warning("WAL replay handler failed: %s", exc)
                            await msg.nak()
                except asyncio.TimeoutError:
                    break
        except Exception as exc:
            logger.warning("JetStream replay error: %s", exc)

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "stream": self.stream_name,
            "url": self.url,
        }


_jetstream_wal: JetStreamWAL | None = None


def get_jetstream_wal() -> JetStreamWAL:
    global _jetstream_wal
    if _jetstream_wal is None:
        _jetstream_wal = JetStreamWAL()
    return _jetstream_wal
