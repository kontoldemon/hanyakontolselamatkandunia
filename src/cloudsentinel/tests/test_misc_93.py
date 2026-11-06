"""Final utility branches for HASSH, GeoIP, DNS, sandbox, validate, and VFS agent."""

from __future__ import annotations

import asyncio
import sys
import time
import types

import pytest

import cloudsentinel.dns_honeypot as dns_module
import cloudsentinel.geoip as geoip
import cloudsentinel.sandbox as sandbox_module
import cloudsentinel.server as server_module
import cloudsentinel.validate_phase1 as validate_module
import cloudsentinel.vfs_agent as vfs_agent_module
from cloudsentinel.sandbox import DockerSandbox, GVisorSandbox
from cloudsentinel.vfs_agent import VFSContext, VFSAgent


def _dns_query(name: str = "unit.test") -> bytes:
    labels = b"".join(bytes([len(label)]) + label.encode() for label in name.split("."))
    return (
        b"\x12\x34\x01\x00\x00\x01" + b"\x00\x00" * 3 + labels + b"\x00\x00\x01\x00\x01"
    )


class FakeTransport:
    def __init__(self) -> None:
        self.sent: list = []

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.sent.append((data, addr))


def test_hassh_packet_path(monkeypatch) -> None:
    import asyncssh.packet as packet_module

    class FakePacket:
        def __init__(self, _raw: bytes) -> None:
            self.names = [
                b"curve25519-sha256",
                b"ssh-ed25519",
                b"aes128-ctr",
                b"aes128-ctr",
                b"hmac-sha2-256",
                b"hmac-sha2-256",
                b"none",
                b"none",
            ]

        def get_bytes(self, _count: int) -> bytes:
            return b"\x00" * 16

        def get_namelist(self) -> list[bytes]:
            return [self.names.pop(0)]

    class FakeConn:
        _client_kexinit = b"packet"

    monkeypatch.setattr(packet_module, "SSHPacket", FakePacket)
    hassh, algorithms = server_module.extract_hassh(FakeConn())
    assert hassh
    assert "curve25519-sha256" in algorithms


def test_geoip_reader_found(monkeypatch) -> None:
    fake_geoip2 = types.ModuleType("geoip2")
    fake_database = types.ModuleType("geoip2.database")
    fake_database.Reader = lambda _path: "reader"
    fake_geoip2.database = fake_database
    monkeypatch.setitem(sys.modules, "geoip2", fake_geoip2)
    monkeypatch.setitem(sys.modules, "geoip2.database", fake_database)
    monkeypatch.setattr(geoip, "_geoip_reader", None)
    monkeypatch.setattr(geoip.Path, "exists", lambda _self: True)
    assert geoip._get_reader() == "reader"


@pytest.mark.asyncio
async def test_dns_short_and_send() -> None:
    honeypot = dns_module.DNSHoneypot()
    await honeypot._handle_query(b"short", ("8.8.8.8", 53), None)
    transport = FakeTransport()
    await honeypot._handle_query(_dns_query(), ("8.8.8.8", 53), transport)
    assert transport.sent


@pytest.mark.asyncio
async def test_sandbox_kill_exceptions(monkeypatch) -> None:
    class SlowProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.sleep(60)
            return b"", b""

        def kill(self) -> None:
            raise RuntimeError("kill failed")

    async def slow_exec(*_args: object, **_kwargs: object) -> SlowProcess:
        return SlowProcess()

    monkeypatch.setattr(sandbox_module.asyncio, "create_subprocess_exec", slow_exec)
    docker = DockerSandbox()
    docker.timeout = 0.01
    assert await docker.execute("id", "~") == (124, "Sandbox timeout exceeded.")
    gvisor = GVisorSandbox()
    gvisor._available = True
    gvisor.timeout = 0.01
    assert await gvisor.execute("id", "~") == (124, "gVisor sandbox timeout.")


def test_validate_admin_error(monkeypatch, tmp_path) -> None:
    async def fake_tcp(*_args: object, **_kwargs: object) -> dict:
        return {"ok": True}

    monkeypatch.setattr(validate_module, "tcp_check", fake_tcp)
    monkeypatch.setattr(validate_module, "http_json", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(validate_module, "write_artifacts", lambda *_args: None)
    monkeypatch.setattr(sys, "argv", ["validate_phase1", "--artifacts-dir", str(tmp_path)])
    asyncio.run(validate_module.main())


def test_vfs_agent_final_edges() -> None:
    old = time.monotonic() - vfs_agent_module._GLOBAL_LLM_WINDOW_SECONDS - 1
    vfs_agent_module._GLOBAL_LLM_CALLS.append(old)
    vfs_agent_module._reserve_global_llm_call(10)

    agent = VFSAgent(vfs_agent_module.LLMSettings(provider="mock"), VFSContext("h", "Ubuntu"))
    try:
        assert agent._handle_local_state("") is None
        agent._handle_local_state("cd ~")
        assert agent.context.cwd == "~"
    finally:
        asyncio.run(agent.close())
