"""Cover DNS honeypot truncation, parsing, and stats branches."""

from __future__ import annotations

import struct

import pytest

from cloudsentinel.dns_honeypot import DNSHoneypot


def _query(name: str = "unit.test") -> bytes:
    labels = b"".join(bytes([len(label)]) + label.encode() for label in name.split("."))
    return (
        b"\x12\x34"
        + struct.pack("!H", 0x0100)
        + struct.pack("!H", 1)
        + b"\x00\x00" * 3
        + labels
        + b"\x00"
        + struct.pack("!H", 1)
        + struct.pack("!H", 1)
    )


class FakeTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple[str, int]]] = []

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.sent.append((data, addr))


@pytest.mark.asyncio
async def test_dns_query_paths() -> None:
    honeypot = DNSHoneypot(max_response_size=1)
    events: list[dict] = []
    honeypot.set_event_callback(events.append)
    transport = FakeTransport()
    await honeypot._handle_query(_query(), ("8.8.8.8", 4444), transport)  # type: ignore[arg-type]
    assert events
    assert transport.sent
    assert transport.sent[0][0][2] & 0x02  # TC flag set

    await honeypot._handle_query(b"short", ("8.8.8.8", 4444), transport)  # type: ignore[arg-type]
    empty = b"\x00" * 12
    await honeypot._handle_query(empty, ("8.8.8.8", 4444), transport)  # type: ignore[arg-type]
    await honeypot._handle_query(_query(), ("8.8.8.8", 4444), None)
    assert honeypot.stats["total_queries"] >= 1


def test_dns_parse_and_build() -> None:
    assert DNSHoneypot._parse_qname(b"\x03www\x03com\x00", 0) == "www.com"
    assert DNSHoneypot._parse_qname(b"\xc0", 0) == ""
    assert DNSHoneypot._parse_qname(b"\x05ab", 0) == ""
    assert DNSHoneypot._parse_qname(b"\xc0\x02\x03www\x00", 0) == "www"
    assert DNSHoneypot._parse_qname(b"", 0) == ""
    assert DNSHoneypot._parse_qname(b"\x00", 0) == ""
    response = DNSHoneypot._build_truncated_response(b"\x12\x34", "unit.test")
    assert response[:2] == b"\x12\x34"
    assert DNSHoneypot._build_response(b"\x12\x34", "unit.test", "10.0.0.4")


def test_dns_rate_limit_and_stats() -> None:
    honeypot = DNSHoneypot(max_queries_per_ip=1, rate_window_seconds=60)
    assert honeypot._check_rate_limit("8.8.8.8") is True
    assert honeypot._check_rate_limit("8.8.8.8") is False
    assert honeypot.stats["rate_limited_ips"] == 1
    assert honeypot.stats["active_rate_limiters"] == 1
