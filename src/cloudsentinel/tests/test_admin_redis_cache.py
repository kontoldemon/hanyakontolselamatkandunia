"""Cover admin hot-cache, war-room, and exposure cooldown with fake Redis."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.admin_api as admin_module
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.values: dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    async def hset(self, key: str, mapping: dict | None = None, **kwargs: object) -> None:
        self.hashes.setdefault(key, {}).update(mapping or kwargs)

    async def expire(self, _key: str, _ttl: int) -> None:
        return None

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, **_kwargs: object) -> None:
        self.values[key] = value

    async def delete(self, *_keys: str) -> None:
        return None

    async def aclose(self) -> None:
        return None


def _client(monkeypatch) -> tuple[TestClient, FakeRedis, dict[str, str]]:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    pipeline = EventPipeline(settings.redis)
    fake = FakeRedis()
    pipeline._redis = fake  # type: ignore[assignment]
    app = create_admin_app(settings, pipeline)
    return TestClient(app), fake, {"Authorization": "Bearer test-token"}


def test_cached_endpoints(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_WAR_ROOM_PERSISTENT_ONLINE", "1")
    client, fake, headers = _client(monkeypatch)
    assert client.get("/war-room-state", headers=headers).status_code == 200

    client.get("/sessions", headers=headers)
    assert client.get("/sessions", headers=headers).status_code == 200

    monkeypatch.setattr(
        admin_module,
        "_load_truth_summary_from_clickhouse",
        lambda _settings: {
            "total_events": 1,
            "unique_ips": 1,
            "unique_countries": 1,
            "active_sessions": 1,
            "total_connections": 1,
            "total_auth_failures": 0,
            "total_commands": 0,
            "unique_commands": 0,
            "total_blocks": 0,
            "blocked_ips_current": 0,
            "mttb_ms": 0.0,
            "avg_risk": 0.0,
            "block_rate": 0.0,
        },
    )
    client.get("/truth-summary", headers=headers)
    assert client.get("/truth-summary", headers=headers).status_code == 200

    client.get("/attack-distribution", headers=headers)
    assert client.get("/attack-distribution", headers=headers).status_code == 200
    client.get("/attack-graph", headers=headers)
    assert client.get("/attack-graph", headers=headers).status_code == 200
    assert fake.values


def test_exposure_cooldown(monkeypatch) -> None:
    client, fake, headers = _client(monkeypatch)
    fake.hashes[admin_module.EXPOSURE_STATE_REDIS_KEY] = {
        "provider": "iptables",
        "desired_enabled": "1",
        "effective_enabled": "1",
        "last_toggle_at": str(int(time.time() * 1000)),
    }
    response = client.post("/admin/exposure", headers=headers, json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["error"] == "cooldown_active"
