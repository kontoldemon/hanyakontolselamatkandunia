"""Third batch of focused unit tests."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from cloudsentinel.config import load_settings
from cloudsentinel.server import CloudSentinelSession
from cloudsentinel.threat_reporter import (
    ThreatReport,
    _build_analysis_prompt,
    _empty_session_data,
    _parse_json_response,
    fetch_session_data,
)
from cloudsentinel.webhook import WebhookConfig, WebhookNotifier


@pytest.mark.asyncio
async def test_threat_reporter_fallbacks() -> None:
    empty = await fetch_session_data("session-1")
    assert empty["session_id"] == "session-1"
    assert empty["commands"] == []
    assert _empty_session_data("x")["attacker_ip"] == ""
    report = ThreatReport("session-1", "8.8.8.8", risk_score=90, commands=["whoami"])
    prompt = _build_analysis_prompt(report)
    assert "8.8.8.8" in prompt
    assert "whoami" in prompt
    parsed = _parse_json_response('```json\n{"summary":"ok","confidence":0.9}\n```', "model")
    assert parsed["summary"] == "ok"
    fallback = _parse_json_response("not json", "model")
    assert fallback["model_used"] == "model"


@pytest.mark.asyncio
async def test_webhook_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    config = WebhookConfig(
        enabled=True,
        slack_url="http://example.invalid",
        min_risk_score=50,
        cooldown_seconds=0,
    )
    notifier = WebhookNotifier(config)

    async def fake_send(_event: dict) -> bool:
        return True

    monkeypatch.setattr(notifier, "_send_slack", fake_send)
    try:
        sent = await notifier.send_alert(
            {"src_ip": "1.2.3.4", "cloudsentinel_risk_score": 80}
        )
        assert sent == ["slack"]
    finally:
        await notifier.close()


@pytest.mark.asyncio
async def test_mttb_benchmark_with_fake_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import cloudsentinel.mttb_benchmark as benchmark

    class FakeEngine:
        def __init__(self, **_kwargs: object) -> None:
            self.started = False

        async def start(self) -> None:
            self.started = True

        async def process_event(self, _session: str, _event: dict) -> dict:
            return {"mttb_ms": 1.0, "cloudsentinel_soar_action": "dry_run_block"}

        async def stop(self) -> None:
            self.started = False

    monkeypatch.setattr(benchmark, "SOAREngine", FakeEngine)
    args = argparse.Namespace(
        iterations=2,
        delay=0.0,
        source_ip="203.0.113.10",
        risk_threshold=30,
        target_ms=100,
        active=False,
        firewall_path="/sbin/iptables",
        block_ttl=60,
        allowlist="127.0.0.1",
        redis_url="",
    )
    report = await benchmark.run_benchmark(args)
    assert report["pass"] is True
    assert report["median_ms"] == 1.0
    benchmark.write_artifacts(report, tmp_path)
    assert (tmp_path / "mttb-benchmark.md").exists()


def test_ttp_coverage_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import cloudsentinel.ttp_coverage_test as ttp

    monkeypatch.setattr(
        sys,
        "argv",
        ["ttp_coverage_test", "--artifacts-dir", str(tmp_path)],
    )
    ttp.main()
    assert (tmp_path / "ttp-coverage.json").exists()
    assert (tmp_path / "ttp-coverage.md").exists()


@pytest.mark.asyncio
async def test_server_session_execute() -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.llm.provider = "mock"

    async def emit_event(*_args: object, **_kwargs: object) -> None:
        return None

    fake_server = SimpleNamespace(
        settings=settings,
        username="root",
        src_ip="8.8.8.8",
        started_at=time.time(),
        anomaly_detector=None,
        _emit_event=emit_event,
    )
    session = CloudSentinelSession(fake_server)
    try:
        output = await session._execute("whoami")
        assert "root" in output
        assert session._detect_honeytoken_access("cat /root/.aws/credentials")
    finally:
        await session.vfs.close()


@pytest.mark.asyncio
async def test_abuseipdb_cached_report(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("hishel")
    from cloudsentinel.abuseipdb import AbuseIPDBClient

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "data": {
                    "abuseConfidenceScore": 90,
                    "totalReports": 200,
                    "countryCode": "US",
                }
            }

    class FakeClient:
        async def get(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse()

        async def aclose(self) -> None:
            return None

    client = AbuseIPDBClient(api_key="test")
    client._client = FakeClient()  # type: ignore[assignment]
    result = await client.check("8.8.8.8")
    assert result["abuse_confidence_score"] == 90
    assert result["total_reports"] == 200
    cached = await client.check("8.8.8.8")
    assert cached == result
    await client.stop()


@pytest.mark.asyncio
async def test_misp_refresh_parsing() -> None:
    pytest.importorskip("hishel")
    from cloudsentinel.misp_feed import MISPFeed

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "response": {
                    "Attribute": [
                        {"type": "ip-src", "value": "1.2.3.4"},
                        {"type": "domain", "value": "evil.example"},
                        {"type": "url", "value": "http://evil.example/x"},
                        {"type": "md5", "value": "a" * 32},
                    ]
                }
            }

    class FakeClient:
        async def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
            return FakeResponse()

        async def aclose(self) -> None:
            return None

    feed = MISPFeed(url="http://misp.invalid", api_key="test")
    feed._client = FakeClient()  # type: ignore[assignment]
    await feed.refresh()
    assert feed.is_malicious_ip("1.2.3.4")
    assert feed.is_malicious_domain("evil.example")
    assert feed.is_malicious_url("http://evil.example/x")
    assert feed.is_malicious_hash("a" * 32)
    await feed.stop()
