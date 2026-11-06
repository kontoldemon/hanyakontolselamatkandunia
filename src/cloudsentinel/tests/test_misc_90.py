"""Final small branches for 90% coverage."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import cloudsentinel.hassh as hassh_module
import cloudsentinel.honeyfs_seed as honeyfs_module
import cloudsentinel.mttb_benchmark as mttb_module
import cloudsentinel.observability as observability
from cloudsentinel.commands import Command
from cloudsentinel.hassh import infer_client_software
from cloudsentinel.vfs import VirtualFileSystem


def test_hassh_client_inference(monkeypatch) -> None:
    monkeypatch.setattr(
        hassh_module.HASSHDNA,
        "lookup",
        lambda _self, _hassh: {"client_software": "CustomSSH"},
    )
    assert infer_client_software("ignored", "hash") == "CustomSSH"
    assert infer_client_software("libssh2") == "libssh2"
    assert infer_client_software("dropbear_2020") == "Dropbear SSH"
    assert infer_client_software("OpenSSH_9.6") == "OpenSSH"
    assert infer_client_software("PuTTY_Release_0.80") == "PuTTY"
    assert infer_client_software("") == "unknown"


def test_commands_with_only_write() -> None:
    class Protocol:
        def __init__(self) -> None:
            self.data: list[bytes] = []

        def write(self, data: bytes) -> None:
            self.data.append(data)

    protocol = Protocol()
    command = Command(protocol)
    command.write("out")
    command.writeBytes(b"raw")
    command.errorWrite("err")
    assert protocol.data == [b"out", b"raw", b"err"]


def test_honeyfs_root_and_empty(monkeypatch, tmp_path) -> None:
    class FakeVfs:
        _entries = {
            "/": {"type": "dir"},
            "/etc": {"type": "dir"},
            "/etc/unit": {"type": "file", "content": b"x"},
        }

    monkeypatch.setattr(
        VirtualFileSystem,
        "generate_realistic_files",
        classmethod(lambda _cls, _profile="ubuntu-22.04": FakeVfs()),
    )
    assert honeyfs_module.seed_honeyfs(tmp_path / "seed") > 0

    monkeypatch.setattr(honeyfs_module, "seed_honeyfs", lambda *_args: 0)
    monkeypatch.setattr(sys, "argv", ["honeyfs_seed", "--output", str(tmp_path / "empty")])
    honeyfs_module.main()


def test_honeyfs_read_error(monkeypatch, tmp_path) -> None:
    root = tmp_path / "honeyfs"
    root.mkdir()
    (root / "file").write_bytes(b"data")

    def fail_read(_self: Path) -> bytes:
        raise OSError("unreadable")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    vfs = VirtualFileSystem.from_honeyfs(str(root))
    assert vfs.exists("/file")
    assert vfs.file_contents("/file") == b""


def test_structlog_fallback(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "structlog", None)
    assert observability.setup_structlog() is not None


def test_mttb_redis_setting(monkeypatch) -> None:
    async def no_start(_self: object) -> None:
        return None

    async def no_stop(_self: object) -> None:
        return None

    monkeypatch.setattr(mttb_module.SOAREngine, "start", no_start)
    monkeypatch.setattr(mttb_module.SOAREngine, "stop", no_stop)
    args = argparse.Namespace(
        allowlist="",
        redis_url="redis://127.0.0.1:6379/0",
        risk_threshold=70,
        active=False,
        firewall_path="/sbin/iptables",
        block_ttl=60,
        iterations=0,
        source_ip="8.8.8.8",
        delay=0,
        target_ms=100,
    )
    report = asyncio.run(mttb_module.run_benchmark(args))
    assert report["iterations"] == 0
