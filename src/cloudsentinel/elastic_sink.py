"""
CloudSentinel Elasticsearch SIEM Sink - ECS-formatted event forwarding.
Streams events to Elasticsearch in Elastic Common Schema (ECS) format
for integration with Kibana, SIEM dashboards, and detection rules.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

logger = structlog.get_logger("cloudsentinel.elastic")

ES_URL = os.getenv("CLOUDSENTINEL_ES_URL", "")
ES_API_KEY = os.getenv("CLOUDSENTINEL_ES_API_KEY", "")
ES_USERNAME = os.getenv("CLOUDSENTINEL_ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("CLOUDSENTINEL_ES_PASSWORD", "")
ES_INDEX_PREFIX = os.getenv("CLOUDSENTINEL_ES_INDEX_PREFIX", "cloudsentinel")
ES_BATCH_SIZE = int(os.getenv("CLOUDSENTINEL_ES_BATCH_SIZE", "100"))
ES_FLUSH_SECONDS = float(os.getenv("CLOUDSENTINEL_ES_FLUSH_SECONDS", "5.0"))


@dataclass
class ElasticSink:
    """Async Elasticsearch sink with ECS formatting and batching."""

    url: str = ES_URL
    api_key: str = ES_API_KEY
    username: str = ES_USERNAME
    password: str = ES_PASSWORD
    index_prefix: str = ES_INDEX_PREFIX
    batch_size: int = ES_BATCH_SIZE
    flush_seconds: float = ES_FLUSH_SECONDS
    _client: httpx.AsyncClient | None = None
    _buffer: deque[dict[str, Any]] = field(default_factory=deque)
    _flush_task: asyncio.Task[None] | None = None
    _total_sent: int = 0
    _total_failed: int = 0

    async def start(self) -> None:
        if not self.url:
            logger.info("Elasticsearch sink not configured -- disabled")
            return
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username and self.password:
            from base64 import b64encode
            creds = b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"

        self._client = httpx.AsyncClient(
            base_url=self.url.rstrip("/"),
            headers=headers,
            timeout=15.0,
        )
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Elasticsearch sink ready: %s", self.url)

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush()
        if self._client:
            await self._client.aclose()

    async def send(self, event: dict[str, Any]) -> None:
        """Queue a CloudSentinel event for ECS forwarding."""
        if not self._client:
            return
        ecs = _to_ecs(event)
        self._buffer.append(ecs)
        if len(self._buffer) >= self.batch_size:
            await self._flush()

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self.flush_seconds)
            await self._flush()

    async def _flush(self) -> None:
        if not self._buffer or not self._client:
            return

        batch_size = min(len(self._buffer), self.batch_size)
        batch = [self._buffer.popleft() for _ in range(batch_size)]

        today = datetime.now(UTC).strftime("%Y.%m.%d")
        index = f"{self.index_prefix}-{today}"
        lines: list[str] = []
        for doc in batch:
            lines.append(json.dumps({"index": {"_index": index}}))
            lines.append(json.dumps(doc, default=str))
        body = "\n".join(lines) + "\n"

        try:
            resp = await self._client.post("/_bulk", content=body)
            if 200 <= resp.status_code < 300:
                result = resp.json()
                if result.get("errors"):
                    self._total_failed += sum(
                        1 for item in result.get("items", [])
                        if item.get("index", {}).get("error")
                    )
                self._total_sent += batch_size
            else:
                logger.warning("Elasticsearch bulk failed: HTTP %d", resp.status_code)
                self._total_failed += batch_size
        except Exception as exc:
            logger.warning("Elasticsearch flush error: %s", exc)
            self._total_failed += batch_size

    @property
    def stats(self) -> dict[str, int]:
        return {
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "buffer_size": len(self._buffer),
        }


def _to_ecs(event: dict[str, Any]) -> dict[str, Any]:
    """Convert CloudSentinel event to Elastic Common Schema (ECS) 8.x."""
    ts = event.get("timestamp", time.time())
    if isinstance(ts, (int, float)):
        ts = datetime.fromtimestamp(ts, tz=UTC).isoformat()

    ecs: dict[str, Any] = {
        "@timestamp": ts,
        "event": {
            "kind": "event",
            "category": ["network", "intrusion_detection"],
            "type": [event.get("eventid", "unknown")],
            "action": event.get("eventid", ""),
            "risk_score": event.get("cloudsentinel_risk_score", 0),
        },
        "source": {
            "ip": event.get("src_ip", "0.0.0.0"),
            "port": event.get("src_port", 0),
            "geo": {
                "country_iso_code": event.get("country_code", "XX"),
                "country_name": event.get("country_name", "Unknown"),
                "city_name": event.get("city", "Unknown"),
                "location": {
                    "lat": float(str(event.get("latitude", 0))),
                    "lon": float(str(event.get("longitude", 0))),
                },
            },
        },
        "user": {
            "name": event.get("username", ""),
        },
        "observer": {
            "product": "CloudSentinel",
            "vendor": "USAS FYP",
            "version": os.getenv("CLOUDSENTINEL_VERSION", "2.0.0"),
        },
        "cloudsentinel": {
            "session": event.get("session", ""),
            "hassh_md5": event.get("hassh_md5", ""),
            "soar_action": event.get("cloudsentinel_soar_action", "none"),
            "mitre_techniques": event.get("cloudsentinel_mitre_techniques", []),
            "mttb_ms": event.get("mttb_ms", 0),
            "input": str(event.get("input", ""))[:2000],
        },
    }

    techniques = event.get("cloudsentinel_mitre_techniques", [])
    if techniques:
        ecs["threat"] = {
            "technique": {"id": techniques},
            "framework": "MITRE ATT&CK",
        }

    return ecs


_elastic_sink: ElasticSink | None = None


def get_elastic_sink() -> ElasticSink:
    global _elastic_sink
    if _elastic_sink is None:
        _elastic_sink = ElasticSink()
    return _elastic_sink
