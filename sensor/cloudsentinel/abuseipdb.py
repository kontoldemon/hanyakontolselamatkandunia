"""
CloudSentinel AbuseIPDB Integration — IP reputation scoring.
Enriches SOAR scoring with community-driven threat intelligence.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger("cloudsentinel.abuseipdb")

ABUSEIPDB_API_KEY = os.getenv("CLOUDSENTINEL_ABUSEIPDB_KEY", "")
ABUSEIPDB_CACHE_TTL = int(os.getenv("CLOUDSENTINEL_ABUSEIPDB_CACHE_TTL", "3600"))


class AbuseIPDBClient:
    """Async AbuseIPDB v2 API client with TTL-based caching."""

    BASE_URL = "https://api.abuseipdb.com/api/v2"

    def __init__(self, api_key: str = ABUSEIPDB_API_KEY) -> None:
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._cache_ttl = ABUSEIPDB_CACHE_TTL

    async def start(self) -> None:
        if not self.api_key:
            logger.info("AbuseIPDB: no API key — disabled")
            return
        self._client = httpx.AsyncClient(
            headers={"Key": self.api_key, "Accept": "application/json"},
            timeout=10.0,
        )
        logger.info("AbuseIPDB client ready")

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()

    async def check(self, ip: str, max_age_days: int = 90) -> dict[str, Any]:
        """Check an IP against AbuseIPDB and return reputation data."""
        if not self._client:
            return {"abuse_confidence_score": 0, "total_reports": 0, "country_code": ""}

        # Check cache
        cached = self._cache.get(ip)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            return cached[1]

        try:
            resp = await self._client.get(
                f"{self.BASE_URL}/check",
                params={
                    "ipAddress": ip,
                    "maxAgeInDays": str(max_age_days),
                    "verbose": "",
                },
            )
            if resp.status_code == 429:
                logger.warning("AbuseIPDB rate limited — using empty report")
                return {"abuse_confidence_score": 0, "total_reports": 0}

            resp.raise_for_status()
            data = resp.json().get("data", {})

            result = {
                "abuse_confidence_score": data.get("abuseConfidenceScore", 0),
                "total_reports": data.get("totalReports", 0),
                "country_code": data.get("countryCode", ""),
                "isp": data.get("isp", ""),
                "domain": data.get("domain", ""),
                "usage_type": data.get("usageType", ""),
                "last_reported_at": data.get("lastReportedAt", ""),
            }
            self._cache[ip] = (time.time(), result)
            return result
        except Exception as exc:
            logger.debug("AbuseIPDB check for %s failed: %s", ip, exc)
            return {"abuse_confidence_score": 0, "total_reports": 0}

    def soar_bonus(self, report: dict[str, Any]) -> int:
        """Convert AbuseIPDB confidence to SOAR score bonus (0-30)."""
        score = report.get("abuse_confidence_score", 0)
        reports = report.get("total_reports", 0)
        bonus = int(score * 0.3)
        if reports > 100:
            bonus = min(30, bonus + 10)
        elif reports > 10:
            bonus = min(30, bonus + 5)
        return bonus

    @property
    def stats(self) -> dict[str, int]:
        return {"cache_size": len(self._cache)}


# Singleton
_abuseipdb: AbuseIPDBClient | None = None


def get_abuseipdb() -> AbuseIPDBClient:
    global _abuseipdb
    if _abuseipdb is None:
        _abuseipdb = AbuseIPDBClient()
    return _abuseipdb
