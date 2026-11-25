"""Sessions and war-room routes."""

from __future__ import annotations

import time
from typing import Any, Callable

from fastapi import APIRouter, Depends

from ...config import Settings
from .. import queries


def build_sessions_router(
    settings: Settings,
    require_auth: Callable[..., Any],
    compute_war_room_state: Callable[..., Any],
    hot_cache_get: Callable[..., Any],
    hot_cache_set: Callable[..., Any],
    soar: Any,
    sessions_cache_ttl_seconds: int,
) -> APIRouter:
    router = APIRouter()

    @router.get("/sessions", dependencies=[Depends(require_auth)])
    async def sessions() -> dict[str, Any]:
        strict_truth = queries._strict_truth_mode_enabled()
        if strict_truth:
            cached_payload, _ = await hot_cache_get("sessions:strict")
            if isinstance(cached_payload, dict) and isinstance(cached_payload.get("sessions"), list):
                await compute_war_room_state(force=False)
                return cached_payload
        sessions_list = queries._load_recent_sessions_from_clickhouse(settings)
        existing = {str(item.get("ip", "")) for item in sessions_list}
        if not strict_truth and soar is not None:
            now_ts = time.time()
            for ip, session_ids in getattr(soar, "_mem_ip_sessions", {}).items():
                if ip in existing:
                    continue
                profile = soar.get_ip_profile(ip) if hasattr(soar, "get_ip_profile") else {}
                last_seen = float(profile.get("last_seen") or profile.get("first_seen") or 0.0)
                if last_seen <= 0 or (now_ts - last_seen) > queries.SYNTHETIC_ACTIVE_WINDOW_SECONDS:
                    continue
                first_seen = float(profile.get("first_seen") or last_seen or now_ts)
                duration_sec = max(0, int(now_ts - first_seen))
                enriched = queries._enrichment_for_ip(ip, "XX", "Unknown")
                sessions_list.append(
                    {
                        "id": f"sess-{ip}",
                        "ip": ip,
                        "country": queries._display_country(enriched),
                        "countryCode": enriched.get("country_code", "XX"),
                        "countryName": enriched.get("country_name", "Unknown"),
                        "asn": enriched.get("asn", ""),
                        "isp": enriched.get("isp", ""),
                        "org": enriched.get("org", ""),
                        "services": enriched.get("services", ""),
                        "region": enriched.get("region", "Unknown"),
                        "city": enriched.get("city", "Unknown"),
                        "latitude": enriched.get("latitude", "0"),
                        "longitude": enriched.get("longitude", "0"),
                        "timezone": enriched.get("timezone", "UTC"),
                        "startTime": time.strftime(
                            "%H:%M:%S",
                            time.localtime(first_seen),
                        ),
                        "duration": f"{duration_sec // 60}m {duration_sec % 60}s",
                        "startedAtEpochMs": int(first_seen * 1000),
                        "firstSeenEpochMs": int(first_seen * 1000),
                        "lastSeenEpochMs": int(last_seen * 1000),
                        "client": "unknown",
                        "fingerprint": "",
                        "input": [],
                        "status": "Active",
                        "sessionCount": len(session_ids),
                        "riskScore": profile.get("cumulative_risk", 0),
                        "soarAction": "none",
                        "mttbMs": 0.0,
                        "blockEffective": False,
                        "mitreTechniques": profile.get("techniques", []),
                        "replay": [],
                        "source": "memory",
                    }
                )
        payload = {
            "sessions": sessions_list,
            "source": "clickhouse" if strict_truth else ("mixed" if any(s.get("source") == "memory" for s in sessions_list) else "clickhouse"),
            "authoritative": strict_truth,
            "sourceBreakdown": {
                "sessions": "clickhouse",
                "memory_fallback_enabled": not strict_truth,
            },
        }
        if strict_truth:
            await hot_cache_set("sessions:strict", payload, sessions_cache_ttl_seconds)
        await compute_war_room_state(force=False)
        return payload

    @router.get("/war-room-state", dependencies=[Depends(require_auth)])
    async def war_room_state() -> dict[str, Any]:
        return await compute_war_room_state(force=True)

    return router
