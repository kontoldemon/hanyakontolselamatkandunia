"""
CloudSentinel GeoIP - IP geolocation enrichment via MaxMind GeoIP2.
Uses local GeoLite2-City.mmdb database file (free tier).
"""

from __future__ import annotations

import ipaddress
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

_geoip_reader: Any = None
_geoip_http_cache: dict[str, tuple[float, dict[str, str]]] = {}
_GEOIP_HTTP_TTL_SECONDS = int(os.getenv("GEOIP_HTTP_CACHE_TTL_SECONDS", "86400"))
_GEOIP_HTTP_ENABLED = os.getenv("GEOIP_HTTP_FALLBACK", "true").lower() in {"1", "true", "yes", "on"}


def _get_reader() -> Any:
    global _geoip_reader
    if _geoip_reader is not None:
        return _geoip_reader
    try:
        import geoip2.database
        search_paths = [
            Path("/usr/share/GeoIP/GeoLite2-City.mmdb"),
            Path("/var/lib/GeoIP/GeoLite2-City.mmdb"),
            Path(__file__).parent.parent.parent / "data" / "GeoLite2-City.mmdb",
        ]
        for db_path in search_paths:
            if db_path.exists():
                _geoip_reader = geoip2.database.Reader(str(db_path))
                return _geoip_reader
    except ImportError:
        pass
    return None


def enrich(ip: str) -> dict[str, str]:
    reader = _get_reader()
    if reader is None:
        http_data = _enrich_http(ip)
        return http_data if http_data is not None else _enrich_fallback(ip)
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_unspecified:
            return _enrich_fallback(ip, reason="private")
        response = reader.city(ip)
        return {
            "country_code": response.country.iso_code or "XX",
            "country_name": response.country.name or "Unknown",
            "city": response.city.name or "Unknown",
            "continent": response.continent.code or "XX",
            "latitude": str(response.location.latitude or 0),
            "longitude": str(response.location.longitude or 0),
            "timezone": response.location.time_zone or "UTC",
        }
    except Exception:
        http_data = _enrich_http(ip)
        return http_data if http_data is not None else _enrich_fallback(ip)


def _enrich_fallback(ip: str, reason: str = "lookup_failed") -> dict[str, str]:
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private:
            return {
                "country_code": "PV", "country_name": "Private Network",
                "city": "Local", "continent": "XX",
                "region": "Local",
                "latitude": "0", "longitude": "0", "timezone": "UTC",
                "asn": "", "isp": "", "org": "", "services": "",
            }
    except ValueError:
        pass
    return {
        "country_code": "XX", "country_name": "Unknown",
        "city": "Unknown", "continent": "XX",
        "region": "Unknown",
        "latitude": "0", "longitude": "0", "timezone": "UTC",
        "asn": "", "isp": "", "org": "", "services": "",
    }


def _enrich_http(ip: str) -> dict[str, str] | None:
    if not _GEOIP_HTTP_ENABLED or not is_public_ip(ip):
        return None

    now = time.time()
    cached = _geoip_http_cache.get(ip)
    if cached and cached[0] > now:
        return cached[1]

    try:
        with urllib.request.urlopen(f"https://ipwho.is/{ip}", timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload or not bool(payload.get("success")):
            return None
        country_code = str(payload.get("country_code") or "XX").upper()
        if len(country_code) != 2:
            country_code = "XX"
        enriched = {
            "country_code": country_code,
            "country_name": str(payload.get("country") or "Unknown"),
            "city": str(payload.get("city") or "Unknown"),
            "region": str(payload.get("region") or "Unknown"),
            "continent": str(payload.get("continent_code") or "XX"),
            "latitude": str(payload.get("latitude") or 0),
            "longitude": str(payload.get("longitude") or 0),
            "timezone": str((payload.get("timezone") or {}).get("id") or "UTC"),
            "asn": str((payload.get("connection") or {}).get("asn") or ""),
            "isp": str((payload.get("connection") or {}).get("isp") or ""),
            "org": str((payload.get("connection") or {}).get("org") or ""),
            "services": str((payload.get("connection") or {}).get("type") or ""),
        }
        _geoip_http_cache[ip] = (now + _GEOIP_HTTP_TTL_SECONDS, enriched)
        return enriched
    except Exception:
        return None


def is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return not (
            addr.is_private or addr.is_loopback
            or addr.is_multicast or addr.is_unspecified
        )
    except ValueError:
        return False


async def enrich_async(ip: str) -> dict[str, str]:
    """Async wrapper for GeoIP enrichment (runs lookup in thread pool).

    Use this instead of enrich() in async contexts to avoid blocking
    the event loop on geoip2 database reads.
    """
    import asyncio
    return await asyncio.to_thread(enrich, ip)
