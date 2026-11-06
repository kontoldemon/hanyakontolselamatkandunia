"""Cover main() failure/shutdown branches and remaining server helpers."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

import cloudsentinel.server as server_module
from cloudsentinel.config import load_settings


@pytest.mark.asyncio
async def test_main_failure_and_shutdown_paths(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.enabled = False
    settings.stream.enabled = False
    settings.honeypot.http_enabled = False
    settings.honeypot.dns_enabled = False

    class ImmediateEvent:
        async def wait(self) -> None:
            return None

        def set(self) -> None:
            return None

    class FakeLoop:
        def __init__(self) -> None:
            self.calls = 0

        def add_signal_handler(self, _sig: object, handler: object) -> None:
            self.calls += 1
            if self.calls == 1:
                handler()
            else:
                raise NotImplementedError

    class FakeServer:
        sockets: list = []

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    async def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    async def failing_start(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("start failed")

    async def fake_create_server(*_args: object, **_kwargs: object) -> FakeServer:
        return FakeServer()

    async def fake_host_key(*_args: object, **_kwargs: object) -> object:
        return object()

    class FakeAuth:
        config = types.SimpleNamespace(enabled=False)

    def failing_save(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("save failed")

    monkeypatch.setattr(server_module, "load_settings", lambda *_a, **_k: settings)
    monkeypatch.setattr(server_module, "setup_observability", lambda *_a: None)
    monkeypatch.setattr(server_module, "generate_self_signed_cert", lambda **_k: ("", ""))
    monkeypatch.setattr(server_module, "get_auth", lambda: FakeAuth())
    monkeypatch.setattr(server_module, "asyncssh", types.SimpleNamespace(create_server=fake_create_server))
    monkeypatch.setattr(server_module, "load_or_create_host_key", fake_host_key)
    monkeypatch.setattr(server_module.asyncio, "Event", ImmediateEvent)
    monkeypatch.setattr(server_module.asyncio, "get_running_loop", lambda: FakeLoop())
    monkeypatch.setattr(server_module.EventPipeline, "start", failing_start)
    monkeypatch.setattr(server_module.EventPipeline, "stop", no_op)
    monkeypatch.setattr(server_module.SOAREngine, "start", no_op)
    monkeypatch.setattr(server_module.SOAREngine, "stop", no_op)
    monkeypatch.setattr(server_module.ClickHouseForwarder, "start", failing_start)
    monkeypatch.setattr(server_module.ClickHouseForwarder, "stop", no_op)
    monkeypatch.setattr(server_module.CommandAnomalyDetector, "save", failing_save)
    monkeypatch.setattr(sys, "argv", ["server"])
    monkeypatch.setitem(sys.modules, "cloudsentinel.metrics", None)
    await server_module.main()
