"""Cover SSH server lifecycle, TTY fallback, and auth branches."""

from __future__ import annotations

import asyncio
import sys
import time

import pytest

import cloudsentinel.server as server_module
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSSHServer, ConnectionLimiter, TTYLogger


class FakePipeline:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, envelope: object) -> None:
        self.events.append(("emit", {}))


class FakeSoar:
    async def process_event(self, _session: str, event: dict) -> dict:
        return event


class FakeConn:
    def __init__(self, version: str | None = None) -> None:
        self.version = version
        self.closed = False

    def get_extra_info(self, name: str, default: object = None) -> object:
        if name == "peername":
            return ("8.8.8.8", 54321)
        if name == "client_version":
            return self.version
        return default

    def close(self) -> None:
        self.closed = True


def _server(limiter: ConnectionLimiter | None = None) -> CloudSentinelSSHServer:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    return CloudSentinelSSHServer(
        settings,
        FakePipeline(),  # type: ignore[arg-type]
        FakeSoar(),  # type: ignore[arg-type]
        HASSHDNA(),
        limiter or ConnectionLimiter(max_total=10),
    )


@pytest.mark.asyncio
async def test_tty_fallbacks(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("pathlib.Path.mkdir", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no dir")))
    broken = TTYLogger("tty-broken")
    await broken.save_async()
    broken.save()

    logger = TTYLogger("tty-sync")
    logger._dir = tmp_path
    logger.record(b"hello")
    monkeypatch.setitem(sys.modules, "aiofiles", None)
    await logger.save_async()
    assert (tmp_path / "tty.log").exists()



def test_tty_sync_save(tmp_path) -> None:
    logger = TTYLogger("tty-no-loop")
    logger._dir = tmp_path
    logger.record(b"world")
    logger.save()
    assert (tmp_path / "tty.raw").read_bytes() == b"world"


@pytest.mark.asyncio
async def test_server_connection_lifecycle() -> None:
    rejected = _server(ConnectionLimiter(max_total=0))
    conn = FakeConn()
    rejected.connection_made(conn)  # type: ignore[arg-type]
    assert conn.closed

    server = _server()
    server.connection_made(FakeConn())  # type: ignore[arg-type]
    assert server._accepted
    server.connection_lost(None)
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_begin_auth_branches(monkeypatch) -> None:
    server = _server()
    server._accepted = True
    server.started_at = time.time() - 1900
    assert server.begin_auth("root") is False

    server = _server()
    server._accepted = True
    server.conn = FakeConn("SSH-2.0-client")  # type: ignore[assignment]
    monkeypatch.setattr(server_module, "extract_hassh", lambda _conn: ("h" * 32, "algs"))
    monkeypatch.setattr(
        server.hassh_dna,
        "lookup",
        lambda _hassh: {"threat_level": "critical", "botnet_family": "unit"},
    )
    assert server.begin_auth("root") is True
    assert server.hassh == "h" * 32

    server = _server()
    server._accepted = True
    server.settings.fingerprinting.enable_hassh = False
    server.conn = FakeConn("SSH-2.0-client")  # type: ignore[assignment]
    assert server.begin_auth("root") is True
    assert server.hassh
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_auth_rejections_and_completion() -> None:
    server = _server()
    server._auth_attempts = 20
    assert server.validate_password("root", "x") is False

    class BadKey:
        def get_algorithm(self) -> bytes:
            raise RuntimeError("bad key")

    assert server.validate_public_key("root", BadKey()) is False  # type: ignore[arg-type]
    server.auth_completed()
