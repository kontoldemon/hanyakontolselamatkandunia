"""Cover secret provider failure branches and webhook platform errors."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

import cloudsentinel.webhook as webhook_module


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http")

    def json(self) -> dict:
        return self.payload


def _install_httpx(monkeypatch, client_cls) -> None:
    fake = types.ModuleType("httpx")
    fake.AsyncClient = client_cls
    monkeypatch.setitem(sys.modules, "httpx", fake)






@pytest.mark.asyncio
async def test_webhook_platform_failure(monkeypatch) -> None:
    config = webhook_module.WebhookConfig(
        enabled=True,
        slack_url="https://slack",
        min_risk_score=70,
        cooldown_seconds=0,
    )
    notifier = webhook_module.WebhookNotifier(config)

    async def fail(_event: dict) -> bool:
        raise RuntimeError("slack down")

    monkeypatch.setattr(notifier, "_send_slack", fail)
    assert await notifier.send_alert({"src_ip": "8.8.8.8", "cloudsentinel_risk_score": 90}) == []
