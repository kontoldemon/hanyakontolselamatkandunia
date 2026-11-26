"""Final branches for attack graph, GeoIP, shell redirects, and secrets."""

from __future__ import annotations

import asyncio
import sys
import types

from cloudsentinel.geoip import _get_reader
from cloudsentinel import geoip as geoip_module
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




def test_geoip_import_error(monkeypatch) -> None:
    monkeypatch.setattr(geoip_module, "_geoip_reader", None)
    monkeypatch.setitem(sys.modules, "geoip2", None)
    monkeypatch.setitem(sys.modules, "geoip2.database", None)
    assert _get_reader() is None




