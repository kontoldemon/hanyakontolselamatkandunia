"""Tests for the pure logic used by the Azure Function NSG blocker."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LOGIC_PATH = REPO_ROOT / "azure" / "function" / "block_logic.py"


def _load_logic():
    spec = importlib.util.spec_from_file_location("cloudsentinel_block_logic", LOGIC_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_validate_request_accepts_public_ip() -> None:
    logic = _load_logic()
    ip, ttl, reason = logic.validate_request(
        {"ip": "8.8.8.8", "ttl": 60, "reason": "unit-test"},
        allowlist="127.0.0.0/8,10.0.0.0/8",
    )
    assert ip == "8.8.8.8"
    assert ttl == 60
    assert reason == "unit-test"


def test_validate_request_rejects_private_and_allowlisted() -> None:
    logic = _load_logic()
    with pytest.raises(ValueError):
        logic.validate_request({"ip": "10.0.0.5"})
    with pytest.raises(ValueError):
        logic.validate_request({"ip": "127.0.0.1"})
    with pytest.raises(ValueError):
        logic.validate_request({"ip": "8.8.8.8"}, allowlist="8.8.8.0/24")
    with pytest.raises(ValueError):
        logic.validate_request({"ip": "not-an-ip"})


def test_validate_request_caps_ttl() -> None:
    logic = _load_logic()
    _, ttl, _ = logic.validate_request({"ip": "8.8.8.8", "ttl": 99999999})
    assert ttl == logic.MAX_TTL_SECONDS
    _, ttl, _ = logic.validate_request({"ip": "8.8.8.8", "ttl": -5})
    assert ttl == 1


def test_parse_rule_expiry() -> None:
    logic = _load_logic()
    description = "CloudSentinel block until 2026-11-23T10:00:00Z (unit-test)"
    assert logic.parse_rule_expiry(description) == datetime(2026, 11, 23, 10, 0, tzinfo=UTC)
    assert logic.parse_rule_expiry("some other rule") is None
    assert logic.parse_rule_expiry("CloudSentinel block until not-a-time (unit)") is None


def test_rule_name_and_priority() -> None:
    logic = _load_logic()
    name = logic.rule_name("8.8.8.8")
    assert name == logic.rule_name("8.8.8.8")
    assert name.startswith("cs-block-")
    assert len(name) <= 80
    assert logic.choose_priority(set()) == logic.BLOCK_PRIORITY_MIN
    assert logic.choose_priority({logic.BLOCK_PRIORITY_MIN}) == logic.BLOCK_PRIORITY_MIN + 1
    full = set(range(logic.BLOCK_PRIORITY_MIN, logic.BLOCK_PRIORITY_MAX + 1))
    with pytest.raises(RuntimeError):
        logic.choose_priority(full)


def test_block_priorities_precede_allow_rules() -> None:
    logic = _load_logic()
    assert logic.BLOCK_PRIORITY_MAX < 200


def test_bicep_allow_rules_start_after_dynamic_block_range() -> None:
    bicep = (REPO_ROOT / "infra" / "main.bicep").read_text(encoding="utf-8")
    for rule in ("Allow-Honeypot-SSH", "Allow-HTTPS", "Allow-HTTP-ACME", "Allow-Management-SSH"):
        marker = f"name: '{rule}'"
        index = bicep.index(marker)
        priority_line = bicep[index:].split("priority:", 1)[1].splitlines()[0].strip()
        priority = int(priority_line.split()[0])
        assert priority > 199
