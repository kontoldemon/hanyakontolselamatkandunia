"""Cover SSH session command fallbacks and remaining auth edges."""

from __future__ import annotations

import asyncio
import types

import pytest

import cloudsentinel.server as server_module
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSession, CloudSentinelSSHServer, ConnectionLimiter


class FakePipeline:
    async def emit(self, _envelope: object) -> None:
        return None


class FakeSoar:
    mttb_ms = 1.0
    _mem_blocked_ips: set[str] = set()

    async def process_event(self, _session: str, event: dict) -> dict:
        return event


class FakeConn:
    def __init__(self, fail_close: bool = False, fail_version: bool = False) -> None:
        self.fail_close = fail_close
        self.fail_version = fail_version
        self.closed = False

    def get_extra_info(self, name: str, default: object = None) -> object:
        if name == "peername":
            return ("8.8.8.8", 1234)
        if name == "client_version" and self.fail_version:
            raise RuntimeError("version failed")
        return default

    def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise RuntimeError("close failed")


def _server(action: str = "none") -> CloudSentinelSSHServer:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.fingerprinting.enable_hassh = False
    settings.fingerprinting.enable_ja4s = False
    soar = FakeSoar()
    soar.process_event = lambda _session, event: _as_event(event, action)  # type: ignore[method-assign]
    return CloudSentinelSSHServer(
        settings,
        FakePipeline(),  # type: ignore[arg-type]
        soar,  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=10),
    )


async def _as_event(event: dict, action: str) -> dict:
    return {**event, "cloudsentinel_soar_action": action, "cloudsentinel_risk_score": 90}


@pytest.mark.asyncio
async def test_session_command_fallbacks(monkeypatch) -> None:
    session = CloudSentinelSession(_server())
    await session._execute("chmod 777 x")
    await session._execute("id")

    class BrokenCommand:
        def __init__(self, *_args: object) -> None:
            return None

        def start(self) -> None:
            raise RuntimeError("registry failed")

    monkeypatch.setitem(server_module.cmd_registry, "echo", BrokenCommand)
    await session._execute("echo hello")

    class Anomaly:
        def score(self, _command: str) -> dict:
            return {"anomaly_score": 99}

    session._anomaly_detector = Anomaly()
    await session._execute("unknown-command")

    async def broken_vfs(_command: str) -> tuple[str, str]:
        raise RuntimeError("vfs failed")

    monkeypatch.setattr(session.vfs, "run_command_with_mode", broken_vfs)
    assert await session._execute("another-unknown") == "bash: command execution error"
    session.data_received("\r", None)


@pytest.mark.asyncio
async def test_process_and_auth_edges() -> None:
    server = _server("iptables_block")
    server.conn = FakeConn(fail_close=True)  # type: ignore[assignment]
    await server._process_event({"eventid": "unit", "src_ip": "8.8.8.8"})
    assert server.conn.closed

    server = _server()
    server._accepted = False
    assert server.begin_auth("root") is False

    server = _server()
    server._accepted = True
    server.conn = FakeConn(fail_version=True)  # type: ignore[assignment]
    assert server.begin_auth("root") is True
