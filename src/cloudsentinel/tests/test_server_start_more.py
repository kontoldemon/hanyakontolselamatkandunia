"""Cover server startup TLS/granian branches with fake ASGI servers."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

import cloudsentinel.config as config
import cloudsentinel.server as server_module


class FakeGranianServe:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, _app: object, **kwargs: object) -> None:
        self.calls.append(kwargs)


class FakeUvicornServer:
    def __init__(self, _config: object) -> None:
        pass

    async def serve(self) -> None:
        return None


def _install_granian(monkeypatch) -> FakeGranianServe:
    serve = FakeGranianServe()
    granian = types.ModuleType("granian")
    constants = types.ModuleType("granian.constants")
    constants.Interfaces = types.SimpleNamespace(ASGI="asgi")
    constants.Loops = types.SimpleNamespace(uvloop="uvloop")
    granian.constants = constants
    granian.serve = serve
    monkeypatch.setitem(sys.modules, "granian", granian)
    monkeypatch.setitem(sys.modules, "granian.constants", constants)
    return serve


def _settings():
    return config.load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )


@pytest.mark.asyncio
async def test_http_honeypot_granian_tls(monkeypatch, tmp_path) -> None:
    serve = _install_granian(monkeypatch)
    cert = tmp_path / "server.crt"
    key = tmp_path / "server.key"
    cert.write_text("cert")
    key.write_text("key")
    settings = _settings()
    settings.honeypot.tls_cert_file = str(cert)
    settings.honeypot.tls_key_file = str(key)
    await server_module.start_http_honeypot(settings, _pipeline(), None)
    assert serve.calls
    assert serve.calls[0]["ssl_certfile"] == str(cert)

    missing = _settings()
    missing.honeypot.tls_cert_file = str(tmp_path / "missing.crt")
    missing.honeypot.tls_key_file = str(tmp_path / "missing.key")
    await server_module.start_http_honeypot(missing, _pipeline(), None)
    assert len(serve.calls) == 2


def _pipeline():
    from cloudsentinel.pipeline import EventPipeline

    return EventPipeline(_settings().redis)


@pytest.mark.asyncio
async def test_admin_api_granian_and_autotls(monkeypatch, tmp_path) -> None:
    serve = _install_granian(monkeypatch)
    monkeypatch.setenv("ADMIN_SERVER", "granian")
    settings = _settings()
    settings.tls.enabled = False
    await server_module.start_admin_api(settings, _pipeline(), None)
    assert serve.calls

    cert = tmp_path / "auto.crt"
    key = tmp_path / "auto.key"
    cert.write_text("cert")
    key.write_text("key")
    monkeypatch.setattr(
        "cloudsentinel.tls.generate_self_signed_cert",
        lambda **_kwargs: (str(cert), str(key)),
    )
    settings = _settings()
    settings.tls.enabled = True
    settings.tls.cert_file = ""
    settings.tls.key_file = ""
    await server_module.start_admin_api(settings, _pipeline(), None)
    assert serve.calls[-1]["ssl_certfile"] == str(cert)


@pytest.mark.asyncio
async def test_admin_granian_fallback(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_SERVER", "granian")
    monkeypatch.setitem(sys.modules, "granian", None)
    fake_uvicorn = types.ModuleType("uvicorn")
    fake_uvicorn.Config = lambda *_args, **_kwargs: object()
    fake_uvicorn.Server = FakeUvicornServer
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    await server_module.start_admin_api(_settings(), _pipeline(), None)


def test_install_uvloop_failure(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "uvloop", None)
    server_module.install_uvloop()
