"""Exercise the server main() startup and teardown without opening real sockets."""

from __future__ import annotations

import sys

import pytest

import cloudsentinel.server as server_module
from cloudsentinel.config import load_settings


@pytest.mark.asyncio
async def test_server_main_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.enabled = False
    settings.stream.enabled = False
    settings.honeypot.http_enabled = False
    settings.honeypot.dns_enabled = False
    settings.tls.enabled = False
    settings.observability.enabled = False

    class ImmediateEvent:
        def __init__(self) -> None:
            self._set = False

        async def wait(self) -> None:
            return None

        def set(self) -> None:
            self._set = True

    class FakeSSHServer:
        sockets: list = []

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    async def fake_create_server(*_args: object, **_kwargs: object) -> FakeSSHServer:
        return FakeSSHServer()

    async def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(server_module, "load_settings", lambda *_args, **_kwargs: settings)
    monkeypatch.setattr(server_module, "setup_observability", lambda *_args: None)
    monkeypatch.setattr(server_module, "generate_self_signed_cert", lambda **_kwargs: ("", ""))
    monkeypatch.setattr(server_module.asyncio, "Event", ImmediateEvent)
    monkeypatch.setattr(server_module.asyncssh, "create_server", fake_create_server)
    monkeypatch.setattr(server_module.EventPipeline, "start", no_op)
    monkeypatch.setattr(server_module.EventPipeline, "stop", no_op)
    monkeypatch.setattr(server_module.ClickHouseForwarder, "start", no_op)
    monkeypatch.setattr(server_module.ClickHouseForwarder, "stop", no_op)
    monkeypatch.setattr(server_module.SOAREngine, "start", no_op)
    monkeypatch.setattr(server_module.SOAREngine, "stop", no_op)
    monkeypatch.setattr(server_module.CommandAnomalyDetector, "save", lambda *_args: None)
    monkeypatch.setattr(sys, "argv", ["server"])

    await server_module.main()
