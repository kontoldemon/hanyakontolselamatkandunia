"""Cover MISP feed, anomaly detector, and firewall backends."""

from __future__ import annotations

import asyncio
import json
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
import cloudsentinel.firewall as firewall
import cloudsentinel.misp_feed as misp_module
from cloudsentinel.misp_feed import MISPFeed


class FakeProc:
    def __init__(self, returncode: int = 0, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"", self.stderr


def test_misp_feed(monkeypatch) -> None:
    feed = MISPFeed()
    asyncio.run(feed.start())
    asyncio.run(feed.stop())

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "response": {
                    "Attribute": [
                        {"type": "ip-src", "value": "8.8.8.8"},
                        {"type": "ip-dst", "value": "1.1.1.1"},
                        {"type": "domain", "value": "evil.test"},
                        {"type": "url", "value": "http://evil.test/path"},
                        {"type": "md5", "value": "a" * 32},
                        {"type": "sha256", "value": "b" * 64},
                        {"type": "domain", "value": ""},
                    ]
                }
            }

    class FakeClient:
        def __init__(self) -> None:
            self.closed = False

        async def post(self, *_args: object, **_kwargs: object) -> FakeResp:
            return FakeResp()

        async def aclose(self) -> None:
            self.closed = True

    fake_client = FakeClient()
    feed._client = fake_client
    asyncio.run(feed.refresh())
    assert feed.is_malicious_ip("8.8.8.8")
    assert feed.is_malicious_domain("evil.test")
    assert feed.is_malicious_url("http://evil.test/path")
    assert feed.is_malicious_hash("A" * 32)
    assert feed.stats["ips"] == 2
    asyncio.run(feed.stop())
    assert fake_client.closed

    monkeypatch.setattr(misp_module.hishel, "AsyncCacheClient", lambda **_kwargs: FakeClient())
    started = MISPFeed(url="http://misp", api_key="key", refresh_seconds=3600)
    asyncio.run(started.start())
    asyncio.run(started.stop())

    monkeypatch.setattr(misp_module, "_misp_feed", None)
    assert misp_module.get_misp_feed() is not None


@pytest.mark.asyncio
async def test_anomaly_detector(tmp_path) -> None:
    detector = anomaly.CommandAnomalyDetector()
    result = detector.score("curl http://evil/x")
    assert result["heuristic_score"] > 0
    assert detector.stats["total_commands_analyzed"] == 1

    class FakeModel:
        def __init__(self) -> None:
            self.fitted = False
            self.prediction = -1

        def predict(self, _values: object) -> list[int]:
            return [self.prediction]

        def fit(self, _values: object) -> None:
            self.fitted = True

    detector._model = FakeModel()
    detector._model_ready = True
    for index in range(10):
        detector.score(f"echo {index}")
    trained = detector.score("wget http://evil/x")
    assert trained["ml_anomaly"] is True
    detector.train()
    assert detector._model.fitted
    detector.save(str(tmp_path / "model.json"))
    assert json.loads((tmp_path / "model.json").read_text())["total_commands"] > 0

    none_model = anomaly.CommandAnomalyDetector()
    none_model._model = None
    assert none_model.score("id")["model_ready"] is False
    none_model.train()

    too_few = anomaly.CommandAnomalyDetector()
    too_few._model = FakeModel()
    too_few.train()

    broken = anomaly.CommandAnomalyDetector()
    broken._model = FakeModel()
    broken._recent_commands.extend(["id"] * 10)

    def fail_fit(_values: object) -> None:
        raise RuntimeError("fit failed")

    broken._model.fit = fail_fit
    broken.train()


def test_firewall_backends(monkeypatch) -> None:
    assert isinstance(firewall.create_firewall("iptables"), firewall.IPTablesBackend)
    assert isinstance(firewall.create_firewall("nftables"), firewall.NFTablesBackend)
    monkeypatch.setattr(firewall.shutil, "which", lambda name: "nft" if name == "nft" else None)
    assert isinstance(firewall.create_firewall(), firewall.NFTablesBackend)
    monkeypatch.setattr(firewall.shutil, "which", lambda name: "iptables" if name == "iptables" else None)
    assert isinstance(firewall.create_firewall(), firewall.IPTablesBackend)
    monkeypatch.setattr(firewall.shutil, "which", lambda _name: None)
    assert isinstance(firewall.create_firewall(), firewall.IPTablesBackend)

    async def success(*_args: object, **_kwargs: object) -> FakeProc:
        return FakeProc(0)

    async def failure(*_args: object, **_kwargs: object) -> FakeProc:
        return FakeProc(1, b"denied")

    async def boom(*_args: object, **_kwargs: object) -> FakeProc:
        raise RuntimeError("exec failed")

    iptables = firewall.IPTablesBackend()
    monkeypatch.setattr(firewall.asyncio, "create_subprocess_exec", success)
    assert asyncio.run(iptables.block("8.8.8.8")) == (True, "")
    assert asyncio.run(iptables.unblock("8.8.8.8")) == (True, "")
    assert asyncio.run(iptables.is_blocked("8.8.8.8")) is True

    monkeypatch.setattr(firewall.asyncio, "create_subprocess_exec", failure)
    assert asyncio.run(iptables.block("8.8.8.8"))[0] is False
    assert asyncio.run(iptables.unblock("8.8.8.8"))[0] is False
    assert asyncio.run(iptables.is_blocked("8.8.8.8")) is False

    monkeypatch.setattr(firewall.asyncio, "create_subprocess_exec", boom)
    assert asyncio.run(iptables.block("8.8.8.8"))[0] is False
    assert asyncio.run(iptables.unblock("8.8.8.8"))[0] is False
    assert asyncio.run(iptables.is_blocked("8.8.8.8")) is False

    nft = firewall.NFTablesBackend()
    monkeypatch.setattr(firewall.asyncio, "create_subprocess_exec", success)
    assert asyncio.run(nft.block("bad-ip")) == (False, "Invalid IP address: bad-ip")
    assert asyncio.run(nft.block("8.8.8.8")) == (True, "")
    assert asyncio.run(nft.unblock("8.8.8.8")) == (True, "")
    assert asyncio.run(nft.is_blocked("8.8.8.8")) is True

    nft_failure = firewall.NFTablesBackend()
    monkeypatch.setattr(firewall.asyncio, "create_subprocess_exec", failure)
    assert asyncio.run(nft_failure.block("8.8.8.8"))[0] is False
    assert asyncio.run(nft_failure.unblock("8.8.8.8"))[0] is False
    assert asyncio.run(nft_failure.is_blocked("8.8.8.8")) is False

    nft_boom = firewall.NFTablesBackend()
    monkeypatch.setattr(firewall.asyncio, "create_subprocess_exec", boom)
    assert asyncio.run(nft_boom.block("8.8.8.8"))[0] is False
    assert asyncio.run(nft_boom.unblock("8.8.8.8"))[0] is False
    assert asyncio.run(nft_boom.is_blocked("8.8.8.8")) is False
