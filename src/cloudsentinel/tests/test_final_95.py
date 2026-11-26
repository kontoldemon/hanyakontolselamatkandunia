"""Final branches to clear 95%."""

from __future__ import annotations

import asyncio
import types

from fastapi.testclient import TestClient

import cloudsentinel.auth as auth_module
import cloudsentinel.config as config
from cloudsentinel.config import load_settings
from cloudsentinel.http_server import create_http_honeypot


class FakePipeline:
    async def emit(self, _envelope: object) -> None:
        return None




def test_http_body_exception(monkeypatch) -> None:
    from starlette.requests import Request

    async def broken_body(_self: object) -> bytes:
        raise RuntimeError("body failed")

    monkeypatch.setattr(Request, "body", broken_body)
    app = create_http_honeypot(FakePipeline())  # type: ignore[arg-type]
    client = TestClient(app)
    assert client.get("/missing").status_code == 404


def test_config_auth_lookup_exception(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.soar.active_profile = "local"
    settings.admin.enabled = True
    settings.stream.enabled = False
    settings.soar.mttb_target_ms = 100

    def broken(_cls: object) -> None:
        raise RuntimeError("auth lookup failed")

    monkeypatch.setattr(auth_module.AuthConfig, "from_env", classmethod(broken))
    config.validate_settings(settings)
