"""Cover remaining pipeline WAL, drain, and forwarder branches."""

from __future__ import annotations

import asyncio
import builtins
import json
import sys

import pytest

import cloudsentinel.pipeline as pipeline_module
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import ClickHouseForwarder, EventEnvelope, EventPipeline, LocalWAL


class FakeRedis:
    def __init__(self) -> None:
        self.xadds: list = []
        self.closed = False

    async def ping(self) -> bool:
        return True

    async def xadd(self, _stream: str, fields: dict, **_kwargs: object) -> str:
        self.xadds.append(fields)
        return "1-0"

    async def aclose(self) -> None:
        self.closed = True


class FakeWal:
    def __init__(self, events: list[EventEnvelope]) -> None:
        self.events = list(events)
        self.written: list[EventEnvelope] = []

    async def read_and_clear(self) -> list[EventEnvelope]:
        events = list(self.events)
        self.events.clear()
        return events

    async def write(self, envelope: EventEnvelope) -> None:
        self.written.append(envelope)


def _settings():
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.nats.enabled = False
    settings.kafka.enabled = False
    return settings


def test_local_wal_empty_and_error(monkeypatch, tmp_path) -> None:
    wal = LocalWAL(tmp_path / "missing.wal")
    assert asyncio.run(wal.read_and_clear()) == []

    wal.path.write_text("\n", encoding="utf-8")
    assert asyncio.run(wal.read_and_clear()) == []

    def broken_open(*_args: object, **_kwargs: object) -> None:
        raise OSError("open failed")

    monkeypatch.setattr(builtins, "open", broken_open)
    assert wal._read_clear() == []


@pytest.mark.asyncio
async def test_pipeline_start_else_and_drain_failure(monkeypatch) -> None:
    settings = _settings()
    fake_redis = FakeRedis()
    monkeypatch.setattr(pipeline_module.redis, "from_url", lambda *_a, **_k: fake_redis)
    monkeypatch.setattr(pipeline_module, "_TENACITY", False)
    pipeline = EventPipeline(settings.redis)
    await pipeline.start()
    await pipeline.stop()

    broken = EventPipeline(settings.redis)

    async def drain_fail() -> None:
        raise RuntimeError("drain failed")

    monkeypatch.setattr(broken, "_drain_pending", drain_fail)
    with pytest.raises(RuntimeError):
        await broken.start()
    await broken.stop()


@pytest.mark.asyncio
async def test_wal_flush_loop(monkeypatch) -> None:
    settings = _settings()
    envelope = EventEnvelope("e", "s", "8.8.8.8", 22, 1.0, {"eventid": "e"})
    pipeline = EventPipeline(settings.redis)
    pipeline._connected = True
    pipeline._redis = FakeRedis()  # type: ignore[assignment]
    pipeline._wal = FakeWal([envelope])  # type: ignore[assignment]

    real_sleep = asyncio.sleep

    async def no_sleep(_seconds: float) -> None:
        await real_sleep(0)

    async def ok_write(_envelope: EventEnvelope) -> None:
        return None

    async def ok_publish(_envelope: EventEnvelope) -> None:
        return None

    monkeypatch.setattr(pipeline_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(pipeline, "_write", ok_write)
    monkeypatch.setattr(pipeline, "_publish_optional_safe", ok_publish)
    task = asyncio.create_task(pipeline._wal_flush_loop())
    await real_sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    failing = EventPipeline(settings.redis)
    failing._connected = True
    failing._redis = FakeRedis()  # type: ignore[assignment]
    failing._wal = FakeWal([envelope])  # type: ignore[assignment]

    async def bad_write(_envelope: EventEnvelope) -> None:
        raise RuntimeError("write failed")

    monkeypatch.setattr(failing, "_write", bad_write)
    task = asyncio.create_task(failing._wal_flush_loop())
    await real_sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert failing._wal.written


@pytest.mark.asyncio
async def test_pipeline_drain_and_login(monkeypatch) -> None:
    settings = _settings()
    pipeline = EventPipeline(settings.redis)
    envelope = EventEnvelope("e", "s", "8.8.8.8", 22, 1.0, {"eventid": "e"})
    pipeline._pending.append(envelope)
    pipeline._redis = FakeRedis()  # type: ignore[assignment]

    async def bad_write(_envelope: EventEnvelope) -> None:
        raise RuntimeError("write failed")

    monkeypatch.setattr(pipeline, "_write", bad_write)
    await pipeline._drain_pending()
    assert pipeline._pending

    pipeline._wal = FakeWal([])  # type: ignore[assignment]
    pipeline._connected = False
    await pipeline.emit_login(
        session_id="s",
        src_ip="8.8.8.8",
        src_port=22,
        username="root",
        password="x",
        hassh=None,
        ja4s=None,
    )


def test_forwarder_spill_blank_and_row(monkeypatch, tmp_path) -> None:
    settings = _settings()
    settings.clickhouse.enabled = True
    forwarder = ClickHouseForwarder(settings.redis, settings.clickhouse)
    forwarder._spill_path = tmp_path / "spill.jsonl"
    forwarder._spill_path.write_text("\n", encoding="utf-8")
    assert forwarder._spill_read() == []

    envelope = EventEnvelope(
        "cloudsentinel.command.output",
        "s",
        "8.8.8.8",
        22,
        1.0,
        {"eventid": "cloudsentinel.command.output", "output": "secret output"},
    )
    row = ClickHouseForwarder.envelope_to_row(envelope)
    assert row["reason"] == "secret output"
