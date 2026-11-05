"""Fifth batch: DNS, stream, stress, admin endpoints, and remaining helpers."""

from __future__ import annotations

import asyncio
import struct
import sys
import time

import pytest
from pydantic import SecretStr

from cloudsentinel.config import load_settings
from cloudsentinel.dns_honeypot import DNSHoneypot
from cloudsentinel.pipeline import EventPipeline
from cloudsentinel.sandbox import GVisorSandbox
from cloudsentinel.stream import LiveStream
from cloudsentinel.stress_test import StressTest
from cloudsentinel.threat_reporter import ThreatReport, generate_report_string
from cloudsentinel.validate_phase1 import http_json


def _dns_query(name: str = "example.com", txid: int = 0x1234) -> bytes:
    qname = b"".join(
        bytes([len(part)]) + part.encode("ascii")
        for part in name.split(".")
    ) + b"\x00"
    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    return header + qname + struct.pack("!HH", 1, 1)


@pytest.mark.asyncio
async def test_dns_query_and_cleanup() -> None:
    honeypot = DNSHoneypot(max_queries_per_ip=10, rate_window_seconds=0.01)
    events: list[dict] = []
    sent: list[tuple[bytes, tuple[str, int]]] = []
    honeypot.set_event_callback(events.append)

    class Transport:
        def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
            sent.append((data, addr))

    await honeypot._handle_query(_dns_query(), ("1.2.3.4", 1234), Transport())
    assert events[0]["domain"] == "example.com"
    assert sent and sent[0][1] == ("1.2.3.4", 1234)
    assert honeypot.stats["total_queries"] == 1

    await honeypot._handle_query(b"short", ("1.2.3.4", 1234), Transport())
    assert honeypot.stats["total_queries"] == 1

    honeypot._rate_limiter["9.9.9.9"] = [time.monotonic() - 1]
    cleanup = asyncio.create_task(honeypot._periodic_cleanup(interval=0.01))
    await asyncio.sleep(0.03)
    cleanup.cancel()
    try:
        await cleanup
    except asyncio.CancelledError:
        pass
    assert "9.9.9.9" not in honeypot._rate_limiter


@pytest.mark.asyncio
async def test_stream_start_stop() -> None:
    stream = LiveStream(host="127.0.0.1", port=0)
    await stream.start()
    assert stream._started is True
    await stream.stop()
    assert stream._started is False


@pytest.mark.asyncio
async def test_stress_run_with_fake_ssh(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeStdin:
        def __init__(self) -> None:
            self.data = b""

        def write(self, data: bytes) -> None:
            self.data += data

    class FakeStdout:
        async def read(self, _size: int) -> bytes:
            return b"ok\n"

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = FakeStdin()
            self.stdout = FakeStdout()

        async def __aenter__(self) -> FakeProcess:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    class FakeConnection:
        def create_process(self) -> FakeProcess:
            return FakeProcess()

        async def __aenter__(self) -> FakeConnection:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    def fake_connect(*_args: object, **_kwargs: object) -> FakeConnection:
        return FakeConnection()

    monkeypatch.setattr("asyncssh.connect", fake_connect)
    test = StressTest("127.0.0.1", 2222, 2, delay=0.0)
    report = await test.run()
    assert report["successful"] == 2
    assert report["failed"] == 0


def test_http_json_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

        def read(self) -> bytes:
            return b'{"ok": true, "value": 1}'

    monkeypatch.setattr(
        "cloudsentinel.validate_phase1.urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    assert http_json("http://example.invalid/healthz", token="token") == {
        "ok": True,
        "value": 1,
    }


@pytest.mark.asyncio
async def test_report_string() -> None:
    report = ThreatReport("session-1", "8.8.8.8", country="US", city="Test")
    text = await generate_report_string(report)
    assert "session-1" in text
    assert "8.8.8.8" in text


@pytest.mark.asyncio
async def test_gvisor_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cloudsentinel.sandbox.shutil.which", lambda _: "/usr/bin/runsc")
    calls: list[tuple[str, ...]] = []

    class FakeProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"ok", b""

    async def fake_exec(*args: str, **_kwargs: object) -> FakeProc:
        calls.append(args)
        return FakeProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    sandbox = GVisorSandbox()
    code, output = await sandbox.execute("whoami", "~")
    assert code == 0
    assert output == "ok"
    assert "--runtime" in calls[0]
    assert "runsc" in calls[0]


def test_mttb_main(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import cloudsentinel.mttb_benchmark as benchmark

    called: dict[str, object] = {}

    async def fake_run(args: object) -> dict:
        called["args"] = args
        return {"ok": True}

    def fake_write(report: dict, artifacts_dir: object) -> None:
        called["report"] = report
        called["artifacts"] = artifacts_dir

    monkeypatch.setattr(sys, "argv", ["bench", "--iterations", "1", "--artifacts-dir", str(tmp_path)])
    monkeypatch.setattr(benchmark, "run_benchmark", fake_run)
    monkeypatch.setattr(benchmark, "write_artifacts", fake_write)
    asyncio.run(benchmark.main())
    assert called["report"] == {"ok": True}
    assert called["artifacts"] == tmp_path


def test_admin_read_only_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from cloudsentinel.admin_api import create_admin_app

    monkeypatch.setenv("CLOUDSENTINEL_STRICT_TRUTH", "0")
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("unit-token")
    settings.clickhouse.enabled = False
    pipeline = EventPipeline(settings.redis)
    client = TestClient(create_admin_app(settings, pipeline))
    headers = {"Authorization": "Bearer unit-token"}

    assert client.get("/stats", headers=headers).status_code == 200
    assert client.get("/metrics/json", headers=headers).status_code == 200
    distribution = client.get("/attack-distribution", headers=headers)
    assert distribution.status_code == 200
    assert isinstance(distribution.json(), list)
    graph = client.get("/attack-graph", headers=headers)
    assert graph.status_code == 200
    assert graph.json()["nodes"]
    sessions = client.get("/sessions", headers=headers)
    assert sessions.status_code == 200
    assert sessions.json()["sessions"] == []
    events = client.get("/events?limit=5", headers=headers)
    assert events.status_code == 200
    assert events.json()["events"] == []
