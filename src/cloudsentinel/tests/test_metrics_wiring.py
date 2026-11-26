"""Prometheus counters must reflect real pipeline traffic and uptime."""

from __future__ import annotations

import pytest

from cloudsentinel.config import Settings
from cloudsentinel.metrics import events_total, get_metrics
from cloudsentinel.pipeline import EventEnvelope, EventPipeline


async def test_pipeline_emit_increments_event_metric() -> None:
    pipeline = EventPipeline(Settings().redis)

    async def no_wal(_envelope: EventEnvelope) -> None:
        return None

    pipeline._wal.write = no_wal  # type: ignore[method-assign]
    counter = events_total.labels(event_type="test.metric")
    before = counter._value.get()
    await pipeline.emit(
        EventEnvelope(
            event_type="test.metric",
            session_id="metric-session",
            src_ip="203.0.113.5",
            src_port=2222,
            timestamp=1.0,
            payload={},
        )
    )
    assert counter._value.get() == before + 1


@pytest.mark.asyncio
async def test_metrics_start_registers_uptime() -> None:
    from cloudsentinel.server import _start_metrics

    await _start_metrics()
    assert get_metrics().render()
