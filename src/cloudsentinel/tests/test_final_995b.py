"""Two final direct branch checks."""

from __future__ import annotations

import asyncio
import sys
import types

from cloudsentinel._secrets import InfisicalProvider
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSSHServer, CloudSentinelSession, ConnectionLimiter


def test_infisical_status(monkeypatch) -> None:
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


def test_resolve_cat() -> None:
    server = CloudSentinelSSHServer(
        load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env"),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=1),
    )
    session = CloudSentinelSession(server)
    assert session._resolve_command("cat")
