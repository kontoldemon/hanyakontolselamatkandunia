"""CloudSentinel Prometheus Metrics - Official prometheus_client library."""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

_registry = CollectorRegistry()

# Gauges (point-in-time values)
uptime_seconds = Gauge(
    "cloudsentinel_uptime_seconds",
    "Sensor uptime in seconds",
    registry=_registry,
)
active_sessions = Gauge(
    "cloudsentinel_active_sessions",
    "Current active SSH/HTTP sessions",
    registry=_registry,
)
mttb_ms = Gauge(
    "cloudsentinel_mttb_ms",
    "Mean time to block in milliseconds",
    registry=_registry,
)
blocked_ips_current = Gauge(
    "cloudsentinel_blocked_ips_current",
    "Currently blocked IP addresses",
    registry=_registry,
)

# Counters (monotonically increasing)
connections_total = Counter(
    "cloudsentinel_connections_total",
    "Total connections since start",
    registry=_registry,
)
auth_failures_total = Counter(
    "cloudsentinel_auth_failures_total",
    "Total failed authentication attempts",
    registry=_registry,
)
auth_successes_total = Counter(
    "cloudsentinel_auth_successes_total",
    "Total successful authentications",
    registry=_registry,
)
commands_total = Counter(
    "cloudsentinel_commands_total",
    "Total commands executed by attackers",
    registry=_registry,
)
blocks_total = Counter(
    "cloudsentinel_blocks_total",
    "Total SOAR blocks triggered",
    registry=_registry,
)
iptables_blocks_total = Counter(
    "cloudsentinel_iptables_blocks_total",
    "Actual firewall rules applied",
    registry=_registry,
)
events_total = Counter(
    "cloudsentinel_events_total",
    "Total events processed",
    labelnames=["event_type"],
    registry=_registry,
)


class Metrics:
    """Thin wrapper around prometheus_client for CloudSentinel integration."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.blocked_ips: set[str] = set()

    async def start(self) -> None:
        uptime_seconds.set_function(lambda: time.time() - self.start_time)

    def record_connect(self) -> None:
        connections_total.inc()
        active_sessions.inc()

    def record_disconnect(self) -> None:
        active_sessions.dec()

    def record_auth_fail(self) -> None:
        auth_failures_total.inc()

    def record_auth_success(self) -> None:
        auth_successes_total.inc()

    def record_command(self) -> None:
        commands_total.inc()

    def record_block(self, action: str) -> None:
        blocks_total.inc()
        if action == "iptables_block":
            iptables_blocks_total.inc()
        self.blocked_ips_current()

    def record_event(self, event_type: str) -> None:
        events_total.labels(event_type=event_type).inc()

    def set_mttb(self, ms: float) -> None:
        mttb_ms.set(ms)

    def set_blocked_count(self, count: int) -> None:
        blocked_ips_current.set(count)

    def blocked_ips_current(self) -> None:
        blocked_ips_current.set(len(self.blocked_ips))

    def render(self) -> bytes:
        """Return Prometheus text format metrics."""
        return generate_latest(_registry)

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE_LATEST


_metrics: Metrics | None = None


def get_metrics() -> Metrics:
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics
