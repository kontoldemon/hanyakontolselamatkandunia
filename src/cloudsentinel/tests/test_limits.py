"""Connection limiter regression tests after extraction."""

from __future__ import annotations

from cloudsentinel.sensor.limits import ConnectionLimiter


def test_connection_limiter_per_ip_window(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("cloudsentinel.sensor.limits.time.monotonic", lambda: clock[0])
    limiter = ConnectionLimiter(max_per_ip=2, max_total=50, window=10)

    assert limiter.acquire_nowait("1.1.1.1") is True
    assert limiter.acquire_nowait("1.1.1.1") is True
    assert limiter.acquire_nowait("1.1.1.1") is False

    clock[0] += 11
    assert limiter.acquire_nowait("1.1.1.1") is True


def test_connection_limiter_total_and_release() -> None:
    limiter = ConnectionLimiter(max_per_ip=10, max_total=1)

    assert limiter.acquire_nowait("1.1.1.1") is True
    assert limiter.acquire_nowait("2.2.2.2") is False
    limiter.release_nowait("1.1.1.1")
    assert limiter.total == 0
    assert limiter.acquire_nowait("2.2.2.2") is True


def test_connection_limiter_evicts_old_entries(monkeypatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("cloudsentinel.sensor.limits.time.monotonic", lambda: clock[0])
    limiter = ConnectionLimiter(max_per_ip=10, max_total=50, window=100, max_entries=1)

    assert limiter.acquire_nowait("1.1.1.1") is True
    clock[0] += 1
    assert limiter.acquire_nowait("2.2.2.2") is True
    assert len(limiter._ips) == 1
    assert "2.2.2.2" in limiter._ips


async def test_connection_limiter_async_lock() -> None:
    limiter = ConnectionLimiter(max_per_ip=10, max_total=1)

    assert await limiter.acquire("1.1.1.1") is True
    assert await limiter.acquire("2.2.2.2") is False
    await limiter.release("1.1.1.1")
    assert await limiter.acquire("2.2.2.2") is True
