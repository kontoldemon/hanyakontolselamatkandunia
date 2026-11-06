"""Cover remaining session replay variants."""

from __future__ import annotations

import time
from datetime import UTC, datetime

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


def test_session_replay_variants(monkeypatch) -> None:
    now = time.time()
    now_dt = datetime.fromtimestamp(now, tz=UTC)
    old_dt = datetime.fromtimestamp(now - 500, tz=UTC)
    timeline = [
        (now_dt, "cloudsentinel.command.input", "id", "", "", "", "bad", "", "", ""),
        ("bad", "cloudsentinel.command.output", "", "id", "", "", 0, "", "", ""),
        (now_dt, "cloudsentinel.login.failed", "", "", "root", "toor", 1, "publickey", "", ""),
    ]
    row = (
        "sess-variants",
        "10.1.1.1",
        "US",
        "United States",
        "City",
        "1",
        "2",
        "UTC",
        old_dt,
        old_dt,
        old_dt,
        None,
        "",
        "kex;enc",
        "",
        "none",
        0.0,
        timeline,
        [],
        10,
    )
    fallback = (
        "sess-fallback",
        "10.1.1.2",
        "XX",
        "",
        "",
        "",
        "",
        "",
        old_dt,
        old_dt,
        old_dt,
        None,
        "",
        "",
        "SSH-2.0-test",
        "none",
        0.0,
        [(now_dt, "cloudsentinel.session.connect", "", "", "", "", 0, "", "", "")],
        [],
        10,
    )
    settings = _settings(monkeypatch, [row, fallback])
    sessions = _load_recent_sessions_from_clickhouse(settings)
    assert len(sessions) == 2
    assert any(item["id"] == "sess-variants" for item in sessions)
