"""Seventh batch: server session, shell, CLI, validate, stress, pipeline, DNS."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

import pytest
from pydantic import SecretStr

from cloudsentinel import cli
from cloudsentinel.config import RedisSettings, load_settings
from cloudsentinel.dns_honeypot import DNSHoneypot
from cloudsentinel.pipeline import EventEnvelope, EventPipeline, LocalWAL
from cloudsentinel.server import (
    CloudSentinelSSHServer,
    CloudSentinelSession,
    ConnectionLimiter,
)
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.stress_test import StressTest
from cloudsentinel.threat_reporter import chat_with_agent
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
async def test_server_session_shell_methods() -> None:
    session = _session_with_fake_server()
    channel = FakeChannel()
    session.connection_made(channel)
    assert session.pty_requested("xterm", (80, 24, 0, 0), {}) is True
    assert session.shell_requested() is True
    assert session.exec_requested("whoami") is True
    assert session._resolve_command("whoami") is not None
    assert session._resolve_command("definitely-not-a-command") is None
    assert session._adapter_cwd() == "/root"
    session._handle_cd(["/tmp"])
    assert session._adapter_cwd() == "/tmp"
    session._handle_cd([])
    assert session.vfs.context.cwd == "~"
    session._handle_cd([".."])
    session._prompt()
    session._write("hello")
    assert session._detect_honeytoken_access("cat /root/.aws/credentials")
    session.data_received("whoami\r\n", None)
    await asyncio.sleep(0.05)
    assert b"root" in channel.output
    await session._run_exec("whoami")
    assert 0 in channel.exits
    await session._run_interactive("exit")
    session.connection_lost(None)
    await asyncio.sleep(0.01)
    await session.vfs.close()


@pytest.mark.asyncio
async def test_ssh_server_methods() -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )

    class FakePipeline:
        async def emit(self, _envelope: EventEnvelope) -> None:
            return None

    class FakeSoar:
        async def process_event(self, _session: str, _event: dict) -> dict:
            return {"cloudsentinel_soar_action": "none", "cloudsentinel_risk_score": 0}

    class FakeHassh:
        def record_sighting(self, *_args: object) -> None:
            return None

        def lookup(self, *_args: object) -> dict:
            return {}

    class FakeKey:
        def get_algorithm(self) -> bytes:
            return b"ssh-rsa"

    server = CloudSentinelSSHServer(
        settings=settings,
        pipeline=FakePipeline(),
        soar=FakeSoar(),
        hassh_dna=FakeHassh(),
        limiter=ConnectionLimiter(),
    )
    assert server.password_auth_supported() is True
    assert server.public_key_auth_supported() is True
    assert server.kbdint_auth_supported() is False
    assert server.connection_requested() is False
    assert server.server_requested() is False
    assert server.validate_public_key("root", FakeKey()) is False
    server.auth_completed()
    await asyncio.sleep(0.01)
    session = server.session_requested()
    assert isinstance(session, CloudSentinelSession)
    await session.vfs.close()


def test_shell_extra_paths() -> None:
    class Transport:
        def __init__(self) -> None:
            self.data = b""
            self.closed = False

        def write(self, data: bytes) -> None:
            self.data += data

        def close(self) -> None:
            self.closed = True

    transport = Transport()
    protocol = HoneyPotInteractiveProtocol(
        transport=transport,
        vfs=VirtualFileSystem.build_default(),
        username="root",
        hostname="unit-host",
        ip="8.8.8.8",
    )
    protocol._execute_single(b"definitely-not-a-command")
    assert protocol._exit_code == 127
    protocol._handle_cd(["/tmp"])
    assert protocol.cwd == "/tmp"
    protocol.show_prompt()
    protocol._send_motd()
    protocol.write_stdout(b"out")
    protocol.write_stderr(b"err")
    protocol.emit_event({"eventid": "unit"})
    protocol._execute_single(b"exit")
    assert protocol._closed is True
    assert transport.closed is True


@pytest.mark.asyncio
async def test_shell_run_paths() -> None:
    class Transport:
        def __init__(self) -> None:
            self.data = b""
            self.closed = False

        def write(self, data: bytes) -> None:
            self.data += data

        def close(self) -> None:
            self.closed = True

        async def read(self, _size: int) -> bytes:
            return b""

    transport = Transport()
    protocol = HoneyPotInteractiveProtocol(
        transport=transport,
        vfs=VirtualFileSystem.build_default(),
        username="root",
        hostname="unit-host",
        ip="8.8.8.8",
    )
    await protocol.run()
    assert protocol._closed is True


def test_cli_benchmark_and_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("typer")
    if not cli._HAS_CLI:
        pytest.skip("typer/rich not installed")

    class FakeSoar:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def process_event(self, _session: str, _event: dict) -> dict:
            return {"mttb_ms": 1.0}

    monkeypatch.setattr("cloudsentinel.soar.SOAREngine", FakeSoar)
    cli.benchmark(iterations=1, redis_url="")
    monkeypatch.setattr("cloudsentinel.validate_phase1.main", lambda: None)
    cli.validate(config="unit.yaml")


@pytest.mark.asyncio
async def test_validate_phase1_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import cloudsentinel.validate_phase1 as validate

    async def fake_tcp(_host: str, _port: int, timeout: float = 3.0) -> dict:
        return {"ok": True, "latency_ms": 1.0}

    captured: dict[str, object] = {}

    def fake_http(url: str, token: str = "", timeout: float = 5.0, allow_self_signed: bool = False) -> dict:
        return {
            "ok": True,
            "redis_connected": True,
            "clickhouse_ok": True,
            "stream_enabled": True,
        }

    def fake_write(report: dict, artifacts_dir: object) -> None:
        captured["report"] = report
        captured["artifacts"] = artifacts_dir

    monkeypatch.setattr(validate, "tcp_check", fake_tcp)
    monkeypatch.setattr(validate, "http_json", fake_http)
    monkeypatch.setattr(validate, "write_artifacts", fake_write)
    monkeypatch.setattr(
        sys,
        "argv",
        ["validate", "--host", "127.0.0.1", "--artifacts-dir", str(tmp_path)],
    )
    await validate.main()
    assert captured["report"]["overall_pass"] is True


@pytest.mark.asyncio
async def test_stress_main(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import cloudsentinel.stress_test as stress

    async def fake_run(_self: object) -> dict:
        return {
            "total_attempted": 1,
            "successful": 1,
            "failed": 0,
            "acceptance_pass": False,
        }

    monkeypatch.setattr(stress.StressTest, "run", fake_run)
    output = tmp_path / "stress.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "stress",
            "--host",
            "127.0.0.1",
            "--port",
            "2222",
            "--connections",
            "1",
            "--output",
            str(output),
        ],
    )
    await stress.main()
    assert output.exists()


@pytest.mark.asyncio
async def test_pipeline_drain_and_safe_publish() -> None:
    pipeline = EventPipeline(RedisSettings())

    class FakeRedis:
        async def xadd(self, *_args: object, **_kwargs: object) -> str:
            return "1-0"

    pipeline._redis = FakeRedis()  # type: ignore[assignment]
    pipeline._connected = True
    envelope = EventEnvelope(
        event_type="cloudsentinel.command.input",
        session_id="drain-1",
        src_ip="8.8.8.8",
        src_port=1,
        timestamp=time.time(),
        payload={"eventid": "cloudsentinel.command.input"},
    )
    pipeline._pending.append(envelope)
    await pipeline._drain_pending()
    assert pipeline.pending_count == 0

    class BrokenNats:
        async def publish(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("nats down")

    pipeline._nats = BrokenNats()
    await pipeline._publish_optional_safe(envelope)


@pytest.mark.asyncio
async def test_dns_start_and_protocol() -> None:
    honeypot = DNSHoneypot(host="127.0.0.1", port=0)
    await honeypot.start()
    try:
        assert honeypot._transport is not None
        protocol = DNSHoneypot.Protocol(honeypot)
        class Transport:
            def sendto(self, *_args: object) -> None:
                return None
        protocol.connection_made(Transport())  # type: ignore[arg-type]
        protocol.datagram_received(b"x", ("1.2.3.4", 1))
        await asyncio.sleep(0.01)
    finally:
        if honeypot._cleanup_task:
            honeypot._cleanup_task.cancel()
        if honeypot._transport:
            honeypot._transport.close()


@pytest.mark.asyncio
async def test_threat_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_raw(prompt: str) -> str:
        return f"answer:{prompt[:20]}"

    monkeypatch.setattr("cloudsentinel.threat_reporter._call_litellm_raw", fake_raw)
    answer = await chat_with_agent("hello", "context")
    assert answer.startswith("answer:")
