"""Cover ClickHouse loader failure paths and event-row fallbacks."""

from __future__ import annotations

import types

import cloudsentinel.admin_api as admin_module
from cloudsentinel.config import load_settings


def test_loader_failures(monkeypatch) -> None:
    fake = types.ModuleType("clickhouse_connect")

    def fail(**_kwargs: object) -> None:
        raise RuntimeError("clickhouse down")

    fake.get_client = fail
    monkeypatch.setitem(__import__("sys").modules, "clickhouse_connect", fake)
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    assert admin_module._load_recent_sessions_from_clickhouse(settings) == []
    assert admin_module._load_recent_events_from_clickhouse(settings) == []
    assert admin_module._latest_mttb_from_clickhouse(settings) == 0.0
    assert admin_module._load_attack_distribution_from_clickhouse(settings)["Brute Force"] == 0
    assert admin_module._load_attack_graph_from_clickhouse(settings) == {"nodes": [], "edges": []}
    assert admin_module._load_truth_summary_from_clickhouse(settings) is None
    assert admin_module._load_war_room_evidence_from_clickhouse(settings)["source"] == "runtime"


def test_event_row_epoch_and_noise(monkeypatch) -> None:
    class Result:
        result_rows = [
            (
                "cloudsentinel.command.output",
                "8.8.8.8",
                "XX",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "cloudsentinel.internal",
                "",
                "",
                [],
                "none",
                0,
                0.0,
                "not-a-datetime",
            ),
            (
                "cloudsentinel.command.input",
                "8.8.4.4",
                "US",
                "United States",
                "",
                "",
                "",
                "",
                "id",
                "",
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
                None,
            ),
        ]

    class Client:
        def query(self, _query: str) -> Result:
            return Result()

    fake = types.ModuleType("clickhouse_connect")
    fake.get_client = lambda **_kwargs: Client()
    monkeypatch.setitem(__import__("sys").modules, "clickhouse_connect", fake)
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    events = admin_module._load_recent_events_from_clickhouse(settings)
    assert len(events) >= 1
    assert any(event["eventid"] == "cloudsentinel.command.input" for event in events)
