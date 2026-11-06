"""Cover admin endpoint degradation when optional modules fail."""

from __future__ import annotations

import sys

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


def test_endpoint_metrics_failures(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_STRICT_TRUTH", "0")
    client = _client()
    headers = {"Authorization": "Bearer test-token"}
    monkeypatch.setitem(sys.modules, "cloudsentinel.metrics", None)

    assert client.get("/metrics", headers=headers).status_code == 200
    assert client.get("/metrics/json", headers=headers).status_code == 200
    assert client.get("/stats", headers=headers).status_code == 200
    assert client.get("/attack-distribution", headers=headers).status_code == 200

    async def fake_run(_args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        return (1, "", "") if "-C" in _args else (0, "", "")

    monkeypatch.setattr(admin_module, "_run_command", fake_run)
    blocked = client.post(
        "/admin/block-ip",
        headers=headers,
        json={"ip": "8.8.8.8", "reason": "unit", "ttl": 60},
    )
    assert blocked.status_code == 200

    monkeypatch.setitem(sys.modules, "cloudsentinel.anomaly", None)
    assert client.get("/anomaly-stats", headers=headers).status_code == 200
