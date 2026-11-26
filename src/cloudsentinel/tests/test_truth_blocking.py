"""Truth checks: dry-run blocks never count as enforcement and wide queries scale."""

from __future__ import annotations

import sys
import types

from cloudsentinel.admin_api import (
    _load_recent_events_from_clickhouse,
    _load_truth_summary_from_clickhouse,
)
from cloudsentinel.config import load_settings
from cloudsentinel.soar import ENFORCED_BLOCK_ACTIONS, NEW_BLOCK_ACTIONS


class FakeResult:
    def __init__(self, rows: list) -> None:
        self.result_rows = rows


class CapturingClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def query(self, query: str) -> FakeResult:
        self.queries.append(query)
        if "AS total_events" in query:
            return FakeResult([[10, 2, 1, 1, 5, 3, 4, 2, 3, 2, 12.0, 40.0]])
        return FakeResult([])


def _settings():
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    return settings


def _install(monkeypatch, client: CapturingClient) -> None:
    module = types.ModuleType("clickhouse_connect")
    module.get_client = lambda **_kwargs: client
    monkeypatch.setitem(sys.modules, "clickhouse_connect", module)


def test_dry_run_is_not_an_enforced_block() -> None:
    assert "dry_run_block" not in ENFORCED_BLOCK_ACTIONS
    assert "dry_run_block" not in NEW_BLOCK_ACTIONS
    assert NEW_BLOCK_ACTIONS <= ENFORCED_BLOCK_ACTIONS
    assert "iptables_block" in NEW_BLOCK_ACTIONS


def test_truth_summary_query_counts_only_enforced_blocks(monkeypatch) -> None:
    client = CapturingClient()
    _install(monkeypatch, client)
    summary = _load_truth_summary_from_clickhouse(_settings())
    assert summary is not None
    query = client.queries[-1]
    assert "dry_run_block" not in query
    assert "'iptables_block'" in query
    assert "'eventgrid_published'" in query


def test_wide_event_query_uses_requested_limit(monkeypatch) -> None:
    client = CapturingClient()
    _install(monkeypatch, client)
    settings = _settings()
    _load_recent_events_from_clickhouse(settings, limit=999999)
    assert "LIMIT 20000" in client.queries[-1]
    monkeypatch.setenv("CLOUDSENTINEL_EVENTS_MAX_LIMIT", "50000")
    _load_recent_events_from_clickhouse(settings, limit=999999)
    assert "LIMIT 50000" in client.queries[-1]
    monkeypatch.setenv("CLOUDSENTINEL_EVENTS_MAX_LIMIT", "not-a-number")
    _load_recent_events_from_clickhouse(settings, limit=5)
    assert "LIMIT 5" in client.queries[-1]
