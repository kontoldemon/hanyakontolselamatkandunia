"""Tests for CloudSentinel Mobile Push Service and FastAPI mobile router."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import cloudsentinel.mobile_push as mobile_module
from cloudsentinel.api.routers.mobile import build_mobile_router

from cloudsentinel.admin_api import create_admin_app
from cloudsentinel.config import Settings
from cloudsentinel.mobile_push import MobilePushService
from cloudsentinel.pipeline import EventPipeline


def test_pairing_lifecycle_and_device_token_verification(tmp_path: Path) -> None:
    store = tmp_path / "mobile_devices.json"
    svc = MobilePushService(storage_path=store)

    challenge = svc.create_pairing_challenge(server_url="https://soc.example.com")
    assert len(challenge["pairingCode"]) == 6
    qr = json.loads(challenge["qrPayload"])
    assert qr["serverUrl"] == "https://soc.example.com"
    assert qr["pairingCode"] == challenge["pairingCode"]

    # Pairing with valid code succeeds once
    paired = svc.pair_device(
        pairing_code=challenge["pairingCode"],
        device_name="Pixel 9 Pro",
        fcm_token="fcm_test_token_123",
    )
    assert paired is not None
    assert paired["deviceToken"].startswith("cs_mob_")
    assert paired["deviceName"] == "Pixel 9 Pro"

    # Reusing the same pairing code fails (one-time use)
    assert svc.pair_device(challenge["pairingCode"], "Pixel 9 Pro") is None

    # Token verification succeeds and rejects bad tokens
    verified = svc.verify_device_token(paired["deviceToken"])
    assert verified is not None
    assert verified.device_id == paired["deviceId"]
    assert svc.verify_device_token("cs_mob_invalid") is None
    assert svc.verify_device_token("bad-token") is None

    # Persistence across reload
    reloaded = MobilePushService(storage_path=store)
    assert len(reloaded.list_devices()) == 1
    assert reloaded.verify_device_token(paired["deviceToken"]) is not None

    # Revocation removes device and invalidates token
    assert reloaded.revoke_device(paired["deviceId"]) is True
    assert reloaded.verify_device_token(paired["deviceToken"]) is None
    assert reloaded.revoke_device("nonexistent") is False


def test_alert_policy_filtering_and_cooldown(tmp_path: Path) -> None:
    svc = MobilePushService(storage_path=tmp_path / "mobile.json")
    challenge = svc.create_pairing_challenge("http://127.0.0.1:8080")
    svc.pair_device(challenge["pairingCode"], "Galaxy S24", fcm_token="fcm_abc")

    svc.update_policy({"minRiskScore": 75, "cooldownSeconds": 120, "enabled": True})

    # Below threshold -> skipped
    low = asyncio.run(svc.dispatch_alert({"ip": "1.2.3.4", "risk_score": 40, "event_type": "COMMAND_EXEC"}))
    assert low["skipped"] is True

    # Above threshold -> dispatched (local_sync_only without FCM env vars)
    high = asyncio.run(svc.dispatch_alert({"ip": "1.2.3.4", "risk_score": 88, "event_type": "COMMAND_EXEC"}))
    assert high["ok"] is True
    assert high["dispatched"] == 1
    assert len(svc.get_recent_alerts()) == 1

    # Same IP within cooldown -> skipped
    dup = asyncio.run(svc.dispatch_alert({"ip": "1.2.3.4", "risk_score": 95, "event_type": "COMMAND_EXEC"}))
    assert dup["skipped"] is True

    # Forced test alert bypasses cooldown
    forced = asyncio.run(svc.dispatch_alert({"ip": "1.2.3.4", "risk_score": 95}, force=True))
    assert forced["dispatched"] == 1
    assert len(svc.get_recent_alerts()) == 2


def test_mobile_router_endpoints_end_to_end(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_MOBILE_STATE_PATH", str(tmp_path / "api_mobile.json"))
    settings = Settings()
    settings.admin.enabled = True
    settings.admin.token = "test-admin-secret"
    pipeline = EventPipeline(settings)
    app = create_admin_app(settings, pipeline)
    client = TestClient(app)

    admin_headers = {"Authorization": "Bearer test-admin-secret"}

    # Unauthenticated admin call rejected
    assert client.get("/mobile/config").status_code == 401

    # Fetch config
    cfg_resp = client.get("/mobile/config", headers=admin_headers)
    assert cfg_resp.status_code == 200
    assert cfg_resp.json()["ok"] is True

    # Generate pairing token
    pair_tok = client.post(
        "/mobile/pairing-token",
        headers=admin_headers,
        json={"serverUrl": "http://192.168.1.50:8080"},
    )
    assert pair_tok.status_code == 200
    code = pair_tok.json()["pairingCode"]
    pairing_token = pair_tok.json()["pairingToken"]

    # Android pairs using code + token
    pair_resp = client.post(
        "/mobile/pair",
        json={
            "pairingCode": code,
            "pairingToken": pairing_token,
            "deviceName": "OnePlus 12",
            "fcmToken": "fcm_xyz",
        },
    )
    assert pair_resp.status_code == 200
    device_token = pair_resp.json()["deviceToken"]
    device_id = pair_resp.json()["deviceId"]
    device_headers = {"Authorization": f"Bearer {device_token}"}

    # Trigger test alert from web settings
    test_resp = client.post("/mobile/test-alert", headers=admin_headers, json={})
    assert test_resp.status_code == 200
    assert test_resp.json()["dispatched"] == 1

    # Android fetches alerts with device token
    alerts_resp = client.get("/mobile/alerts", headers=device_headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["ip"] == "test-alert"

    # Refresh FCM token
    fcm_resp = client.post("/mobile/fcm-token", headers=device_headers, json={"fcmToken": "fcm_new_999"})
    assert fcm_resp.status_code == 200

    # Revoke device
    del_resp = client.delete(f"/mobile/devices/{device_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    # Revoked token can no longer fetch alerts
    assert client.get("/mobile/alerts", headers=device_headers).status_code == 401


def test_mobile_router_error_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_MOBILE_STATE_PATH", str(tmp_path / "api_errors.json"))
    settings = Settings()
    settings.admin.enabled = True
    settings.admin.token = "test-admin-secret"
    client = TestClient(create_admin_app(settings, EventPipeline(settings)))

    admin_headers = {"Authorization": "Bearer test-admin-secret"}
    assert client.get("/mobile/alerts").status_code == 401
    assert client.get("/mobile/alerts", headers={"Authorization": "Bearer bad"}).status_code == 401
    assert client.post("/mobile/pair", json={}).status_code == 400
    assert client.post("/mobile/pair", json={"pairingCode": "000000"}).status_code == 400
    assert client.post(
        "/mobile/pair", json={"pairingCode": "000000", "pairingToken": "bad"}
    ).status_code == 401
    assert client.delete("/mobile/devices/missing", headers=admin_headers).status_code == 404

    pairing = client.post("/mobile/pairing-token", headers=admin_headers, json={})
    assert pairing.status_code == 200
    paired = client.post(
        "/mobile/pair",
        json={
            "pairingCode": pairing.json()["pairingCode"],
            "pairingToken": pairing.json()["pairingToken"],
            "deviceName": "Test",
        },
    )
    device_headers = {"Authorization": f"Bearer {paired.json()['deviceToken']}"}
    assert client.post("/mobile/fcm-token", headers=device_headers, json={}).status_code == 400
    assert client.post("/mobile/block-ip", headers=device_headers, json={}).status_code == 400
    updated = client.post("/mobile/config", headers=admin_headers, json={"minRiskScore": 50})
    assert updated.status_code == 200


def test_mobile_fcm_dispatch_paths(tmp_path: Path, monkeypatch) -> None:
    svc = MobilePushService(storage_path=tmp_path / "fcm.json")
    pairing = svc.create_pairing_challenge("http://127.0.0.1:8080")
    paired = svc.pair_device(pairing["pairingCode"], "Pixel", fcm_token="fcm_token")
    assert paired is not None
    monkeypatch.setenv("CLOUDSENTINEL_FCM_PROJECT_ID", "project")
    monkeypatch.setenv("CLOUDSENTINEL_FCM_ACCESS_TOKEN", "bearer")

    class OkClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(200)

    monkeypatch.setattr("cloudsentinel.mobile_push.httpx.AsyncClient", OkClient)
    result = asyncio.run(svc.dispatch_alert({"ip": "1.2.3.4", "risk_score": 90}, force=True))
    assert result["mode"] == "fcm_v1"
    assert result["dispatched"] == 1

    class BrokenClient(OkClient):
        async def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            raise RuntimeError("fcm down")

    monkeypatch.setattr("cloudsentinel.mobile_push.httpx.AsyncClient", BrokenClient)
    result = asyncio.run(svc.dispatch_alert({"ip": "1.2.3.5", "risk_score": 90}, force=True))
    assert result["mode"] == "fcm_v1"
    assert result["dispatched"] == 0

    assert svc.update_fcm_token("missing", "token") is False
    assert svc.get_recent_alerts(limit=0)



def test_mobile_service_storage_and_policy_edges(tmp_path: Path, monkeypatch) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not-json", encoding="utf-8")
    assert MobilePushService(storage_path=broken).list_devices() == []

    storage_dir = tmp_path / "storage-dir"
    storage_dir.mkdir()
    failing = MobilePushService(storage_path=storage_dir)
    failing.update_policy({"minRiskScore": 60})

    clock = [1000.0]
    monkeypatch.setattr("cloudsentinel.mobile_push.time.time", lambda: clock[0])
    svc = MobilePushService(storage_path=tmp_path / "expired.json")
    challenge = svc.create_pairing_challenge("http://127.0.0.1:8080")
    clock[0] += 400
    assert svc.pair_device(challenge["pairingCode"], "Late Device") is None

    for index in range(21):
        code = svc.create_pairing_challenge("http://127.0.0.1:8080")["pairingCode"]
        assert svc.pair_device(code, f"Device {index}") is not None
    assert len(svc.list_devices()) == 20

    svc.update_policy(
        {
            "enabled": True,
            "notifyBruteForce": False,
            "notifyCommandExec": False,
            "notifySoarBlock": False,
            "minRiskScore": 0,
        }
    )
    assert svc._should_notify("AUTH_FAILED", 90, "", False) is False
    assert svc._should_notify("COMMAND_EXEC", 90, "", False) is False
    assert svc._should_notify("SOAR_BLOCK", 90, "", False) is False
    svc.update_policy({"enabled": False})
    assert svc._should_notify("OTHER", 90, "", False) is False


def test_mobile_fcm_no_token_and_non_200(tmp_path: Path, monkeypatch) -> None:
    svc = MobilePushService(storage_path=tmp_path / "fcm-errors.json")
    code = svc.create_pairing_challenge("http://127.0.0.1:8080")["pairingCode"]
    svc.pair_device(code, "No FCM")
    monkeypatch.setenv("CLOUDSENTINEL_FCM_PROJECT_ID", "project")
    monkeypatch.setenv("CLOUDSENTINEL_FCM_ACCESS_TOKEN", "bearer")

    class Non200Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(500)

    monkeypatch.setattr("cloudsentinel.mobile_push.httpx.AsyncClient", Non200Client)
    result = asyncio.run(svc.dispatch_alert({"ip": "1.2.3.6", "risk_score": 90}, force=True))
    assert result["mode"] == "fcm_v1"
    assert result["dispatched"] == 0


def test_mobile_router_block_ip_endpoint(tmp_path: Path, monkeypatch) -> None:
    import cloudsentinel.threat_reporter as threat_reporter

    async def offline_agent(*_args: object, **_kwargs: object) -> str:
        return "I am currently offline or cannot reach the LLM provider."

    monkeypatch.setattr(threat_reporter, "chat_with_agent", offline_agent)
    settings = Settings()
    svc = MobilePushService(storage_path=tmp_path / "block.json")
    code = svc.create_pairing_challenge("http://127.0.0.1:8080")["pairingCode"]
    paired = svc.pair_device(code, "Blocker")
    assert paired is not None

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(build_mobile_router(settings, lambda: True, svc, block_handler))
    client = TestClient(app)
    response = client.post(
        "/mobile/block-ip",
        headers={"Authorization": f"Bearer {paired['deviceToken']}"},
        json={"ip": "8.8.8.8"},
    )
    assert response.status_code == 200
    assert response.json()["blocked"] == "8.8.8.8"

    # Test dashboard, exposure, sessions, and ai-copilot endpoints
    dash_res = client.get("/mobile/dashboard", headers={"Authorization": f"Bearer {paired['deviceToken']}"})
    assert dash_res.status_code == 200
    assert dash_res.json()["sensor_status"] == "OFFLINE"
    assert dash_res.json()["mttb_seconds"] >= 0
    assert dash_res.json()["active_attackers_count"] >= 0
    assert "ingress_exposure" in dash_res.json()

    exp_res = client.post(
        "/mobile/exposure",
        headers={"Authorization": f"Bearer {paired['deviceToken']}"},
        json={"enabled": False},
    )
    assert exp_res.status_code == 200
    assert exp_res.json()["enabled"] is False

    sess_res = client.get("/mobile/sessions", headers={"Authorization": f"Bearer {paired['deviceToken']}"})
    assert sess_res.status_code == 200
    assert sess_res.json()["sessions"] == []

    copilot_res = client.post(
        "/mobile/ai-copilot",
        headers={"Authorization": f"Bearer {paired['deviceToken']}"},
        json={"prompt": "Explain honeypot killswitch"},
    )
    assert copilot_res.status_code == 200
    assert copilot_res.json()["ok"] is False
    assert "error" in copilot_res.json()


def test_mobile_pairing_requires_token_and_rate_limits(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_MOBILE_STATE_PATH", str(tmp_path / "pair-rate.json"))
    settings = Settings()
    settings.admin.enabled = True
    settings.admin.token = "test-admin-secret"
    settings.honeypot.hostname = ""
    settings.admin.host = "0.0.0.0"
    client = TestClient(create_admin_app(settings, EventPipeline(settings)))
    headers = {"Authorization": "Bearer test-admin-secret"}

    no_url = client.post("/mobile/pairing-token", headers=headers, json={})
    assert no_url.status_code == 400

    generated = client.post(
        "/mobile/pairing-token",
        headers=headers,
        json={"serverUrl": "https://soc.example.com"},
    )
    assert generated.status_code == 200
    code = generated.json()["pairingCode"]
    token = generated.json()["pairingToken"]
    assert client.post("/mobile/pair", json={"pairingCode": code}).status_code == 400

    for _ in range(9):
        response = client.post(
            "/mobile/pair",
            json={"pairingCode": "000000", "pairingToken": "wrong"},
        )
        assert response.status_code == 401
    limited = client.post(
        "/mobile/pair",
        json={"pairingCode": "000000", "pairingToken": "wrong"},
    )
    assert limited.status_code == 429


def test_mobile_state_is_shared_between_processes(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "shared.json"
    first = MobilePushService(storage_path=state)
    challenge = first.create_pairing_challenge("https://soc.example.com")
    paired = first.pair_device(
        challenge["pairingCode"],
        "Shared Device",
        pairing_token=challenge["pairingToken"],
    )
    assert paired is not None

    second = MobilePushService(storage_path=state)
    assert len(second.list_devices()) == 1
    asyncio.run(second.dispatch_alert({"ip": "9.9.9.9", "risk_score": 91}, force=True))

    third = MobilePushService(storage_path=state)
    alerts = third.get_recent_alerts()
    assert alerts and alerts[0]["ip"] == "9.9.9.9"


def test_sensor_dispatches_to_paired_mobile(tmp_path: Path, monkeypatch) -> None:
    import cloudsentinel.sensor.ssh as sensor_ssh

    state = tmp_path / "sensor-shared.json"
    monkeypatch.setenv("CLOUDSENTINEL_MOBILE_STATE_PATH", str(state))
    service = MobilePushService(storage_path=state)
    challenge = service.create_pairing_challenge("https://soc.example.com")
    assert service.pair_device(
        challenge["pairingCode"],
        "Sensor Device",
        pairing_token=challenge["pairingToken"],
    )
    monkeypatch.setattr(sensor_ssh, "_mobile_service", service)
    asyncio.run(sensor_ssh._dispatch_mobile_alert({"ip": "7.7.7.7", "risk_score": 92}))
    assert any(alert["ip"] == "7.7.7.7" for alert in service.get_recent_alerts())


def _paired_mobile_service(tmp_path: Path) -> tuple[MobilePushService, dict[str, str]]:
    svc = MobilePushService(storage_path=tmp_path / "mobile.json")
    challenge = svc.create_pairing_challenge("http://127.0.0.1:8080")
    paired = svc.pair_device(challenge["pairingCode"], "Test Phone")
    assert paired is not None
    return svc, {"Authorization": f"Bearer {paired['deviceToken']}"}


def test_mobile_dashboard_uses_live_metrics_and_exposure(tmp_path: Path) -> None:
    settings = Settings()
    settings.clickhouse.enabled = False
    svc, headers = _paired_mobile_service(tmp_path)

    class Pipe:
        connected = True

    class Soar:
        mttb_ms = 1200.0
        _mem_blocked_ips = {"8.8.8.8"}
        _mem_ip_techniques = {"8.8.8.8": {"T1059"}}
        _mem_ip_last_seen = {"8.8.8.8": __import__("time").time()}

    async def load_state() -> dict:
        return {"effective_enabled": False, "provider": "azure-nsg"}

    persisted: dict = {}

    async def persist(state: dict) -> None:
        persisted.update(state)

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(
        build_mobile_router(
            settings,
            lambda: True,
            svc,
            block_handler,
            load_exposure_state=load_state,
            persist_exposure_state=persist,
            exposure_provider=lambda: "azure-nsg",
            soar=Soar(),
            pipeline=Pipe(),
        )
    )
    client = TestClient(app)
    asyncio.run(
        svc.dispatch_alert(
            {
                "ip": "1.2.3.4",
                "country": "Testland",
                "risk_score": 88,
                "mitre_id": "T1059",
                "event_type": "COMMAND_EXEC",
            },
            force=True,
        )
    )

    dashboard = client.get("/mobile/dashboard", headers=headers).json()
    assert dashboard["sensor_status"] == "ONLINE"
    assert isinstance(dashboard["events_total"], int)
    assert dashboard["mttb_seconds"] == 1.2
    assert dashboard["blocked_ips_count"] >= 1
    assert dashboard["mitre_count"] == 1
    assert dashboard["top_threat_origin"] == "Testland"
    assert dashboard["active_attackers_count"] == 1
    assert dashboard["ingress_exposure"]["enabled"] is False

    exposure = client.post("/mobile/exposure", headers=headers, json={"enabled": False}).json()
    assert exposure["enabled"] is False
    assert persisted["effective_enabled"] is False
    assert persisted["provider"] == "azure-nsg"

    sessions = client.get("/mobile/sessions", headers=headers).json()
    assert sessions["sessions"][0]["mitre_techniques"] == ["T1059"]
    assert sessions["sessions"][0]["country"] == "Testland"


def test_mobile_policy_and_runtime_controls(tmp_path: Path) -> None:
    settings = Settings()
    settings.clickhouse.enabled = False
    svc, headers = _paired_mobile_service(tmp_path)

    class Soar:
        firewall_dry_run = True

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(
        build_mobile_router(settings, lambda: True, svc, block_handler, soar=Soar())
    )
    client = TestClient(app)

    policy = client.post(
        "/mobile/policy",
        headers=headers,
        json={"enabled": False, "minRiskScore": 55, "cooldownSeconds": 30},
    ).json()
    assert policy["ok"] is True
    assert policy["policy"]["enabled"] is False
    assert policy["policy"]["minRiskScore"] == 55

    controls = client.post(
        "/mobile/runtime-controls",
        headers=headers,
        json={"deception_level": "listener", "soar_dry_run": False, "hassh_action": "drop"},
    ).json()
    assert controls["ok"] is True
    assert settings.deception.level == "listener"
    assert settings.soar.firewall_dry_run is False
    assert settings.deception.hassh_action == "drop"
    assert controls["deception_level"] == "listener"
    assert controls["soar_dry_run"] is False
    assert controls["hassh_action"] == "drop"

    assert client.post(
        "/mobile/runtime-controls", headers=headers, json={"deception_level": "off"}
    ).status_code == 400
    assert client.post(
        "/mobile/runtime-controls", headers=headers, json={"hassh_action": "block"}
    ).status_code == 400


def test_mobile_exposure_uses_firewall_callback(tmp_path: Path) -> None:
    settings = Settings()
    settings.clickhouse.enabled = False
    svc, headers = _paired_mobile_service(tmp_path)
    calls: list[bool] = []
    async def toggle(enabled: bool) -> dict:
        calls.append(enabled)
        return {
            "ok": True,
            "enabled": enabled,
            "paused": not enabled,
            "provider": "iptables",
            "actions": [{"port": 2222, "action": "paused", "ok": True}],
        }

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(
        build_mobile_router(
            settings,
            lambda: True,
            svc,
            block_handler,
            toggle_exposure=toggle,
        )
    )
    body = TestClient(app).post("/mobile/exposure", headers=headers, json={"enabled": False}).json()

    assert calls == [False]
    assert body["ok"] is True
    assert body["enabled"] is False
    assert body["provider"] == "iptables"
    assert body["deviceId"]
    assert body["actions"][0]["port"] == 2222


def test_mobile_exposure_reports_firewall_failure(tmp_path: Path) -> None:
    settings = Settings()
    settings.clickhouse.enabled = False
    svc, headers = _paired_mobile_service(tmp_path)

    async def failed_toggle(_enabled: bool) -> dict:
        return {
            "ok": False,
            "enabled": True,
            "paused": False,
            "provider": "iptables",
            "error": "permission denied",
            "actions": [],
        }

    async def broken_toggle(_enabled: bool) -> dict:
        raise RuntimeError("iptables missing")

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(
        build_mobile_router(settings, lambda: True, svc, block_handler, toggle_exposure=failed_toggle)
    )
    body = TestClient(app).post("/mobile/exposure", headers=headers, json={"enabled": True}).json()
    assert body["ok"] is False
    assert "failed" in body["message"].lower()

    app = FastAPI()
    app.include_router(
        build_mobile_router(settings, lambda: True, svc, block_handler, toggle_exposure=broken_toggle)
    )
    response = TestClient(app).post("/mobile/exposure", headers=headers, json={"enabled": True})
    assert response.status_code == 503


def test_mobile_sessions_use_clickhouse_rows(tmp_path: Path, monkeypatch) -> None:
    import cloudsentinel.api.queries as queries

    settings = Settings()
    settings.clickhouse.enabled = True
    svc, headers = _paired_mobile_service(tmp_path)
    monkeypatch.setattr(
        queries,
        "_load_recent_sessions_from_clickhouse",
        lambda _settings, limit=20: [
            {
                "id": "sess-1",
                "ip": "9.9.9.9",
                "country": "Malaysia",
                "city": "Kuala Lumpur",
                "isp": "ISP",
                "fingerprint": "abcdef0123456789abcdef0123456789",
                "riskScore": 77,
                "duration": "1m 2s",
                "mitreTechniques": ["T1110"],
                "input": ["id", "whoami"],
                "blockEffective": True,
                "lastSeenEpochMs": 123456,
            }
        ],
    )

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(build_mobile_router(settings, lambda: True, svc, block_handler))
    body = TestClient(app).get("/mobile/sessions", headers=headers).json()
    assert body["sessions"][0]["risk_score"] == 77
    assert body["sessions"][0]["hassh"] == "abcdef0123456789abcdef0123456789"
    assert body["sessions"][0]["commands"] == ["id", "whoami"]
    assert body["sessions"][0]["blocked"] is True
    assert body["sessions"][0]["timestamp_ms"] == 123456


def test_mobile_copilot_success_error_and_failure(tmp_path: Path, monkeypatch) -> None:
    import cloudsentinel.threat_reporter as threat_reporter

    settings = Settings()
    svc, headers = _paired_mobile_service(tmp_path)

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(build_mobile_router(settings, lambda: True, svc, block_handler))
    client = TestClient(app)

    assert client.post("/mobile/ai-copilot", headers=headers, json={}).status_code == 400

    async def ok_agent(*_args: object, **_kwargs: object) -> str:
        return "Use the killswitch in Settings."

    monkeypatch.setattr(threat_reporter, "chat_with_agent", ok_agent)
    ok_body = client.post(
        "/mobile/ai-copilot", headers=headers, json={"prompt": "killswitch?"}
    ).json()
    assert ok_body["ok"] is True
    assert "killswitch" in ok_body["response"].lower()

    async def broken_agent(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("llm down")

    monkeypatch.setattr(threat_reporter, "chat_with_agent", broken_agent)
    failed = client.post(
        "/mobile/ai-copilot", headers=headers, json={"prompt": "status?"}
    ).json()
    assert failed["ok"] is False

    async def offline_agent(*_args: object, **_kwargs: object) -> str:
        return "I am currently offline or cannot reach the LLM provider."

    monkeypatch.setattr(threat_reporter, "chat_with_agent", offline_agent)
    offline = client.post(
        "/mobile/ai-copilot", headers=headers, json={"prompt": "status?"}
    ).json()
    assert offline["ok"] is False


def test_mobile_sessions_fall_back_to_alerts_on_clickhouse_error(tmp_path: Path, monkeypatch) -> None:
    import cloudsentinel.api.queries as queries

    settings = Settings()
    settings.clickhouse.enabled = True
    svc, headers = _paired_mobile_service(tmp_path)

    def broken_loader(_settings, limit=20):
        raise RuntimeError("clickhouse down")

    monkeypatch.setattr(queries, "_load_recent_sessions_from_clickhouse", broken_loader)
    asyncio.run(
        svc.dispatch_alert(
            {
                "id": "alert-1",
                "ip": "1.2.3.4",
                "country": "Malaysia",
                "riskScore": 88,
                "risk_score": 88,
                "eventType": "TEST",
                "summary": "fallback",
                "timestampMs": 123456,
            },
            force=True,
        )
    )
    app = FastAPI()
    app.include_router(
        build_mobile_router(settings, lambda: True, svc, lambda body: {"blocked": body["ip"]})
    )
    body = TestClient(app).get("/mobile/sessions", headers=headers).json()
    assert body["sessions"][0]["ip"] == "1.2.3.4"
    assert body["sessions"][0]["risk_score"] == 88


def test_mobile_alert_state_round_trip_preserves_details(tmp_path: Path) -> None:
    store = tmp_path / "round-trip.json"
    svc = MobilePushService(storage_path=store)
    asyncio.run(
        svc.dispatch_alert(
            {
                "ip": "4.3.2.1",
                "country": "Testland",
                "risk_score": 91,
                "mitre_id": "T1110",
                "event_type": "COMMAND_EXEC",
            },
            force=True,
        )
    )
    reloaded = MobilePushService(storage_path=store)
    alert = reloaded.get_recent_alerts(limit=1)[0]
    assert alert["riskScore"] == 91
    assert alert["eventType"] == "COMMAND_EXEC"
    assert alert["mitreId"] == "T1110"
    assert alert["timestampMs"] > 0


def test_mobile_dashboard_survives_state_store_errors(tmp_path: Path) -> None:
    settings = Settings()
    settings.clickhouse.enabled = False
    svc, headers = _paired_mobile_service(tmp_path)

    async def broken_state() -> dict:
        raise RuntimeError("state store down")

    async def broken_persist(_state: dict) -> None:
        raise RuntimeError("state store down")

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(
        build_mobile_router(
            settings,
            lambda: True,
            svc,
            block_handler,
            load_exposure_state=broken_state,
            persist_exposure_state=broken_persist,
            exposure_provider=lambda: "azure-nsg",
        )
    )
    client = TestClient(app)
    assert client.get("/mobile/dashboard", headers=headers).status_code == 200
    exposure = client.post("/mobile/exposure", headers=headers, json={"enabled": True})
    assert exposure.status_code == 200
    assert exposure.json()["enabled"] is True


def test_mobile_sessions_fall_back_when_clickhouse_fails(tmp_path: Path, monkeypatch) -> None:
    import cloudsentinel.api.queries as queries

    settings = Settings()
    settings.clickhouse.enabled = True
    svc, headers = _paired_mobile_service(tmp_path)

    def broken_loader(_settings, limit=20):
        raise RuntimeError("clickhouse down")

    monkeypatch.setattr(queries, "_load_recent_sessions_from_clickhouse", broken_loader)

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(build_mobile_router(settings, lambda: True, svc, block_handler))
    body = TestClient(app).get("/mobile/sessions", headers=headers).json()
    assert body["sessions"] == []


def test_mobile_pair_attempts_expire(tmp_path: Path, monkeypatch) -> None:
    settings = Settings()
    svc = MobilePushService(storage_path=tmp_path / "pair-window.json")

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(build_mobile_router(settings, lambda: True, svc, block_handler))
    client = TestClient(app)
    clock = [1000.0]
    monkeypatch.setattr("cloudsentinel.api.routers.mobile.time.monotonic", lambda: clock[0])

    first = client.post("/mobile/pair", json={"pairingCode": "x", "pairingToken": "y"})
    assert first.status_code in (400, 401)
    clock[0] += 61
    second = client.post("/mobile/pair", json={"pairingCode": "x", "pairingToken": "y"})
    assert second.status_code in (400, 401)


def test_mobile_dashboard_uses_metrics_mttb_fallback(tmp_path: Path) -> None:
    from cloudsentinel.metrics import get_metrics

    settings = Settings()
    settings.clickhouse.enabled = False
    svc, headers = _paired_mobile_service(tmp_path)

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(build_mobile_router(settings, lambda: True, svc, block_handler))

    metrics = get_metrics()
    previous = metrics.mttb_ms
    metrics.set_mttb(250.0)
    try:
        dashboard = TestClient(app).get("/mobile/dashboard", headers=headers).json()
    finally:
        metrics.set_mttb(previous)
    assert dashboard["mttb_seconds"] == 0.25


def test_mobile_state_load_skips_invalid_entries(tmp_path: Path) -> None:
    store = tmp_path / "bad-state.json"
    store.write_text(
        json.dumps(
            {
                "devices": [{"device_id": "good", "device_name": "Good"}, {"nope": 1}],
                "challenges": [{"code": "123456", "token": "t"}, {"token": "no-code"}],
                "recent_alerts": [{"id": "a1", "ip": "1.2.3.4"}, {"ip": "no-id"}],
            }
        ),
        encoding="utf-8",
    )
    svc = MobilePushService(storage_path=store)
    assert [device["deviceId"] for device in svc.list_devices()] == ["good"]
    assert [alert["id"] for alert in svc.get_recent_alerts()] == ["a1"]


def test_mobile_save_survives_chmod_error(tmp_path: Path, monkeypatch) -> None:
    svc = MobilePushService(storage_path=tmp_path / "save.json")

    def deny_chmod(*_args, **_kwargs) -> None:
        raise OSError("denied")

    monkeypatch.setattr("pathlib.Path.chmod", deny_chmod)
    svc.update_policy({"minRiskScore": 42})
    assert svc.get_policy().min_risk_score == 42


def test_mobile_dashboard_events_total_survives_restart(tmp_path: Path, monkeypatch) -> None:
    settings = Settings()
    settings.clickhouse.enabled = True
    svc, headers = _paired_mobile_service(tmp_path)
    calls: list[int] = []

    async def fake_summary(_settings) -> dict:
        calls.append(1)
        return {"total_events": 9001}

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    monkeypatch.setattr(
        "cloudsentinel.api.routers.mobile.load_truth_summary_async",
        fake_summary,
    )
    app = FastAPI()
    app.include_router(build_mobile_router(settings, lambda: True, svc, block_handler))
    client = TestClient(app)
    first = client.get("/mobile/dashboard", headers=headers).json()
    second = client.get("/mobile/dashboard", headers=headers).json()
    assert first["events_total"] >= 9001
    assert second["events_total"] >= 9001
    assert len(calls) == 1


def test_mobile_dashboard_uses_clickhouse_mttb_fallback(tmp_path: Path, monkeypatch) -> None:
    from cloudsentinel.metrics import get_metrics

    settings = Settings()
    settings.clickhouse.enabled = False
    svc, headers = _paired_mobile_service(tmp_path)

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    async def fake_latest_mttb(_settings) -> float:
        return 117.35

    monkeypatch.setattr(
        "cloudsentinel.api.routers.mobile.load_latest_mttb_async",
        fake_latest_mttb,
    )
    app = FastAPI()
    app.include_router(build_mobile_router(settings, lambda: True, svc, block_handler))

    metrics = get_metrics()
    previous = metrics.mttb_ms
    metrics.set_mttb(0.0)
    try:
        dashboard = TestClient(app).get("/mobile/dashboard", headers=headers).json()
    finally:
        metrics.set_mttb(previous)
    assert dashboard["mttb_seconds"] == 0.117


def test_mobile_runtime_controls_persist_to_runtime_config(tmp_path: Path) -> None:
    from cloudsentinel.runtime_config import RuntimeConfigStore

    settings = Settings()
    settings.deception.level = "full"
    settings.deception.hassh_action = "monitor"
    store = RuntimeConfigStore(settings, path=str(tmp_path / "runtime.json"))
    svc, headers = _paired_mobile_service(tmp_path)

    class Soar:
        firewall_dry_run = True

    async def block_handler(body: dict) -> dict:
        return {"blocked": body["ip"]}

    app = FastAPI()
    app.include_router(
        build_mobile_router(
            settings,
            lambda: True,
            svc,
            block_handler,
            soar=Soar(),
            runtime_store=store,
        )
    )
    client = TestClient(app)
    response = client.post(
        "/mobile/runtime-controls",
        headers=headers,
        json={"deception_level": "listener", "hassh_action": "drop"},
    )
    assert response.status_code == 200
    assert response.json()["deception_level"] == "listener"
    assert response.json()["hassh_action"] == "drop"
    assert store.snapshot()["deception"]["level"] == "listener"
    assert store.snapshot()["hassh"]["action"] == "drop"

    reloaded = RuntimeConfigStore(Settings(), path=str(tmp_path / "runtime.json"))
    assert reloaded.snapshot()["deception"]["level"] == "listener"
    assert reloaded.snapshot()["hassh"]["action"] == "drop"
