"""Cover stress-test connection branches and final shell redirect/error paths."""

from __future__ import annotations

import asyncio
import os
import sys
import types

import pytest

import cloudsentinel.shell as shell_module
import cloudsentinel.stress_test as stress_module
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.vfs import VirtualFileSystem


class FakeTransport:
    def __init__(self, fail: bool = False) -> None:
        self.writes: list[bytes] = []
        self.fail = fail

    async def read(self, _size: int) -> bytes:
        return b""

    def write(self, data: bytes) -> None:
        if self.fail:
            raise RuntimeError("transport closed")
        self.writes.append(data)

    def close(self) -> None:
        return None


def _shell(fail: bool = False) -> HoneyPotInteractiveProtocol:
    return HoneyPotInteractiveProtocol(
        FakeTransport(fail),
        VirtualFileSystem(),
        session_id="unit-stress-shell",
        ip="10.0.0.1",
    )


def test_shell_redirect_and_write_errors() -> None:
    session = _shell()
    session._dispatch_line(">")
    session._dispatch_line("echo hello > /tmp/file")
    session._execute_single(b"bad 'quote")
    session.write("ignored")
    session.transport.fail = True
    session.write("ignored")
    assert session._exit_code in {0, 127}


def test_stress_connection_paths(monkeypatch) -> None:
    class FakeStdout:
        async def read(self, _size: int) -> bytes:
            raise TimeoutError

    class FakeStdin:
        def write(self, _data: bytes) -> None:
            return None

    class FakeProcess:
        stdin = FakeStdin()
        stdout = FakeStdout()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class FakeConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def create_process(self) -> FakeProcess:
            return FakeProcess()

    fake_asyncssh = types.ModuleType("asyncssh")
    fake_asyncssh.connect = lambda *_args, **_kwargs: FakeConnection()
    monkeypatch.setitem(sys.modules, "asyncssh", fake_asyncssh)
    stress = stress_module.StressTest("127.0.0.1", 22, 1)
    report = asyncio.run(stress.run())
    assert report["total_attempted"] == 1

    def fail_connect(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("ssh down")

    fake_asyncssh.connect = fail_connect
    failed = stress_module.StressTest("127.0.0.1", 22, 1)
    report = asyncio.run(failed.run())
    assert report["failed"] == 1

    stress.connected = 500
    stress.timings = [0.1]
    monkeypatch.setattr(os, "getloadavg", lambda: (_ for _ in ()).throw(OSError("no loadavg")), raising=False)
    assert stress._resource_snapshot()["loadavg"] is None
    assert stress._report(1.0)["successful"] == 500

    async def fake_run(_self: object) -> dict:
        return {"acceptance_pass": False}

    monkeypatch.setattr(stress_module.StressTest, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["stress_test", "--acceptance"])
    with pytest.raises(SystemExit):
        asyncio.run(stress_module.main())
