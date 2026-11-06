"""Cover shell error branches and JWT validation edge cases."""

from __future__ import annotations

import asyncio
import builtins
import sys
import types
from pathlib import Path

import pytest

import cloudsentinel.auth as auth_module
import cloudsentinel.shell as shell_module
from cloudsentinel.auth import AuthConfig, JWTAuth, PyJWTAuth
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.vfs import VirtualFileSystem


class FakeTransport:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False

    async def read(self, _size: int) -> bytes:
        return b""

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def close(self) -> None:
        self.closed = True


def _session() -> HoneyPotInteractiveProtocol:
    return HoneyPotInteractiveProtocol(
        FakeTransport(),
        VirtualFileSystem(),
        session_id="unit-shell-edges",
        ip="10.0.0.1",
    )


@pytest.mark.asyncio
async def test_shell_error_paths(monkeypatch, tmp_path) -> None:
    session = _session()

    def broken_mkdir(*_args: object, **_kwargs: object) -> None:
        raise OSError("no tty")

    monkeypatch.setattr(Path, "mkdir", broken_mkdir)
    session._init_tty_log()
    assert session._tty_dir is None
    monkeypatch.undo()

    session._tty_dir = tmp_path

    def broken_open(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(builtins, "open", broken_open)
    session._save_tty_log()
    monkeypatch.undo()

    class BrokenTransport(FakeTransport):
        async def read(self, _size: int) -> bytes:
            raise RuntimeError("socket gone")

    broken = HoneyPotInteractiveProtocol(
        BrokenTransport(),
        VirtualFileSystem(),
        session_id="unit-shell-broken",
        ip="10.0.0.1",
    )
    await broken.run()

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    exec_session = _session()
    exec_session._exec_command = "id"

    def broken_close() -> None:
        raise RuntimeError("close failed")

    exec_session.transport.close = broken_close  # type: ignore[method-assign]
    await exec_session.run_exec()

    session.cmdstack.append(object())
    session._handle_data(b"\x04")
    session._dispatch_line(object())  # type: ignore[arg-type]
    session._dispatch_line(">")
    session._dispatch_line("bad 'quote")
    session._execute_single(object())  # type: ignore[arg-type]

    class Boom:
        def __init__(self, *_args: object) -> None:
            return None

        def start(self) -> None:
            raise RuntimeError("boom")

    monkeypatch.setitem(shell_module.cmd_registry, "boom", Boom)
    session._execute_single(b"boom")

    original = session.fs.file_contents

    def broken_motd(_path: str) -> bytes:
        raise OSError("no motd")

    monkeypatch.setattr(session.fs, "file_contents", broken_motd)
    session._send_motd()
    session.fs.file_contents = original  # type: ignore[method-assign]


def test_jwt_validation_errors(monkeypatch) -> None:
    auth = PyJWTAuth(AuthConfig(secret="secret", enabled=True))
    fake_jwt = types.ModuleType("jwt")

    def decode(*_args: object, **_kwargs: object) -> dict:
        raise RuntimeError("generic jwt error")

    fake_jwt.decode = decode
    fake_jwt.ExpiredSignatureError = type("ExpiredSignatureError", (Exception,), {})
    fake_jwt.InvalidTokenError = type("InvalidTokenError", (Exception,), {})
    fake_jwt.encode = lambda *_args, **_kwargs: "token"
    monkeypatch.setitem(sys.modules, "jwt", fake_jwt)
    assert auth.validate_token("token") is None

    manual = JWTAuth(AuthConfig(secret="secret", enabled=True))
    monkeypatch.setattr(auth_module.hmac, "compare_digest", lambda *_args: True)
    monkeypatch.setattr(
        JWTAuth,
        "_b64url_decode",
        staticmethod(lambda _data: b"not-json"),
    )
    assert manual.validate_token("a.b.c") is None
