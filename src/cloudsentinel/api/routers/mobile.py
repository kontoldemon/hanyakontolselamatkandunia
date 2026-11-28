"""Mobile Companion App pairing, push notification policy, and alert action routes."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ...config import Settings
from ...metrics import get_metrics
from ...mobile_push import MobilePushService, PairedDevice
from ..block_state import count_active_blocks
from ..queries import load_latest_mttb_async, load_truth_summary_async

logger = structlog.get_logger("cloudsentinel.api.routers.mobile")
mobile_security = HTTPBearer(auto_error=False)


def build_mobile_router(
    settings: Settings,
    require_auth: Callable[..., Any],
    mobile_service: MobilePushService,
    block_ip_handler: Callable[[dict[str, Any]], Any],
    load_exposure_state: Callable[..., Any] | None = None,
    persist_exposure_state: Callable[..., Any] | None = None,
    exposure_provider: Callable[[], str] | None = None,
    toggle_exposure: Callable[[bool], Any] | None = None,
    soar: Any | None = None,
    pipeline: Any | None = None,
    runtime_store: Any | None = None,
) -> APIRouter:
    """Create FastAPI router for Android companion pairing and alert delivery."""
    router = APIRouter(prefix="/mobile", tags=["mobile"])
    pair_attempts: dict[str, deque[float]] = {}
    pair_window_seconds = 60.0
    pair_max_attempts = 10
    events_cache: dict[str, Any] = {"total": None, "checked_at": 0.0}

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
            "ip": str(payload.get("ip") or "test-alert"),
            "country": str(payload.get("country") or "Unknown"),
            "risk_score": int(payload.get("riskScore") or 0),
            "event_type": "TEST",
            "summary": str(payload.get("summary") or "Test alert sent from CloudSentinel Settings"),
            "mitre_id": "",
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

    @router.post("/policy")
    async def update_mobile_policy_from_device(
        body: dict[str, Any],
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        policy = mobile_service.update_policy(body)
        return {"ok": True, "deviceId": device.device_id, "policy": policy.to_dict()}

    @router.post("/runtime-controls")
    async def update_runtime_controls_from_device(
        body: dict[str, Any],
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        persisted: dict[str, dict[str, Any]] = {}
        if "deception_level" in body:
            lvl = str(body["deception_level"]).strip().lower()
            if lvl not in {"full", "restricted", "listener"}:
                raise HTTPException(status_code=400, detail="Invalid deception_level")
            settings.deception.level = lvl
            persisted["deception"] = {"level": lvl}
        if "soar_dry_run" in body:
            dry_run = bool(body["soar_dry_run"])
            settings.soar.firewall_dry_run = dry_run
            if soar is not None and hasattr(soar, "firewall_dry_run"):
                soar.firewall_dry_run = dry_run
        if "hassh_action" in body:
            action = str(body["hassh_action"]).strip().lower()
            if action not in {"monitor", "drop"}:
                raise HTTPException(status_code=400, detail="Invalid hassh_action")
            settings.deception.hassh_action = action
            persisted["hassh"] = {"action": action}
        if runtime_store is not None and persisted:
            try:
                runtime_store.update(persisted)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "ok": True,
            "deviceId": device.device_id,
            "deception_level": settings.deception.level,
            "soar_dry_run": bool(getattr(soar, "firewall_dry_run", settings.soar.firewall_dry_run)),
            "hassh_action": settings.deception.hassh_action,
        }

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

    @router.get("/dashboard")
    async def get_mobile_dashboard(
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        """Live mini war-room telemetry and ingress status for mobile companion."""
        exposure_enabled = True
        provider = "iptables"
        if exposure_provider:
            provider = exposure_provider()
        if load_exposure_state:
            try:
                state = await load_exposure_state()
                exposure_enabled = bool(state.get("effective_enabled", True))
                provider = str(state.get("provider") or provider)
            except Exception:
                pass

        metrics = get_metrics()
        alerts = mobile_service.get_recent_alerts(limit=50)
        blocked_ips = set(getattr(metrics, "blocked_ips", set()) or set())
        if soar is not None:
            blocked_ips |= set(getattr(soar, "_mem_blocked_ips", set()) or set())
        blocked_ips_count = await count_active_blocks(settings.redis.url, len(blocked_ips))

        mttb_seconds = 0.0
        if soar is not None:
            soar_mttb_ms = float(getattr(soar, "mttb_ms", 0.0) or 0.0)
            if soar_mttb_ms > 0:
                mttb_seconds = round(soar_mttb_ms / 1000, 3)
        if mttb_seconds <= 0 and metrics.mttb_ms > 0:
            mttb_seconds = round(metrics.mttb_ms / 1000, 3)
        if mttb_seconds <= 0:
            latest_mttb_ms = await load_latest_mttb_async(settings)
            if latest_mttb_ms > 0:
                mttb_seconds = round(latest_mttb_ms / 1000, 3)

        mitre_ids: set[str] = set()
        for alert in alerts:
            if alert.get("mitreId"):
                mitre_ids.add(str(alert["mitreId"]))
        if soar is not None:
            for techniques in getattr(soar, "_mem_ip_techniques", {}).values():
                mitre_ids.update(techniques)

        country_counts: dict[str, int] = {}
        for alert in alerts:
            country = str(alert.get("country") or "").strip()
            if country:
                country_counts[country] = country_counts.get(country, 0) + 1
        top_country = max(country_counts, key=lambda key: country_counts[key]) if country_counts else "Unknown"

        active_attackers = int(metrics.active_sessions)
        if soar is not None:
            cutoff = time.time() - 90
            last_seen_map = getattr(soar, "_mem_ip_last_seen", {}) or {}
            active_attackers = sum(1 for ts in last_seen_map.values() if float(ts) >= cutoff)

        ssh_port = int(settings.honeypot.ssh_port)
        listen_host = str(settings.honeypot.listen_host or "0.0.0.0")
        pipeline_connected = bool(getattr(pipeline, "connected", False)) if pipeline is not None else False
        now = time.time()
        events_total = int(getattr(metrics, "total_events", 0))
        if settings.clickhouse.enabled:
            checked_at = float(events_cache["checked_at"] or 0.0)
            if events_cache["total"] is None or now - checked_at >= 60:
                try:
                    summary = await load_truth_summary_async(settings)
                    if summary is not None:
                        events_cache["total"] = int(summary.get("total_events") or 0)
                except Exception:
                    pass
                events_cache["checked_at"] = now
            if events_cache["total"] is not None:
                events_total = max(events_total, int(events_cache["total"]))

        return {
            "ok": True,
            "deviceId": device.device_id,
            "connections": int(metrics.active_sessions),
            "events_total": events_total,
            "mttb_seconds": mttb_seconds,
            "mitre_count": len(mitre_ids),
            "blocked_ips_count": blocked_ips_count,
            "sensor_status": "ONLINE" if pipeline_connected else "OFFLINE",
            "sensor_uptime_seconds": int(max(0.0, time.time() - metrics.start_time)),
            "ingress_exposure": {
                "enabled": exposure_enabled,
                "port": ssh_port,
                "provider": provider,
                "target": f"{listen_host}:{ssh_port}/TCP",
            },
            "top_threat_origin": top_country,
            "active_attackers_count": active_attackers,
            "blocked_ips": sorted(blocked_ips)[:100],
            "deception_level": str(getattr(settings.deception, "level", "full")),
            "soar_dry_run": bool(getattr(soar, "firewall_dry_run", settings.soar.firewall_dry_run)),
            "hassh_action": str(getattr(settings.deception, "hassh_action", "monitor")),
            "alert_policy": mobile_service.get_policy().to_dict(),
        }

    @router.post("/exposure")
    async def toggle_mobile_exposure(
        body: dict[str, Any],
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        """Emergency ingress port 2222 killswitch from mobile."""
        enabled = bool(body.get("enabled", True))
        if toggle_exposure is not None:
            try:
                result = dict(await toggle_exposure(enabled))
            except Exception as exc:
                logger.warning("mobile_exposure_failed", error=str(exc))
                raise HTTPException(status_code=503, detail="Exposure control unavailable") from exc
            effective = bool(result.get("enabled", enabled))
            status_text = "ONLINE" if effective else "PAUSED (KILLSWITCH ENGAGED)"
            result["deviceId"] = device.device_id
            result["message"] = f"Honeypot ingress is now {status_text}"
            if not result.get("ok"):
                result["message"] = f"Exposure toggle failed: {result.get('error', 'firewall error')}"
            return result

        provider = "iptables"
        if exposure_provider:
            provider = exposure_provider()

        if persist_exposure_state:
            try:
                await persist_exposure_state({
                    "effective_enabled": enabled,
                    "paused": not enabled,
                    "provider": provider,
                    "last_toggle_by": f"mobile:{device.device_name}",
                    "last_toggle_at": int(time.time() * 1000),
                })
            except Exception:
                pass

        status_text = "ONLINE" if enabled else "PAUSED (KILLSWITCH ENGAGED)"
        return {
            "ok": True,
            "enabled": enabled,
            "provider": provider,
            "message": f"Honeypot ingress is now {status_text}",
        }

    @router.get("/sessions")
    async def get_mobile_sessions(
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        """Attacker forensic inspection sessions with DVR keystrokes."""
        sessions: list[dict[str, Any]] = []

        if settings.clickhouse.enabled:
            try:
                from .. import queries

                session_limit = 50
                rows = await queries.load_recent_sessions_async(settings, limit=session_limit)
                fetch_capped = len(rows) >= session_limit
                grouped: dict[str, list[dict[str, Any]]] = {}
                for row in rows:
                    ip = str(row.get("ip") or "").strip()
                    if ip:
                        grouped.setdefault(ip, []).append(row)
                collapsed: list[dict[str, Any]] = []
                for ip, group in grouped.items():
                    group.sort(
                        key=lambda item: int(
                            item.get("lastSeenEpochMs") or item.get("startedAtEpochMs") or 0
                        ),
                        reverse=True,
                    )
                    latest = group[0]
                    collapsed.append({
                        "id": latest.get("id", ""),
                        "ip": ip,
                        "country": latest.get("country", "Unknown"),
                        "city": latest.get("city", "Unknown"),
                        "isp": latest.get("isp", ""),
                        "hassh": next(
                            (
                                str(item.get("fingerprint"))
                                for item in group
                                if item.get("fingerprint")
                            ),
                            "",
                        ),
                        "risk_score": max(int(item.get("riskScore") or 0) for item in group),
                        "duration": latest.get("duration", ""),
                        "mitre_techniques": sorted({
                            str(technique)
                            for item in group
                            for technique in (item.get("mitreTechniques") or [])
                        }),
                        "commands": next(
                            (list(item.get("input") or [])[:10] for item in group if item.get("input")),
                            [],
                        ),
                        "blocked": any(bool(item.get("blockEffective", False)) for item in group),
                        "timestamp_ms": int(
                            latest.get("lastSeenEpochMs") or latest.get("startedAtEpochMs") or 0
                        ),
                        "session_count": len(group),
                        "session_count_capped": fetch_capped,
                    })
                sessions = sorted(
                    collapsed,
                    key=lambda item: int(item.get("timestamp_ms") or 0),
                    reverse=True,
                )
            except Exception:
                sessions = []

        if not sessions:
            for item in mobile_service.get_recent_alerts(limit=20):
                mitre_id = str(item.get("mitreId") or "")
                sessions.append({
                    "id": f"alert-{item.get('id') or item.get('ip', 'unknown')}",
                    "ip": item.get("ip", "unknown"),
                    "country": item.get("country", "Unknown"),
                    "city": "Unknown",
                    "isp": "",
                    "risk_score": int(item.get("riskScore") or 0),
                    "duration": "",
                    "mitre_techniques": [mitre_id] if mitre_id else [],
                    "commands": [],
                    "blocked": bool(item.get("blocked", False)),
                    "timestamp_ms": int(item.get("timestampMs") or time.time() * 1000),
                })

        return {"ok": True, "deviceId": device.device_id, "sessions": sessions}

    @router.post("/ai-copilot")
    async def ask_mobile_copilot(
        body: dict[str, Any],
        device: PairedDevice = Depends(require_device_auth),
    ) -> dict[str, Any]:
        """Mobile AI Security Copilot query endpoint."""
        prompt = str(body.get("prompt") or "").strip()
        context = str(body.get("context") or "Mobile SOC Companion session")
        if not prompt:
            raise HTTPException(status_code=400, detail="prompt is required")

        try:
            from ...threat_reporter import chat_with_agent

            response_text = await chat_with_agent(prompt, context)
            if response_text and "offline" not in response_text.lower():
                return {"ok": True, "response": response_text}
        except Exception as exc:
            logger.warning("mobile_copilot_failed", error=str(exc))
        return {"ok": False, "error": "AI assistant unavailable on sensor"}

    return router
