"""Cover login when auth is disabled."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


def test_login_auth_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_AUTH_ENABLED", "false")
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    client = TestClient(create_admin_app(settings, EventPipeline(settings.redis)))
    response = client.post("/auth/login", json={})
    assert response.status_code == 200
    assert response.json()["token"] == "dev-mode"
