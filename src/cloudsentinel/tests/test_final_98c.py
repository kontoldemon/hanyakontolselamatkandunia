"""Final DNS query and shell/session branch coverage."""

from __future__ import annotations

import asyncio

from cloudsentinel.dns_honeypot import DNSHoneypot
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSSHServer, CloudSentinelSession, ConnectionLimiter
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.vfs import VirtualFileSystem


class Transport:
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


def test_dns_short_and_valid() -> None:
    honeypot = DNSHoneypot()
    asyncio.run(honeypot._handle_query(b"short", ("8.8.8.8", 53), None))
    transport = Transport()
    asyncio.run(honeypot._handle_query(_query(), ("8.8.8.8", 53), transport))
    assert transport.sent


def test_shell_redirect() -> None:
    session = HoneyPotInteractiveProtocol(
        Transport(),
        VirtualFileSystem(),
        session_id="unit-final-98c",
        ip="10.0.0.1",
    )
    session._dispatch_line(">")
    session._execute_single(b"bad 'quote")


def test_session_cd_parent() -> None:
    server = CloudSentinelSSHServer(
        load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env"),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=1),
    )
    session = CloudSentinelSession(server)
    session.vfs.context.cwd = "/root/sub"
    session._handle_cd([".."])
    assert session.vfs.context.cwd == "/root"
