"""Pure validation and naming helpers for the Azure NSG blocker."""

from __future__ import annotations

import hashlib
import ipaddress
from datetime import UTC, datetime
from typing import Any

DEFAULT_ALLOWLIST = (
    "10.0.0.0/8,"
    "172.16.0.0/12,"
    "192.168.0.0/16,"
    "127.0.0.0/8,"
    "169.254.0.0/16"
)
BLOCK_PRIORITY_MIN = 200
BLOCK_PRIORITY_MAX = 3999
MAX_TTL_SECONDS = 7 * 24 * 60 * 60


def validate_request(data: dict[str, Any], allowlist: str = "") -> tuple[str, int, str]:
    ip = str(data.get("ip") or "").strip()
    address = ipaddress.ip_address(ip)
    if not address.is_global:
        raise ValueError(f"IP is not public: {ip}")

    raw_allowlist = allowlist or DEFAULT_ALLOWLIST
    networks = [
        ipaddress.ip_network(part.strip(), strict=False)
        for part in raw_allowlist.split(",")
        if part.strip()
    ]
    if any(address in network for network in networks):
        raise ValueError(f"IP is allowlisted: {ip}")

    ttl = int(data.get("ttl") or 86400)
    ttl = max(1, min(ttl, MAX_TTL_SECONDS))
    reason = str(data.get("reason") or "cloudsentinel")[:120]
    return ip, ttl, reason


def rule_name(ip: str) -> str:
    digest = hashlib.sha256(ip.encode()).hexdigest()[:12]
    return f"cs-block-{digest}"


def choose_priority(used: set[int]) -> int:
    for priority in range(BLOCK_PRIORITY_MIN, BLOCK_PRIORITY_MAX + 1):
        if priority not in used:
            return priority
    raise RuntimeError("No free NSG rule priority")


def parse_rule_expiry(description: str) -> datetime | None:
    prefix = "CloudSentinel block until "
    if not description.startswith(prefix):
        return None
    raw = description[len(prefix):].split(" ", 1)[0]
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None
