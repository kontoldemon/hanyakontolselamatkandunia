"""Exercise read-only admin endpoints not covered by the smaller tests."""

from __future__ import annotations

import types

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.threat_reporter as reporter
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


def test_admin_read_endpoints(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    pipeline = EventPipeline(settings.redis)
    app = create_admin_app(settings, pipeline)
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}

    for path in (
        "/metrics/json",
        "/sessions",
        "/events",
        "/truth-summary",
        "/attack-distribution",
        "/attack-graph",
        "/llm/status",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)

    fake_report = types.SimpleNamespace(to_dict=lambda: {"summary": "unit"})

    async def fake_generate_report(**_kwargs: object) -> object:
        return fake_report

    async def fake_chat(_prompt: str, _context: str) -> str:
        return "unit response"

    monkeypatch.setattr(reporter, "generate_report", fake_generate_report)
    monkeypatch.setattr(reporter, "chat_with_agent", fake_chat)
    assert client.post("/threat-summary", headers=headers, json={}).status_code == 200
    chat = client.post("/llm/chat", headers=headers, json={"prompt": "hi"})
    assert chat.status_code == 200
    assert chat.json()["response"] == "unit response"
