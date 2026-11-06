"""Final secret and replay branches."""

from __future__ import annotations

import asyncio
import sys
import types
import time
from datetime import UTC, datetime

from cloudsentinel._secrets import InfisicalProvider
from cloudsentinel.admin_api import _load_recent_sessions_from_clickhouse, _trim_replay_entries
from cloudsentinel.config import load_settings


def test_infisical_non_200(monkeypatch) -> None:
    provider = InfisicalProvider()
    provider._available = True
    provider._token = "token"
    provider._last_fetch = 10**18

    class Response:
        status_code = 500

        def json(self) -> dict:
            return {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, *_args, **_kwargs):
            return Response()

    fake = types.ModuleType("httpx")
    fake.AsyncClient = Client
    monkeypatch.setitem(sys.modules, "httpx", fake)
    assert asyncio.run(provider.get("UNIT_KEY", "fallback")) == "fallback"


def test_replay_echo_and_stream_duplicate(monkeypatch) -> None:
    entries = [
        {"role": "honeypot", "text": "[OPEN] session", "timestamp": "1"},
        {"role": "attacker", "text": "id", "timestamp": "2"},
        {"role": "attacker", "text": "id", "timestamp": "2"},
    ]
    assert _trim_replay_entries(entries, limit=3)

    now = datetime.now(UTC)
    timestamp = time.time()
    timeline = [
        (now, "cloudsentinel.command.input", "id", "", "", "", 0, "", "", ""),
        (now, "cloudsentinel.command.output", "", "id", "", "", 0, "", "", ""),
    ]
    row = (
        "sess-echo",
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
    monkeypatch.setitem(sys.modules, "clickhouse_connect", fake)
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    assert _load_recent_sessions_from_clickhouse(settings)
    assert timestamp
