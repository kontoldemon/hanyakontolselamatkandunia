"""More small branches: MISP, anomaly fallback, and VFS default loading."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

try:
    import hishel  # noqa: F401
except ModuleNotFoundError:
    _fake_hishel = types.ModuleType("hishel")
    _fake_hishel.AsyncCacheClient = type("AsyncCacheClient", (), {})
    sys.modules["hishel"] = _fake_hishel

try:
    import tenacity  # noqa: F401
except ModuleNotFoundError:
    _fake_tenacity = types.ModuleType("tenacity")
    _fake_tenacity.retry = lambda *_args, **_kwargs: (lambda func: func)
    _fake_tenacity.stop_after_attempt = lambda *_args, **_kwargs: None
    _fake_tenacity.wait_exponential = lambda *_args, **_kwargs: None
    sys.modules["tenacity"] = _fake_tenacity

import cloudsentinel.anomaly as anomaly
import cloudsentinel.misp_feed as misp_module
import cloudsentinel.vfs as vfs_module
from cloudsentinel.misp_feed import MISPFeed
from cloudsentinel.vfs import VirtualFileSystem


@pytest.mark.asyncio
async def test_misp_refresh_branches(monkeypatch) -> None:
    assert await MISPFeed()._fetch_misp_data() == []
    await MISPFeed().refresh()

    feed = MISPFeed(refresh_seconds=0)

    async def no_refresh() -> None:
        return None

    real_sleep = asyncio.sleep

    async def no_sleep(_seconds: float) -> None:
        await real_sleep(0)

    feed.refresh = no_refresh  # type: ignore[method-assign]
    monkeypatch.setattr(misp_module.asyncio, "sleep", no_sleep)
    task = asyncio.create_task(feed._refresh_loop())
    await real_sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    failing = MISPFeed()

    async def boom() -> list:
        raise RuntimeError("misp down")

    failing._fetch_misp_data = boom  # type: ignore[method-assign]
    await failing.refresh()

    class BrokenClient:
        async def post(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("misp down")

    failing._client = BrokenClient()  # type: ignore[assignment]
    await failing.refresh()


def test_anomaly_import_and_predict_fallback(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sklearn", None)
    detector = anomaly.CommandAnomalyDetector()
    assert detector._model is None

    class BrokenModel:
        def predict(self, _values: object) -> list[int]:
            raise RuntimeError("model failed")

    working = anomaly.CommandAnomalyDetector()
    working._model = BrokenModel()
    working._model_ready = True
    result = working.score("id")
    assert result["anomaly_score"] >= 0


def test_vfs_build_default_paths(monkeypatch) -> None:
    marker = VirtualFileSystem()
    marker.mkdir("/proc")
    marker.mkfile("/proc/cpuinfo", b"cpu\n")

    monkeypatch.setattr(vfs_module.Path, "exists", lambda _self: True)
    monkeypatch.setattr(
        VirtualFileSystem,
        "from_pickle",
        classmethod(lambda _cls, *_args: marker),
    )
    assert VirtualFileSystem.build_default() is marker

    monkeypatch.setattr(vfs_module.Path, "exists", lambda _self: False)
    monkeypatch.setattr(vfs_module.Path, "is_dir", lambda _self: True)
    monkeypatch.setattr(
        VirtualFileSystem,
        "from_honeyfs",
        classmethod(lambda _cls, *_args: marker),
    )
    assert VirtualFileSystem.build_default() is marker
