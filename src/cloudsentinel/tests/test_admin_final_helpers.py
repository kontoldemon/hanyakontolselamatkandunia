"""Final admin helper branches: numeric parsing, replay trimming, and auth."""

from __future__ import annotations

import types

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.admin_api as admin_module
import cloudsentinel.auth as auth_module
from cloudsentinel.admin_api import _as_int, _trim_replay_entries, create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


def test_as_int_and_replay_trim() -> None:
    assert _as_int("bad") == 0
    assert _as_int("7") == 7
    entries = [
        {"role": "honeypot", "text": "info", "timestamp": "1"},
        {"role": "honeypot", "text": "info", "timestamp": "1"},
        {"role": "attacker", "text": "cmd", "timestamp": "2"},
    ]
    trimmed = _trim_replay_entries(entries, limit=2)
    assert trimmed


def test_require_auth_jwt_branches(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("")
    settings.admin.enabled = True
    settings.clickhouse.enabled = False
    app = create_admin_app(settings, EventPipeline(settings.redis))
    client = TestClient(app)

    fake_auth = types.SimpleNamespace(
        config=types.SimpleNamespace(enabled=True),
        validate_token=lambda token: {"sub": "admin"} if token == "good" else None,
    )
    monkeypatch.setattr(auth_module, "get_auth", lambda: fake_auth)

    assert client.get("/stats").status_code == 401
    assert client.get("/stats", headers={"Authorization": "Bearer bad"}).status_code == 401
    assert client.get("/stats", headers={"Authorization": "Bearer good"}).status_code == 200

    fake_auth.config.enabled = False
    assert client.get("/stats").status_code == 200
