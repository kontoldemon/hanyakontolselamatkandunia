"""Cover the ClickHouse dashboard loaders with an in-memory fake client."""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime

from cloudsentinel.admin_api import (
    _latest_mttb_from_clickhouse,
    _load_attack_distribution_from_clickhouse,
    _load_attack_graph_from_clickhouse,
    _load_recent_events_from_clickhouse,
    _load_truth_summary_from_clickhouse,
    _load_war_room_evidence_from_clickhouse,
)
from cloudsentinel.config import load_settings


class FakeResult:
    def __init__(self, rows: list) -> None:
        self.result_rows = rows


class FakeClient:
    def __init__(self, rows: list, events_rows: list | None = None) -> None:
        self.rows = rows
        self.events_rows = events_rows or []

    def query(self, query: str) -> FakeResult:
        if "arrayDistinct" in query:
            return FakeResult(self.rows)
        if "AS total_events" in query:
            return FakeResult(self.rows)
        if "last_online_ms" in query:
            return FakeResult(self.rows)
        if "anyLast(mttb_ms)" in query:
            return FakeResult(self.rows)
        if "eventid, count() AS hits" in query:
            return FakeResult(self.rows)
        if "AS source" in query:
            return FakeResult(self.events_rows)
        return FakeResult([])


def install_fake(monkeypatch, client: FakeClient) -> None:
    module = types.ModuleType("clickhouse_connect")
    module.get_client = lambda **_kwargs: client
    monkeypatch.setitem(sys.modules, "clickhouse_connect", module)


def settings_with_clickhouse():
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    return settings


def test_attack_graph_loader(monkeypatch) -> None:
    rows = [
        ["8.8.8.8", 3, 90, ["T1110", "T1021.004", "T1059", "T1071"], "c" * 32],
        ["8.8.4.4", 1, 50, ["T1110"], "c" * 32],
    ]
    install_fake(monkeypatch, FakeClient(rows))
    graph = _load_attack_graph_from_clickhouse(settings_with_clickhouse())
    assert graph["nodes"]
    assert graph["edges"]
    assert any(node["type"] == "fingerprint" for node in graph["nodes"])


def test_truth_summary_loader(monkeypatch) -> None:
    rows = [[100, 5, 3, 2, 40, 10, 20, 8, 5, 4, 1200.0, 55.0]]
    install_fake(monkeypatch, FakeClient(rows))
    summary = _load_truth_summary_from_clickhouse(settings_with_clickhouse())
    assert summary is not None
    assert summary["total_events"] == 100
    assert summary["block_rate"] == 12.5
    assert summary["avg_risk"] == 55.0


def test_war_room_and_mttb_loaders(monkeypatch) -> None:
    settings = settings_with_clickhouse()
    install_fake(monkeypatch, FakeClient([(123456, 123000)]))
    evidence = _load_war_room_evidence_from_clickhouse(settings)
    assert evidence["source"] == "clickhouse"
    assert evidence["last_online_at"] == 123456

    install_fake(monkeypatch, FakeClient([(1200.0,)]))
    assert _latest_mttb_from_clickhouse(settings) == 1200.0

    install_fake(
        monkeypatch,
        FakeClient(
            [
                ["cloudsentinel.login.failed", 7],
                ["cloudsentinel.command.input", 4],
                ["cloudsentinel.session.connect", 2],
                ["cloudsentinel.http.request", 1],
            ]
        ),
    )
    distribution = _load_attack_distribution_from_clickhouse(settings)
    assert distribution["Brute Force"] == 7
    assert distribution["Malware Upload"] == 1


def test_empty_clickhouse_results(monkeypatch) -> None:
    settings = settings_with_clickhouse()
    install_fake(monkeypatch, FakeClient([]))
    assert _load_truth_summary_from_clickhouse(settings) is None
    assert _latest_mttb_from_clickhouse(settings) == 0.0
    evidence = _load_war_room_evidence_from_clickhouse(settings)
    assert evidence["authoritative"] is True
    assert _load_attack_graph_from_clickhouse(settings) == {"nodes": [], "edges": []}


def test_recent_events_loader(monkeypatch) -> None:
    noise = [
        "cloudsentinel.session.connect",
        "8.8.8.8",
        "US",
        "United States",
        "Ashburn",
        "39.0",
        "-77.5",
        "UTC",
        "",
        "root",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        [],
        "none",
        0,
        0.0,
        datetime.now(UTC),
    ]
    valid = [
        "cloudsentinel.command.input",
        "8.8.4.4",
        "SG",
        "Singapore",
        "Singapore",
        "1.3",
        "103.8",
        "Asia/Singapore",
        "id",
        "root",
        "",
        "d" * 32,
        "hmac-sha2-256",
        "SSH-2.0-OpenSSH_8.9",
        "exec",
        "manual",
        "block",
        ["T1059"],
        "blocked",
        80,
        900.0,
        datetime.now(UTC),
    ]
    install_fake(monkeypatch, FakeClient([], events_rows=[noise, valid]))
    events = _load_recent_events_from_clickhouse(settings_with_clickhouse())
    assert len(events) == 1
    assert events[0]["eventid"] == "cloudsentinel.command.input"
    assert events[0]["response_mode"] == "block"
    assert events[0]["cloudsentinel_mitre_techniques"] == ["T1059"]
