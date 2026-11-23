"""Final metrics and stream constructor branches."""

from __future__ import annotations

import asyncio

from cloudsentinel.metrics import get_metrics
from cloudsentinel.stream import LiveStream


def test_metrics_start() -> None:
    asyncio.run(get_metrics().start())


def test_live_stream_explicit_cors_origin() -> None:
    stream = LiveStream(cors_origin=["https://unit.test"])
    assert stream._cors_origins == ["https://unit.test"]
