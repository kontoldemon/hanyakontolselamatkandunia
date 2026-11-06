"""Cover admin shutdown closing the direct war-room Redis client."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


class DirectRedis:
    def __init__(self) -> None:
        self.closed = False
        self.hashes: dict[str, dict[str, str]] = {}
        self.values: dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    async def hset(self, key: str, mapping: dict | None = None, **_kwargs: object) -> None:
        self.hashes.setdefault(key, {}).update(mapping or {})

    async def expire(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, **_kwargs: object) -> None:
        self.values[key] = value

    async def delete(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def aclose(self) -> None:
        self.closed = True


def test_shutdown_closes_direct_redis(monkeypatch) -> None:
    fake = DirectRedis()
    monkeypatch.setattr(aioredis, "from_url", lambda *_args, **_kwargs: fake)
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    pipeline = EventPipeline(settings.redis)
    pipeline._redis = None
    with TestClient(create_admin_app(settings, pipeline)) as client:
        response = client.get("/war-room-state", headers={"Authorization": "Bearer test-token"})
        assert response.status_code == 200
    assert fake.closed
