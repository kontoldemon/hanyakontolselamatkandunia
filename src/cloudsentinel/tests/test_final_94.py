"""Final branches for attack graph, GeoIP, shell redirects, and secrets."""

from __future__ import annotations

import asyncio
import sys
import types

from cloudsentinel._secrets import InfisicalProvider
from cloudsentinel.attack_graph import AttackGraph
from cloudsentinel.geoip import _get_reader
from cloudsentinel import geoip as geoip_module
from cloudsentinel.shell import HoneyPotInteractiveProtocol
from cloudsentinel.vfs import VirtualFileSystem


class FakeTransport:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    async def read(self, _size: int) -> bytes:
        return b""

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def close(self) -> None:
        return None


def test_attack_graph_edges_and_depth() -> None:
    graph = AttackGraph()
    base = {
        "src_ip": "1.1.1.1",
        "session": "s1",
        "eventid": "cloudsentinel.command.input",
        "input": "id",
        "cloudsentinel_mitre_techniques": ["T1059"],
    }
    graph.add_event(base)
    graph.add_event({**base, "session": "s2"})
    assert graph.get_subgraph("1.1.1.1", depth=-1)["nodes"] == []

    graph.add_event(
        {
            "src_ip": "2.2.2.2",
            "session": "s3",
            "eventid": "cloudsentinel.command.input",
            "input": "ssh root@1.1.1.1",
        }
    )
    assert graph.get_subgraph("1.1.1.1")["edges"]


def test_geoip_import_error(monkeypatch) -> None:
    monkeypatch.setattr(geoip_module, "_geoip_reader", None)
    monkeypatch.setitem(sys.modules, "geoip2", None)
    monkeypatch.setitem(sys.modules, "geoip2.database", None)
    assert _get_reader() is None


def test_shell_redirect_regression() -> None:
    session = HoneyPotInteractiveProtocol(
        FakeTransport(),
        VirtualFileSystem(),
        session_id="unit-final-shell",
        ip="10.0.0.1",
    )
    session._dispatch_line(">")
    session._dispatch_line("echo hello > /tmp/out")
    assert session._exit_code == 0


def test_infisical_status_and_exception(monkeypatch) -> None:
    provider = InfisicalProvider()
    provider._available = True
    provider._token = "token"

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

    fake_httpx = types.ModuleType("httpx")
    fake_httpx.AsyncClient = Client
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    assert asyncio.run(provider.get("UNIT_KEY", "fallback")) == "fallback"

    class Broken(Client):
        async def get(self, *_args, **_kwargs):
            raise RuntimeError("down")

    fake_httpx.AsyncClient = Broken
    assert asyncio.run(provider.get("UNIT_KEY", "fallback")) == "fallback"
