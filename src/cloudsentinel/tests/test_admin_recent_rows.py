"""Coverage for admin ClickHouse recent events and sessions row parsing."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from cloudsentinel.admin_api import (
    _load_recent_events_from_clickhouse,
    _load_recent_sessions_from_clickhouse,
)
from cloudsentinel.config import load_settings


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self.result_rows = rows


class _FakeClickHouse:
    def __init__(self, rows: list) -> None:
        self.rows = rows

    def query(self, _query: str) -> _FakeResult:
        return _FakeResult(self.rows)


def _settings_with_rows(monkeypatch: pytest.MonkeyPatch, rows: list):
    import clickhouse_connect

    monkeypatch.setattr(
        clickhouse_connect,
        "get_client",
        lambda **_kwargs: _FakeClickHouse(rows),
    )
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    return settings


def test_recent_events_row_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    row = (
        "cloudsentinel.command.input",
        "10.1.1.1",
        "US",
        "United States",
        "Test City",
        "1.5",
        "2.5",
        "UTC",
        "whoami",
        "root",
        "toor",
        "a" * 32,
        "kex;enc;mac;comp",
        "SSH-2.0-test",
        "",
        "",
        "",
        ["T1105"],
        "iptables_block",
        80,
        12.5,
        now,
    )
    noise_row = (
        "cloudsentinel.session.connect",
        "10.1.1.2",
        "US",
        "United States",
        "Test",
        "0",
        "0",
        "UTC",
        "",
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
        now,
    )
    settings = _settings_with_rows(monkeypatch, [row, noise_row])
    events = _load_recent_events_from_clickhouse(settings)
    assert len(events) == 1
    event = events[0]
    assert event["eventid"] == "cloudsentinel.command.input"
    assert event["input"] == "whoami"
    assert event["username"] == "root"
    assert event["hassh_md5"] == "a" * 32
    assert event["cloudsentinel_risk_score"] == 80
    assert event["mttb_ms"] == 12.5


def test_recent_sessions_row_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    connect_ts = datetime.fromtimestamp(time.time() - 100, tz=UTC)
    last_ts = datetime.now(UTC)
    timeline = [
        (connect_ts, "cloudsentinel.session.connect", "", "", "", "", 0, "", "", ""),
        (connect_ts, "cloudsentinel.login.failed", "", "", "root", "toor", 1, "password", "", ""),
        (connect_ts, "cloudsentinel.command.input", "whoami", "", "", "", 0, "", "", ""),
        (connect_ts, "cloudsentinel.command.output", "", "root\n", "", "", 0, "", "", ""),
        (last_ts, "cloudsentinel.command.input", "cloudsentinel.hidden", "", "", "", 0, "", "", ""),
        (last_ts, "cloudsentinel.login.success", "", "", "root", "toor", 0, "", "", ""),
        (last_ts, "cloudsentinel.client.version", "", "", "", "", 0, "", "SSH-2.0-test", ""),
        (last_ts, "cloudsentinel.session.closed", "", "", "", "", 0, "", "", "12.5"),
    ]
    row = (
        "sess-1",
        "10.1.1.1",
        "US",
        "United States",
        "Test City",
        "1.5",
        "2.5",
        "UTC",
        connect_ts,
        last_ts,
        connect_ts,
        None,
        "",
        "kex;enc;mac;comp",
        "SSH-2.0-test",
        "iptables_block",
        12.5,
        timeline,
        ["T1105"],
        80,
    )
    settings = _settings_with_rows(monkeypatch, [row])
    sessions = _load_recent_sessions_from_clickhouse(settings)
    assert len(sessions) == 1
    session = sessions[0]
    assert session["id"] == "sess-1"
    assert session["ip"] == "10.1.1.1"
    assert session["status"] == "Active"
    assert session["riskScore"] == 80
    assert session["commands"] if "commands" in session else session["input"] == ["whoami"]
    assert session["soarAction"] == "iptables_block"
    assert session["replay"]
