"""Cover admin exposure toggle outcomes without touching a real firewall."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.admin_api as admin_module
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


def _client() -> tuple[TestClient, dict[str, str]]:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    app = create_admin_app(settings, EventPipeline(settings.redis))
    return TestClient(app), {"Authorization": "Bearer test-token"}


def test_exposure_outcomes(monkeypatch) -> None:
    client, headers = _client()
    monkeypatch.setattr(admin_module, "_exposure_target_ports", lambda _settings: [22])
    monkeypatch.setattr(admin_module, "_exposure_admin_ports", lambda: {22})

    runs: list[tuple[int, str, str]] = [(0, "", ""), (0, "", "")]

    async def fake_run(_args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        return runs.pop(0) if runs else (0, "", "")

    monkeypatch.setattr(admin_module, "_run_command", fake_run)
    removed = client.post("/admin/exposure", headers=headers, json={"enabled": True})
    assert removed.status_code == 200
    assert removed.json()["actions"][0]["action"] == "removed"

    runs[:] = [(1, "", ""), (0, "", "")]
    paused = client.post("/admin/exposure", headers=headers, json={"enabled": False})
    assert paused.status_code == 200
    assert paused.json()["actions"][0]["action"] == "paused"

    runs[:] = [(0, "", "")]
    already_paused = client.post("/admin/exposure", headers=headers, json={"enabled": False})
    assert already_paused.status_code == 200
    assert already_paused.json()["actions"][0]["action"] == "already_paused"

    runs[:] = [(1, "", "")]
    already_open = client.post("/admin/exposure", headers=headers, json={"enabled": True})
    assert already_open.status_code == 200
    assert already_open.json()["actions"][0]["action"] == "already_open"

