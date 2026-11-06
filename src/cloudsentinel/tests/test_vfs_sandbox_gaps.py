"""Cover VFS loaders/generators and sandbox fallback/error paths."""

from __future__ import annotations

import asyncio
import pickle
import sys
import types

import pytest

import cloudsentinel.sandbox as sandbox_module
from cloudsentinel.sandbox import (
    DockerSDKSandbox,
    DockerSandbox,
    FirecrackerSandbox,
    GVisorSandbox,
    create_sandbox,
)
from cloudsentinel.vfs import VirtualFileSystem


def test_vfs_loaders_and_generators(tmp_path) -> None:
    root = tmp_path / "honeyfs"
    (root / "etc").mkdir(parents=True)
    (root / "etc" / "hostname").write_bytes(b"unit-host\n")
    (root / "root").mkdir()
    (root / "root" / "note.txt").write_text("secret")
    loaded = VirtualFileSystem.from_honeyfs(str(root))
    assert loaded.file_contents("/etc/hostname") == b"unit-host\n"
    assert loaded.isfile("/root/note.txt")
    assert VirtualFileSystem.from_honeyfs(str(tmp_path / "missing")).listdir("/") == []

    pickle_path = tmp_path / "fs.pickle"
    source = VirtualFileSystem()
    source.mkdir("/etc")
    source.mkfile("/etc/hostname", b"picked\n")
    pickle_path.write_bytes(pickle.dumps(source._entries))
    picked = VirtualFileSystem.from_pickle(str(pickle_path))
    assert picked.file_contents("/etc/hostname") == b"picked\n"

    realistic = VirtualFileSystem.generate_realistic_files()
    assert realistic.exists("/etc")
    assert realistic.exists("/root")
    assert realistic.listdir("/etc")

    minimal = VirtualFileSystem._build_minimal()
    assert minimal.exists("/proc/cpuinfo")
    assert minimal.stat("/proc/cpuinfo")
    assert minimal.isdir("/proc")
    minimal._add_proc_stubs()
    assert VirtualFileSystem.build_default().exists("/proc/cpuinfo")
    assert VirtualFileSystem.resolve_path("../../etc", "/root") == "/"


@pytest.mark.asyncio
async def test_docker_sandbox_errors(monkeypatch) -> None:
    class SlowProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.sleep(60)
            return b"", b""

        def kill(self) -> None:
            return None

    async def slow_exec(*_args: object, **_kwargs: object) -> SlowProcess:
        return SlowProcess()

    sandbox = DockerSandbox()
    sandbox.timeout = 0.01
    monkeypatch.setattr(sandbox_module.asyncio, "create_subprocess_exec", slow_exec)
    assert await sandbox.execute("id", "~") == (124, "Sandbox timeout exceeded.")

    async def boom_exec(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("docker down")

    monkeypatch.setattr(sandbox_module.asyncio, "create_subprocess_exec", boom_exec)
    code, message = await sandbox.execute("id", "/")
    assert code == 1
    assert "Sandbox error" in message


@pytest.mark.asyncio
async def test_gvisor_sandbox_errors(monkeypatch) -> None:
    sandbox = GVisorSandbox()
    sandbox._available = True
    sandbox.timeout = 0.01

    class SlowProcess:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            await asyncio.sleep(60)
            return b"", b""

        def kill(self) -> None:
            return None

    async def slow_exec(*_args: object, **_kwargs: object) -> SlowProcess:
        return SlowProcess()

    monkeypatch.setattr(sandbox_module.asyncio, "create_subprocess_exec", slow_exec)
    assert await sandbox.execute("id", "~") == (124, "gVisor sandbox timeout.")

    async def boom_exec(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("runsc down")

    monkeypatch.setattr(sandbox_module.asyncio, "create_subprocess_exec", boom_exec)
    code, message = await sandbox.execute("id", "/")
    assert code == 1
    assert "gVisor error" in message


@pytest.mark.asyncio
async def test_docker_sdk_sandbox(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "docker", None)
    monkeypatch.setattr(
        DockerSandbox,
        "execute",
        lambda _self, _command, _cwd: asyncio.sleep(0, result=(0, "fallback")),
    )
    sdk = DockerSDKSandbox()
    assert await sdk.execute("id", "~") == (0, "fallback")

    class FakeContainer:
        def wait(self, **_kwargs: object) -> dict:
            return {"StatusCode": 0}

        def logs(self) -> bytes:
            return b"sdk output"

        def kill(self) -> None:
            return None

    class FakeContainers:
        def run(self, *_args: object, **_kwargs: object) -> FakeContainer:
            return FakeContainer()

    class FakeClient:
        containers = FakeContainers()

    fake_docker = types.ModuleType("docker")
    errors = types.ModuleType("docker.errors")
    errors.DockerException = RuntimeError
    fake_docker.errors = errors
    fake_docker.from_env = lambda: FakeClient()
    monkeypatch.setitem(sys.modules, "docker", fake_docker)
    monkeypatch.setitem(sys.modules, "docker.errors", errors)
    assert await DockerSDKSandbox().execute("id", "~") == (0, "sdk output")

    class BrokenContainers:
        def run(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("sdk down")

    class BrokenClient:
        containers = BrokenContainers()

    fake_docker.from_env = lambda: BrokenClient()
    code, message = await DockerSDKSandbox().execute("id", "~")
    assert code == 1
    assert "Sandbox error" in message

    class SlowContainer:
        def wait(self, **_kwargs: object) -> dict:
            import time

            time.sleep(1)
            return {"StatusCode": 0}

        def logs(self) -> bytes:
            return b""

        def kill(self) -> None:
            return None

    class SlowContainers:
        def run(self, *_args: object, **_kwargs: object) -> SlowContainer:
            return SlowContainer()

    class SlowClient:
        containers = SlowContainers()

    fake_docker.from_env = lambda: SlowClient()
    slow = DockerSDKSandbox()
    slow.timeout = 0.01
    assert await slow.execute("id", "~") == (124, "Sandbox timeout exceeded.")


def test_sandbox_factory_and_firecracker(monkeypatch) -> None:
    assert isinstance(create_sandbox("docker"), DockerSandbox)
    assert isinstance(create_sandbox("firecracker"), FirecrackerSandbox)
    monkeypatch.setattr(sandbox_module.shutil, "which", lambda _name: None)
    assert isinstance(create_sandbox("gvisor"), DockerSandbox)
    monkeypatch.setattr(sandbox_module.shutil, "which", lambda _name: "/usr/bin/tool")
    assert isinstance(create_sandbox("gvisor"), GVisorSandbox)
    assert asyncio.run(FirecrackerSandbox().execute("id", "~"))[0] == 1
    available = FirecrackerSandbox()
    available._available = True
    assert asyncio.run(available.execute("id", "~"))[0] == 1
