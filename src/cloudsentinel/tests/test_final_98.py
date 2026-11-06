"""Cover event-row replay edges and final server helpers."""

from __future__ import annotations

import asyncio
import builtins
import sys
import types
from datetime import UTC, datetime

import pytest

import cloudsentinel.admin_api as admin_module
import cloudsentinel.server as server_module
from cloudsentinel.admin_api import _load_recent_events_from_clickhouse, _load_recent_sessions_from_clickhouse
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSSHServer, CloudSentinelSession, ConnectionLimiter, TTYLogger


class Result:
    def __init__(self, rows: list) -> None:
        self.result_rows = rows


class Client:
    def __init__(self, rows: list) -> None:
        self.rows = rows

    def query(self, _query: str) -> Result:
        return Result(self.rows)


def _settings(monkeypatch, rows: list):
    import clickhouse_connect

    monkeypatch.setattr(clickhouse_connect, "get_client", lambda **_kwargs: Client(rows))
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    return settings


def _event(eventid: str, input_value: str = "", reason: str = "") -> tuple:
    return (
        eventid,
        "8.8.8.8",
        "US",
        "United States",
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
        datetime.now(UTC),
    )


def test_event_replay_edges(monkeypatch) -> None:
    rows = [
        _event("cloudsentinel.command.output", "", ""),
        _event("cloudsentinel.command.input", "id"),
        _event("cloudsentinel.command.output", "", "id"),
        _event("cloudsentinel.command.input", "cloudsentinel.internal", "cloudsentinel.internal"),
    ]
    settings = _settings(monkeypatch, rows)
    events = _load_recent_events_from_clickhouse(settings)
    assert len(events) >= 3


def test_session_hassh_failures(monkeypatch) -> None:
    now = datetime.now(UTC)
    row = (
        "sess-hassh",
        "8.8.8.8",
        "US",
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
        "kex",
        "",
        "none",
        0.0,
        [],
        [],
        0,
    )
    settings = _settings(monkeypatch, [row])
    import hashlib

    monkeypatch.setattr(hashlib, "md5", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("md5")))
    assert len(_load_recent_sessions_from_clickhouse(settings)) == 1

    fallback_row = list(row)
    fallback_row[12] = ""
    fallback_row[13] = ""
    fallback_row[14] = "SSH-2.0-test"
    monkeypatch.setattr(
        admin_module,
        "fallback_hassh_from_version",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fallback")),
    )
    settings = _settings(monkeypatch, [tuple(fallback_row)])
    assert len(_load_recent_sessions_from_clickhouse(settings)) == 1


def test_unknown_client_with_known_hassh(monkeypatch) -> None:
    now = datetime.now(UTC)
    row = (
        "sess-known",
        "8.8.8.8",
        "US",
        "",
        "",
        "",
        "",
        "",
        now,
        now,
        now,
        None,
        "b" * 32,
        "",
        "",
        "none",
        0.0,
        [],
        [],
        0,
    )
    settings = _settings(monkeypatch, [row])
    monkeypatch.setattr(admin_module, "infer_client_software", lambda *_a: "unknown")
    monkeypatch.setattr(admin_module.HASSHDNA, "lookup", lambda _self, _h: {"client_software": "KnownBot"})
    sessions = _load_recent_sessions_from_clickhouse(settings)
    assert sessions[0]["client"] == "KnownBot"


def test_tty_and_session_final(monkeypatch, tmp_path) -> None:
    logger = TTYLogger("tty-final-98")
    logger._dir = tmp_path
    logger.record(b"x")
    monkeypatch.setitem(sys.modules, "aiofiles", None)
    monkeypatch.setattr(builtins, "open", lambda *_a, **_k: (_ for _ in ()).throw(OSError("open")))
    asyncio.run(logger.save_async())
    monkeypatch.undo()

    server = CloudSentinelSSHServer(
        load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env"),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=1),
    )
    session = CloudSentinelSession(server)
    session.data_received("\r", None)
    assert session._resolve_command("id")
    session._handle_cd([".."])
