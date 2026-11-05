"""Cover shell protocol branches and threat-reporter optional paths."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
import types
from pathlib import Path

import pytest

import cloudsentinel.threat_reporter as reporter
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.vfs import VirtualFileSystem


class FakeTransport:
    def __init__(self, reads: list[bytes] | None = None) -> None:
        self.reads = list(reads or [])
        self.writes: list[bytes] = []
        self.closed = False

    async def read(self, _size: int) -> bytes:
        return self.reads.pop(0) if self.reads else b""

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def close(self) -> None:
        self.closed = True


def _protocol(reads: list[bytes] | None = None) -> HoneyPotInteractiveProtocol:
    vfs = VirtualFileSystem()
    return HoneyPotInteractiveProtocol(
        FakeTransport(reads),
        vfs,
        session_id="unit-shell",
        ip="10.0.0.1",
    )


@pytest.mark.asyncio
async def test_shell_protocol(monkeypatch) -> None:
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    session = _protocol([b"id\n", b""])
    try:
        await session.run()
        assert session._tty_dir is not None
        assert session.transport.writes
    finally:
        shutil.rmtree(Path("var/lib/cloudsentinel/tty/unit-shell"), ignore_errors=True)

    session = _protocol()
    session._exec_command = "id"
    await session.run_exec()
    assert session.transport.closed
    shutil.rmtree(Path("var/lib/cloudsentinel/tty/unit-shell"), ignore_errors=True)


def test_shell_editing_and_dispatch() -> None:
    session = _protocol()
    session._handle_data(b"\x03")
    session._handle_data(b"\t")
    session._handle_data(b"ab\x7f\x08c\r")
    session._handle_data(b"|")
    session._handle_data(b">")
    session._handle_data(b"echo hello | cat")
    session._handle_data(b"cat < /tmp/missing")
    session._handle_data(b"nosuchcommand")
    session._handle_data(b"bad 'quote")
    session._handle_data(b"\x04")

    class FakeCommand:
        def handle_CTRL_C(self) -> None:
            self.interrupted = True

    command = FakeCommand()
    session.cmdstack.append(command)
    session._handle_data(b"\x03")
    assert command.interrupted

    session.fs.mkdir("/tmp")
    session._handle_cd(["/tmp"])
    assert session.cwd == "/tmp"
    session._handle_cd(["-"])
    assert session.cwd == "/root"
    session._handle_cd(["/missing"])
    session.cwd = "/"
    session.show_prompt()
    session.cwd = "/root/sub"
    session.show_prompt()

    session.starttime = time.time() - 90000
    assert "days" in session.uptime()
    session.starttime = time.time() - 7200
    assert ":" in session.uptime()
    session.starttime = time.time() - 120
    assert "min" in session.uptime()

    seen: list[dict] = []
    session._event_handler = seen.append
    session.emit_event({"eventid": "unit"})
    assert seen


class FakeRedis:
    def __init__(self) -> None:
        self.lists = {"cloudsentinel:session:s:commands": ["id", "whoami"]}
        self.values = {
            "cloudsentinel:session:s:ip": "8.8.8.8",
            "cloudsentinel:session:s:risk": "55",
            "soar:session:s:hassh": "h" * 32,
        }

    async def lrange(self, key: str, _start: int, _end: int) -> list[str]:
        return self.lists.get(key, [])

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def smembers(self, _key: str) -> set[str]:
        return {"T1110"}

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_threat_reporter_paths(monkeypatch) -> None:
    assert await reporter.fetch_session_data("empty", "") == reporter._empty_session_data("empty")

    fake_redis_module = types.ModuleType("redis.asyncio")
    fake_redis_module.from_url = lambda *_a, **_k: FakeRedis()
    monkeypatch.setitem(sys.modules, "redis.asyncio", fake_redis_module)
    data = await reporter.fetch_session_data("s", "redis://unit")
    assert data["attacker_ip"] == "8.8.8.8"
    assert data["mitre_techniques"] == ["T1110"]

    broken = FakeRedis()

    async def fail(_key: str) -> str | None:
        raise RuntimeError("redis down")

    broken.get = fail  # type: ignore[method-assign]
    fake_redis_module.from_url = lambda *_a, **_k: broken
    assert await reporter.fetch_session_data("s", "redis://unit") == reporter._empty_session_data("s")

    assert reporter._parse_json_response('```json\n{"summary":"x"}\n```', "m")["summary"] == "x"
    assert reporter._parse_json_response('```\n{"summary":"y"}\n```', "m")["summary"] == "y"
    assert reporter._parse_json_response("plain text", "m")["confidence"] == 0.2

    fake_litellm = types.ModuleType("litellm")

    async def success(**_kwargs: object) -> object:
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='{"summary":"ok"}'))]
        )

    fake_litellm.acompletion = success
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    assert (await reporter._call_litellm("prompt"))["summary"] == "ok"
    assert "ok" in await reporter._call_litellm_raw("prompt")
    assert "ok" in await reporter.chat_with_agent("hello", "context")

    async def fail_call(**_kwargs: object) -> object:
        raise RuntimeError("llm down")

    fake_litellm.acompletion = fail_call
    assert (await reporter._call_litellm("prompt"))["summary"] == "LLM analysis unavailable"
    assert "offline" in await reporter._call_litellm_raw("prompt")

    monkeypatch.setitem(sys.modules, "litellm", None)
    assert (await reporter._call_litellm("prompt"))["summary"] == "litellm not installed on sensor"
    assert "not installed" in await reporter._call_litellm_raw("prompt")

    no_commands = await reporter.generate_report("s")
    assert no_commands.summary.startswith("No command telemetry")
    assert "CLOUDSENTINEL AI THREAT REPORT" in await reporter.generate_report_string(no_commands)

    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
    fake_litellm.acompletion = success
    with_commands = await reporter.generate_report(
        "s",
        attacker_ip="10.0.0.1",
        mitre_techniques=["T1110"],
        commands=["id"],
        risk_score=50,
    )
    assert with_commands.summary == "ok"
    assert "T1110" in await reporter.generate_report_string(with_commands)

    await reporter.main()
