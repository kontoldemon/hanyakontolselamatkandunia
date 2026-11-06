"""Cover synthetic sessions and manual-block error branches."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.admin_api as admin_module
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


class FakeSoar:
    _mem_ip_sessions = {"8.8.8.8": {"s1", "s2"}}

    async def _mark_blocked(self, _ip: str) -> None:
        raise RuntimeError("mark failed")

    async def process_event(self, _session: str, event: dict) -> dict:
        return event

    def get_ip_profile(self, ip: str) -> dict:
        return {
            "ip": ip,
            "last_seen": time.time(),
            "first_seen": time.time() - 60,
            "cumulative_risk": 70,
            "techniques": ["T1110"],
        }


def _client(soar=None) -> TestClient:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    return TestClient(create_admin_app(settings, EventPipeline(settings.redis), soar))


def test_synthetic_sessions(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_STRICT_TRUTH", "0")
    client = _client(FakeSoar())
    response = client.get("/sessions", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert any(item["source"] == "memory" for item in response.json()["sessions"])


def test_manual_block_with_soar_and_metrics_failures(monkeypatch) -> None:
    client = _client(FakeSoar())
    headers = {"Authorization": "Bearer test-token"}

    async def fake_run(args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        return (1, "", "") if "-C" in args else (0, "", "")

    monkeypatch.setattr(admin_module, "_run_command", fake_run)
    response = client.post(
        "/admin/block-ip",
        headers=headers,
        json={"ip": "8.8.8.8", "reason": "unit", "ttl": 60},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
