"""Cover server event pipeline and session execution branches."""

from __future__ import annotations

import asyncio
import types

import pytest

import cloudsentinel.server as server_module
import cloudsentinel.webhook as webhook_module
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import (
    CloudSentinelSSHServer,
    CloudSentinelSession,
    ConnectionLimiter,
)


class FakePipeline:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.events: list = []

    async def emit(self, envelope: object) -> None:
        if self.fail:
            raise RuntimeError("pipeline failed")
        self.events.append(envelope)


class FakeStream:
    def emit(self, _event: dict) -> None:
        raise RuntimeError("stream failed")


class FakeSoar:
    mttb_ms = 12.0
    _mem_blocked_ips = {"1.2.3.4"}

    def __init__(self, action: str = "iptables_block") -> None:
        self.action = action

    async def process_event(self, _session: str, event: dict) -> dict:
        return {
            **event,
            "cloudsentinel_soar_action": self.action,
            "cloudsentinel_risk_score": 90,
            "src_ip": "8.8.8.8",
        }


class FakeConn:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _server(pipeline=None, soar=None, stream=None):
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    return CloudSentinelSSHServer(
        settings,
        pipeline or FakePipeline(),  # type: ignore[arg-type]
        soar or FakeSoar(),  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=10),
        stream=stream,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_process_event_failures(monkeypatch) -> None:
    server = _server(pipeline=FakePipeline(fail=True), stream=FakeStream())
    server.conn = FakeConn()  # type: ignore[assignment]
    server.hassh = "h" * 32
    server.hassh_algorithms = "algs"
    server.ja4s = "ja4s"

    async def fail_alert(_event: dict) -> None:
        raise RuntimeError("webhook down")

    class Notifier:
        send_alert = staticmethod(fail_alert)

    monkeypatch.setattr(webhook_module, "get_notifier", lambda: Notifier())
    await server._process_event({"eventid": "unit", "src_ip": "8.8.8.8"})
    assert server.conn.closed
    assert server._build_base_event("unit")["hassh_md5"] == "h" * 32


@pytest.mark.asyncio
async def test_session_execution(monkeypatch) -> None:
    server = _server()
    session = CloudSentinelSession(server)

    class Chan:
        def __init__(self) -> None:
            self.writes: list[bytes] = []
            self.exits: list[int] = []
            self.fail = True

        def write(self, data: bytes) -> None:
            self.writes.append(data)

        def exit(self, status: int = 0) -> None:
            self.exits.append(status)
            if self.fail:
                raise OSError("closed")

    channel = Chan()
    session.connection_made(channel)  # type: ignore[arg-type]
    session.session_started()
    session.exec_command = "id"
    session.session_started()
    await asyncio.sleep(0)
    await session._run_exec("id")
    channel.fail = False
    await session._run_interactive("exit")
    session.connection_lost(None)
    assert channel.exits

    assert await session._execute("") == ""
    await session._execute("echo hello")
    await session._execute("bad 'quote")
    session.data_received("\r", None)
    await asyncio.sleep(0)
