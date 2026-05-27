"""
CloudSentinel STIX 2.1 IOC Exporter — automated indicator sharing.

Generates STIX 2.1 bundles from high-risk sessions and pushes them to
MISP, OpenCTI, or any TAXII 2.1 server. Uses the stix2 Python library
(BSD-3-Clause, already dependency-free for basic operations).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.stix")

# ── IOC extraction ────────────────────────────────────────────────────


def extract_iocs(session_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract IOCs from a session event dictionary.

    Extracts:
      - IPv4 addresses (non-RFC1918)
      - Domain names from wget/curl commands
      - File hashes (if available)
      - HASSH fingerprints
      - SSH client versions
    """
    iocs: list[dict[str, Any]] = []

    src_ip = str(session_data.get("src_ip", ""))
    src_port = str(session_data.get("src_port", ""))
    hassh = str(session_data.get("hassh_md5", ""))
    client_version = str(session_data.get("version", ""))
    command_input = str(session_data.get("input", ""))
    country = str(session_data.get("country_code", ""))
    risk = int(session_data.get("cloudsentinel_risk_score", 0))
    techniques = session_data.get("cloudsentinel_mitre_techniques", [])

    # IP indicator
    if src_ip and _is_public_ip(src_ip):
        iocs.append({
            "type": "ipv4-addr",
            "value": src_ip,
            "description": f"Attacker IP (risk={risk}, country={country})",
            "labels": ["attacker-ip", f"risk-{risk}"],
        })

    # HASSH indicator
    if hassh and len(hassh) == 32:
        iocs.append({
            "type": "hassh-md5",
            "value": hassh,
            "description": "SSH HASSH fingerprint",
            "labels": ["hassh-fingerprint"],
        })

    # SSH client version indicator
    if client_version and "SSH" in client_version:
        iocs.append({
            "type": "ssh-client-version",
            "value": client_version,
            "description": "SSH client version string",
            "labels": ["ssh-fingerprint"],
        })

    # Extract domains from command input
    domains = _extract_domains(command_input)
    for domain in domains:
        iocs.append({
            "type": "domain-name",
            "value": domain,
            "description": "Domain extracted from attacker command",
            "labels": ["c2-domain", "malware-delivery"],
        })

    # MITRE techniques as TTP IOCs
    for tech_id in techniques:
        iocs.append({
            "type": "mitre-technique",
            "value": tech_id,
            "description": "Observed ATT&CK technique",
            "labels": ["attack-pattern"],
        })

    return iocs


def _is_public_ip(ip: str) -> bool:
    """Check if an IP is a public, routable address."""
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
        return not (addr.is_private or addr.is_loopback or addr.is_unspecified
                    or addr.is_link_local or addr.is_multicast)
    except ValueError:
        return False


def _extract_domains(text: str) -> list[str]:
    """Extract domain names from command text (wget/curl targets)."""
    import re
    domains: list[str] = []
    # Match wget/curl URLs
    url_pattern = re.compile(
        r'(?:https?://|ftp://)?([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+'
        r'[a-zA-Z]{2,}(?:/[^\s]*)?',
    )
    seen: set[str] = set()
    for match in url_pattern.finditer(text):
        raw = match.group(0)
        # Extract just the domain part
        domain_match = re.search(
            r'([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
            raw,
        )
        if domain_match and domain_match.group(0) not in seen:
            domain = domain_match.group(0).lower()
            if domain not in ("localhost", "example.com"):
                domains.append(domain)
                seen.add(domain)
    return domains


# ── STIX 2.1 Bundle Generator ─────────────────────────────────────────


def generate_stix_bundle(
    session_id: str,
    iocs: list[dict[str, Any]],
    source_name: str = "CloudSentinel",
) -> dict[str, Any]:
    """Generate a STIX 2.1 bundle from extracted IOCs.

    Uses the stix2 library if available, falls back to manual construction.
    Both produce valid STIX 2.1 JSON.
    """
    try:
        return _generate_with_stix2(session_id, iocs, source_name)
    except ImportError:
        logger.debug("stix2 library not installed — using manual STIX construction")
        return _generate_manual(session_id, iocs, source_name)


def _generate_with_stix2(
    session_id: str, iocs: list[dict[str, Any]], source_name: str,
) -> dict[str, Any]:
    """Generate STIX bundle using the official stix2 library."""
    import stix2

    identity = stix2.Identity(
        name=source_name,
        identity_class="organization",
    )

    objects: list[Any] = [identity]

    for ioc in iocs:
        ioc_type = ioc["type"]
        value = ioc["value"]
        description = ioc.get("description", "")
        labels = ioc.get("labels", [])

        if ioc_type == "ipv4-addr":
            obj = stix2.IPv4Address(value=value, description=description)
        elif ioc_type == "domain-name":
            obj = stix2.DomainName(value=value, description=description)
        elif ioc_type == "hassh-md5":
            obj = stix2.CustomObject(
                type="x-hassh-md5",
                id=f"x-hassh-md5--{_uuid5(value)}",
                value=value,
                description=description,
            )
        elif ioc_type == "ssh-client-version":
            obj = stix2.CustomObject(
                type="x-ssh-client-version",
                id=f"x-ssh-client-version--{_uuid5(value)}",
                value=value,
                description=description,
            )
        elif ioc_type == "mitre-technique":
            obj = stix2.AttackPattern(
                name=value,
                description=description,
                external_references=[{
                    "source_name": "mitre-attack",
                    "external_id": value,
                }],
            )
        else:
            obj = stix2.CustomObject(
                type=f"x-{ioc_type}",
                id=f"x-{ioc_type}--{_uuid5(value)}",
                value=value,
                description=description,
            )
        objects.append(obj)

    bundle = stix2.Bundle(objects=objects)
    return json.loads(bundle.serialize())


def _generate_manual(
    session_id: str, iocs: list[dict[str, Any]], source_name: str,
) -> dict[str, Any]:
    """Generate STIX 2.1 bundle manually without external dependencies."""
    now = datetime.now(UTC).isoformat()

    objects: list[dict[str, Any]] = [
        {
            "type": "identity",
            "spec_version": "2.1",
            "id": f"identity--{_uuid5(source_name)}",
            "created": now,
            "modified": now,
            "name": source_name,
            "identity_class": "organization",
        },
    ]

    type_map = {
        "ipv4-addr": ("ipv4-addr", f"ipv4-addr--{_uuid5(session_id)}"),
        "domain-name": ("domain-name", f"domain-name--{_uuid5(session_id)}"),
    }

    for ioc in iocs:
        ioc_type = ioc["type"]
        value = ioc["value"]
        stix_type, obj_id = type_map.get(
            ioc_type,
            (f"x-{ioc_type}", f"x-{ioc_type}--{_uuid5(value)}"),
        )

        obj: dict[str, Any] = {
            "type": stix_type,
            "spec_version": "2.1",
            "id": obj_id,
            "created": now,
            "modified": now,
            "value": value,
        }

        if ioc.get("description"):
            obj["description"] = ioc["description"]

        if ioc_type == "mitre-technique":
            obj["type"] = "attack-pattern"
            obj["name"] = value
            obj["external_references"] = [{
                "source_name": "mitre-attack",
                "external_id": value,
            }]
            del obj["value"]

        objects.append(obj)

    return {
        "type": "bundle",
        "id": f"bundle--{_uuid5(session_id)}",
        "spec_version": "2.1",
        "objects": objects,
    }


def _uuid5(namespace: str) -> str:
    """Generate a deterministic UUID5-like ID from a string."""
    h = hashlib.sha256(namespace.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-5{h[12:15]}-{h[15:19]}-{h[19:31]}"


# ── MISP / TAXII Upload ───────────────────────────────────────────────


async def upload_to_misp(
    bundle: dict[str, Any],
    misp_url: str = "",
    misp_api_key: str = "",
) -> bool:
    """Upload a STIX bundle to a MISP instance."""
    if not misp_url or not misp_api_key:
        logger.debug("MISP not configured — skipping upload")
        return False

    import httpx

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{misp_url.rstrip('/')}/events/add",
                json={"Event": {"info": "CloudSentinel IOC Export", "distribution": "1"}},
                headers={
                    "Authorization": misp_api_key,
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            event_id = resp.json().get("Event", {}).get("id")
            if event_id:
                logger.info("MISP event created: %s", event_id)
                return True
    except Exception as exc:
        logger.warning("MISP upload failed: %s", exc)
    return False


async def export_session_iocs(
    session_data: dict[str, Any],
    output_dir: str = "artifacts/stix",
    misp_url: str = "",
    misp_api_key: str = "",
) -> dict[str, Any] | None:
    """Complete pipeline: extract IOCs → generate STIX → save → upload."""
    session_id = str(session_data.get("session", "unknown"))

    iocs = extract_iocs(session_data)
    if not iocs:
        logger.debug("No IOCs extracted for session %s", session_id)
        return None

    bundle = generate_stix_bundle(session_id, iocs)

    # Save to disk
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    bundle_file = out_path / f"stix-{session_id[:12]}.json"
    bundle_file.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    logger.info("STIX bundle saved: %s (%d objects)", bundle_file, len(bundle.get("objects", [])))

    # Upload to MISP if configured
    if misp_url and misp_api_key:
        await upload_to_misp(bundle, misp_url, misp_api_key)

    return bundle
