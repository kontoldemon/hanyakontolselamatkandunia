"""Final admin branches: replay trim, auth failure, exposure firewall, synthetic sessions."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.admin_api as admin_module
import cloudsentinel.auth as auth_module
from cloudsentinel.admin_api import (
    _load_recent_events_from_clickhouse,
    _toggle_exposure_digitalocean,
    _trim_replay_entries,
    create_admin_app,
)
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


class FakeRedis:
    async def hset(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("redis write failed")

    async def hgetall(self, _key: str) -> dict:
        return {}

    async def get(self, _key: str) -> None:
        return None

    async def set(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("redis set failed")

    async def expire(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def aclose(self) -> None:
        return None


def test_replay_trim_duplicates() -> None:
    entries = [
        {"role": "honeypot", "text": "info", "timestamp": "1"},
        {"role": "honeypot", "text": "info", "timestamp": "1"},
        {"role": "attacker", "text": "cmd", "timestamp": "2"},
        {"role": "attacker", "text": "cmd", "timestamp": "2"},
    ]
    trimmed = _trim_replay_entries(entries, limit=1)
    assert len(trimmed) == 1


def test_event_output_echo_and_empty(monkeypatch) -> None:
    class Result:
        result_rows = [
            (
                "cloudsentinel.command.output",
                "8.8.8.8",
                "XX",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                [],
                "none",
                0,
                0.0,
                "bad-ts",
            ),
            (
                "cloudsentinel.command.input",
                "8.8.8.8",
                "XX",
                "",
                "",
                "",
                "",
                "",
                "id",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                [],
                "none",
                0,
                0.0,
                None,
            ),
            (
                "cloudsentinel.command.output",
                "8.8.8.8",
                "XX",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "id",
                "",
                "",
                [],
                "none",
                0,
                0.0,
                None,
            ),
        ]

    class Client:
        def query(self, _query: str) -> Result:
            return Result()

    import types

    fake = types.ModuleType("clickhouse_connect")
    fake.get_client = lambda **_kwargs: Client()
    monkeypatch.setitem(sys.modules, "clickhouse_connect", fake)
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    assert _load_recent_events_from_clickhouse(settings)


def test_auth_failure(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("")
    settings.clickhouse.enabled = False
    client = TestClient(create_admin_app(settings, EventPipeline(settings.redis)))

    def fail_auth() -> None:
        raise RuntimeError("auth down")

    monkeypatch.setattr(auth_module, "get_auth", fail_auth)
    assert client.get("/stats", headers={"Authorization": "Bearer x"}).status_code == 503


def test_exposure_firewall_failures(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    app = create_admin_app(settings, EventPipeline(settings.redis))
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}
    monkeypatch.setattr(admin_module, "_exposure_firewall_paths", lambda _settings: ["/bin/fw"])
    monkeypatch.setattr(admin_module, "_exposure_target_ports", lambda _settings: [22])
    responses = [(0, "", ""), (1, "", "delete failed")]

    async def fake_run(_args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        return responses.pop(0) if responses else (2, "", "check failed")

    monkeypatch.setattr(admin_module, "_run_command", fake_run)
    first = client.post("/admin/exposure", headers=headers, json={"enabled": True})
    assert first.status_code == 200
    assert first.json()["ok"] is False


def test_persist_exposure_failure(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    pipeline = EventPipeline(settings.redis)
    pipeline._redis = FakeRedis()  # type: ignore[assignment]
    client = TestClient(create_admin_app(settings, pipeline))
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_PROVIDER", "digitalocean")

    async def fake_toggle(_enabled: bool, _settings: object) -> dict:
        return {"ok": True, "effective_enabled": True}

    monkeypatch.setattr(admin_module, "_toggle_exposure_digitalocean", fake_toggle)
    response = client.post(
        "/admin/exposure",
        headers={"Authorization": "Bearer test-token"},
        json={"enabled": True},
    )
    assert response.status_code == 200
