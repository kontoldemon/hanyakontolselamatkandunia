"""Final server metric-exception and shell branches."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.vfs import VirtualFileSystem
from cloudsentinel.server import CloudSentinelSSHServer, ConnectionLimiter


class FakePipeline:
    async def emit(self, _envelope: object) -> None:
        return None


class FakeSoar:
    async def process_event(self, _session: str, event: dict) -> dict:
        return event


class FakeConn:
    def get_extra_info(self, name: str, default: object = None) -> object:
        return ("8.8.8.8", 1234) if name == "peername" else default

    def close(self) -> None:
        return None


class FakeKey:
    def get_algorithm(self) -> bytes:
        return b"ssh-ed25519"


@pytest.mark.asyncio
async def test_server_metric_exception_branches(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    server = CloudSentinelSSHServer(
        settings,
        FakePipeline(),  # type: ignore[arg-type]
        FakeSoar(),  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=2),
    )
    monkeypatch.setitem(sys.modules, "cloudsentinel.metrics", None)
    server.connection_made(FakeConn())  # type: ignore[arg-type]
    server.connection_lost(None)
    assert server.validate_public_key("root", FakeKey()) is False  # type: ignore[arg-type]
    server.auth_completed()
    await asyncio.sleep(0)


