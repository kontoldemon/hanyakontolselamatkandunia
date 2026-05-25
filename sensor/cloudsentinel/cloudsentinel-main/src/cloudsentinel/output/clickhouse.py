# SPDX-FileCopyrightText: 2026 CloudSentinel contributors
#
# SPDX-License-Identifier: BSD-3-Clause

"""
CloudSentinel ClickHouse output connector.

Writes normalized audit events to ClickHouse over its HTTP interface using
Twisted-friendly async I/O. Also annotates events with MVP SOAR risk metadata.
"""

from __future__ import annotations

import ipaddress
import json
import re
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import quote

import geoip2.database
import geoip2.errors
import treq
from twisted.internet import protocol, reactor, task
from twisted.python import log
from twisted.web.http_headers import Headers

import cloudsentinel.core.output
from cloudsentinel.core.config import CloudSentinelConfig


class _IptablesProtocol(protocol.ProcessProtocol):
    def __init__(self, attacker_ip: str) -> None:
        self.attacker_ip = attacker_ip

    def processEnded(self, reason: Any) -> None:
        log.msg(f"output_clickhouse: iptables finished for {self.attacker_ip}: {reason}")


class Output(cloudsentinel.core.output.Output):
    """
    ClickHouse output with CloudSentinel MVP risk scoring.
    """

    _IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    _ATTACK_PATTERNS = (
        (re.compile(r"\b(?:wget|curl|tftp|ftpget)\b"), 25, "T1105"),
        (re.compile(r"\b(?:sh|bash|dash|python|perl)\b\s+-c\b"), 25, "T1059.004"),
        (re.compile(r"\bchmod\b|\bchown\b"), 20, "T1222"),
        (re.compile(r"\b(?:uname|hostnamectl|lscpu|cat\s+/etc/os-release)\b"), 10, "T1082"),
        (re.compile(r"\b(?:whoami|id|w)\b"), 10, "T1033"),
        (re.compile(r"\b(?:ps|top|netstat|ss)\b"), 10, "T1057"),
        (re.compile(r"\b(?:ifconfig|ip\s+addr|ip\s+route|route)\b"), 10, "T1016"),
        (re.compile(r"\b(?:ls|find|du|df)\b"), 8, "T1083"),
        (re.compile(r"\bcat\s+/etc/(?:passwd|shadow|group)\b"), 20, "T1003.008"),
        (re.compile(r"\b(?:ssh|scp|rsync)\b"), 15, "T1021.004"),
        (re.compile(r"\b(?:crontab|systemctl|service)\b"), 15, "T1053.003"),
        (re.compile(r"\b(?:iptables|ufw|firewall-cmd)\b"), 25, "T1562.004"),
        (re.compile(r"\b(?:rm\s+-rf|shred|wipe)\b"), 30, "T1485"),
        (re.compile(r"\b(?:base64\s+-d|xxd\s+-r)\b"), 15, "T1140"),
        (re.compile(r"\b(?:nc|netcat|ncat|socat)\b"), 25, "T1095"),
        (re.compile(r"\b(?:tar|zip|gzip|7z)\b"), 12, "T1560.001"),
    )

    def start(self) -> None:
        self.url = CloudSentinelConfig.get(
            "output_clickhouse", "url", fallback="http://127.0.0.1:8123"
        ).rstrip("/")
        self.database = self._validated_identifier(
            CloudSentinelConfig.get("output_clickhouse", "database", fallback="default")
        )
        self.table = self._validated_identifier(
            CloudSentinelConfig.get(
                "output_clickhouse", "table", fallback="cloudsentinel_events"
            )
        )
        self.batch_size = max(
            1, CloudSentinelConfig.getint("output_clickhouse", "batch_size", fallback=20)
        )
        self.flush_interval = max(
            0.1,
            CloudSentinelConfig.getfloat("output_clickhouse", "flush_interval", fallback=5.0),
        )
        self.max_queue = max(
            1, CloudSentinelConfig.getint("output_clickhouse", "max_queue", fallback=1000)
        )
        self.timeout = CloudSentinelConfig.getfloat("output_clickhouse", "timeout", fallback=10.0)
        self.debug = CloudSentinelConfig.getboolean(
            "output_clickhouse", "debug", fallback=False
        )
        self.soar_enabled = CloudSentinelConfig.getboolean(
            "output_clickhouse", "soar_enabled", fallback=True
        )
        self.firewall_enabled = CloudSentinelConfig.getboolean(
            "output_clickhouse", "firewall_enabled", fallback=False
        )
        self.firewall_dry_run = CloudSentinelConfig.getboolean(
            "output_clickhouse", "firewall_dry_run", fallback=True
        )
        self.firewall_path = CloudSentinelConfig.get(
            "output_clickhouse", "firewall_path", fallback="/sbin/iptables"
        )
        self.risk_threshold = CloudSentinelConfig.getint(
            "output_clickhouse", "risk_threshold", fallback=70
        )
        self.geoip_enabled = CloudSentinelConfig.getboolean(
            "output_clickhouse", "geoip_enabled", fallback=False
        )
        self.geoip_database = CloudSentinelConfig.get(
            "output_clickhouse",
            "geoip_database",
            fallback="var/lib/cloudsentinel/GeoLite2-City.mmdb",
        )
        self.live_stream_enabled = CloudSentinelConfig.getboolean(
            "output_clickhouse", "live_stream_enabled", fallback=False
        )
        self.live_stream_url = CloudSentinelConfig.get(
            "output_clickhouse",
            "live_stream_url",
            fallback="http://127.0.0.1:3001/events",
        )
        self._geoip_reader = None
        if self.geoip_enabled:
            geoip_path = Path(self.geoip_database)
            if geoip_path.exists():
                self._geoip_reader = geoip2.database.Reader(str(geoip_path))
            else:
                log.msg(f"output_clickhouse: GeoIP database not found: {geoip_path}")

        self._queue: deque[dict[str, Any]] = deque()
        self._sending = False
        self._stopped = False
        self._session_scores: dict[str, int] = {}
        self._session_failed_auth: dict[str, int] = {}
        self._session_techniques: dict[str, set[str]] = {}
        self._blocked_ips: set[str] = set()
        self._reactor = reactor
        self._loop = task.LoopingCall(self._flush)
        self._loop.clock = self._reactor
        self._loop.start(self.flush_interval, now=False)

    def stop(self) -> None:
        self._stopped = True
        if self._loop.running:
            self._loop.stop()
        if self._geoip_reader is not None:
            self._geoip_reader.close()
        self._flush()

    def write(self, event: dict[str, Any]) -> None:
        if self._stopped:
            return
        event = dict(event)
        self._annotate_soar(event)
        self._annotate_geoip(event)
        self._stream_event(event)
        self._enqueue(self._normalise(event))
        if len(self._queue) >= self.batch_size:
            self._flush()

    def _validated_identifier(self, value: str) -> str:
        if not self._IDENTIFIER.match(value):
            raise ValueError(value)
        return value

    def _normalise(self, event: dict[str, Any]) -> dict[str, Any]:
        event_json = json.dumps(event, separators=(",", ":"), default=str)
        for key in list(event):
            if key.startswith("log_") or key == "system":
                del event[key]
        return {
            "timestamp": event.get("timestamp"),
            "eventid": event.get("eventid", ""),
            "session": event.get("session", ""),
            "sensor": event.get("sensor", ""),
            "src_ip": event.get("src_ip", ""),
            "protocol": event.get("protocol", ""),
            "country_code": event.get("country_code", ""),
            "city": event.get("city", ""),
            "latitude": float(event.get("latitude", 0.0) or 0.0),
            "longitude": float(event.get("longitude", 0.0) or 0.0),
            "hassh": event.get("hassh", ""),
            "hasshAlgorithms": event.get("hasshAlgorithms", ""),
            "cloudsentinel_risk_score": int(
                event.get("cloudsentinel_risk_score", 0) or 0
            ),
            "cloudsentinel_mitre_techniques": event.get(
                "cloudsentinel_mitre_techniques", []
            ),
            "cloudsentinel_soar_action": event.get("cloudsentinel_soar_action", ""),
            "event_json": event_json,
        }

    def _enqueue(self, event: dict[str, Any]) -> None:
        while len(self._queue) >= self.max_queue:
            dropped = self._queue.popleft()
            log.msg(
                "output_clickhouse: queue full, dropped oldest event "
                f"{dropped.get('eventid', 'unknown')}"
            )
        self._queue.append(event)

    def _flush(self) -> None:
        if self._stopped and not self._queue:
            return
        if self._sending or not self._queue:
            return

        batch_size = max(1, self.batch_size)
        batch = [self._queue.popleft() for _ in range(min(len(self._queue), batch_size))]
        self._sending = True
        d = self._post_batch(batch)
        d.addCallback(self._handle_response, batch)
        d.addErrback(self._handle_error, batch)

    def _post_batch(self, batch: list[dict[str, Any]]) -> Any:
        query = f"INSERT INTO {self.database}.{self.table} FORMAT JSONEachRow"
        target = f"{self.url}/?query={quote(query)}"
        payload = "\n".join(
            json.dumps(event, separators=(",", ":"), default=str) for event in batch
        ).encode("utf-8")
        payload += b"\n"
        headers = Headers({b"Content-Type": [b"application/json"]})
        if self.debug:
            log.msg(f"output_clickhouse: posting {len(batch)} events to {target}")
        return treq.post(target, data=payload, headers=headers, timeout=self.timeout)

    def _stream_event(self, event: dict[str, Any]) -> None:
        if not self.live_stream_enabled:
            return
        payload = json.dumps(event, separators=(",", ":"), default=str).encode("utf-8")
        headers = Headers({b"Content-Type": [b"application/json"]})
        d = treq.post(
            self.live_stream_url,
            data=payload,
            headers=headers,
            timeout=min(self.timeout, 2.0),
        )
        d.addErrback(
            lambda failure: log.msg(f"output_clickhouse: live stream failed {failure!r}")
        )

    def _handle_response(self, response: Any, batch: list[dict[str, Any]]) -> None:
        self._sending = False
        if 200 <= response.code < 300:
            if self.debug:
                log.msg(f"output_clickhouse: wrote {len(batch)} events")
            self._flush()
        else:
            log.msg(f"output_clickhouse: HTTP {response.code}, requeueing batch")
            self._requeue_front(batch)

    def _handle_error(self, failure: Any, batch: list[dict[str, Any]]) -> None:
        self._sending = False
        log.msg(f"output_clickhouse: write failed {failure!r}, requeueing batch")
        self._requeue_front(batch)

    def _requeue_front(self, batch: list[dict[str, Any]]) -> None:
        for event in reversed(batch):
            while len(self._queue) >= self.max_queue:
                self._queue.pop()
            self._queue.appendleft(event)

    def _annotate_soar(self, event: dict[str, Any]) -> None:
        if not self.soar_enabled:
            return

        session = str(event.get("session", "unknown"))
        current_score = self._session_scores.get(session, 0)
        techniques = set(self._session_techniques.get(session, set()))

        event_score = 0
        if event.get("eventid") == "cloudsentinel.login.failed":
            failed = self._session_failed_auth.get(session, 0) + 1
            self._session_failed_auth[session] = failed
            event_score += 10 + min(failed * 5, 30)
            techniques.add("T1110")
        elif event.get("eventid") == "cloudsentinel.login.success":
            self._session_failed_auth.pop(session, None)

        command = str(event.get("input", ""))
        if event.get("eventid") in ("cloudsentinel.command.input", "cloudsentinel.command.failed"):
            for pattern, score, technique in self._ATTACK_PATTERNS:
                if pattern.search(command):
                    event_score += score
                    techniques.add(technique)

        current_score += event_score
        self._session_scores[session] = current_score
        self._session_techniques[session] = techniques
        event["cloudsentinel_risk_score"] = current_score
        event["cloudsentinel_mitre_techniques"] = sorted(techniques)
        event["cloudsentinel_soar_action"] = "none"

        if current_score >= self.risk_threshold:
            event["cloudsentinel_soar_action"] = self._block_ip(event)

        if event.get("eventid") == "cloudsentinel.session.closed":
            self._session_scores.pop(session, None)
            self._session_failed_auth.pop(session, None)
            self._session_techniques.pop(session, None)

    def _annotate_geoip(self, event: dict[str, Any]) -> None:
        if self._geoip_reader is None:
            return
        src_ip = event.get("src_ip")
        if not src_ip:
            return
        try:
            response = self._geoip_reader.city(str(src_ip))
        except (geoip2.errors.AddressNotFoundError, ValueError):
            return
        event["country_code"] = response.country.iso_code or ""
        event["city"] = response.city.name or ""
        event["latitude"] = response.location.latitude or 0.0
        event["longitude"] = response.location.longitude or 0.0

    def _block_ip(self, event: dict[str, Any]) -> str:
        attacker_ip = event.get("src_ip")
        if not attacker_ip or not self._is_public_ip(str(attacker_ip)):
            return "skip_invalid_or_private_ip"
        if attacker_ip in self._blocked_ips:
            return "already_blocked"

        self._blocked_ips.add(str(attacker_ip))
        if not self.firewall_enabled:
            return "detect_only"
        if self.firewall_dry_run:
            return "dry_run_block"

        args = ["iptables", "-A", "INPUT", "-s", str(attacker_ip), "-j", "DROP"]
        self._reactor.spawnProcess(
            _IptablesProtocol(str(attacker_ip)),
            self.firewall_path,
            args,
            env=None,
        )
        return "iptables_block"

    def _is_public_ip(self, value: str) -> bool:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return False
        return not (
            address.is_private
            or address.is_loopback
            or address.is_multicast
            or address.is_unspecified
        )
