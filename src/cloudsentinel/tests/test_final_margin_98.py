"""Small margin batch for HTTP error parsing and session helpers."""

from __future__ import annotations

import asyncio
import io
import urllib.error

import cloudsentinel.admin_api as admin_module
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSSHServer, CloudSentinelSession, ConnectionLimiter






def test_session_prompt_and_resolution() -> None:
    server = CloudSentinelSSHServer(
        load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env"),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=1),
    )
    session = CloudSentinelSession(server)
    session.data_received("\r", None)
    assert session._resolve_command("cat")
