"""Cover CLI module entry points and non-tenacity forwarder startup."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

import cloudsentinel.honeyfs_seed as honeyfs_module
import cloudsentinel.pipeline as pipeline_module
import cloudsentinel.stress_test as stress_module
import cloudsentinel.ttp_coverage_test as ttp_module
from cloudsentinel.config import load_settings
from cloudsentinel.pipeline import ClickHouseForwarder


def _run_main(monkeypatch, module, argv: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    path = Path(module.__file__)
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    exec(code, {"__name__": "__main__", "__package__": module.__package__, "__file__": str(path)})


def test_module_entrypoints(monkeypatch, tmp_path) -> None:
    _run_main(monkeypatch, honeyfs_module, ["honeyfs_seed", "--output", str(tmp_path / "honeyfs")])
    _run_main(monkeypatch, ttp_module, ["ttp_coverage_test", "--artifacts-dir", str(tmp_path / "ttp")])
    _run_main(
        monkeypatch,
        stress_module,
        ["stress_test", "--host", "127.0.0.1", "--port", "22", "--connections", "0"],
    )


@pytest.mark.asyncio
async def test_forwarder_without_tenacity(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True

    class FakeRedis:
        def __init__(self) -> None:
            self.closed = False

        async def ping(self) -> bool:
            return True

        async def xread(self, *_args: object, **_kwargs: object) -> list:
            return []

        async def aclose(self) -> None:
            self.closed = True

    fake_redis = FakeRedis()
    monkeypatch.setattr(pipeline_module.redis, "from_url", lambda *_a, **_k: fake_redis)
    monkeypatch.setattr(pipeline_module, "_TENACITY", False)
    forwarder = ClickHouseForwarder(settings.redis, settings.clickhouse)
    monkeypatch.setattr(forwarder, "_connect_clickhouse", lambda: None)
    await forwarder.start()
    await asyncio.sleep(0)
    await forwarder.stop()
    assert fake_redis.closed
