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
    assert alerts[0]["ip"] == "185.220.101.42"

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


def test_mobile_router_block_ip_endpoint(tmp_path: Path) -> None:
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
