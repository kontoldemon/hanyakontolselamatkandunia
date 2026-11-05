"""Sixth batch: small gaps to push coverage past 65%."""

from __future__ import annotations

import json

import pytest

from cloudsentinel import geoip
from cloudsentinel.attack_graph import AttackGraph
from cloudsentinel.config import RedisSettings
from cloudsentinel.firewall import IPTablesBackend, NFTablesBackend, create_firewall
from cloudsentinel.honeyfs_seed import is_text_content
from cloudsentinel.observability import get_tracer, setup_sentry, setup_structlog
from cloudsentinel.pipeline import EventPipeline
from cloudsentinel.threat_reporter import generate_report


def test_geoip_http_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "success": True,
        "country_code": "us",
        "country": "United States",
        "city": "Test City",
        "region": "Test Region",
        "continent_code": "NA",
        "latitude": 1.5,
        "longitude": 2.5,
        "timezone": {"id": "UTC"},
        "connection": {"asn": 1, "isp": "ISP", "org": "Org", "type": "hosting"},
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(payload).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse())
    monkeypatch.setattr(geoip, "_GEOIP_HTTP_ENABLED", True)
    geoip._geoip_http_cache.clear()
    result = geoip._enrich_http("8.8.8.8")
    assert result is not None
    assert result["country_code"] == "US"
    assert result["isp"] == "ISP"


def test_observability_helpers() -> None:
    setup_sentry("")
    assert setup_structlog() is not None
    assert get_tracer() is not None


def test_honeyfs_text_detection() -> None:
    assert is_text_content(b"hello world") is True
    assert is_text_content(b"\xff\xfe\x00") is False


def test_attack_graph_prune() -> None:
    graph = AttackGraph(prune_after_seconds=0)
    graph.add_event({"src_ip": "8.8.8.8", "session": "s1"})
    assert graph._nodes
    graph._prune()
    assert graph._nodes == {}


def test_firewall_auto_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cloudsentinel.firewall.shutil.which",
        lambda name: "/usr/sbin/nft" if name == "nft" else None,
    )
    assert isinstance(create_firewall("auto"), NFTablesBackend)
    monkeypatch.setattr(
        "cloudsentinel.firewall.shutil.which",
        lambda name: "/sbin/iptables" if name == "iptables" else None,
    )
    assert isinstance(create_firewall("auto"), IPTablesBackend)
    monkeypatch.setattr("cloudsentinel.firewall.shutil.which", lambda _name: None)
    assert isinstance(create_firewall("auto"), IPTablesBackend)


@pytest.mark.asyncio
async def test_pipeline_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = EventPipeline(RedisSettings())
    stopped = {"stop": False, "start": False}

    async def fake_stop() -> None:
        stopped["stop"] = True

    async def fake_start() -> None:
        stopped["start"] = True

    monkeypatch.setattr(pipeline, "stop", fake_stop)
    monkeypatch.setattr(pipeline, "start", fake_start)
    assert await pipeline.reconnect() is True
    assert stopped == {"stop": True, "start": True}


@pytest.mark.asyncio
async def test_threat_report_with_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analysis(_prompt: str) -> dict:
        return {
            "summary": "Test summary",
            "primary_objective": "Recon",
            "confidence": 0.8,
            "model_used": "unit-model",
        }

    monkeypatch.setattr("cloudsentinel.threat_reporter._call_litellm", fake_analysis)
    report = await generate_report(
        "session-analysis",
        attacker_ip="8.8.8.8",
        commands=["whoami"],
        risk_score=50,
    )
    assert report.summary == "Test summary"
    assert report.primary_objective == "Recon"
    assert report.confidence == 0.8
    assert report.model_used == "unit-model"
