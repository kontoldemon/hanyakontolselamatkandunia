"""Cover config validation/getters and secret provider fallbacks."""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

import cloudsentinel.config as config
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




def test_config_secret_and_yaml_helpers() -> None:
    assert config.secret_to_str(None) == ""
    assert config._read_yaml(Path("does-not-exist.yaml")) == {}
