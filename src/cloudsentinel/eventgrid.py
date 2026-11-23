"""Event Grid custom-topic publisher for SOAR block requests."""

from __future__ import annotations

import ipaddress
import json
import uuid
from datetime import UTC, datetime

import httpx
import structlog

logger = structlog.get_logger("cloudsentinel.eventgrid")

EVENT_TYPE = "CloudSentinel.BlockRequested"
EVENT_SOURCE = "cloudsentinel.sensor"


async def publish_block(
    endpoint: str,
    key: str,
    ip: str,
    ttl: int,
    reason: str,
    risk_score: int,
    session_id: str,
    timeout: float = 5.0,
) -> tuple[bool, str]:
    """Publish a block request to an Event Grid custom topic.

    Returns (ok, error). The caller falls back to Redis or the local
    firewall when the publish fails.
    """
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False, f"invalid IP address: {ip}"
    if not endpoint.startswith("https://"):
        return False, "Event Grid endpoint must be https"
    if not key:
        return False, "missing Event Grid topic key"

    event = {
        "id": str(uuid.uuid4()),
        "source": EVENT_SOURCE,
        "specversion": "1.0",
        "type": EVENT_TYPE,
        "subject": ip,
        "time": datetime.now(UTC).isoformat(),
        "data": {
            "ip": ip,
            "ttl": int(ttl),
            "reason": str(reason)[:120],
            "risk_score": int(risk_score),
            "session_id": str(session_id),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                endpoint,
                content=json.dumps(event).encode(),
                headers={
                    "Content-Type": "application/cloudevents+json",
                    "aeg-sas-key": key,
                },
            )
    except Exception as exc:
        logger.warning("Event Grid publish failed: %s", exc)
        return False, str(exc)

    if 200 <= response.status_code < 300:
        return True, ""
    return False, f"{response.status_code} {response.text[:200]}"
