"""ClickHouse loaders must not block the admin event loop."""

from __future__ import annotations

import asyncio
import threading
import time

from cloudsentinel.api import queries


def test_event_loader_runs_in_worker_thread(monkeypatch) -> None:
    seen: dict[str, int] = {}

    def slow_loader(_settings, limit=100):
        seen["worker"] = threading.get_ident()
        time.sleep(0.01)
        return [{"limit": limit}]

    monkeypatch.setattr(queries, "_load_recent_events_from_clickhouse", slow_loader)

    async def run():
        seen["loop"] = threading.get_ident()
        return await queries.load_recent_events_async(object(), limit=7)

    result = asyncio.run(run())
    assert result == [{"limit": 7}]
    assert seen["worker"] != seen["loop"]


def test_session_loader_keeps_optional_limit(monkeypatch) -> None:
    calls: list[int | None] = []

    def loader(_settings, limit=50):
        calls.append(limit)
        return []

    monkeypatch.setattr(queries, "_load_recent_sessions_from_clickhouse", loader)

    async def run():
        await queries.load_recent_sessions_async(object())
        await queries.load_recent_sessions_async(object(), limit=5)

    asyncio.run(run())
    assert calls == [50, 5]


def test_other_loaders_are_awaitable(monkeypatch) -> None:
    monkeypatch.setattr(queries, "_load_truth_summary_from_clickhouse", lambda _settings: {"ok": True})
    monkeypatch.setattr(queries, "_load_attack_distribution_from_clickhouse", lambda _settings: {})
    monkeypatch.setattr(queries, "_load_attack_graph_from_clickhouse", lambda _settings, limit=60: {"limit": limit})
    monkeypatch.setattr(queries, "_latest_mttb_from_clickhouse", lambda _settings: 1.5)
    monkeypatch.setattr(queries, "_load_war_room_evidence_from_clickhouse", lambda _settings: {"ok": True})

    async def run():
        return (
            await queries.load_truth_summary_async(object()),
            await queries.load_attack_distribution_async(object()),
            await queries.load_attack_graph_async(object()),
            await queries.load_latest_mttb_async(object()),
            await queries.load_war_room_evidence_async(object()),
        )

    summary, distribution, graph, mttb, evidence = asyncio.run(run())
    assert summary == {"ok": True}
    assert distribution == {}
    assert graph == {"limit": 60}
    assert mttb == 1.5
    assert evidence == {"ok": True}
