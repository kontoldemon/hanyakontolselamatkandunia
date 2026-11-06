"""Two final direct server helper calls."""

from __future__ import annotations

import asyncio
import builtins
import sys

from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSSHServer, CloudSentinelSession, ConnectionLimiter, TTYLogger


def test_final_command_resolution_and_cd() -> None:
    server = CloudSentinelSSHServer(
        load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env"),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=1),
    )
    session = CloudSentinelSession(server)
    assert session._resolve_command("cat")
    session.vfs.context.cwd = "/root"
    session._handle_cd([".."])


def test_final_tty_sync(monkeypatch, tmp_path) -> None:
    logger = TTYLogger("tty-sync-final")
    logger._dir = tmp_path
    logger.record(b"x")
    monkeypatch.setitem(sys.modules, "aiofiles", None)
    monkeypatch.setattr(builtins, "open", lambda *_a, **_k: (_ for _ in ()).throw(OSError("open")))
    asyncio.run(logger.save_async())
