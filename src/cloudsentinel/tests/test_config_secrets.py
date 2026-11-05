"""Cover config validation/getters and secret provider fallbacks."""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

import cloudsentinel.config as config
import cloudsentinel._secrets as secrets
from cloudsentinel.config import SandboxSettings, load_settings


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self) -> dict:
        return self.payload


class FakeHTTPClient:
    def __init__(self, **_kwargs: object) -> None:
        self.posts: list = []
        self.gets: list = []

    async def __aenter__(self) -> FakeHTTPClient:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def post(self, url: str, **_kwargs: object) -> FakeResponse:
        self.posts.append(url)
        return FakeResponse(200, {"accessToken": "token"})

    async def get(self, url: str, **_kwargs: object) -> FakeResponse:
        self.gets.append(url)
        if url.endswith("/secrets"):
            return FakeResponse(200, {"secrets": [{"secretKey": "PREFIX_ONE", "secretValue": "1"}]})
        return FakeResponse(200, {"secret": {"secretValue": "value"}})


def test_env_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNIT_SECRET", "value")
    provider = secrets.EnvProvider()
    assert asyncio.run(provider.get("UNIT_SECRET")) == "value"
    assert asyncio.run(provider.get("MISSING", "default")) == "default"
    assert asyncio.run(provider.get_all("UNIT_"))["UNIT_SECRET"] == "value"
    asyncio.run(provider.close())


def test_infisical_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFISICAL_CLIENT_ID", "id")
    monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "secret")
    monkeypatch.setenv("INFISICAL_PROJECT_ID", "project")
    fake_httpx = types.ModuleType("httpx")
    fake_httpx.AsyncClient = FakeHTTPClient
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    provider = secrets.InfisicalProvider()
    assert asyncio.run(provider.get("UNIT_KEY", "fallback")) == "value"
    assert asyncio.run(provider.get_all("PREFIX_")) == {"PREFIX_ONE": "1"}
    asyncio.run(provider.close())

    unavailable = secrets.InfisicalProvider()
    unavailable._available = False
    monkeypatch.setenv("UNIT_KEY", "env-value")
    assert asyncio.run(unavailable.get("UNIT_KEY")) == "env-value"


def test_vault_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_ADDR", "http://vault")
    monkeypatch.setenv("VAULT_TOKEN", "token")
    fake_hvac = types.ModuleType("hvac")

    class FakeKV:
        async def read_secret_version(self, **_kwargs: object) -> dict:
            return {"data": {"data": {"value": "vault-value"}}}

        async def list_secrets(self, **_kwargs: object) -> dict:
            return {"data": {"keys": ["UNIT_KEY"]}}

    class FakeVaultClient:
        def __init__(self, **_kwargs: object) -> None:
            self.secrets = types.SimpleNamespace(kv=types.SimpleNamespace(v2=FakeKV()))
            self.closed = False

        async def is_authenticated(self) -> bool:
            return True

        async def close(self) -> None:
            self.closed = True

    fake_hvac.AsyncClient = FakeVaultClient
    monkeypatch.setitem(sys.modules, "hvac", fake_hvac)
    provider = secrets.VaultProvider()
    assert asyncio.run(provider.get("UNIT_KEY", "fallback")) == "vault-value"
    assert asyncio.run(provider.get_all("UNIT_")) == {"UNIT_KEY": "vault-value"}
    asyncio.run(provider.close())

    monkeypatch.setitem(sys.modules, "hvac", None)
    missing = secrets.VaultProvider()
    missing._available = True
    assert asyncio.run(missing.get("UNIT_KEY", "fallback")) == "fallback"


def test_provider_factory_and_get_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(secrets.SecretsProvider.create("env"), secrets.EnvProvider)
    assert isinstance(secrets.SecretsProvider.create("infisical"), secrets.InfisicalProvider)
    assert isinstance(secrets.SecretsProvider.create("vault"), secrets.VaultProvider)
    assert isinstance(secrets.SecretsProvider.create("unknown"), secrets.EnvProvider)

    provider = secrets.EnvProvider()
    monkeypatch.setattr(secrets, "_provider", provider)
    monkeypatch.setenv("UNIT_GET_SECRET", "x")
    assert asyncio.run(secrets.get_secret("UNIT_GET_SECRET")) == "x"


def test_config_validation_errors() -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.soar.active_profile = "production"
    settings.soar.firewall_dry_run = True
    settings.clickhouse.enabled = False
    with pytest.raises(ValueError, match="Production profile"):
        config.validate_settings(settings)

    settings.soar.firewall_dry_run = False
    settings.clickhouse.enabled = True
    settings.redis.url = ""
    with pytest.raises(ValueError, match="ClickHouse requires Redis"):
        config.validate_settings(settings)

    settings.redis.url = "redis://localhost:6379/0"
    settings.stream.enabled = True
    settings.admin.enabled = True
    settings.stream.port = settings.admin.port
    with pytest.raises(ValueError, match="Stream port"):
        config.validate_settings(settings)

    settings.stream.enabled = False
    settings.admin.enabled = False
    settings.soar.mttb_target_ms = 0
    with pytest.raises(ValueError, match="MTTB target"):
        config.validate_settings(settings)


def test_config_getters_and_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    monkeypatch.setattr(config, "_SETTINGS_CACHE", settings)
    assert config.get("honeypot", "listen_host")
    assert isinstance(config.getint("honeypot", "ssh_port"), int)
    assert isinstance(config.getfloat("sandbox", "timeout_seconds"), float)
    assert isinstance(config.getboolean("admin", "enabled"), bool)
    assert config.has_section("honeypot") is True
    assert config.has_option("honeypot", "ssh_port") is True
    assert config.has_option("honeypot", "missing") is False
    with pytest.raises(KeyError):
        config.get("missing", "key")
    with pytest.raises(KeyError):
        config.getint("honeypot", "missing")
    with pytest.raises(KeyError):
        config.getfloat("honeypot", "missing")
    with pytest.raises(KeyError):
        config.getboolean("honeypot", "missing")

    assert config.secret_to_str(None) == ""
    assert config.secret_to_str("plain") == "plain"
    assert config._split_csv(None) is None
    assert config._split_csv("a, b") == ["a", "b"]
    assert config._read_yaml(Path("does-not-exist.yaml")) == {}
    assert SandboxSettings(cpus=0.5).cpus == "0.5"
