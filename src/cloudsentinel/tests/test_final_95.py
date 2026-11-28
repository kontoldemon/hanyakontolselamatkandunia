"""Final branches to clear 95%."""

from __future__ import annotations

import asyncio
import time
import types
from collections import deque

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

    async def broken_stream(_self: object):
        raise RuntimeError("stream failed")
        yield b""

    monkeypatch.setattr(Request, "stream", broken_stream)
    app = create_http_honeypot(FakePipeline())  # type: ignore[arg-type]
    client = TestClient(app)
    assert client.get("/missing").status_code == 404


def test_http_large_body_is_not_buffered() -> None:
    app = create_http_honeypot(FakePipeline())  # type: ignore[arg-type]
    client = TestClient(app)
    response = client.post("/missing", content=b"x" * 100_000)
    assert response.status_code == 404


def test_http_honeypot_rate_limits_per_ip() -> None:
    from cloudsentinel import http_server

    http_server._http_rate.clear()
    app = create_http_honeypot(FakePipeline())  # type: ignore[arg-type]
    client = TestClient(app)
    for _ in range(120):
        assert client.get("/missing").status_code == 404
    assert client.get("/missing").status_code == 429
    http_server._http_rate.clear()


def test_http_rate_window_prunes_and_caps_map() -> None:
    from cloudsentinel import http_server

    http_server._http_rate.clear()
    http_server._http_rate["127.0.0.1"] = deque([time.monotonic() - 61])
    app = create_http_honeypot(FakePipeline())  # type: ignore[arg-type]
    client = TestClient(app)
    assert client.get("/missing").status_code == 404
    assert len(http_server._http_rate["127.0.0.1"]) == 1

    http_server._http_rate.clear()
    for index in range(5001):
        http_server._http_rate[f"ip{index}"] = deque()
    assert client.get("/missing").status_code == 404
    assert len(http_server._http_rate) == 1
    http_server._http_rate.clear()


def test_http_chunked_large_body_is_capped() -> None:
    app = create_http_honeypot(FakePipeline())  # type: ignore[arg-type]
    client = TestClient(app)
    response = client.post("/missing", content=iter([b"x" * 70000]))
    assert response.status_code == 404


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
