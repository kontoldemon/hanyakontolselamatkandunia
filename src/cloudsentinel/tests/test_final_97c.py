"""Final short branches for DNS, shell, and Infisical status."""

from __future__ import annotations

import asyncio
import sys
import types

from cloudsentinel._secrets import InfisicalProvider
from cloudsentinel.dns_honeypot import DNSHoneypot
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.vfs import VirtualFileSystem


class FakeTransport:
    def __init__(self) -> None:
        self.sent: list = []
        self.writes: list[bytes] = []

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.sent.append((data, addr))

    async def read(self, _size: int) -> bytes:
        return b""

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def close(self) -> None:
        return None


def _query() -> bytes:
    return b"\x12\x34\x01\x00\x00\x01" + b"\x00\x00" * 3 + b"\x04test\x00\x00\x01\x00\x01"


def test_dns_short_and_send() -> None:
    honeypot = DNSHoneypot()
    asyncio.run(honeypot._handle_query(b"short", ("8.8.8.8", 53), None))
    transport = FakeTransport()
    asyncio.run(honeypot._handle_query(_query(), ("8.8.8.8", 53), transport))
    assert transport.sent


def test_shell_redirect_and_bad_quote() -> None:
    transport = FakeTransport()
    session = HoneyPotInteractiveProtocol(
        transport,
        VirtualFileSystem(),
        session_id="unit-final-97",
        ip="10.0.0.1",
    )
    session._dispatch_line(">")
    session._execute_single(b"bad 'quote")


def test_infisical_non_200(monkeypatch) -> None:
    provider = InfisicalProvider()
    provider._available = True
    provider._token = "token"
    provider._last_fetch = 10**18

    class Response:
        status_code = 500

        def json(self) -> dict:
            return {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, *_args, **_kwargs):
            return Response()

    fake = types.ModuleType("httpx")
    fake.AsyncClient = Client
    monkeypatch.setitem(sys.modules, "httpx", fake)
    assert asyncio.run(provider.get("UNIT_KEY", "fallback")) == "fallback"
