"""Final exposure firewall failure and persist branches."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.admin_api as admin_module
from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import EventPipeline


class FailingRedis:
    async def hset(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("redis down")

    async def hgetall(self, _key: str) -> dict:
        return {}

    async def get(self, _key: str) -> None:
        return None

    async def set(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("redis down")

    async def expire(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def aclose(self) -> None:
        return None


def _client(monkeypatch, redis=None) -> TestClient:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    pipeline = EventPipeline(settings.redis)
    if redis is not None:
        pipeline._redis = redis  # type: ignore[assignment]
    monkeypatch.setattr(admin_module, "_exposure_firewall_paths", lambda _settings: ["/bin/fw"])
    monkeypatch.setattr(admin_module, "_exposure_target_ports", lambda _settings: [22])
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_PROVIDER", "iptables")
    return TestClient(create_admin_app(settings, pipeline))


def test_exposure_check_failures(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    async def check_fails(_args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        return 2, "", "check failed"

    monkeypatch.setattr(admin_module, "_run_command", check_fails)
    enabled = client.post("/admin/exposure", headers=headers, json={"enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["ok"] is False
    disabled = client.post("/admin/exposure", headers=headers, json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["ok"] is False


def test_exposure_persist_failure(monkeypatch) -> None:
    client = _client(monkeypatch, FailingRedis())
    headers = {"Authorization": "Bearer test-token"}

    async def apply(_args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        return (1, "", "") if "-C" in _args else (0, "", "")

    monkeypatch.setattr(admin_module, "_run_command", apply)
    response = client.post("/admin/exposure", headers=headers, json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["ok"] is True
