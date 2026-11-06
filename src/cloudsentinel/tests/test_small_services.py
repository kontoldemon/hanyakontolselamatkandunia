"""Cover small service modules: AbuseIPDB, TLS, validation, webhooks, stress, auth."""

from __future__ import annotations

import asyncio
import sys
import time
import types

import pytest

try:
    import hishel  # noqa: F401
except ModuleNotFoundError:
    _fake_hishel = types.ModuleType("hishel")
    _fake_hishel.AsyncCacheClient = type("AsyncCacheClient", (), {})
    sys.modules["hishel"] = _fake_hishel

try:
    import tenacity  # noqa: F401
except ModuleNotFoundError:
    _fake_tenacity = types.ModuleType("tenacity")
    _fake_tenacity.retry = lambda *_args, **_kwargs: (lambda func: func)
    _fake_tenacity.retry_if_exception_type = lambda *_args, **_kwargs: None
    _fake_tenacity.stop_after_attempt = lambda *_args, **_kwargs: None
    _fake_tenacity.wait_exponential = lambda *_args, **_kwargs: None
    sys.modules["tenacity"] = _fake_tenacity

import cloudsentinel.abuseipdb as abuseipdb
import cloudsentinel.auth as auth_module
import cloudsentinel.stress_test as stress_module
import cloudsentinel.tls as tls_module
import cloudsentinel.validate_phase1 as validate_module
import cloudsentinel.webhook as webhook_module


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self) -> dict:
        return self.payload


def test_abuseipdb(monkeypatch) -> None:
    client = abuseipdb.AbuseIPDBClient(api_key="")
    asyncio.run(client.start())
    assert asyncio.run(client.check("8.8.8.8"))["abuse_confidence_score"] == 0

    class FakeHTTP:
        def __init__(self, response: FakeResponse) -> None:
            self.response = response
            self.closed = False

        async def get(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return self.response

        async def aclose(self) -> None:
            self.closed = True

    enabled = abuseipdb.AbuseIPDBClient(api_key="key")
    http = FakeHTTP(
        FakeResponse(
            200,
            {
                "data": {
                    "abuseConfidenceScore": 80,
                    "totalReports": 120,
                    "countryCode": "US",
                    "isp": "ISP",
                    "domain": "example.test",
                    "usageType": "hosting",
                    "lastReportedAt": "now",
                }
            },
        )
    )
    monkeypatch.setattr(abuseipdb.hishel, "AsyncCacheClient", lambda **_kwargs: http)
    asyncio.run(enabled.start())
    assert asyncio.run(enabled.check("8.8.8.8"))["abuse_confidence_score"] == 80
    assert enabled.stats["cache_size"] == 1
    assert asyncio.run(enabled.check("8.8.8.8"))["abuse_confidence_score"] == 80
    asyncio.run(enabled.stop())
    assert http.closed

    limited = abuseipdb.AbuseIPDBClient(api_key="key")
    limited._client = FakeHTTP(FakeResponse(429))
    assert asyncio.run(limited._fetch_report("8.8.8.8", 90))["abuse_confidence_score"] == 0

    invalid = abuseipdb.AbuseIPDBClient(api_key="key")
    invalid._client = FakeHTTP(FakeResponse(200, {"data": {}}))
    assert asyncio.run(invalid.check("8.8.8.8"))["abuse_confidence_score"] == 0

    failing = abuseipdb.AbuseIPDBClient(api_key="key")

    class Broken(FakeHTTP):
        async def get(self, *_args: object, **_kwargs: object) -> FakeResponse:
            raise RuntimeError("api down")

    failing._client = Broken(FakeResponse())
    assert asyncio.run(failing.check("8.8.8.8"))["abuse_confidence_score"] == 0
    assert abuseipdb.AbuseIPDBClient().soar_bonus({"abuse_confidence_score": 80, "total_reports": 200}) == 30
    assert abuseipdb.AbuseIPDBClient().soar_bonus({"abuse_confidence_score": 50, "total_reports": 20}) == 20
    assert abuseipdb.AbuseIPDBClient().soar_bonus({"abuse_confidence_score": 10, "total_reports": 1}) == 3
    monkeypatch.setattr(abuseipdb, "_abuseipdb", None)
    assert abuseipdb.get_abuseipdb() is not None


def test_tls(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(sys.modules, "cryptography", None)
    assert tls_module.generate_self_signed_cert(output_dir=str(tmp_path / "none")) == ("", "")
    monkeypatch.undo()
    pytest.importorskip("cryptography")
    cert, key = tls_module.generate_self_signed_cert(output_dir=str(tmp_path / "tls"))
    assert cert and key
    assert tls_module.generate_self_signed_cert(output_dir=str(tmp_path / "tls")) == (cert, key)


def test_validate_phase1(monkeypatch, tmp_path) -> None:
    class FakeHTTPResponse:
        def __enter__(self) -> FakeHTTPResponse:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b'{"ok": true}'

    monkeypatch.setattr(validate_module, "urlopen", lambda *_args, **_kwargs: FakeHTTPResponse())
    assert validate_module.http_json("https://example.test", "token", allow_self_signed=True) == {"ok": True}

    class FakeWriter:
        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    async def open_ok(*_args: object, **_kwargs: object) -> tuple[object, FakeWriter]:
        return object(), FakeWriter()

    async def open_fail(*_args: object, **_kwargs: object) -> tuple[object, FakeWriter]:
        raise OSError("down")

    monkeypatch.setattr(validate_module.asyncio, "open_connection", open_ok)
    assert asyncio.run(validate_module.tcp_check("127.0.0.1", 22))["ok"] is True
    monkeypatch.setattr(validate_module.asyncio, "open_connection", open_fail)
    assert asyncio.run(validate_module.tcp_check("127.0.0.1", 22))["ok"] is False

    report = {
        "generated_at": "now",
        "target": "host",
        "overall_pass": True,
        "checks": {
            "ssh_honeypot": {"ok": True},
            "management_ssh": {"ok": True},
            "socketio": {"ok": True},
            "mitre_coverage": {"ok": True, "count": 15},
            "admin_readiness": {"ok": True, "redis_connected": True, "clickhouse_ok": True, "stream_enabled": True},
        },
    }
    validate_module.write_artifacts(report, tmp_path / "artifacts")
    assert (tmp_path / "artifacts" / "phase1-validation.md").exists()

    async def fake_tcp(*_args: object, **_kwargs: object) -> dict:
        return {"ok": True}

    monkeypatch.setattr(validate_module, "tcp_check", fake_tcp)
    monkeypatch.setattr(validate_module, "http_json", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(sys, "argv", ["validate_phase1", "--artifacts-dir", str(tmp_path / "out")])
    asyncio.run(validate_module.main())
    assert (tmp_path / "out" / "phase1-validation.json").exists()


@pytest.mark.asyncio
async def test_webhook(monkeypatch) -> None:
    config = webhook_module.WebhookConfig(
        enabled=True,
        slack_url="https://slack",
        discord_url="https://discord",
        telegram_bot_token="token",
        telegram_chat_id="chat",
        min_risk_score=70,
        cooldown_seconds=300,
    )
    notifier = webhook_module.WebhookNotifier(config)

    class FakeClient:
        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse(200)

        async def aclose(self) -> None:
            return None

    notifier._client = FakeClient()
    event = {
        "src_ip": "8.8.8.8",
        "cloudsentinel_risk_score": 95,
        "cloudsentinel_soar_action": "iptables_block",
        "cloudsentinel_mitre_techniques": ["T1110"],
        "username": "root",
        "password": "toor",
        "hassh_md5": "a" * 32,
        "session": "session-123456",
        "eventid": "login.failed",
        "input": "echo `whoami`",
    }
    assert set(await notifier.send_alert(event)) == {"slack", "discord", "telegram"}
    assert "BLOCKED" in notifier._format_payload(event)["action"]
    assert await notifier.send_alert({**event, "cloudsentinel_risk_score": 10}) == []
    assert await notifier.send_alert(event) == []
    disabled = webhook_module.WebhookNotifier(webhook_module.WebhookConfig())
    assert await disabled.send_alert(event) == []
    await notifier.close()

    monkeypatch.setattr(webhook_module, "_notifier", None)
    assert webhook_module.get_notifier() is not None


def test_stress_report_and_main(monkeypatch, tmp_path) -> None:
    stress = stress_module.StressTest("127.0.0.1", 22, 0)
    empty = stress._report(0.0)
    assert empty["avg_connect_time_ms"] == 0.0
    stress.connected = 1
    stress.timings = [0.1, 0.2, 0.3]
    report = stress._report(1.0)
    assert report["p95_connect_ms"] >= 0
    assert stress._resource_snapshot()["pid"]

    async def fake_run(_self) -> dict:
        return report

    monkeypatch.setattr(stress_module.StressTest, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stress_test", "--host", "127.0.0.1", "--port", "22", "--connections", "0", "--output", str(tmp_path / "report.json")],
    )
    asyncio.run(stress_module.main())
    assert (tmp_path / "report.json").exists()


def test_pyjwt_error_paths(monkeypatch) -> None:
    auth = auth_module.PyJWTAuth(auth_module.AuthConfig(secret="secret", enabled=True))
    fake_jwt = types.ModuleType("jwt")

    class ExpiredSignatureError(Exception):
        pass

    class InvalidTokenError(Exception):
        pass

    def encode(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("encode failed")

    def decode(*_args: object, **_kwargs: object) -> dict:
        raise ExpiredSignatureError("expired")

    fake_jwt.encode = encode
    fake_jwt.decode = decode
    fake_jwt.ExpiredSignatureError = ExpiredSignatureError
    fake_jwt.InvalidTokenError = InvalidTokenError
    monkeypatch.setitem(sys.modules, "jwt", fake_jwt)
    assert auth.create_token("user") is None
    assert auth.validate_token("token") is None

    manual = auth_module.JWTAuth(auth_module.AuthConfig(secret="secret", enabled=True))
    expired = manual.create_token({"sub": "user"}, expiry=-1)
    assert manual.validate_token(expired) is None
    assert manual.validate_token("bad.token") is None
    monkeypatch.setenv("CLOUDSENTINEL_AUTH_SECRET", "secret")
    monkeypatch.setattr(auth_module, "_auth", None)
    assert auth_module.get_auth() is not None
