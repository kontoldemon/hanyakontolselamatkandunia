"""Final replay and module-entry branches."""

from __future__ import annotations

import asyncio
import types
from datetime import UTC, datetime

import cloudsentinel.server as server_module
from cloudsentinel.admin_api import _load_recent_sessions_from_clickhouse, _trim_replay_entries
from cloudsentinel.config import load_settings


def test_replay_echo_prefix() -> None:
    now = datetime.now(UTC)
    timeline = [
        (now, "cloudsentinel.command.input", "id", "", "", "", 0, "", "", ""),
        (now, "cloudsentinel.command.output", "", "id extra", "", "", 0, "", "", ""),
    ]
    row = (
        "sess-echo-prefix",
        "8.8.8.8",
        "XX",
        "",
        "",
        "",
        "",
        "",
        now,
        now,
        now,
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

    fake = types.ModuleType("clickhouse_connect")
    fake.get_client = lambda **_kwargs: Client()
    import sys

    sys.modules["clickhouse_connect"] = fake
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    assert _load_recent_sessions_from_clickhouse(settings)


def test_replay_stream_duplicate() -> None:
    entries = [
        {"role": "honeypot", "text": "[OPEN]", "timestamp": "1"},
        {"role": "attacker", "text": "id", "timestamp": "2"},
        {"role": "attacker", "text": "id", "timestamp": "2"},
    ]
    assert _trim_replay_entries(entries, limit=3)


def test_server_main_entry(monkeypatch) -> None:
    from pathlib import Path

    path = Path(server_module.__file__)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    real_run = asyncio.run

    def close(coro):
        coro.close()

    monkeypatch.setattr(asyncio, "run", close)
    try:
        exec(code, {"__name__": "__main__", "__package__": "cloudsentinel", "__file__": str(path)})
    finally:
        monkeypatch.setattr(asyncio, "run", real_run)
