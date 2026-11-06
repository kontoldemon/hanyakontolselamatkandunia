"""Cover attack-graph SOAR branch and admin AI/login error responses."""

from __future__ import annotations

import types

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.auth as auth_module
import cloudsentinel.threat_reporter as reporter
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


class FakeSoar:
    def get_attack_chains(self) -> list[dict]:
        return [
            {
                "ip": "8.8.8.8",
                "sessions": 2,
                "risk": 80,
                "techniques": ["T1110", "T1059"],
            }
        ]


def _client(soar=None) -> TestClient:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    return TestClient(create_admin_app(settings, EventPipeline(settings.redis), soar))


def test_attack_graph_soar_branch(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_STRICT_TRUTH", "0")
    client = _client(FakeSoar())
    response = client.get("/attack-graph", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    payload = response.json()
    assert any(node["id"].startswith("ip-") for node in payload["nodes"])
    assert any(node["id"].startswith("tech-") for node in payload["nodes"])


def test_admin_ai_error_branches(monkeypatch) -> None:
    client = _client()
    headers = {"Authorization": "Bearer test-token"}

    async def fail_report(**_kwargs: object) -> object:
        raise RuntimeError("report failed")

    async def fail_chat(_prompt: str, _context: str) -> str:
        raise RuntimeError("chat failed")

    monkeypatch.setattr(reporter, "generate_report", fail_report)
    monkeypatch.setattr(reporter, "chat_with_agent", fail_chat)
    summary = client.post("/threat-summary", headers=headers, json={})
    assert summary.status_code == 200
    assert summary.json()["ok"] is False
    chat = client.post("/llm/chat", headers=headers, json={"prompt": "hi"})
    assert chat.status_code == 200
    assert chat.json()["ok"] is False

    def fail_auth() -> None:
        raise RuntimeError("auth down")

    monkeypatch.setattr(auth_module, "get_auth", fail_auth)
    login = client.post("/auth/login", json={"username": "x", "password": "y"})
    assert login.status_code == 200
    assert login.json()["token"] == "dev-mode"
