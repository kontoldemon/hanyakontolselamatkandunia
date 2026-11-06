"""Cover admin manual block success/failure and login branches."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.admin_api as admin_module
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


def _client() -> TestClient:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    return TestClient(create_admin_app(settings, EventPipeline(settings.redis)))


def test_manual_block_success_and_failure(monkeypatch) -> None:
    client = _client()
    headers = {"Authorization": "Bearer test-token"}
    responses: list[tuple[int, str, str]] = [(1, "", ""), (0, "", "")]

    async def fake_run(_args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        return responses.pop(0) if responses else (0, "", "")

    monkeypatch.setattr(admin_module, "_run_command", fake_run)
    blocked = client.post(
        "/admin/block-ip",
        headers=headers,
        json={"ip": "8.8.8.8", "reason": "unit", "ttl": 60},
    )
    assert blocked.status_code == 200
    assert blocked.json()["action"] == "blocked"

    responses[:] = [(0, "", "")]
    already = client.post(
        "/admin/block-ip",
        headers=headers,
        json={"ip": "8.8.4.4", "reason": "unit", "ttl": 60},
    )
    assert already.status_code == 200
    assert already.json()["action"] == "already_blocked"

    responses[:] = [(1, "", ""), (1, "", "denied")]
    failed = client.post(
        "/admin/block-ip",
        headers=headers,
        json={"ip": "1.1.1.1", "reason": "unit", "ttl": 60},
    )
    assert failed.status_code == 500


def test_login_branches(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_AUTH_ENABLED", "true")
    monkeypatch.setenv("CLOUDSENTINEL_AUTH_SECRET", "unit-secret")
    monkeypatch.setenv("CLOUDSENTINEL_ADMIN_USER", "admin")
    monkeypatch.setenv("CLOUDSENTINEL_ADMIN_PASS", "pass")
    client = _client()

    valid = client.post("/auth/login", json={"username": "admin", "password": "pass"})
    assert valid.status_code == 200
    assert valid.json()["access_token"]

    invalid = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert invalid.status_code == 401
