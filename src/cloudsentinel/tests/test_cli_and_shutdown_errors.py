"""Cover CLI command error paths and admin shutdown exception."""

from __future__ import annotations

import sys
import types
import urllib.error

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from typer.testing import CliRunner

import cloudsentinel.admin_api as admin_module
import cloudsentinel.cli as cli
import cloudsentinel.validate_phase1 as validate_module
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


def test_cli_status_and_validate_errors(monkeypatch) -> None:
    runner = CliRunner()

    def fail_url(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", fail_url)
    result = runner.invoke(cli.app, ["status", "--url", "http://127.0.0.1:1"])
    assert result.exit_code == 0

    def fail_validate() -> None:
        raise RuntimeError("validation down")

    monkeypatch.setattr(validate_module, "main", fail_validate)
    result = runner.invoke(cli.app, ["validate"])
    assert result.exit_code == 0

    monkeypatch.setattr(sys, "argv", ["cloudsentinel"])
    try:
        cli.main()
    except SystemExit:
        pass


def test_shutdown_close_exception(monkeypatch) -> None:
    class DirectRedis:
        async def ping(self):
            return True

        async def hgetall(self, _key: str) -> dict:
            return {}

        async def hset(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def expire(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def get(self, _key: str) -> None:
            return None

        async def set(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def delete(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def aclose(self) -> None:
            raise RuntimeError("close failed")

    import redis.asyncio as aioredis

    monkeypatch.setattr(aioredis, "from_url", lambda *_a, **_k: DirectRedis())
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    pipeline = EventPipeline(settings.redis)
    pipeline._redis = None
    with TestClient(create_admin_app(settings, pipeline)) as client:
        assert client.get("/war-room-state", headers={"Authorization": "Bearer test-token"}).status_code == 200
