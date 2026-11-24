"""Pure read-model helpers shared by the admin API."""

from __future__ import annotations

import os
import time
from typing import Any

from ..geoip import enrich as geo_enrich


def _truth_window_hours() -> int:
    raw = os.getenv("CLOUDSENTINEL_TRUTH_WINDOW_HOURS", "0").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _truth_time_filter() -> str:
    hours = _truth_window_hours()
    return "1=1" if hours == 0 else f"timestamp >= now() - INTERVAL {hours} HOUR"


def _strict_truth_mode_enabled() -> bool:
    raw = os.getenv("CLOUDSENTINEL_STRICT_TRUTH", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _persistent_online_enabled() -> bool:
    raw = os.getenv("CLOUDSENTINEL_WAR_ROOM_PERSISTENT_ONLINE", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _display_country(enriched: dict[str, str]) -> str:
    code = str(enriched.get("country_code") or "XX")
    name = str(enriched.get("country_name") or "Unknown")
    return code if code != "XX" else name


def _enrichment_for_ip(ip: str, country_code: str = "", country_name: str = "") -> dict[str, str]:
    enriched = geo_enrich(ip)
    if country_code and country_code not in {"XX", "??", "UNKNOWN"}:
        enriched["country_code"] = country_code
    if country_name and country_name.lower() != "unknown":
        enriched["country_name"] = country_name
    return enriched


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _is_noise_event(eventid: str) -> bool:
    normalized = (eventid or "").strip().lower()
    return normalized in {
        "cloudsentinel.session.connect",
        "cloudsentinel.session.closed",
    }


def _is_noise_text(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return False
    return (
        text.startswith("cloudsentinel.")
        or text == "auth-attempt"
        or "[redacted]" in text
    )


def _derive_response_mode(eventid: str, source: str, output: str, command: str) -> str:
    src = (source or "").strip().lower()
    if src == "command_registry":
        return "command_registry"
    if src in {"blocked", "deterministic", "templated", "llm", "noise_filtered"}:
        return src
    out = (output or "").strip().lower()
    cmd = (command or "").strip().lower()
    if "command not found" in out or "permission denied" in out:
        return "blocked"
    if cmd.startswith(("ps", "free", "df", "netstat", "ss ", "find ", "history", "env ")):
        return "templated"
    if eventid == "cloudsentinel.command.output":
        return "deterministic"
    return "deterministic"


def _event_sort_priority(eventid: str) -> int:
    normalized = (eventid or "").strip().lower()
    if normalized == "cloudsentinel.command.input":
        return 0
    if normalized == "cloudsentinel.command.output":
        return 1
    return 2


def _now_ms() -> int:
    return int(time.time() * 1000)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _state_to_public(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"under_attack", "under attack"}:
        return "under_attack"
    if normalized == "live":
        return "live"
    return "offline"


def _trim_replay_entries(entries: list[dict[str, str]], limit: int = 400) -> list[dict[str, str]]:
    if len(entries) <= limit:
        return entries
    info_entries: list[dict[str, str]] = []
    stream_entries: list[dict[str, str]] = []
    for entry in entries:
        text = str(entry.get("text") or "").strip().lower()
        if text.startswith("[open]") or text.startswith("[close]") or text.startswith("[auth]") or text.startswith("[version]"):
            info_entries.append(entry)
        else:
            stream_entries.append(entry)
    keep: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in info_entries:
        key = (
            str(entry.get("role") or ""),
            str(entry.get("text") or ""),
            str(entry.get("timestamp") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        keep.append(entry)
    remaining = max(0, limit - len(keep))
    if remaining > 0:
        tail = stream_entries[-remaining:]
        for entry in tail:
            key = (
                str(entry.get("role") or ""),
                str(entry.get("text") or ""),
                str(entry.get("timestamp") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            keep.append(entry)
    keep.sort(key=lambda e: str(e.get("timestamp") or ""))
    if len(keep) > limit:
        keep = keep[-limit:]
    return keep
