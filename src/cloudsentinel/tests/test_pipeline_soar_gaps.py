"""Cover ClickHouse forwarder lifecycle and SOAR blocking/scheduler branches."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from datetime import UTC, datetime

import pytest

import cloudsentinel.pipeline as pipeline_module
import cloudsentinel.soar as soar_module
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import ClickHouseForwarder, EventEnvelope
from cloudsentinel.soar import SOAREngine, SOARScheduler


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self.closed = False

    async def ping(self) -> bool:
        return True

    async def xread(self, *_args: object, **_kwargs: object) -> list:
        return []

    async def aclose(self) -> None:
        self.closed = True

    async def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))

    async def exists(self, _key: str) -> int:
        return 0


class FakeCHClient:
    def __init__(self) -> None:
        self.rows: list = []
        self.closed = False

    def insert(self, _table: str, rows: list, **_kwargs: object) -> None:
        self.rows.extend(rows)

    def close(self) -> None:
        self.closed = True


def _forwarder(monkeypatch) -> tuple[ClickHouseForwarder, FakeRedis]:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    fake_redis = FakeRedis()
    monkeypatch.setattr(pipeline_module.redis, "from_url", lambda *_a, **_k: fake_redis)
    forwarder = ClickHouseForwarder(settings.redis, settings.clickhouse)
    forwarder._client = FakeCHClient()
    monkeypatch.setattr(forwarder, "_connect_clickhouse", lambda: None)
    return forwarder, fake_redis


@pytest.mark.asyncio
async def test_forwarder_start_stop(monkeypatch) -> None:
    forwarder, fake_redis = _forwarder(monkeypatch)
    await forwarder.start()
    await asyncio.sleep(0.01)
    await forwarder.stop()
    assert fake_redis.closed
    assert forwarder._client.closed


@pytest.mark.asyncio
async def test_forwarder_spill_and_checkpoint(monkeypatch, tmp_path) -> None:
    forwarder, _ = _forwarder(monkeypatch)
    forwarder._spill_path = tmp_path / "spill.jsonl"
    envelope = EventEnvelope(
        event_type="cloudsentinel.command.input",
        session_id="spill-1",
        src_ip="8.8.8.8",
        src_port=22,
        timestamp=1.0,
        payload={"eventid": "cloudsentinel.command.input"},
    )
    forwarder._spill_append([envelope.to_redis_fields()])
    forwarder._spill_append([])
    assert forwarder._spill_read()
    with open(forwarder._spill_path, "a", encoding="utf-8") as handle:
        handle.write("not-json\n")
    await forwarder._flush_spill()
    assert not forwarder._spill_path.exists()

    forwarder._checkpoint_path = tmp_path / "lastid"
    forwarder._save_checkpoint("9-0")
    assert forwarder._load_checkpoint() == "9-0"
    forwarder._checkpoint_path = tmp_path / "missing" / "lastid"
    assert forwarder._load_checkpoint() == "0-0"


def test_forwarder_connect_clickhouse(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    forwarder = ClickHouseForwarder(settings.redis, settings.clickhouse)
    fake_module = types.ModuleType("clickhouse_connect")
    fake_module.get_client = lambda **_kwargs: "client"
    monkeypatch.setitem(sys.modules, "clickhouse_connect", fake_module)
    forwarder._connect_clickhouse()
    assert forwarder._client == "client"


@pytest.mark.asyncio
async def test_soar_block_branches(monkeypatch) -> None:
    engine = SOAREngine(firewall_enabled=False, firewall_dry_run=False)
    assert await engine._block_ip({}) == "skip_no_ip"
    assert await engine._block_ip({"src_ip": "10.1.1.1"}) == "skip_allowlisted_ip"
    assert await engine._block_ip({"src_ip": "224.0.0.1"}) == "skip_private_ip"

    async def blocked(_ip: str) -> bool:
        return True

    monkeypatch.setattr(engine, "_is_blocked", blocked)
    assert await engine._block_ip({"src_ip": "8.8.8.8"}) == "already_blocked"

    detect = SOAREngine(firewall_enabled=False, firewall_dry_run=False)
    assert await detect._block_ip({"src_ip": "8.8.4.4"}) == "detect_only"

    dry = SOAREngine(firewall_enabled=True, firewall_dry_run=True)
    assert await dry._block_ip({"src_ip": "8.8.4.4"}) == "dry_run_block"

    published = SOAREngine(firewall_enabled=True, firewall_dry_run=False)
    fake_redis = FakeRedis()
    published._redis = fake_redis

    async def mark(_ip: str) -> None:
        return None

    monkeypatch.setattr(published, "_mark_blocked", mark)
    result = await published._block_ip(
        {"src_ip": "8.8.4.4", "session": "s", "cloudsentinel_risk_score": 90}
    )
    assert result == "event_published"
    assert fake_redis.published

    local = SOAREngine(firewall_enabled=True, firewall_dry_run=False)
    monkeypatch.setattr(local, "_mark_blocked", mark)

    async def already_present(_args: list[str], _event: dict) -> tuple[int, str, str]:
        return 0, "", ""

    monkeypatch.setattr(local, "_run_firewall", already_present)
    assert await local._block_ip({"src_ip": "8.8.4.4"}) == "already_blocked"

    applied = SOAREngine(firewall_enabled=True, firewall_dry_run=False)
    monkeypatch.setattr(applied, "_mark_blocked", mark)

    async def apply_rule(args: list[str], _event: dict) -> tuple[int, str, str]:
        return (1, "", "") if "-C" in args else (0, "", "")

    monkeypatch.setattr(applied, "_run_firewall", apply_rule)
    assert await applied._block_ip({"src_ip": "8.8.4.4"}) == "iptables_block"

    timed_out = SOAREngine(firewall_enabled=True, firewall_dry_run=False)

    async def timeout_rule(_args: list[str], _event: dict) -> tuple[int, str, str]:
        raise TimeoutError

    monkeypatch.setattr(timed_out, "_run_firewall", timeout_rule)
    assert await timed_out._block_ip({"src_ip": "8.8.4.4"}) == "block_timeout"

    errored = SOAREngine(firewall_enabled=True, firewall_dry_run=False)

    async def error_rule(_args: list[str], _event: dict) -> tuple[int, str, str]:
        raise RuntimeError("boom")

    monkeypatch.setattr(errored, "_run_firewall", error_rule)
    assert await errored._block_ip({"src_ip": "8.8.4.4"}) == "block_error"


@pytest.mark.asyncio
async def test_soar_run_firewall(monkeypatch) -> None:
    class FakeProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"out", b"err"

    async def fake_exec(*_args: object, **_kwargs: object) -> FakeProcess:
        return FakeProcess()

    monkeypatch.setattr(soar_module.asyncio, "create_subprocess_exec", fake_exec)
    engine = SOAREngine()
    event: dict = {}
    code, out, err = await engine._run_firewall(["-C", "INPUT"], event)
    assert code == 0
    assert out == "out"
    assert err == "err"
    assert event["block_stdout"] == "out"


@pytest.mark.asyncio
async def test_soar_scheduler(monkeypatch) -> None:
    cron_module = types.ModuleType("croniter")

    class FakeCron:
        def __init__(self, expr: str, _base: object) -> None:
            if expr == "bad":
                raise ValueError("bad cron")
            self.expr = expr

        def get_next(self, _type: object) -> datetime:
            return datetime.now(UTC)

    cron_module.croniter = FakeCron
    monkeypatch.setitem(sys.modules, "croniter", cron_module)

    scheduler = SOARScheduler()
    called: list[str] = []

    async def unblock(ip: str) -> None:
        called.append(f"unblock:{ip}")

    async def cron_job() -> None:
        called.append("cron")
        scheduler.stop()

    scheduler.add_ttl_unblock("8.8.8.8", 0, unblock)
    assert scheduler.add_cron_task("*/5 * * * *", "unit", cron_job) is True
    assert scheduler.add_cron_task("bad", "bad", cron_job) is False
    for task in scheduler._tasks:
        if task["type"] == "cron":
            task["next_run"] = 0
    await scheduler.start(check_interval=0)
    assert "unblock:8.8.8.8" in called
    assert "cron" in called

    monkeypatch.setitem(sys.modules, "croniter", None)
    assert scheduler.add_cron_task("* * * * *", "missing", cron_job) is False
