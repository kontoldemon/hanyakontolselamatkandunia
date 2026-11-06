"""Cover session replay branches for auth type, echo, stale sessions, and HASSH clients."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from cloudsentinel.admin_api import _load_recent_sessions_from_clickhouse
from cloudsentinel.config import load_settings


class FakeResult:
    def __init__(self, rows: list) -> None:
        self.result_rows = rows


class FakeClient:
    def __init__(self, rows: list) -> None:
        self.rows = rows

    def query(self, _query: str) -> FakeResult:
        return FakeResult(self.rows)


def _settings(monkeypatch, rows: list):
    import clickhouse_connect

    monkeypatch.setattr(clickhouse_connect, "get_client", lambda **_kwargs: FakeClient(rows))
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    return settings


def test_session_replay_rich_rows(monkeypatch) -> None:
    now = time.time()
    now_dt = datetime.fromtimestamp(now, tz=UTC)
    old_dt = datetime.fromtimestamp(now - 500, tz=UTC)
    connect_dt = datetime.fromtimestamp(now - 1000, tz=UTC)
    close_dt = datetime.fromtimestamp(now - 200, tz=UTC)
    timeline = [
        (connect_dt, "cloudsentinel.session.connect", "", "", "", "", 0, "", "", ""),
        (connect_dt, "cloudsentinel.login.failed", "", "", "root", "toor", 2, "publickey", "", ""),
        (connect_dt, "cloudsentinel.command.input", "whoami", "", "", "", 0, "", "", ""),
        (connect_dt, "cloudsentinel.command.output", "", "whoami", "", "", 0, "", "", ""),
        (connect_dt, "cloudsentinel.command.output", "", "root\n", "", "", 0, "", "", ""),
        (now_dt, "cloudsentinel.login.success", "", "", "root", "toor", 0, "", "", ""),
        (now_dt, "cloudsentinel.client.version", "", "", "", "", 0, "", "SSH-2.0-test", ""),
        (close_dt, "cloudsentinel.session.closed", "", "", "", "", 0, "", "", "12.5"),
    ]
    row = (
        "sess-rich",
        "10.1.1.1",
        "US",
        "United States",
        "City",
        "1.5",
        "2.5",
        "UTC",
        old_dt,
        old_dt,
        connect_dt,
        close_dt,
        "",
        "kex;enc;mac;comp",
        "SSH-2.0-test",
        "iptables_block",
        12.5,
        timeline,
        ["T1105"],
        80,
    )
    bad_timeline = [
        ("bad",),
        (now_dt, "cloudsentinel.command.output", "", "[redacted]", "", "", 0, "", "", ""),
    ]
    unknown_row = (
        "sess-unknown",
        "10.1.1.2",
        "XX",
        "",
        "",
        "",
        "",
        "",
        old_dt,
        old_dt,
        connect_dt,
        None,
        "b" * 32,
        "",
        "",
        "none",
        0.0,
        bad_timeline,
        [],
        10,
    )
    settings = _settings(monkeypatch, [row, unknown_row])
    sessions = _load_recent_sessions_from_clickhouse(settings)
    assert len(sessions) == 2
    rich = next(item for item in sessions if item["id"] == "sess-rich")
    assert rich["fingerprint"]
    assert rich["replay"]
    unknown = next(item for item in sessions if item["id"] == "sess-unknown")
    assert unknown["client"].startswith("hassh:")
