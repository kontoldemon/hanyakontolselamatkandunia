"""Cover main() optional services and teardown branches."""

from __future__ import annotations

import sys
import types

import pytest

import cloudsentinel.dns_honeypot as dns_module
import cloudsentinel.server as server_module
from cloudsentinel.config import load_settings


@pytest.mark.asyncio
async def test_main_with_optional_services(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.enabled = True
    settings.stream.enabled = True
    settings.honeypot.http_enabled = True
    settings.honeypot.dns_enabled = True
    settings.honeypot.tls_cert_file = "var/lib/cloudsentinel/tls/unit.crt"
    settings.honeypot.tls_key_file = "var/lib/cloudsentinel/tls/unit.key"

    class ImmediateEvent:
        async def wait(self) -> None:
            return None

        def set(self) -> None:
            return None

    class FakeSSHServer:
        sockets: list = []

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    class FakeStream:
        def __init__(self, **_kwargs: object) -> None:
            self.stopped = False

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            self.stopped = True

    class FakeDNS:
        def __init__(self, **_kwargs: object) -> None:
            return None

        async def start(self) -> None:
            return None

    class FakeAuth:
        config = types.SimpleNamespace(enabled=True)

    async def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    async def fake_create_server(*_args: object, **_kwargs: object) -> FakeSSHServer:
        return FakeSSHServer()

    async def fake_host_key(*_args: object, **_kwargs: object) -> object:
        return object()

    monkeypatch.setattr(server_module, "load_settings", lambda *_a, **_k: settings)
    monkeypatch.setattr(server_module, "setup_observability", lambda *_a: None)
    monkeypatch.setattr(server_module, "generate_self_signed_cert", lambda **_k: ("cert", "key"))
    monkeypatch.setattr(server_module, "get_auth", lambda: FakeAuth())
    monkeypatch.setattr(server_module, "asyncssh", types.SimpleNamespace(create_server=fake_create_server))
    monkeypatch.setattr(server_module, "load_or_create_host_key", fake_host_key)
    monkeypatch.setattr(server_module.asyncio, "Event", ImmediateEvent)
    monkeypatch.setattr(server_module.EventPipeline, "start", no_op)
    monkeypatch.setattr(server_module.EventPipeline, "stop", no_op)
    monkeypatch.setattr(server_module.SOAREngine, "start", no_op)
    monkeypatch.setattr(server_module.SOAREngine, "stop", no_op)
    monkeypatch.setattr(server_module.ClickHouseForwarder, "start", no_op)
    monkeypatch.setattr(server_module.ClickHouseForwarder, "stop", no_op)
    monkeypatch.setattr(server_module.CommandAnomalyDetector, "save", lambda *_a: None)
    monkeypatch.setattr(server_module, "start_admin_api", no_op)
    monkeypatch.setattr(server_module, "start_http_honeypot", no_op)
    monkeypatch.setattr(server_module, "LiveStream", FakeStream)
    monkeypatch.setattr(dns_module, "DNSHoneypot", FakeDNS)
    monkeypatch.setattr(sys, "argv", ["server"])

    await server_module.main()
