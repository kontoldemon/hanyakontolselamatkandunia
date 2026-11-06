"""Cover admin exposure provider and truth-summary success branches."""

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
    return TestClient(create_admin_app(settings, EventPipeline(settings.redis)))


def test_exposure_digitalocean_and_no_ports(monkeypatch) -> None:
    client = _client()
    headers = {"Authorization": "Bearer test-token"}
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_PROVIDER", "digitalocean")

    async def fake_toggle(_enabled: bool, _settings: object) -> dict:
        return {"ok": True, "effective_enabled": True}

    monkeypatch.setattr(admin_module, "_toggle_exposure_digitalocean", fake_toggle)
    response = client.post("/admin/exposure", headers=headers, json={"enabled": True})
    assert response.status_code == 200
    assert response.json()["ok"] is True

    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_PROVIDER", "iptables")
    monkeypatch.setattr(admin_module, "_exposure_target_ports", lambda _settings: [])
    no_ports = client.post("/admin/exposure", headers=headers, json={"enabled": False})
    assert no_ports.status_code == 200
    assert no_ports.json()["ok"] is False


def test_private_block_and_truth_summary(monkeypatch) -> None:
    client = _client()
    headers = {"Authorization": "Bearer test-token"}
    private = client.post(
        "/admin/block-ip",
        headers=headers,
        json={"ip": "0.0.0.0", "reason": "unit", "ttl": 60},
    )
    assert private.status_code == 400

    monkeypatch.setattr(
        admin_module,
        "_load_truth_summary_from_clickhouse",
        lambda _settings: {
            "total_events": 1,
            "unique_ips": 1,
            "unique_countries": 1,
            "active_sessions": 1,
            "total_connections": 1,
            "total_auth_failures": 0,
            "total_commands": 0,
            "unique_commands": 0,
            "total_blocks": 0,
            "blocked_ips_current": 0,
            "mttb_ms": 0.0,
            "avg_risk": 0.0,
            "block_rate": 0.0,
        },
    )
    truth = client.get("/truth-summary", headers=headers)
    assert truth.status_code == 200
    assert truth.json()["ok"] is True
