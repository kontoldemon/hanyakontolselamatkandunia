"""Final DNS, shell, and stream replay branches."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from cloudsentinel.dns_honeypot import DNSHoneypot
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.stream import LiveStream
from cloudsentinel.vfs import VirtualFileSystem


class DNSClient:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list = []
        self.fail = fail

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append((data, addr))


def _query() -> bytes:
    return b"\x12\x34\x01\x00\x00\x01" + b"\x00\x00" * 3 + b"\x04test\x00\x00\x01\x00\x01"


def test_dns_rate_limit_and_exception() -> None:
    honeypot = DNSHoneypot(max_queries_per_ip=1)
    good = DNSClient()
    asyncio.run(honeypot._handle_query(_query(), ("8.8.8.8", 53), good))
    asyncio.run(honeypot._handle_query(_query(), ("8.8.8.8", 53), good))
    assert good.sent

    failing = DNSHoneypot()
    asyncio.run(failing._handle_query(_query(), ("9.9.9.9", 53), DNSClient(fail=True)))
    assert DNSHoneypot._parse_qname(b"\xc0\x02\x03www\xc0\x02", 0) == "www"


def test_shell_redirect_lines() -> None:
    class Transport:
        def write(self, _data: bytes) -> None:
            return None

        def close(self) -> None:
            return None

    session = HoneyPotInteractiveProtocol(
        Transport(),
        VirtualFileSystem(),
        session_id="unit-final-99",
        ip="10.0.0.1",
    )
    session._dispatch_line(">")
    session._dispatch_line("echo hi > /tmp/x")
    session._execute_single(b"bad 'quote")


@pytest.mark.asyncio
async def test_stream_replay_emit() -> None:
    class FakeSio:
        def __init__(self, **_kwargs: object) -> None:
            self.handlers: dict = {}
            self.emitted: list = []

        def event(self, func):
            self.handlers[func.__name__] = func
            return func

        def attach(self, _app: object) -> None:
            return None

        async def emit(self, event: str, data: dict, to: str | None = None) -> None:
            self.emitted.append((event, data, to))

        async def disconnect(self, _sid: str) -> None:
            return None

    socketio = types.ModuleType("socketio")
    socketio.AsyncServer = FakeSio
    aiohttp = types.ModuleType("aiohttp")
    web = types.ModuleType("aiohttp.web")
    web.Application = type("Application", (), {})
    web.AppRunner = type(
        "AppRunner",
        (),
        {
            "__init__": lambda self, _app: None,
            "setup": lambda self: asyncio.sleep(0),
            "cleanup": lambda self: asyncio.sleep(0),
        },
    )
    web.TCPSite = type("TCPSite", (), {"__init__": lambda *_a, **_k: None, "start": lambda self: asyncio.sleep(0)})
    aiohttp.web = web
    sys.modules["socketio"] = socketio
    sys.modules["aiohttp"] = aiohttp
    sys.modules["aiohttp.web"] = web

    stream = LiveStream(auth_token="secret")
    await stream.start()
    stream._buffer.append({"eventid": "cached"})
    await stream._sio.handlers["connect"]("sid", {"HTTP_AUTHORIZATION": "Bearer secret", "QUERY_STRING": ""})
    assert any(item[2] == "sid" for item in stream._sio.emitted)
