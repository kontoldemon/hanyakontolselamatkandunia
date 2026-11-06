"""Cover remaining server helper/error branches."""

from __future__ import annotations

import builtins
import types
from pathlib import Path

import pytest

import cloudsentinel.server as server_module
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import (
    CloudSentinelSSHServer,
    CloudSentinelSession,
    ConnectionLimiter,
    TTYLogger,
    extract_hassh,
    extract_ja4s,
)


class FakePipeline:
    async def emit(self, _envelope: object) -> None:
        return None


class FakeSoar:
    async def process_event(self, _session: str, event: dict) -> dict:
        return event


def _server() -> CloudSentinelSSHServer:
    return CloudSentinelSSHServer(
        load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env"),
        FakePipeline(),  # type: ignore[arg-type]
        FakeSoar(),  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=10),
    )


def test_hassh_and_ja4s_fallbacks(monkeypatch) -> None:
    class BrokenKex:
        @property
        def algorithm(self) -> bytes:
            raise RuntimeError("kex failed")

    class FallbackConn:
        _kex = BrokenKex()

        def get_extra_info(self, name: str, default: object = None) -> object:
            if "alg" in name:
                raise RuntimeError("missing")
            values = {"recv_cipher": "aes", "recv_mac": "hmac", "recv_compression": "none"}
            return values.get(name, default)

    hassh, algorithms = extract_hassh(FallbackConn())
    assert hassh
    assert "unknown-kex" in algorithms

    class LastResortConn:
        def get_extra_info(self, name: str, default: object = None) -> object:
            if name in {"recv_cipher", "recv_mac", "recv_compression"}:
                return ""
            raise RuntimeError("no version")

    assert extract_hassh(LastResortConn()) == (None, None)

    class BrokenConn:
        def get_extra_info(self, _name: str, _default: object = None) -> object:
            raise RuntimeError("broken")

    assert extract_ja4s(BrokenConn(), "algs") is None


def test_host_key_creation_and_tty_failures(monkeypatch, tmp_path) -> None:
    class Key:
        def export_private_key(self) -> str:
            return "private"

        def public_key(self) -> object:
            return object()

    monkeypatch.setattr(server_module.asyncssh, "generate_private_key", lambda _kind: Key())
    key_path = tmp_path / "host.key"
    assert server_module._load_or_create_host_key_sync(key_path)
    assert key_path.read_text() == "private"

    logger = TTYLogger("tty-final")
    logger._dir = tmp_path
    logger.record(b"x")

    def broken_open(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(builtins, "open", broken_open)
    logger.save()
    logger.save_async = lambda: (_ for _ in ()).throw(RuntimeError("async failed"))  # type: ignore[method-assign]
    logger.save()


def test_session_cd_and_write_errors() -> None:
    session = CloudSentinelSession(_server())
    session._handle_cd([".."])
    session._handle_cd(["/tmp"])
    session._handle_cd(["~"])
    session._handle_cd(["work"])
    session._handle_cd([])

    class BrokenChan:
        def write(self, _data: object) -> None:
            raise OSError("closed")

    session.chan = BrokenChan()  # type: ignore[assignment]
    session._write("ignored")
