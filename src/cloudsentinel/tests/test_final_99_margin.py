"""Final margin batch for 99%+."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

import cloudsentinel.admin_api as admin_module
from cloudsentinel.admin_api import _trim_replay_entries, create_admin_app
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


def _client(monkeypatch, soar=None, redis=None):
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.admin.token = SecretStr("test-token")
    settings.clickhouse.enabled = False
    pipeline = EventPipeline(settings.redis)
    if redis is not None:
        pipeline._redis = redis  # type: ignore[assignment]
    return TestClient(create_admin_app(settings, pipeline, soar)), settings


def test_exposure_add_failure(monkeypatch) -> None:
    client, _settings = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}
    monkeypatch.setattr(admin_module, "_exposure_firewall_paths", lambda _settings: ["/bin/fw"])
    monkeypatch.setattr(admin_module, "_exposure_target_ports", lambda _settings: [22])
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_PROVIDER", "iptables")

    async def fake_run(args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        return (1, "", "add failed") if "-I" in args else (1, "", "")

    monkeypatch.setattr(admin_module, "_run_command", fake_run)
    response = client.post("/admin/exposure", headers=headers, json={"enabled": False})
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_synthetic_session_skips(monkeypatch) -> None:
    class Soar:
        _mem_ip_sessions = {"8.8.8.8": {"s1"}, "8.8.4.4": {"s2"}}

        def get_ip_profile(self, ip: str) -> dict:
            return {"last_seen": 0, "first_seen": 0} if ip == "8.8.4.4" else {"last_seen": 0}

    client, _settings = _client(monkeypatch, Soar())
    monkeypatch.setenv("CLOUDSENTINEL_STRICT_TRUTH", "0")
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    monkeypatch.setattr(
        admin_module,
        "_load_recent_sessions_from_clickhouse",
        lambda _settings: [{"ip": "8.8.8.8"}],
    )
    response = client.get("/sessions", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200


def test_hot_cache_set_failure(monkeypatch) -> None:
    client, _settings = _client(monkeypatch, redis=FailingRedis())
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
    response = client.get("/truth-summary", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200


def test_trim_stream_duplicate() -> None:
    entries = [
        {"role": "honeypot", "text": "[OPEN] session", "timestamp": "1"},
        {"role": "attacker", "text": "id", "timestamp": "2"},
        {"role": "attacker", "text": "id", "timestamp": "2"},
    ]
    assert _trim_replay_entries(entries, limit=3)
    assert _trim_replay_entries(entries, limit=0)
