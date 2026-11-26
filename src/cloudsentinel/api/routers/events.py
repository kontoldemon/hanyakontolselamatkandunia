"""Events and truth-summary routes."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends

from ...config import Settings
from .. import queries


def build_events_router(
    settings: Settings,
    require_auth: Callable[..., Any],
    compute_war_room_state: Callable[..., Any],
    hot_cache_get: Callable[..., Any],
    hot_cache_set: Callable[..., Any],
    summary_cache_ttl_seconds: int,
) -> APIRouter:
    router = APIRouter()

    @router.get("/events", dependencies=[Depends(require_auth)])
    async def events(limit: int = 100) -> dict[str, Any]:
        payload = {
            "events": await queries.load_recent_events_async(settings, limit=limit),
            "source": "clickhouse",
            "authoritative": True,
            "sourceBreakdown": {"events": "clickhouse"},
        }
        await compute_war_room_state(force=False)
        return payload

    @router.get("/truth-summary", dependencies=[Depends(require_auth)])
    async def truth_summary() -> dict[str, Any]:
        cached_payload, _ = await hot_cache_get("truth-summary")
        if isinstance(cached_payload, dict) and isinstance(cached_payload.get("metrics"), dict):
            await compute_war_room_state(force=False)
            return cached_payload
        summary = await queries.load_truth_summary_async(settings)
        if summary is None:
            payload = {
                "ok": False,
                "source": "runtime",
                "authoritative": False,
                "metrics": {},
                "sourceBreakdown": {"metrics": "runtime"},
            }
            await compute_war_room_state(force=False)
            return payload
        payload = {
            "ok": True,
            "source": "clickhouse",
            "authoritative": True,
            "metrics": summary,
            "sourceBreakdown": {"metrics": "clickhouse"},
        }
        await hot_cache_set("truth-summary", payload, summary_cache_ttl_seconds)
        await compute_war_room_state(force=False)
        return payload

    return router
