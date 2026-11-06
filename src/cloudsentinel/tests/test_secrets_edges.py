"""Cover secret provider failure branches and webhook platform errors."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

import cloudsentinel._secrets as secrets
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


def test_infisical_failure_branches(monkeypatch) -> None:
    monkeypatch.setenv("INFISICAL_CLIENT_ID", "id")
    monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "secret")
    monkeypatch.setenv("INFISICAL_PROJECT_ID", "project")
    monkeypatch.setenv("UNIT_SECRET_KEY", "env-value")

    class AuthFailure:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            raise RuntimeError("auth down")

    _install_httpx(monkeypatch, AuthFailure)
    provider = secrets.InfisicalProvider()
    assert asyncio.run(provider.get("UNIT_SECRET_KEY")) == "env-value"

    class BadStatus:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            return FakeResponse(200, {"accessToken": "token"})

        async def get(self, *_args, **_kwargs):
            return FakeResponse(500, {})

    _install_httpx(monkeypatch, BadStatus)
    assert asyncio.run(secrets.InfisicalProvider().get("UNIT_SECRET_KEY")) == "env-value"

    class GetFailure(BadStatus):
        async def get(self, *_args, **_kwargs):
            raise RuntimeError("get down")

    _install_httpx(monkeypatch, GetFailure)
    assert asyncio.run(secrets.InfisicalProvider().get("UNIT_SECRET_KEY")) == "env-value"
    assert asyncio.run(secrets.InfisicalProvider().get_all("UNIT_")) == {}


def test_vault_failure_branches(monkeypatch) -> None:
    monkeypatch.setenv("VAULT_ADDR", "http://vault")
    monkeypatch.setenv("VAULT_TOKEN", "token")
    monkeypatch.setenv("UNIT_SECRET_KEY", "env-value")
    fake_hvac = types.ModuleType("hvac")

    class AuthFailure:
        def __init__(self, **_kwargs):
            pass

        async def is_authenticated(self):
            return False

    fake_hvac.AsyncClient = AuthFailure
    monkeypatch.setitem(sys.modules, "hvac", fake_hvac)
    assert asyncio.run(secrets.VaultProvider().get("UNIT_SECRET_KEY")) == "env-value"

    class InitFailure:
        def __init__(self, **_kwargs):
            raise RuntimeError("vault down")

    fake_hvac.AsyncClient = InitFailure
    assert asyncio.run(secrets.VaultProvider().get("UNIT_SECRET_KEY")) == "env-value"

    class ReadFailure:
        def __init__(self, **_kwargs):
            self.secrets = types.SimpleNamespace(kv=types.SimpleNamespace(v2=self))

        async def is_authenticated(self):
            return True

        async def read_secret_version(self, **_kwargs):
            raise RuntimeError("read down")

        async def list_secrets(self, **_kwargs):
            raise RuntimeError("list down")

        async def close(self):
            return None

    fake_hvac.AsyncClient = ReadFailure
    provider = secrets.VaultProvider()
    assert asyncio.run(provider.get("UNIT_SECRET_KEY")) == "env-value"
    assert asyncio.run(provider.get_all("UNIT_")) == {}

    monkeypatch.setattr(secrets, "_provider", None)
    assert asyncio.run(secrets.get_secrets_provider()) is not None


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
