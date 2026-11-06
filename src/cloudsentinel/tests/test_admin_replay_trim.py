"""Final replay trim and session-output branches."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from cloudsentinel.admin_api import _load_recent_sessions_from_clickhouse, _trim_replay_entries
from cloudsentinel.config import load_settings


def test_trim_duplicate_info_and_stream() -> None:
    entries = [
        {"role": "honeypot", "text": "[OPEN] session", "timestamp": "1"},
        {"role": "honeypot", "text": "[OPEN] session", "timestamp": "1"},
        {"role": "attacker", "text": "id", "timestamp": "2"},
        {"role": "attacker", "text": "id", "timestamp": "2"},
    ]
    assert _trim_replay_entries(entries, limit=2)
    assert _trim_replay_entries(entries, limit=0)


def test_session_output_empty_and_echo(monkeypatch) -> None:
    now = time.time()
    ts = datetime.fromtimestamp(now, tz=UTC)
    timeline = [
        (ts, "cloudsentinel.command.input", "id", "", "", "", 0, "", "", ""),
        (ts, "cloudsentinel.command.output", "", "", "", "", 0, "", "", ""),
        (ts, "cloudsentinel.command.output", "", "id", "", "", 0, "", "", ""),
    ]
    row = (
        "sess-output",
        "8.8.8.8",
        "US",
        "United States",
        "",
        "",
        "",
        "",
        ts,
        ts,
        ts,
        None,
        "",
        "",
        "",
        "none",
        0.0,
        timeline,
        [],
        0,
    )

    class Result:
        result_rows = [row]

    class Client:
        def query(self, _query: str) -> Result:
            return Result()

    import types

    fake = types.ModuleType("clickhouse_connect")
    fake.get_client = lambda **_kwargs: Client()
    monkeypatch.setitem(__import__("sys").modules, "clickhouse_connect", fake)
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    assert _load_recent_sessions_from_clickhouse(settings)
