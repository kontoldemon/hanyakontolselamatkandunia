"""Final TTY fallback and session helper branches."""

from __future__ import annotations

import asyncio
import builtins
import sys

from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import (
    CloudSentinelSSHServer,
    CloudSentinelSession,
    ConnectionLimiter,
    TTYLogger,
)


def test_tty_sync_fallback_exception(monkeypatch, tmp_path) -> None:
    logger = TTYLogger("tty-final-98b")
    logger._dir = tmp_path
    logger.record(b"x")
    monkeypatch.setitem(sys.modules, "aiofiles", None)
    monkeypatch.setattr(builtins, "open", lambda *_a, **_k: (_ for _ in ()).throw(OSError("open")))
    asyncio.run(logger.save_async())


def test_session_prompt_resolve_and_cd() -> None:
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
    session._handle_cd(["/tmp"])
