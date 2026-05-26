"""CloudSentinel Prometheus Metrics - Official prometheus_client library."""

from __future__ import annotations

import time
from typing import Any

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        generate_latest,
    )
except ModuleNotFoundError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    class _MetricValue:
        def __init__(self) -> None:
            self.value = 0.0

        def get(self) -> float:
            return self.value

    class CollectorRegistry:
        def __init__(self) -> None:
            self.metrics: list[Any] = []

    class _Metric:
        def __init__(
            self,
            name: str,
            description: str,
            labelnames: list[str] | None = None,
            registry: CollectorRegistry | None = None,
        ) -> None:
            self.name = name
            self.description = description
            self.labelnames = labelnames or []
            self._value = _MetricValue()
            if registry is not None:
                registry.metrics.append(self)

        def labels(self, **_labels: str) -> "_Metric":
            return self

    class Gauge(_Metric):
        def inc(self) -> None:
            self._value.value += 1

        def dec(self) -> None:
            self._value.value = max(0.0, self._value.value - 1)

        def set(self, value: float) -> None:
            self._value.value = float(value)

        def set_function(self, callback) -> None:
            self._callback = callback

    class Counter(_Metric):
        def inc(self) -> None:
            self._value.value += 1

    def generate_latest(registry: CollectorRegistry) -> bytes:
        lines: list[str] = []
        for metric in registry.metrics:
            value = getattr(metric, "_callback", None)
            rendered_value = value() if value is not None else metric._value.get()
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} gauge")
            lines.append(f"{metric.name} {rendered_value}")
        return ("\n".join(lines) + "\n").encode("utf-8")

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



pipeline_connected = Gauge(
    "cloudsentinel_pipeline_connected",
    "Whether the Redis event pipeline is connected (1=yes, 0=no)",
    registry=_registry,
)

event_pipeline_events_pending = Gauge(
    "cloudsentinel_pipeline_events_pending",
    "Number of events pending in the pipeline buffer",
    registry=_registry,
)


class Metrics:
    """Thin wrapper around prometheus_client for CloudSentinel integration."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.blocked_ips: set[str] = set()

    # ── Property accessors for admin API /metrics/json ──
    @property
    def active_sessions(self) -> float:
        return active_sessions._value.get()

    @property
    def mttb_ms(self) -> float:
        return mttb_ms._value.get()

    @property
    def total_connections(self) -> float:
        return connections_total._value.get()

    @property
    def total_auth_failures(self) -> float:
        return auth_failures_total._value.get()

    @property
    def total_auth_successes(self) -> float:
        return auth_successes_total._value.get()

    @property
    def total_commands(self) -> float:
        return commands_total._value.get()

    @property
    def total_blocks(self) -> float:
        return blocks_total._value.get()

    @property
    def total_blocks_iptables(self) -> float:
        return iptables_blocks_total._value.get()

    @property
    def pipeline_is_connected(self) -> int:
        return int(pipeline_connected._value.get())

    @property
    def pending_events(self) -> float:
        return event_pipeline_events_pending._value.get()

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

    def set_pipeline_status(self, connected: bool, pending: int = 0) -> None:
        """Update pipeline connectivity metrics (called from server.py)."""
        pipeline_connected.set(1 if connected else 0)
        event_pipeline_events_pending.set(pending)

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
