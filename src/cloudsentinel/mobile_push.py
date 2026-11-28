"""CloudSentinel Mobile Push Notification & Android Device Pairing Service.

Manages Android companion pairing tokens, scoped device bearer credentials,
alert policy thresholds, recent alert history, and FCM HTTP v1 push dispatch.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx
import structlog

logger = structlog.get_logger("cloudsentinel.mobile_push")

PAIRING_TTL_SECONDS = 300
MAX_PAIRED_DEVICES = 20
MAX_RECENT_ALERTS = 100

_fcm_credentials: Any = None


def _fcm_bearer() -> str:
    static = os.getenv("CLOUDSENTINEL_FCM_ACCESS_TOKEN", "").strip()
    if static:
        return static
    path = os.getenv("CLOUDSENTINEL_FCM_SERVICE_ACCOUNT", "").strip()
    if not path:
        return ""
    global _fcm_credentials
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        if _fcm_credentials is None:
            _fcm_credentials = service_account.Credentials.from_service_account_file(
                path,
                scopes=["https://www.googleapis.com/auth/firebase.messaging"],
            )
        if not _fcm_credentials.valid:
            _fcm_credentials.refresh(Request())
        return str(_fcm_credentials.token or "")
    except Exception as exc:
        logger.warning("fcm_service_account_failed", error=str(exc))
        return ""


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass
class PairedDevice:
    """Registered Android companion device."""

    device_id: str
    device_name: str
    platform: str
    fcm_token: str
    token_hash: str
    paired_at_ms: int
    last_seen_at_ms: int

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "deviceId": self.device_id,
            "deviceName": self.device_name,
            "platform": self.platform,
            "hasFcmToken": bool(self.fcm_token),
            "pairedAtMs": self.paired_at_ms,
            "lastSeenAtMs": self.last_seen_at_ms,
        }


@dataclass
class MobileAlertPolicy:
    """Configurable alert rules for mobile push delivery."""

    enabled: bool = True
    min_risk_score: int = 70
    cooldown_seconds: int = 60
    notify_brute_force: bool = True
    notify_command_exec: bool = True
    notify_soar_block: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "minRiskScore": self.min_risk_score,
            "cooldownSeconds": self.cooldown_seconds,
            "notifyBruteForce": self.notify_brute_force,
            "notifyCommandExec": self.notify_command_exec,
            "notifySoarBlock": self.notify_soar_block,
        }


@dataclass
class PairingChallenge:
    """Short-lived one-time pairing token for QR / 6-digit code onboarding."""

    code: str
    token: str
    server_url: str
    created_at_ms: int
    expires_at_ms: int


@dataclass
class MobileAlertRecord:
    """Normalized alert entry delivered to Android companion clients."""

    id: str
    ip: str
    country: str
    risk_score: int
    event_type: str
    summary: str
    mitre_id: str = ""
    blocked: bool = False
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ip": self.ip,
            "country": self.country,
            "riskScore": self.risk_score,
            "eventType": self.event_type,
            "summary": self.summary,
            "mitreId": self.mitre_id,
            "blocked": self.blocked,
            "timestampMs": self.timestamp_ms,
        }


class MobilePushService:
    """Manages paired Android devices and dispatches threat alerts via FCM HTTP v1."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        default_path = os.getenv("CLOUDSENTINEL_MOBILE_STATE_PATH", "var/mobile_devices.json")
        self._storage_path = Path(storage_path) if storage_path is not None else Path(default_path)
        self._devices: dict[str, PairedDevice] = {}
        self._policy = MobileAlertPolicy()
        self._challenges: dict[str, PairingChallenge] = {}
        self._recent_alerts: deque[MobileAlertRecord] = deque(maxlen=MAX_RECENT_ALERTS)
        self._last_alert_by_ip: dict[str, float] = {}
        self._load_state()

    def _load_state(self) -> None:
        if not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
            policy_data = raw.get("policy")
            if isinstance(policy_data, dict):
                self._policy = MobileAlertPolicy(
                    enabled=bool(policy_data.get("enabled", True)),
                    min_risk_score=max(0, min(100, int(policy_data.get("min_risk_score", 70)))),
                    cooldown_seconds=max(0, min(3600, int(policy_data.get("cooldown_seconds", 60)))),
                    notify_brute_force=bool(policy_data.get("notify_brute_force", True)),
                    notify_command_exec=bool(policy_data.get("notify_command_exec", True)),
                    notify_soar_block=bool(policy_data.get("notify_soar_block", True)),
                )
            for item in raw.get("devices", []):
                if not isinstance(item, dict) or not item.get("device_id"):
                    continue
                device = PairedDevice(
                    device_id=str(item["device_id"]),
                    device_name=str(item.get("device_name", "Android Device")),
                    platform=str(item.get("platform", "android")),
                    fcm_token=str(item.get("fcm_token", "")),
                    token_hash=str(item.get("token_hash", "")),
                    paired_at_ms=int(item.get("paired_at_ms", 0)),
                    last_seen_at_ms=int(item.get("last_seen_at_ms", 0)),
                )
                self._devices[device.device_id] = device
            for item in raw.get("challenges", []):
                if not isinstance(item, dict) or not item.get("code"):
                    continue
                challenge = PairingChallenge(
                    code=str(item["code"]),
                    token=str(item.get("token", "")),
                    server_url=str(item.get("server_url", "")),
                    created_at_ms=int(item.get("created_at_ms", 0)),
                    expires_at_ms=int(item.get("expires_at_ms", 0)),
                )
                self._challenges[challenge.code] = challenge
            for item in raw.get("recent_alerts", []):
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                self._recent_alerts.append(
                    MobileAlertRecord(
                        id=str(item["id"]),
                        ip=str(item.get("ip", "")),
                        country=str(item.get("country", "Unknown")),
                        risk_score=int(item.get("risk_score", item.get("riskScore", 0))),
                        event_type=str(item.get("event_type", item.get("eventType", "THREAT_DETECTED"))),
                        summary=str(item.get("summary", "")),
                        mitre_id=str(item.get("mitre_id", item.get("mitreId", ""))),
                        blocked=bool(item.get("blocked", False)),
                        timestamp_ms=int(item.get("timestamp_ms", item.get("timestampMs", 0))),
                    )
                )
        except Exception as exc:
            logger.warning("mobile_push_load_failed", error=str(exc))

    def _save_state(self) -> None:
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "policy": asdict(self._policy),
                "devices": [asdict(dev) for dev in self._devices.values()],
                "challenges": [asdict(ch) for ch in self._challenges.values()],
                "recent_alerts": [alert.to_dict() for alert in self._recent_alerts],
            }
            self._storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            try:
                self._storage_path.chmod(0o600)
            except OSError:
                pass
        except Exception as exc:
            logger.warning("mobile_push_save_failed", error=str(exc))

    def refresh(self) -> None:
        """Reload shared state written by another process."""
        self._devices.clear()
        self._policy = MobileAlertPolicy()
        self._challenges.clear()
        self._recent_alerts.clear()
        self._load_state()

    def _prune_challenges(self) -> None:
        now_ms = int(time.time() * 1000)
        expired = [code for code, ch in self._challenges.items() if ch.expires_at_ms <= now_ms]
        for code in expired:
            self._challenges.pop(code, None)

    def get_policy(self) -> MobileAlertPolicy:
        return self._policy

    def update_policy(self, updates: dict[str, Any]) -> MobileAlertPolicy:
        if "enabled" in updates:
            self._policy.enabled = bool(updates["enabled"])
        if "minRiskScore" in updates or "min_risk_score" in updates:
            val = updates.get("minRiskScore", updates.get("min_risk_score", self._policy.min_risk_score))
            self._policy.min_risk_score = max(0, min(100, int(val)))
        if "cooldownSeconds" in updates or "cooldown_seconds" in updates:
            val = updates.get("cooldownSeconds", updates.get("cooldown_seconds", self._policy.cooldown_seconds))
            self._policy.cooldown_seconds = max(0, min(3600, int(val)))
        if "notifyBruteForce" in updates or "notify_brute_force" in updates:
            self._policy.notify_brute_force = bool(
                updates.get("notifyBruteForce", updates.get("notify_brute_force"))
            )
        if "notifyCommandExec" in updates or "notify_command_exec" in updates:
            self._policy.notify_command_exec = bool(
                updates.get("notifyCommandExec", updates.get("notify_command_exec"))
            )
        if "notifySoarBlock" in updates or "notify_soar_block" in updates:
            self._policy.notify_soar_block = bool(
                updates.get("notifySoarBlock", updates.get("notify_soar_block"))
            )
        self._save_state()
        return self._policy

    def create_pairing_challenge(self, server_url: str) -> dict[str, Any]:
        """Generate a 5-minute one-time pairing code and QR payload."""
        self._prune_challenges()
        now_ms = int(time.time() * 1000)
        expires_ms = now_ms + PAIRING_TTL_SECONDS * 1000
        code = f"{secrets.randbelow(900000) + 100000}"
        token = secrets.token_urlsafe(24)
        clean_url = server_url.strip().rstrip("/")
        challenge = PairingChallenge(
            code=code,
            token=token,
            server_url=clean_url,
            created_at_ms=now_ms,
            expires_at_ms=expires_ms,
        )
        self._challenges[code] = challenge
        self._save_state()
        qr_payload = json.dumps(
            {"v": 1, "serverUrl": clean_url, "pairingCode": code, "pairingToken": token},
            separators=(",", ":"),
        )
        return {
            "pairingCode": code,
            "pairingToken": token,
            "serverUrl": clean_url,
            "expiresAtMs": expires_ms,
            "ttlSeconds": PAIRING_TTL_SECONDS,
            "qrPayload": qr_payload,
        }

    def pair_device(
        self,
        pairing_code: str,
        device_name: str,
        fcm_token: str = "",
        platform: str = "android",
        pairing_token: str = "",
    ) -> dict[str, Any] | None:
        """Consume a valid pairing code and register the Android device."""
        self.refresh()
        self._prune_challenges()
        normalized_code = pairing_code.strip()
        challenge = self._challenges.get(normalized_code)
        if challenge is None:
            return None
        if pairing_token and not hmac.compare_digest(challenge.token, pairing_token):
            return None
        self._challenges.pop(normalized_code, None)

        if len(self._devices) >= MAX_PAIRED_DEVICES:
            oldest_id = min(self._devices.values(), key=lambda d: d.paired_at_ms).device_id
            self._devices.pop(oldest_id, None)

        now_ms = int(time.time() * 1000)
        device_id = f"dev_{secrets.token_hex(8)}"
        raw_device_token = f"cs_mob_{secrets.token_urlsafe(32)}"
        clean_name = (device_name or "Android Companion").strip()[:64] or "Android Companion"
        clean_platform = (platform or "android").strip().lower()[:24]

        device = PairedDevice(
            device_id=device_id,
            device_name=clean_name,
            platform=clean_platform,
            fcm_token=fcm_token.strip()[:512],
            token_hash=_hash_token(raw_device_token),
            paired_at_ms=now_ms,
            last_seen_at_ms=now_ms,
        )
        self._devices[device_id] = device
        self._save_state()
        logger.info("mobile_device_paired", device_id=device_id, device_name=clean_name)
        return {
            "deviceId": device_id,
            "deviceName": clean_name,
            "deviceToken": raw_device_token,
            "pairedAtMs": now_ms,
        }

    def verify_device_token(self, raw_token: str) -> PairedDevice | None:
        """Constant-time validation of a paired Android device bearer token."""
        if not raw_token or not raw_token.startswith("cs_mob_"):
            return None
        candidate_hash = _hash_token(raw_token)
        for device in self._devices.values():
            if hmac.compare_digest(device.token_hash, candidate_hash):
                device.last_seen_at_ms = int(time.time() * 1000)
                return device
        return None

    def update_fcm_token(self, device_id: str, fcm_token: str) -> bool:
        device = self._devices.get(device_id)
        if not device:
            return False
        device.fcm_token = fcm_token.strip()[:512]
        device.last_seen_at_ms = int(time.time() * 1000)
        self._save_state()
        return True

    def list_devices(self) -> list[dict[str, Any]]:
        return [d.to_public_dict() for d in sorted(self._devices.values(), key=lambda x: x.paired_at_ms, reverse=True)]

    def revoke_device(self, device_id: str) -> bool:
        removed = self._devices.pop(device_id, None)
        if removed is None:
            return False
        self._save_state()
        logger.info("mobile_device_revoked", device_id=device_id)
        return True

    def get_recent_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        self.refresh()
        safe_limit = max(1, min(MAX_RECENT_ALERTS, limit))
        return [item.to_dict() for item in list(self._recent_alerts)[:safe_limit]]

    def _should_notify(self, event_type: str, risk_score: int, ip: str, force: bool) -> bool:
        if force:
            return True
        if not self._policy.enabled:
            return False
        if risk_score < self._policy.min_risk_score:
            return False
        normalized = event_type.upper()
        if "AUTH" in normalized and not self._policy.notify_brute_force:
            return False
        if "COMMAND" in normalized and not self._policy.notify_command_exec:
            return False
        if "BLOCK" in normalized and not self._policy.notify_soar_block:
            return False
        if self._policy.cooldown_seconds > 0 and ip:
            now = time.monotonic()
            last = self._last_alert_by_ip.get(ip)
            if last is not None and (now - last) < self._policy.cooldown_seconds:
                return False
        return True

    async def dispatch_alert(self, event: dict[str, Any], force: bool = False) -> dict[str, Any]:
        """Record alert and push to all paired Android devices via FCM HTTP v1."""
        ip = str(event.get("ip") or event.get("src_ip") or "0.0.0.0").strip()
        country = str(event.get("country") or event.get("country_name") or "Unknown").strip()
        risk_score = max(0, min(100, int(event.get("risk_score") or event.get("cloudsentinel_risk_score") or 0)))
        event_type = str(event.get("event_type") or event.get("eventid") or "THREAT_DETECTED").strip()
        summary = str(event.get("summary") or event.get("input") or "Suspicious SSH activity detected").strip()[:180]
        mitre_id = str(event.get("mitre_id") or "").strip()[:32]
        blocked = bool(event.get("blocked", False))

        if not self._should_notify(event_type, risk_score, ip, force=force):
            return {"ok": True, "dispatched": 0, "skipped": True, "reason": "policy_or_cooldown"}

        if ip:
            self._last_alert_by_ip[ip] = time.monotonic()

        record = MobileAlertRecord(
            id=f"alrt_{secrets.token_hex(6)}",
            ip=ip,
            country=country,
            risk_score=risk_score,
            event_type=event_type,
            summary=summary,
            mitre_id=mitre_id,
            blocked=blocked,
        )
        self._recent_alerts.appendleft(record)
        self._save_state()

        devices = list(self._devices.values())
        if not devices:
            return {"ok": True, "dispatched": 0, "alert": record.to_dict(), "mode": "no_devices"}

        fcm_project = os.getenv("CLOUDSENTINEL_FCM_PROJECT_ID", "").strip()
        fcm_bearer = _fcm_bearer()

        if not fcm_project or not fcm_bearer:
            logger.info(
                "mobile_push_dry_run",
                alert_id=record.id,
                device_count=len(devices),
                ip=ip,
                risk_score=risk_score,
            )
            return {
                "ok": True,
                "dispatched": len(devices),
                "alert": record.to_dict(),
                "mode": "local_sync_only",
            }

        endpoint = f"https://fcm.googleapis.com/v1/projects/{fcm_project}/messages:send"
        headers = {
            "Authorization": f"Bearer {fcm_bearer}",
            "Content-Type": "application/json",
        }

        dispatched = 0
        async with httpx.AsyncClient(timeout=8.0) as client:
            tasks = []
            for dev in devices:
                if not dev.fcm_token:
                    continue
                body = {
                    "message": {
                        "token": dev.fcm_token,
                        "android": {"priority": "HIGH"},
                        "data": {
                            "alertId": record.id,
                            "ip": record.ip,
                            "country": record.country,
                            "riskScore": str(record.risk_score),
                            "eventType": record.event_type,
                            "summary": record.summary,
                            "mitreId": record.mitre_id,
                            "blocked": "true" if record.blocked else "false",
                            "timestampMs": str(record.timestamp_ms),
                        },
                    }
                }
                tasks.append(client.post(endpoint, headers=headers, json=body))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, httpx.Response) and res.status_code == 200:
                    dispatched += 1
                elif isinstance(res, Exception):
                    logger.warning("fcm_send_exception", error=str(res))

        return {
            "ok": True,
            "dispatched": dispatched,
            "alert": record.to_dict(),
            "mode": "fcm_v1",
        }
