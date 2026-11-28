"""Eighth batch: secrets providers, Docker SDK, server lifecycle, admin endpoints."""

from __future__ import annotations

import asyncio
import time

import pytest
from pydantic import SecretStr

from cloudsentinel.config import RedisSettings, load_settings
from cloudsentinel.pipeline import EventEnvelope, EventPipeline
from cloudsentinel.sandbox import DockerSandbox
from cloudsentinel.server import CloudSentinelSSHServer, ConnectionLimiter
from cloudsentinel.stream import LiveStream






@pytest.mark.asyncio
async def test_docker_sdk_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("docker")
    from cloudsentinel.sandbox import DockerSDKSandbox

    class FakeContainer:
        def wait(self, timeout: int) -> dict:
            return {"StatusCode": 0}

        def logs(self) -> bytes:
            return b"ok"

        def kill(self) -> None:
            return None

    class FakeContainers:
        def run(self, *_args: object, **_kwargs: object) -> FakeContainer:
            return FakeContainer()

    class FakeClient:
        containers = FakeContainers()

    sandbox = DockerSDKSandbox()
    sandbox._client = FakeClient()
    code, output = await sandbox.execute("whoami", "~")
    assert code == 0
    assert output == "ok"


@pytest.mark.asyncio
async def test_sandbox_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_exec(*_args: object, **_kwargs: object):
        raise OSError("docker missing")

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    code, message = await DockerSandbox().execute("whoami", "~")
    assert code == 1
    assert "Sandbox error" in message


@pytest.mark.asyncio
async def test_ssh_server_lifecycle() -> None:
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

    class FakeConn:
        def __init__(self) -> None:
            self.closed = False

        def get_extra_info(self, name: str, default: object = None) -> object:
            if name == "peername":
                return ("1.2.3.4", 1234)
            return default

        def close(self) -> None:
            self.closed = True

    server = CloudSentinelSSHServer(
        settings=settings,
        pipeline=FakePipeline(),
        soar=FakeSoar(),
        hassh_dna=FakeHassh(),
        limiter=ConnectionLimiter(),
    )
    conn = FakeConn()
    server.connection_made(conn)  # type: ignore[arg-type]
    assert server.src_ip == "1.2.3.4"
    assert server.src_port == 1234
    await server._process_event(
        {
            "eventid": "cloudsentinel.command.input",
            "session": server.session_id,
            "src_ip": "1.2.3.4",
            "src_port": 1234,
            "input": "whoami",
            "timestamp": time.time(),
        }
    )
    server.connection_lost(None)
    await asyncio.sleep(0.02)
    assert server._accepted is False


@pytest.mark.asyncio
async def test_stream_emit_started() -> None:
    class FakeSio:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []

        async def emit(self, event: str, payload: dict) -> None:
            self.events.append((event, payload))

    stream = LiveStream()
    stream._sio = FakeSio()
    stream._started = True
    stream.emit({"eventid": "unit", "system": "hidden"})
    await asyncio.sleep(0)
    assert stream._buffer
    assert "system" not in stream._buffer[-1]
    assert stream._sio.events


def test_admin_health_metrics_and_block(monkeypatch: pytest.MonkeyPatch) -> None:
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

    assert client.get("/healthz").status_code == 200
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers=headers).status_code == 200
    assert client.get("/anomaly-stats", headers=headers).status_code == 200
    blocked = client.post(
        "/admin/block-ip",
        headers=headers,
        json={"ip": "not-an-ip"},
    )
    assert blocked.status_code == 400
    truth = client.get("/truth-summary", headers=headers)
    assert truth.status_code == 200
    war = client.get("/war-room-state", headers=headers)
    assert war.status_code == 200
