"""Final admin edge tests for gate 99."""

from __future__ import annotations

import asyncio
import types
from datetime import UTC, datetime

import cloudsentinel.admin_api as admin_module
from cloudsentinel.admin_api import _load_recent_events_from_clickhouse, _trim_replay_entries
from cloudsentinel.config import load_settings


def test_replay_trim_duplicate_paths() -> None:
    entries = [
        {"role": "honeypot", "text": "same", "timestamp": "1"},
        {"role": "honeypot", "text": "same", "timestamp": "1"},
        {"role": "attacker", "text": "cmd", "timestamp": "2"},
        {"role": "attacker", "text": "cmd", "timestamp": "2"},
    ]
    assert len(_trim_replay_entries(entries, limit=1)) == 1


def test_event_output_empty_and_echo(monkeypatch) -> None:
    now = datetime.now(UTC)

    def row(eventid: str, input_value: str, reason: str) -> tuple:
        return (
            eventid,
            "8.8.8.8",
            "XX",
            "",
            "",
            "",
            "",
            "",
            input_value,
            "",
            "",
            "",
            "",
            "",
            reason,
            "",
            "",
            [],
            "none",
            0,
            0.0,
            now,
        )

    class Result:
        result_rows = [
            row("cloudsentinel.command.output", "", ""),
            row("cloudsentinel.command.input", "id", ""),
            row("cloudsentinel.command.output", "", "id"),
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
    assert _load_recent_events_from_clickhouse(settings)


def test_digitalocean_non_dict_rule(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    monkeypatch.setattr(admin_module, "_do_firewall_id", lambda: "fw")
    monkeypatch.setattr(admin_module, "_do_token", lambda: "token")
    monkeypatch.setattr(admin_module, "_do_api_base", lambda: "https://do.test")
    monkeypatch.setattr(admin_module, "_exposure_target_ports", lambda _settings: [22])
    before = {"firewall": {"name": "fw", "inbound_rules": ["bad"], "outbound_rules": []}}
    after = {"firewall": {"name": "fw", "inbound_rules": [], "outbound_rules": []}}
    queue = [(200, before, ""), (202, {}, ""), (200, after, "")]

    async def fake_http(_method: str, _url: str, _token: str, payload=None, **_kwargs):
        return queue.pop(0)

    monkeypatch.setattr(admin_module, "_http_json", fake_http)
    result = asyncio.run(admin_module._toggle_exposure_digitalocean(False, settings))
    assert result["ok"] is True
