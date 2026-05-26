"""
CloudSentinel MISP Integration — Live threat feed ingestion.
Pulls IOCs from MISP instances and enriches SOAR scoring.
"""

from __future__ import annotations

import asyncio
import hashlib
import structlog
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import hishel
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger("cloudsentinel.misp")

MISP_URL = os.getenv("CLOUDSENTINEL_MISP_URL", "")
MISP_API_KEY = os.getenv("CLOUDSENTINEL_MISP_API_KEY", "")
MISP_VERIFY_SSL = os.getenv("CLOUDSENTINEL_MISP_VERIFY_SSL", "true").lower() == "true"
MISP_REFRESH_SECONDS = int(os.getenv("CLOUDSENTINEL_MISP_REFRESH", "3600"))


@dataclass
class MISPFeed:
    """MISP IOC feed with in-memory caching and auto-refresh."""

    url: str = MISP_URL
    api_key: str = MISP_API_KEY
    verify_ssl: bool = MISP_VERIFY_SSL
    refresh_seconds: int = MISP_REFRESH_SECONDS
    _client: hishel.AsyncCacheClient | None = None
    _ips: set[str] = field(default_factory=set)
    _domains: set[str] = field(default_factory=set)
    _urls: set[str] = field(default_factory=set)
    _hashes: set[str] = field(default_factory=set)
    _last_refresh: float = 0.0
    _refresh_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if not self.url or not self.api_key:
            logger.info("MISP not configured — skipping threat feed")
            return
        self._client = hishel.AsyncCacheClient(
            base_url=self.url.rstrip("/"),
            headers={
                "Authorization": self.api_key,
                "Accept": "application/json",
            },
            verify=self.verify_ssl,
            timeout=30.0,
        )
        await self.refresh()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("MISP feed active: %d IPs, %d domains, %d URLs",
                     len(self._ips), len(self._domains), len(self._urls))

    async def stop(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self.refresh_seconds)
            await self.refresh()

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(5))
    async def _fetch_misp_data(self) -> list[dict[str, Any]]:
        if not self._client:
            return []
        resp = await self._client.post(
            "/attributes/restSearch",
            json={
                "returnFormat": "json",
                "last": "7d",
                "type": ["ip-src", "ip-dst", "domain", "url", "md5", "sha256"],
                "to_ids": True,
                "limit": 5000,
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", {}).get("Attribute", [])

    async def refresh(self) -> None:
        """Pull recent IOCs from MISP REST API."""
        if not self._client:
            return
        try:
            attributes = await self._fetch_misp_data()

            for attr in attributes:
                atype = attr.get("type", "")
                value = attr.get("value", "").strip()
                if not value:
                    continue
                if atype in ("ip-src", "ip-dst"):
                    self._ips.add(value)
                elif atype == "domain":
                    self._domains.add(value)
                elif atype == "url":
                    self._urls.add(value)
                elif atype in ("md5", "sha256"):
                    self._hashes.add(value)

            self._last_refresh = time.time()
            logger.debug("MISP refresh: %d IOCs loaded", len(attributes))
        except Exception as exc:
            logger.warning("MISP refresh failed: %s", exc)

    def is_malicious_ip(self, ip: str) -> bool:
        return ip in self._ips

    def is_malicious_domain(self, domain: str) -> bool:
        return domain in self._domains

    def is_malicious_url(self, url: str) -> bool:
        return url in self._urls or any(u in url for u in self._urls if len(u) > 8)

    def is_malicious_hash(self, h: str) -> bool:
        return h.lower() in self._hashes

    @property
    def stats(self) -> dict[str, int]:
        return {
            "ips": len(self._ips),
            "domains": len(self._domains),
            "urls": len(self._urls),
            "hashes": len(self._hashes),
            "last_refresh": self._last_refresh,
        }


# Singleton
_misp_feed: MISPFeed | None = None


def get_misp_feed() -> MISPFeed:
    global _misp_feed
    if _misp_feed is None:
        _misp_feed = MISPFeed()
    return _misp_feed
