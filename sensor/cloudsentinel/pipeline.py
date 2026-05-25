"""
Async event pipeline for CloudSentinel.

Redis Streams are used as the fast shock absorber between SSH sessions and
analytics storage. The optional ClickHouse forwarder batches Redis events and
uses clickhouse-connect in a background thread so synchronous driver calls do
not block the asyncio loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import redis.asyncio as redis

from .config import ClickHouseSettings, KafkaSettings, NATSSettings, RedisSettings, secret_to_str
from .event_codec import dumps_text, loads_text
from .mitre import score_command

logger = logging.getLogger("cloudsentinel.pipeline")


@dataclass(slots=True)
class EventEnvelope:
    event_type: str
    session_id: str
    src_ip: str
    src_port: int
    timestamp: float
    payload: dict[str, Any]

    def to_redis_fields(self) -> dict[str, str]:
        data = asdict(self)
        data["payload"] = dumps_text(self.payload)
        return {key: dumps_text(value) for key, value in data.items()}

    def to_clickhouse_row(self) -> dict[str, Any]:
        return ClickHouseForwarder.envelope_to_row(self)

    def to_message_bytes(self) -> bytes:
        from .event_codec import dumps_bytes

        return dumps_bytes(asdict(self))


class LocalWAL:
    """Write-Ahead Log for persisting events when upstream is down."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def write(self, envelope: EventEnvelope) -> None:
        line = json.dumps(asdict(envelope)) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)

    async def read_and_clear(self) -> list[EventEnvelope]:
        async with self._lock:
            if not self.path.exists():
                return []
            lines = await asyncio.to_thread(self._read_clear)

        envelopes = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                envelopes.append(EventEnvelope(**data))
            except Exception as exc:
                logger.warning("Failed to parse WAL entry: %s", exc)
        return envelopes

    def _read_clear(self) -> list[str]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(self.path, "w", encoding="utf-8") as f:
                f.truncate(0)
            return lines
        except Exception:
            return []


class EventPipeline:
    """Async Redis Stream writer with graceful failure handling and WAL."""

    def __init__(
        self,
        settings: RedisSettings,
        nats_settings: NATSSettings | None = None,
        kafka_settings: KafkaSettings | None = None,
    ) -> None:
        self.settings = settings
        self.nats_settings = nats_settings or NATSSettings()
        self.kafka_settings = kafka_settings or KafkaSettings()
        self._redis: redis.Redis | None = None
        self._nats: Any = None
        self._kafka: Any = None
        self._pending: deque[EventEnvelope] = deque(maxlen=1000)
        self._wal = LocalWAL("var/lib/cloudsentinel/wal/events.jsonl")
        self._connected = False
        self._session_scores: dict[str, int] = {}
        self._session_techniques: dict[str, set[str]] = {}
        self._wal_flush_task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def session_scores(self) -> dict[str, int]:
        return dict(self._session_scores)

    async def start(self) -> None:
        try:
            self._redis = redis.from_url(
                self.settings.url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            await self._redis.ping()
            self._connected = True
            await self._drain_pending()
            logger.info("Redis pipeline connected: %s", self.settings.url)
        except Exception:
            self._connected = False
            if self._redis is not None:
                await self._redis.aclose()
            self._redis = None
            raise
        finally:
            # Always try to start background flush task if not running
            if self._wal_flush_task is None or self._wal_flush_task.done():
                self._wal_flush_task = asyncio.create_task(self._wal_flush_loop())

        await self._start_nats()
        await self._start_kafka()

    async def stop(self) -> None:
        if self._wal_flush_task is not None:
            self._wal_flush_task.cancel()
            try:
                await self._wal_flush_task
            except asyncio.CancelledError:
                pass
            self._wal_flush_task = None
            
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        if self._nats is not None:
            await self._nats.drain()
            self._nats = None
        if self._kafka is not None:
            await self._kafka.stop()
            self._kafka = None
        self._connected = False

    async def emit(self, envelope: EventEnvelope) -> None:
        if self._redis is None or not self._connected:
            self._pending.append(envelope)
            await self._wal.write(envelope)
            return
        try:
            await self._write(envelope)
        except Exception as exc:
            self._connected = False
            self._pending.append(envelope)
            await self._wal.write(envelope)
            logger.warning("Redis event write failed: %s, written to WAL.", exc)
            return
        await self._publish_optional_safe(envelope)

    async def reconnect(self) -> bool:
        """Try to restore Redis connection and drain pending events."""

        try:
            await self.stop()
            await self.start()
            return True
        except Exception as exc:
            logger.debug("Redis reconnect failed: %s", exc)
            return False

    async def _wal_flush_loop(self) -> None:
        """Background task to continually attempt to flush WAL if connected."""
        while True:
            await asyncio.sleep(5.0)
            if self._connected and self._redis is not None:
                wal_events = await self._wal.read_and_clear()
                if wal_events:
                    logger.info("Flushing %d events from WAL to Redis.", len(wal_events))
                    for env in wal_events:
                        try:
                            await self._write(env)
                            await self._publish_optional_safe(env)
                        except Exception as exc:
                            logger.warning("Failed to flush event from WAL, returning to WAL: %s", exc)
                            await self._wal.write(env)
                            self._connected = False
                            break

    async def _write(self, envelope: EventEnvelope) -> None:
        assert self._redis is not None
        await self._redis.xadd(
            self.settings.stream,
            envelope.to_redis_fields(),
            maxlen=self.settings.maxlen,
            approximate=True,
        )

    async def _drain_pending(self) -> None:
        # Also flush any pending memory queue directly
        while self._pending and self._redis is not None:
            envelope = self._pending.popleft()
            # We don't need to write to Redis here if the WAL logic handles it,
            # but for in-memory pending items that haven't hit WAL (though emit writes to WAL now),
            # we can flush them.
            try:
                await self._write(envelope)
                await self._publish_optional_safe(envelope)
            except Exception:
                # Put it back on left if we fail, though loop might break
                self._pending.appendleft(envelope)
                break

    async def _start_nats(self) -> None:
        if not self.nats_settings.enabled:
            return
        try:
            import nats

            self._nats = await nats.connect(self.nats_settings.url)
            logger.info("NATS connected: %s", self.nats_settings.url)
        except Exception as exc:
            logger.warning("NATS disabled after connection failure: %s", exc)
            self._nats = None

    async def _start_kafka(self) -> None:
        if not self.kafka_settings.enabled:
            return
        try:
            from aiokafka import AIOKafkaProducer

            self._kafka = AIOKafkaProducer(bootstrap_servers=self.kafka_settings.bootstrap_servers)
            await self._kafka.start()
            logger.info("Kafka producer connected: %s", self.kafka_settings.bootstrap_servers)
        except Exception as exc:
            logger.warning("Kafka disabled after connection failure: %s", exc)
            self._kafka = None

    async def _publish_optional(self, envelope: EventEnvelope) -> None:
        payload = envelope.to_message_bytes()
        if self._nats is not None:
            await self._nats.publish(self.nats_settings.subject, payload)
        if self._kafka is not None:
            await self._kafka.send_and_wait(self.kafka_settings.topic, payload)

    async def _publish_optional_safe(self, envelope: EventEnvelope) -> None:
        try:
            await self._publish_optional(envelope)
        except Exception as exc:
            logger.warning("Optional event publish failed: %s", exc)

    async def emit_login(
        self,
        *,
        session_id: str,
        src_ip: str,
        src_port: int,
        username: str,
        password: str,
        hassh: str | None,
        ja4s: str | None,
    ) -> None:
        await self.emit(
            EventEnvelope(
                event_type="auth.login",
                session_id=session_id,
                src_ip=src_ip,
                src_port=src_port,
                timestamp=time.time(),
                payload={
                    "username": username,
                    "password": password,
                    "hassh": hassh,
                    "ja4s": ja4s,
                    "risk_score": 5,
                    "mitre_techniques": ["T1078"],
                },
            )
        )

    async def emit_command(
        self,
        *,
        session_id: str,
        src_ip: str,
        src_port: int,
        username: str,
        command: str,
        output: str,
        hassh: str | None,
        ja4s: str | None,
    ) -> None:
        annotation = self._annotate_command(session_id, command)
        await self.emit(
            EventEnvelope(
                event_type="shell.command",
                session_id=session_id,
                src_ip=src_ip,
                src_port=src_port,
                timestamp=time.time(),
                payload={
                    "username": username,
                    "command": command,
                    "output": output,
                    "hassh": hassh,
                    "ja4s": ja4s,
                    "risk_score": annotation["risk_score"],
                    "session_risk_score": annotation["session_risk_score"],
                    "mitre_techniques": annotation["mitre_techniques"],
                    "mitre_names": annotation["mitre_names"],
                },
            )
        )

    def _annotate_command(self, session_id: str, command: str) -> dict[str, object]:
        annotation = score_command(command)
        risk_score = int(annotation["risk_score"])
        session_score = min(self._session_scores.get(session_id, 0) + risk_score, 100)
        self._session_scores[session_id] = session_score

        session_techniques = self._session_techniques.setdefault(session_id, set())
        for tech_id in annotation["mitre_techniques"]:
            session_techniques.add(str(tech_id))

        return {
            "risk_score": risk_score,
            "session_risk_score": session_score,
            "mitre_techniques": sorted(session_techniques),
            "mitre_names": annotation["mitre_names"],
        }


class ClickHouseForwarder:
    """Optional Redis Stream to ClickHouse batch forwarder."""

    COLUMNS = [
        "eventid",
        "session",
        "sensor",
        "src_ip",
        "src_port",
        "dst_ip",
        "dst_port",
        "country_code",
        "country_name",
        "city",
        "continent",
        "latitude",
        "longitude",
        "timezone",
        "username",
        "password",
        "auth_type",
        "attempt",
        "hassh_md5",
        "hassh_algorithms",
        "kexAlgs",
        "encCS",
        "macCS",
        "compCS",
        "version",
        "key_type",
        "input",
        "reason",
        "cloudsentinel_risk_score",
        "cloudsentinel_mitre_techniques",
        "cloudsentinel_soar_action",
        "detected_at",
        "block_started_at",
        "block_completed_at",
        "mttb_ms",
        "block_command",
        "block_stdout",
        "block_stderr",
        "duration",
        "timestamp",
    ]

    def __init__(
        self, redis_settings: RedisSettings, clickhouse_settings: ClickHouseSettings
    ) -> None:
        self.redis_settings = redis_settings
        self.clickhouse_settings = clickhouse_settings
        self._redis: redis.Redis | None = None
        self._client: Any = None
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._checkpoint_path = Path("var/lib/cloudsentinel/clickhouse_forwarder.lastid")

    async def start(self) -> None:
        if not self.clickhouse_settings.enabled:
            return
        try:
            self._redis = redis.from_url(
                self.redis_settings.url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()
            await asyncio.to_thread(self._connect_clickhouse)
            self._task = asyncio.create_task(self._run())
            logger.info("ClickHouse forwarder started")
        except Exception:
            if self._redis is not None:
                await self._redis.aclose()
            self._redis = None
            raise

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._redis is not None:
            await self._redis.aclose()
        if self._client is not None:
            await asyncio.to_thread(self._client.close)

    def _connect_clickhouse(self) -> None:
        import clickhouse_connect

        self._client = clickhouse_connect.get_client(
            host=self.clickhouse_settings.host,
            port=self.clickhouse_settings.port,
            username=self.clickhouse_settings.username,
            password=secret_to_str(self.clickhouse_settings.password),
            database=self.clickhouse_settings.database,
        )

    async def _run(self) -> None:
        assert self._redis is not None
        last_id = await asyncio.to_thread(self._load_checkpoint)
        while not self._stopped.is_set():
            try:
                streams = await self._redis.xread(
                    {self.redis_settings.stream: last_id},
                    count=self.clickhouse_settings.batch_size,
                    block=int(self.clickhouse_settings.flush_interval_seconds * 1000),
                )
                rows: list[dict[str, Any]] = []
                batch_last_id = last_id
                for _, messages in streams:
                    for message_id, fields in messages:
                        batch_last_id = message_id
                        rows.append(self._redis_fields_to_row(fields))
                if rows:
                    await asyncio.to_thread(self._insert_rows, rows)
                    last_id = batch_last_id
                    await asyncio.to_thread(self._save_checkpoint, last_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("ClickHouse forwarder error: %s", exc)
                await asyncio.sleep(1)

    def _load_checkpoint(self) -> str:
        try:
            value = self._checkpoint_path.read_text(encoding="utf-8").strip()
            return value or "0-0"
        except OSError:
            return "0-0"

    def _save_checkpoint(self, message_id: str) -> None:
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._checkpoint_path.with_suffix(".tmp")
        tmp_path.write_text(message_id, encoding="utf-8")
        os.replace(tmp_path, self._checkpoint_path)

    @staticmethod
    def _redis_fields_to_row(fields: dict[str, str]) -> dict[str, Any]:
        payload = loads_text(loads_text(fields.get("payload", "{}")))
        envelope = EventEnvelope(
            event_type=str(loads_text(fields.get("event_type", '"unknown"'))),
            session_id=str(loads_text(fields.get("session_id", '""'))),
            src_ip=str(loads_text(fields.get("src_ip", '""'))),
            src_port=int(loads_text(fields.get("src_port", "0"))),
            timestamp=float(loads_text(fields.get("timestamp", "0"))),
            payload=payload,
        )
        return ClickHouseForwarder.envelope_to_row(envelope)

    @staticmethod
    def envelope_to_row(envelope: EventEnvelope) -> dict[str, Any]:
        payload = envelope.payload
        def as_datetime(value: Any) -> datetime:
            return datetime.fromtimestamp(float(value or 0), tz=UTC)

        return {
            "eventid": str(payload.get("eventid", envelope.event_type)),
            "session": str(payload.get("session", envelope.session_id)),
            "sensor": str(payload.get("sensor", "CloudSentinel")),
            "src_ip": str(payload.get("src_ip", envelope.src_ip)),
            "src_port": int(payload.get("src_port", envelope.src_port) or 0),
            "dst_ip": str(payload.get("dst_ip", "")),
            "dst_port": int(payload.get("dst_port", 0) or 0),
            "country_code": str(payload.get("country_code", "XX")),
            "country_name": str(payload.get("country_name", "")),
            "city": str(payload.get("city", "")),
            "continent": str(payload.get("continent", "XX")),
            "latitude": str(payload.get("latitude", "0")),
            "longitude": str(payload.get("longitude", "0")),
            "timezone": str(payload.get("timezone", "UTC")),
            "username": str(payload.get("username", "")),
            "password": str(payload.get("password", "")),
            "auth_type": str(payload.get("auth_type", "password")),
            "attempt": int(payload.get("attempt", 0) or 0),
            "hassh_md5": str(payload.get("hassh_md5", payload.get("hassh", ""))),
            "hassh_algorithms": str(payload.get("hassh_algorithms", "")),
            "kexAlgs": list(payload.get("kexAlgs", [])),
            "encCS": list(payload.get("encCS", [])),
            "macCS": list(payload.get("macCS", [])),
            "compCS": list(payload.get("compCS", [])),
            "version": str(payload.get("version", "")),
            "key_type": str(payload.get("key_type", "")),
            "input": str(payload.get("input", payload.get("command", ""))),
            "reason": str(payload.get("reason", "")),
            "cloudsentinel_risk_score": int(
                payload.get("cloudsentinel_risk_score", payload.get("risk_score", 0)) or 0
            ),
            "cloudsentinel_mitre_techniques": list(
                payload.get(
                    "cloudsentinel_mitre_techniques",
                    payload.get("mitre_techniques", []),
                )
            ),
            "cloudsentinel_soar_action": str(payload.get("cloudsentinel_soar_action", "none")),
            "detected_at": as_datetime(payload.get("detected_at", 0)),
            "block_started_at": as_datetime(payload.get("block_started_at", 0)),
            "block_completed_at": as_datetime(payload.get("block_completed_at", 0)),
            "mttb_ms": float(payload.get("mttb_ms", 0) or 0),
            "block_command": str(payload.get("block_command", "")),
            "block_stdout": str(payload.get("block_stdout", "")),
            "block_stderr": str(payload.get("block_stderr", "")),
            "duration": str(payload.get("duration", "")),
            "timestamp": datetime.fromtimestamp(
                float(payload.get("timestamp", envelope.timestamp) or envelope.timestamp),
                tz=UTC,
            ),
        }

    def _insert_rows(self, rows: list[dict[str, Any]]) -> None:
        assert self._client is not None
        self._client.insert(
            self.clickhouse_settings.table,
            rows,
            column_names=self.COLUMNS,
        )
