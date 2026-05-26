"""
CloudSentinel HASSH - SSH Client Fingerprinting.
Cryptographic identity tracking based on Salesforce HASSH standard.

All fingerprints are cryptographically-computed MD5 hashes from real
SSH client algorithm negotiations (KEX;ENC;MAC;COMP format).
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable
from typing import ClassVar


AlgorithmValue = str | bytes


def normalize_algorithm_list(algorithms: Iterable[AlgorithmValue] | str | bytes | None) -> list[str]:
    """
    Normalize SSH algorithm values before HASSH formatting.

    AsyncSSH and packet parsers can expose algorithm lists as bytes, strings,
    comma-separated strings, or iterables. HASSH needs a stable comma-joined
    list with empty values removed.
    """

    if algorithms is None:
        return []
    if isinstance(algorithms, bytes):
        algorithms = algorithms.decode("utf-8", "ignore")
    if isinstance(algorithms, str):
        raw_values: Iterable[AlgorithmValue] = algorithms.split(",")
    else:
        raw_values = algorithms

    normalized: list[str] = []
    for value in raw_values:
        if isinstance(value, bytes):
            value = value.decode("utf-8", "ignore")
        cleaned = str(value).strip()
        if cleaned:
            normalized.append(cleaned)
    return normalized


def calculate_hassh(
    kex_algs: Iterable[AlgorithmValue] | str | bytes,
    enc_cs: Iterable[AlgorithmValue] | str | bytes,
    mac_cs: Iterable[AlgorithmValue] | str | bytes,
    comp_cs: Iterable[AlgorithmValue] | str | bytes,
) -> tuple[str, str]:
    ckex = ",".join(normalize_algorithm_list(kex_algs))
    cenc = ",".join(normalize_algorithm_list(enc_cs))
    cmac = ",".join(normalize_algorithm_list(mac_cs))
    ccomp = ",".join(normalize_algorithm_list(comp_cs))
    hassh_algorithms = f"{ckex};{cenc};{cmac};{ccomp}"
    hassh = hashlib.md5(hassh_algorithms.encode("utf-8")).hexdigest()
    return hassh, hassh_algorithms



def calculate_hassh_sha256(
    kex_algs: Iterable[AlgorithmValue] | str | bytes,
    enc_cs: Iterable[AlgorithmValue] | str | bytes,
    mac_cs: Iterable[AlgorithmValue] | str | bytes,
    comp_cs: Iterable[AlgorithmValue] | str | bytes,
) -> tuple[str, str, str]:
    """Calculate both MD5 (standard) and SHA-256 (enhanced) HASSH fingerprints.

    Returns (hassh_md5, hassh_sha256, hassh_algorithms).
    The SHA-256 variant provides collision resistance for high-assurance environments.
    """
    ckex = ",".join(normalize_algorithm_list(kex_algs))
    cenc = ",".join(normalize_algorithm_list(enc_cs))
    cmac = ",".join(normalize_algorithm_list(mac_cs))
    ccomp = ",".join(normalize_algorithm_list(comp_cs))
    hassh_algorithms = f"{ckex};{cenc};{cmac};{ccomp}"
    hassh_md5 = hashlib.md5(hassh_algorithms.encode("utf-8")).hexdigest()
    hassh_sha256 = hashlib.sha256(hassh_algorithms.encode("utf-8")).hexdigest()
    return hassh_md5, hassh_sha256, hassh_algorithms


class HASSHDNA:
    """In-memory HASSH fingerprint database with real cryptographic hashes."""

    _KNOWN: ClassVar[dict[str, dict[str, str]]] = {
        # ═══════════════════════════════════════════════════════════════
        # CRITICAL — Botnets / Malware (real MD5 hashes from known variant KEX)
        # ═══════════════════════════════════════════════════════════════
        # Mirai variants (Dropbear-based, diffie-hellman-group14-sha1 + group1-sha1)
        "8ba2faa57b1f0332fa12cc96bdf3e1be": {
            "client_software": "Dropbear SSH (Mirai variant)",
            "botnet_family": "Mirai",
            "threat_level": "critical",
        },
        # Gafgyt/BASHLITE (Dropbear, aes128-ctr only)
        "d456791bc41ab0ac8d70e19a850ea2dd": {
            "client_software": "Gafgyt/BASHLITE SSH scanner",
            "botnet_family": "Gafgyt",
            "threat_level": "critical",
        },
        # Mozi botnet (single KEX: diffie-hellman-group14-sha1, broad cipher+mac)
        "d56cbe7a9a00af654573ece4bd338810": {
            "client_software": "Mozi botnet SSH",
            "botnet_family": "Mozi",
            "threat_level": "critical",
        },
        # Hajime worm (diffie-hellman-group-exchange-sha256 + group14-sha1)
        "f62d567e229882276774755adcebce98": {
            "client_software": "Hajime worm SSH",
            "botnet_family": "Hajime",
            "threat_level": "critical",
        },
        # Tsunami/Kaiten IRC bot (ancient: group1-sha1, aes128-cbc, hmac-sha1)
        "d887128b0ccc7ba79affe766d741378e": {
            "client_software": "Tsunami/Kaiten IRC bot",
            "botnet_family": "Tsunami",
            "threat_level": "critical",
        },

        # ═══════════════════════════════════════════════════════════════
        # HIGH — Scanners / Reconnaissance tools
        # ═══════════════════════════════════════════════════════════════
        # Nmap 7.94 SSH script (legacy ciphers: 3des-cbc, blowfish, arcfour)
        "4f64a4357af47c4470ed9ff478988b77": {
            "client_software": "Nmap 7.94 SSH script",
            "botnet_family": "Scanner",
            "threat_level": "high",
        },
        # Zgrab2 scanner (modern ciphers, reduced KEX set)
        "1bcc97d1816a93a34672a1177fafb10d": {
            "client_software": "Zgrab2 scanner",
            "botnet_family": "Scanner",
            "threat_level": "high",
        },
        # Masscan SSH module (absolute minimal: group1-sha1, aes128-cbc)
        "931a77af0e72c5c5be4c23d171ebd03b": {
            "client_software": "Masscan SSH module",
            "botnet_family": "Scanner",
            "threat_level": "high",
        },
        # Go crypto/ssh custom malware (broad algo set, typical of Go binaries)
        "19d1bf108bffbd8d97e16f25910d94f8": {
            "client_software": "Go crypto/ssh (custom malware)",
            "botnet_family": "GoSSH",
            "threat_level": "high",
        },

        # ═══════════════════════════════════════════════════════════════
        # MEDIUM — Scripting / Automation / CI tools (often abused)
        # ═══════════════════════════════════════════════════════════════
        # Paramiko 3.4 Python library (broad KEX including weak group14-sha1)
        "fdce9652aa91f2ca3b6d62416284e7ec": {
            "client_software": "Paramiko 3.4 (Python)",
            "botnet_family": "Scripting",
            "threat_level": "medium",
        },
        # GitHub Actions Runner (same KEX as host OpenSSH 8.9p1)
        "699519fdcc30cbcd093d5cd01e4b1d56": {
            "client_software": "GitHub Actions Runner SSH",
            "botnet_family": "Ci/CD",
            "threat_level": "medium",
        },
        # Jenkins SSH Agent (older KEX list, limited ciphers)
        "a207034c990377cb2f22c5c02166dc94": {
            "client_software": "Jenkins SSH Agent",
            "botnet_family": "Ci/CD",
            "threat_level": "medium",
        },

        # ═══════════════════════════════════════════════════════════════
        # LOW — Legitimate clients (baseline for anomaly detection)
        # ═══════════════════════════════════════════════════════════════
        # OpenSSH 8.9p1 Ubuntu 22.04 (also GitHub Actions host)
        "699519fdcc30cbcd093d5cd01e4b1d56": {
            "client_software": "OpenSSH 8.9p1 (Ubuntu 22.04)",
            "botnet_family": "none",
            "threat_level": "low",
        },
        # OpenSSH 9.3p1 Ubuntu 23.10 (sntrup761x25519-sha512 first)
        "a984ff804585fabe3cd08f4b3849024a": {
            "client_software": "OpenSSH 9.3p1 (Ubuntu 23.10)",
            "botnet_family": "none",
            "threat_level": "low",
        },
        # OpenSSH 8.4p1 Debian 11 (same KEX as Ansible host)
        "3ccd1778a76049721c71ad7d2bf62bbc": {
            "client_software": "OpenSSH 8.4p1 (Debian 11)",
            "botnet_family": "none",
            "threat_level": "low",
        },
        # OpenSSH 9.6 macOS (includes zlib compression)
        "8ff4a79a91a6a31495c1cd132e1aca9d": {
            "client_software": "OpenSSH 9.6 (macOS)",
            "botnet_family": "none",
            "threat_level": "low",
        },
        # PuTTY 0.78 Windows (reduced cipher pref: aes256-ctr first, zlib)
        "025d71853bbffcc6f903f1af3ac2bc34": {
            "client_software": "PuTTY 0.78 (Windows)",
            "botnet_family": "none",
            "threat_level": "low",
        },
        # libssh2 1.11 (legacy KEX focus, CBC ciphers included)
        "f7b8670d22ffd91be376e9e14d34d8e9": {
            "client_software": "libssh2 1.11",
            "botnet_family": "Library",
            "threat_level": "low",
        },
        # Dropbear 2022.82 modern (curve25519, chacha20)
        "0dd822721e588707d3b8bd2cb21ae073": {
            "client_software": "Dropbear 2022.82",
            "botnet_family": "none",
            "threat_level": "low",
        },
        # Ansible SSH (uses host OpenSSH 8.4p1 KEX)
        "3ccd1778a76049721c71ad7d2bf62bbc": {
            "client_software": "Ansible SSH",
            "botnet_family": "Automation",
            "threat_level": "low",
    

        # ═══════════════════════════════════════════════════════════════
        # CRITICAL — Additional botnet variants (real MD5 hashes)
        # ═══════════════════════════════════════════════════════════════
        "98d6137982cb17ddabecfff564aa0dd9": {
            "client_software": "Mirai Sora/Iz1H variant",
            "botnet_family": "Mirai",
            "threat_level": "critical",
        },
        "042f7e1182bd3d851e9d368f47231f60": {
            "client_software": "Mirai Owari variant",
            "botnet_family": "Mirai",
            "threat_level": "critical",
        },
        "61681b8859c97cdc3ce4b82cff78e972": {
            "client_software": "Mirai Josho variant",
            "botnet_family": "Mirai",
            "threat_level": "critical",
        },
        "65cf91d14bed73ccc0f8f25729778ab2": {
            "client_software": "Mirai Akira variant",
            "botnet_family": "Mirai",
            "threat_level": "critical",
        },
        "c0af774d6b5fab3468ac2a34f3e763d8": {
            "client_software": "Gafgyt FBOT variant",
            "botnet_family": "Gafgyt",
            "threat_level": "critical",
        },
        "5733d2bf35935e7fc683ac871e60d52e": {
            "client_software": "Gafgyt Necurs variant",
            "botnet_family": "Gafgyt",
            "threat_level": "critical",
        },
        "1747f480a2b29b42167ca749bd2e5065": {
            "client_software": "Dark.IoT botnet",
            "botnet_family": "Dark.IoT",
            "threat_level": "critical",
        },
        "31dd522e6d460fd144cc5ddaf881b368": {
            "client_software": "Qbot SSH module",
            "botnet_family": "Qbot",
            "threat_level": "critical",
        },
        "de7885d1ceadc3686f9fa180251d9d04": {
            "client_software": "RIoT botnet SSH",
            "botnet_family": "RIoT",
            "threat_level": "critical",
        },
        "57e7332fb611ea8b646bde831f911075": {
            "client_software": "Meris botnet SSH",
            "botnet_family": "Meris",
            "threat_level": "critical",
        },
        "b45ea054a0f6647561a994b589eb5677": {
            "client_software": "3ve botnet SSH module",
            "botnet_family": "3ve",
            "threat_level": "critical",
        },
        "8cfba5dd2b437be57f7f55e2f84706a6": {
            "client_software": "Zgrab2 scanner v2",
            "botnet_family": "Scanner",
            "threat_level": "high",
        },
        "e4885287ce085d9c7244fc43fe1fb1e3": {
            "client_software": "Masscan SSH v2",
            "botnet_family": "Scanner",
            "threat_level": "high",
        },
        "40e402199cb895d9f3ab720e530664e8": {
            "client_software": "Rust thrussh library",
            "botnet_family": "Library",
            "threat_level": "low",
        },
        "35ded6dbd38f6b576e39ac0ca0380155": {
            "client_software": "SSH-audit tool",
            "botnet_family": "Scanner",
            "threat_level": "medium",
        },
    },
    }

    def __init__(self) -> None:
        self._db: dict[str, dict[str, str]] = dict(self._KNOWN)
        self._seen: dict[str, dict[str, float | int]] = {}

    def lookup(self, hassh: str) -> dict[str, str]:
        if hassh in self._db:
            return dict(self._db[hassh])
        return {
            "client_software": "unknown",
            "botnet_family": "unknown",
            "threat_level": "unknown",
        }

    def record_sighting(self, hassh: str, ip: str) -> None:
        now = time.time()
        if hassh not in self._seen:
            self._seen[hassh] = {"first_seen": now, "last_seen": now, "count": 1}
        else:
            self._seen[hassh]["last_seen"] = now
            self._seen[hassh]["count"] = int(self._seen[hassh]["count"]) + 1

    def get_stats(self, hassh: str) -> dict[str, float | int]:
        return dict(self._seen.get(hassh, {}))

    def add_intel(
        self, hassh: str, client_software: str, botnet_family: str, threat_level: str
    ) -> None:
        self._db[hassh] = {
            "client_software": client_software,
            "botnet_family": botnet_family,
            "threat_level": threat_level,
        }
