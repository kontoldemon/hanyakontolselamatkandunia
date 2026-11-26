"""Final short branches for DNS, shell, and Infisical status."""

from __future__ import annotations

import asyncio
import sys
import types

from cloudsentinel.dns_honeypot import DNSHoneypot
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




