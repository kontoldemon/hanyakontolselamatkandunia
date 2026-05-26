"""
CloudSentinel GeoIP - IP geolocation enrichment via MaxMind GeoIP2.
Uses local GeoLite2-City.mmdb database file (free tier).
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

_geoip_reader: Any = None


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
        return _enrich_fallback(ip)
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
        return _enrich_fallback(ip)


def _enrich_fallback(ip: str, reason: str = "lookup_failed") -> dict[str, str]:
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private:
            return {
                "country_code": "PV", "country_name": "Private Network",
                "city": "Local", "continent": "XX",
                "latitude": "0", "longitude": "0", "timezone": "UTC",
            }
    except ValueError:
        pass
    return {
        "country_code": "XX", "country_name": "Unknown",
        "city": "Unknown", "continent": "XX",
        "latitude": "0", "longitude": "0", "timezone": "UTC",
    }


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
