"""Mobile Companion App pairing, push notification policy, and alert action routes."""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ...config import Settings
from ...mobile_push import MobilePushService, PairedDevice

mobile_security = HTTPBearer(auto_error=False)


def build_mobile_router(
    settings: Settings,
    require_auth: Callable[..., Any],
    mobile_service: MobilePushService,
    block_ip_handler: Callable[[dict[str, Any]], Any],
) -> APIRouter:
    """Create FastAPI router for Android companion pairing and alert delivery."""
    router = APIRouter(prefix="/mobile", tags=["mobile"])
    pair_attempts: dict[str, deque[float]] = {}
    pair_window_seconds = 60.0
    pair_max_attempts = 10

    async def require_device_auth(
        credentials: HTTPAuthorizationCredentials | None = Depends(mobile_security),
    ) -> PairedDevice:
        if credentials is None or not credentials.credentials:
            raise HTTPException(status_code=401, detail="Missing mobile device bearer token")
        device = mobile_service.verify_device_token(credentials.credentials)
        if device is None:
            raise HTTPException(status_code=401, detail="Invalid or revoked mobile device token")
        return device

    @router.get("/config", dependencies=[Depends(require_auth)])
    async def get_mobile_config() -> dict[str, Any]:
        return {
            "ok": True,
            "policy": mobile_service.get_policy().to_dict(),
            "devices": mobile_service.list_devices(),
        }

    @router.post("/config", dependencies=[Depends(require_auth)])
    async def update_mobile_config(body: dict[str, Any]) -> dict[str, Any]:
        policy = mobile_service.update_policy(body)
        return {
            "ok": True,
            "policy": policy.to_dict(),
            "devices": mobile_service.list_devices(),
        }

    @router.post("/pairing-token", dependencies=[Depends(require_auth)])
    async def create_pairing_token(body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = body or {}
        host = settings.honeypot.hostname or settings.admin.host
        scheme = "https" if settings.tls.enabled else "http"
        default_url = (
            f"{scheme}://{host}:{settings.admin.port}"
            if host and host not in {"0.0.0.0", "::", "[::]"}
            else ""
        )
        server_url = str(payload.get("serverUrl") or default_url).strip()
        if not server_url:
            raise HTTPException(
                status_code=400,
                detail="serverUrl is required when the admin API binds to a wildcard address",
            )
        challenge = mobile_service.create_pairing_challenge(server_url=server_url)
        return {"ok": True, **challenge}

    @router.post("/pair")
    async def pair_android_device(body: dict[str, Any], request: Request) -> dict[str, Any]:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        attempts = pair_attempts.setdefault(client_ip, deque())
        while attempts and now - attempts[0] > pair_window_seconds:
            attempts.popleft()
        if len(attempts) >= pair_max_attempts:
            raise HTTPException(status_code=429, detail="too many pairing attempts")
        attempts.append(now)

        code = str(body.get("pairingCode") or body.get("pairing_code") or "").strip()
        device_name = str(body.get("deviceName") or body.get("device_name") or "Android Device").strip()
        fcm_token = str(body.get("fcmToken") or body.get("fcm_token") or "").strip()
        pairing_token = str(body.get("pairingToken") or body.get("pairing_token") or "").strip()
        platform = str(body.get("platform") or "android").strip()
        if not code or not pairing_token:
            raise HTTPException(status_code=400, detail="pairingCode and pairingToken are required")
        paired = mobile_service.pair_device(
            pairing_code=code,
            device_name=device_name,
            fcm_token=fcm_token,
            platform=platform,
            pairing_token=pairing_token,
        )
        if paired is None:
            raise HTTPException(status_code=401, detail="Invalid or expired pairing code")
        return {"ok": True, **paired}

    @router.delete("/devices/{device_id}", dependencies=[Depends(require_auth)])
    async def revoke_mobile_device(device_id: str) -> dict[str, Any]:
        removed = mobile_service.revoke_device(device_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Device not found")
        return {"ok": True, "deviceId": device_id, "devices": mobile_service.list_devices()}

    @router.post("/test-alert", dependencies=[Depends(require_auth)])
    async def send_test_alert(body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = body or {}
        event = {
            "ip": str(payload.get("ip") or "185.220.101.42"),
            "country": str(payload.get("country") or "Germany"),
            "risk_score": int(payload.get("riskScore") or 92),
            "event_type": "COMMAND_EXEC",
            "summary": str(payload.get("summary") or "Test DEFCON alert triggered from CloudSentinel Web Settings"),
            "mitre_id": "T1059.004",
            "blocked": False,
        }
        return await mobile_service.dispatch_alert(event, force=True)

    @router.get("/alerts")
    async def get_mobile_alerts(
        limit: int = 50,
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "deviceId": device.device_id,
            "alerts": mobile_service.get_recent_alerts(limit=limit),
        }

    @router.post("/fcm-token")
    async def refresh_fcm_token(
        body: dict[str, Any],
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        fcm_token = str(body.get("fcmToken") or body.get("fcm_token") or "").strip()
        if not fcm_token:
            raise HTTPException(status_code=400, detail="fcmToken is required")
        mobile_service.update_fcm_token(device.device_id, fcm_token)
        return {"ok": True, "deviceId": device.device_id}

    @router.post("/block-ip")
    async def block_ip_from_mobile(
        body: dict[str, Any],
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        ip = str(body.get("ip") or "").strip()
        if not ip:
            raise HTTPException(status_code=400, detail="ip is required")
        reason = str(body.get("reason") or f"mobile-action:{device.device_name}")[:120]
        result = await block_ip_handler({"ip": ip, "reason": reason, "ttl": body.get("ttl")})
        return {"ok": True, "deviceId": device.device_id, **result}

    return router
