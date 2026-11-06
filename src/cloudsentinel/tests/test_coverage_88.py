"""Cover static VFS fallback and GeoIP HTTP failure branches."""

from __future__ import annotations

import sys

import cloudsentinel.geoip as geoip
from cloudsentinel.vfs import VirtualFileSystem


def test_vfs_without_faker(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "faker", None)
    vfs = VirtualFileSystem.generate_realistic_files()
    assert vfs.file_contents("/etc/hostname") == b"usas-prod-srv-01\n"
    assert vfs.file_contents("/root/.bash_history").startswith(b"ls -la")
    assert vfs.exists("/var/log/auth.log")


def test_geoip_reader_cache_and_http_failures(monkeypatch) -> None:
    marker = object()
    monkeypatch.setattr(geoip, "_geoip_reader", marker)
    assert geoip._get_reader() is marker

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return (
                b'{"success":true,"country_code":"USA","country":"United States",'
                b'"city":"Ashburn","region":"Virginia","continent_code":"NA",'
                b'"latitude":39,"longitude":-77,"timezone":{"id":"UTC"},'
                b'"connection":{"asn":1,"isp":"ISP","org":"ORG","type":"hosting"}}'
            )

    geoip._geoip_http_cache.clear()
    monkeypatch.setattr(geoip.urllib.request, "urlopen", lambda *_a, **_k: FakeResponse())
    enriched = geoip._enrich_http("8.8.8.8")
    assert enriched is not None
    assert enriched["country_code"] == "XX"

    def fail(*_args, **_kwargs):
        raise RuntimeError("http down")

    geoip._geoip_http_cache.clear()
    monkeypatch.setattr(geoip.urllib.request, "urlopen", fail)
    assert geoip._enrich_http("8.8.4.4") is None
