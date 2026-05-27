"""
CloudSentinel DNS Honeypot — lightweight UDP listener for DNS reconnaissance traps.
Catches attackers performing DNS lookups against the honeypot server.

Includes per-IP rate limiting to prevent DNS amplification abuse and
response size caps to comply with EDNS0 best practices.
"""

from __future__ import annotations

import asyncio
import socket
import struct
import time
from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.dns")


class DNSHoneypot:
    """Async UDP DNS server with per-IP rate limiting and response size caps."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 53,
        fake_ns: str = "ns1.internal.usas.edu.my",
        fake_admin: str = "admin.internal.usas.edu.my",
        max_queries_per_ip: int = 60,
        rate_window_seconds: float = 60.0,
        max_response_size: int = 512,
    ) -> None:
        self.host = host
        self.port = port
        self.fake_ns = fake_ns
        self.fake_admin = fake_admin
        self.max_queries_per_ip = max_queries_per_ip
        self.rate_window_seconds = rate_window_seconds
        self.max_response_size = max_response_size
        self._transport: asyncio.DatagramTransport | None = None
        self._event_callback: Any = None
        self._domains_queried: dict[str, int] = {}
        self._total_queries = 0
        self._rate_limiter: dict[str, list[float]] = {}
        self._blocked_ips: set[str] = set()
        self._cleanup_task: asyncio.Task[None] | None = None

    def set_event_callback(self, callback: Any) -> None:
        self._event_callback = callback

    def _check_rate_limit(self, ip: str) -> bool:
        """Return True if the IP is allowed, False if rate-limited."""
        now = time.monotonic()
        if ip not in self._rate_limiter:
            self._rate_limiter[ip] = [now]
            return True

        timestamps = self._rate_limiter[ip]
        # Prune old entries
        cutoff = now - self.rate_window_seconds
        self._rate_limiter[ip] = [t for t in timestamps if t > cutoff]

        if len(self._rate_limiter[ip]) >= self.max_queries_per_ip:
            self._blocked_ips.add(ip)
            logger.warning(
                "DNS rate limit exceeded for %s: %d queries in %.0fs",
                ip, len(self._rate_limiter[ip]), self.rate_window_seconds,
            )
            return False

        self._rate_limiter[ip].append(now)
        return True

    async def _periodic_cleanup(self, interval: float = 120.0) -> None:
        """Background task to prune stale rate limiter entries."""
        while True:
            await asyncio.sleep(interval)
            now = time.monotonic()
            cutoff = now - self.rate_window_seconds
            stale = [
                ip for ip, ts_list in self._rate_limiter.items()
                if not any(t > cutoff for t in ts_list)
            ]
            for ip in stale:
                del self._rate_limiter[ip]
                self._blocked_ips.discard(ip)

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
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info("DNS honeypot started on %s:%d (rate limit: %d/min/IP)", self.host, self.port, self.max_queries_per_ip)

    async def _handle_query(
        self, data: bytes, addr: tuple[str, int], transport: asyncio.DatagramTransport | None
    ) -> None:
        ip = addr[0]

        # Rate limit check
        if not self._check_rate_limit(ip):
            return

        if len(data) < 12:
            return

        try:
            transaction_id = data[:2]
            query_name = self._parse_qname(data, 12)
            if not query_name:
                return
            self._total_queries += 1
            self._domains_queried[query_name] = self._domains_queried.get(query_name, 0) + 1
            logger.info("DNS query: %s from %s:%d", query_name, ip, addr[1])
            if self._event_callback:
                self._event_callback({
                    "eventid": "cloudsentinel.dns.query",
                    "session": "dns",
                    "src_ip": ip,
                    "src_port": addr[1],
                    "domain": query_name,
                    "timestamp": time.time(),
                    "sensor": "CloudSentinel",
                })

            response = self._build_response(transaction_id, query_name, "10.0.0.4")
            # Enforce max response size
            if len(response) > self.max_response_size:
                response = self._build_truncated_response(transaction_id, query_name)
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

    @staticmethod
    def _build_truncated_response(trans_id: bytes, qname: str) -> bytes:
        """Return a TC (truncated) flag response when response would be too large."""
        flags = struct.pack("!H", 0x8380)  # QR=1, TC=1, RD=1, RA=1
        qdcount = struct.pack("!H", 1)
        ancount = struct.pack("!H", 0)
        nscount = struct.pack("!H", 0)
        arcount = struct.pack("!H", 0)
        labels = qname.split(".")
        qname_encoded = b"".join(
            bytes([len(label)]) + label.encode("ascii", errors="replace") for label in labels
        ) + bytes([0])
        qtype = struct.pack("!H", 1)
        qclass = struct.pack("!H", 1)
        return trans_id + flags + qdcount + ancount + nscount + arcount + qname_encoded + qtype + qclass

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_queries": self._total_queries,
            "unique_domains": len(self._domains_queried),
            "top_domains": sorted(
                self._domains_queried.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "rate_limited_ips": len(self._blocked_ips),
            "active_rate_limiters": len(self._rate_limiter),
        }
