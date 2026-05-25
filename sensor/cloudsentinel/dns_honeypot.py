"""
CloudSentinel DNS Honeypot — lightweight UDP listener for DNS reconnaissance traps.
Catches attackers performing DNS lookups against the honeypot server.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
import time
from typing import Any

logger = logging.getLogger("cloudsentinel.dns")


class DNSHoneypot:
    """Async UDP DNS server that logs all queries and returns fake responses."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 53,
        fake_ns: str = "ns1.internal.usas.edu.my",
        fake_admin: str = "admin.internal.usas.edu.my",
    ) -> None:
        self.host = host
        self.port = port
        self.fake_ns = fake_ns
        self.fake_admin = fake_admin
        self._transport: asyncio.DatagramTransport | None = None
        self._event_callback: Any = None
        self._domains_queried: dict[str, int] = {}
        self._total_queries = 0

    def set_event_callback(self, callback: Any) -> None:
        self._event_callback = callback

    class Protocol(asyncio.DatagramProtocol):
        def __init__(self, honeypot: DNSHoneypot) -> None:
            self.hp = honeypot
            self.transport: asyncio.DatagramTransport | None = None

        def connection_made(self, transport: asyncio.DatagramTransport) -> None:
            self.transport = transport
            logger.info("DNS honeypot listening on UDP %s:%d", self.hp.host, self.hp.port)

        def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
            asyncio.create_task(self.hp._handle_query(data, addr, self.transport))

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self.Protocol(self),
            local_addr=(self.host, self.port),
        )
        logger.info("DNS honeypot started on %s:%d", self.host, self.port)

    async def _handle_query(
        self, data: bytes, addr: tuple[str, int], transport: asyncio.DatagramTransport | None
    ) -> None:
        if len(data) < 12:
            return
        try:
            transaction_id = data[:2]
            query_name = self._parse_qname(data, 12)
            if not query_name:
                return
            self._total_queries += 1
            self._domains_queried[query_name] = self._domains_queried.get(query_name, 0) + 1
            logger.info("DNS query: %s from %s:%d", query_name, addr[0], addr[1])
            if self._event_callback:
                self._event_callback({
                    "eventid": "cloudsentinel.dns.query",
                    "session": "dns",
                    "src_ip": addr[0],
                    "src_port": addr[1],
                    "domain": query_name,
                    "timestamp": time.time(),
                    "sensor": "CloudSentinel",
                })
            response = self._build_response(transaction_id, query_name, "10.0.0.4")
            if transport:
                transport.sendto(response, addr)
        except Exception as exc:
            logger.debug("DNS query handling error: %s", exc)

    @staticmethod
    def _parse_qname(data: bytes, offset: int) -> str:
        parts = []
        jumped = False
        max_hops = 10
        while max_hops > 0:
            max_hops -= 1
            if offset >= len(data):
                break
            length = data[offset]
            if length == 0:
                break
            if (length & 0xC0) == 0xC0:
                if not jumped:
                    offset = ((length & 0x3F) << 8) | data[offset + 1]
                    jumped = True
                    continue
                break
            offset += 1
            if offset + length > len(data):
                break
            parts.append(data[offset:offset + length].decode("ascii", errors="replace"))
            offset += length
        return ".".join(parts) if parts else ""

    @staticmethod
    def _build_response(trans_id: bytes, qname: str, ip: str) -> bytes:
        flags = struct.pack("!H", 0x8180)
        qdcount = struct.pack("!H", 1)
        ancount = struct.pack("!H", 1)
        nscount = struct.pack("!H", 0)
        arcount = struct.pack("!H", 0)
        labels = qname.split(".")
        qname_encoded = b"".join(
            bytes([len(label)]) + label.encode("ascii", errors="replace") for label in labels
        ) + bytes([0])
        qtype = struct.pack("!H", 1)
        qclass = struct.pack("!H", 1)
        answer_name = bytes([0xC0, 0x0C])
        answer_type = struct.pack("!H", 1)
        answer_class = struct.pack("!H", 1)
        answer_ttl = struct.pack("!I", 300)
        answer_rdlength = struct.pack("!H", 4)
        answer_rdata = socket.inet_aton(ip)
        return (
            trans_id + flags + qdcount + ancount + nscount + arcount +
            qname_encoded + qtype + qclass +
            answer_name + answer_type + answer_class + answer_ttl + answer_rdlength + answer_rdata
        )

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_queries": self._total_queries,
            "unique_domains": len(self._domains_queried),
            "top_domains": sorted(
                self._domains_queried.items(), key=lambda x: x[1], reverse=True
            )[:10],
        }
