"""Pure read-model helpers shared by the admin API."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any

import structlog

from ..config import Settings, secret_to_str
from ..geoip import enrich as geo_enrich
from ..hassh import HASSHDNA, fallback_hassh_from_version, infer_client_software
from ..soar import ENFORCED_BLOCK_ACTIONS, NEW_BLOCK_ACTIONS

logger = structlog.get_logger("cloudsentinel.api.queries")


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


ACTIVE_FRESHNESS_WINDOW_SECONDS = 90


SYNTHETIC_ACTIVE_WINDOW_SECONDS = ACTIVE_FRESHNESS_WINDOW_SECONDS


WAR_ROOM_ACTIVE_FRESHNESS_MS = ACTIVE_FRESHNESS_WINDOW_SECONDS * 1000


WAR_ROOM_EVIDENCE_LOOKBACK_MINUTES = 30


WAR_ROOM_ATTACK_EVENT_IDS = (
    "cloudsentinel.login.failed",
    "cloudsentinel.command.input",
    "cloudsentinel.command.failed",
    "cloudsentinel.client.version",
    "cloudsentinel.http.request",
)


def _load_recent_sessions_from_clickhouse(settings: Settings, limit: int = 50) -> list[dict[str, Any]]:
    if not settings.clickhouse.enabled:
        return []
    try:
        import clickhouse_connect

        query = f"""
            SELECT
                session,
                src_ip,
                anyIf(country_code, country_code != '') AS country_code,
                anyIf(country_name, country_name != '') AS country_name,
                anyIf(city, city != '') AS city,
                anyIf(latitude, latitude != '' AND latitude != '0') AS latitude,
                anyIf(longitude, longitude != '' AND longitude != '0') AS longitude,
                anyIf(timezone, timezone != '') AS timezone,
                min(timestamp) AS first_seen,
                max(timestamp) AS last_seen,
                maxIf(timestamp, eventid = 'cloudsentinel.session.connect') AS latest_connect,
                maxIf(timestamp, eventid = 'cloudsentinel.session.closed') AS latest_close,
                anyIf(hassh_md5, hassh_md5 != '') AS hassh_md5,
                anyIf(hassh_algorithms, hassh_algorithms != '') AS hassh_algorithms,
                anyIf(version, version != '') AS client_version,
                argMax(cloudsentinel_soar_action, timestamp) AS last_soar_action,
                max(mttb_ms) AS max_mttb_ms,
                groupArray((timestamp, eventid, input, reason, username, password, attempt, auth_type, version, duration)) AS replay_timeline,
                arrayDistinct(arrayFlatten(groupArray(cloudsentinel_mitre_techniques))) AS techniques,
                max(cloudsentinel_risk_score) AS max_risk
            FROM {settings.clickhouse.table}
            WHERE {_truth_time_filter()}
              AND session != ''
              AND src_ip != ''
              AND src_ip != '0.0.0.0'
            GROUP BY session, src_ip
            ORDER BY last_seen DESC
            LIMIT {int(limit)}
        """
        client = clickhouse_connect.get_client(
            host=settings.clickhouse.host,
            port=settings.clickhouse.port,
            username=settings.clickhouse.username,
            password=secret_to_str(settings.clickhouse.password),
            database=settings.clickhouse.database,
        )
        result = client.query(query)
        rows: list[dict[str, Any]] = []
        now = time.time()
        hassh_db = HASSHDNA()
        for row in result.result_rows:
            session_id = str(row[0] or "")
            src_ip = str(row[1] or "")
            country = str(row[2] or "XX")
            country_name = str(row[3] or "")
            city = str(row[4] or "")
            latitude = str(row[5] or "")
            longitude = str(row[6] or "")
            timezone_name = str(row[7] or "")
            first_seen = row[8]
            last_seen = row[9]
            latest_connect = row[10]
            latest_close = row[11]
            hassh = str(row[12] or "")
            hassh_algorithms = str(row[13] or "")
            client_version = str(row[14] or "")
            last_soar_action = str(row[15] or "none")
            max_mttb_ms = float(row[16] or 0)
            timeline_items = list(row[17] or [])
            techniques = [str(v) for v in (row[18] or []) if str(v).strip()]
            risk = int(row[19] or 0)
            if not hassh and hassh_algorithms:
                try:
                    import hashlib

                    hassh = hashlib.md5(hassh_algorithms.encode("utf-8"), usedforsecurity=False).hexdigest()
                except Exception:
                    pass
            if not hassh and client_version:
                try:
                    hassh, hassh_algorithms = fallback_hassh_from_version(
                        client_version,
                        settings.honeypot.server_version,
                    )
                except Exception:
                    pass
            first_ts = first_seen.timestamp() if hasattr(first_seen, "timestamp") else now
            last_ts = last_seen.timestamp() if hasattr(last_seen, "timestamp") else now
            latest_connect_ts = (
                latest_connect.timestamp() if hasattr(latest_connect, "timestamp") else first_ts
            )
            latest_close_ts = (
                latest_close.timestamp() if hasattr(latest_close, "timestamp") else 0.0
            )
            is_active = now - last_ts <= ACTIVE_FRESHNESS_WINDOW_SECONDS
            if is_active:
                duration_sec = max(0, int(now - latest_connect_ts))
            elif latest_close_ts >= latest_connect_ts > 0:
                duration_sec = max(0, int(latest_close_ts - latest_connect_ts))
            else:
                duration_sec = max(0, int(last_ts - first_ts))

            replay: list[dict[str, str]] = []
            commands: list[str] = []
            normalized_timeline: list[tuple[float, str, str, str, str, str, int, str, str, str]] = []
            latest_input = ""
            for item in timeline_items:
                try:
                    ts_raw = item[0]
                    eventid = item[1]
                    input_value = item[2]
                    reason = item[3]
                    username = item[4] if len(item) > 4 else ""
                    password_value = item[5] if len(item) > 5 else ""
                    attempt_raw = item[6] if len(item) > 6 else 0
                    try:
                        attempt = int(attempt_raw or 0)
                    except Exception:
                        attempt = 0
                    auth_type = item[7] if len(item) > 7 else ""
                    version = item[8] if len(item) > 8 else ""
                    duration = item[9] if len(item) > 9 else ""
                except Exception:
                    continue
                if hasattr(ts_raw, "timestamp"):
                    ts_value = float(ts_raw.timestamp())
                else:
                    ts_value = float(now)
                normalized_timeline.append(
                    (
                        ts_value,
                        str(eventid or ""),
                        str(input_value or ""),
                        str(reason or ""),
                        str(username or ""),
                        str(password_value or ""),
                        attempt,
                        str(auth_type or ""),
                        str(version or ""),
                        str(duration or ""),
                    )
                )

            normalized_timeline.sort(key=lambda value: (value[0], _event_sort_priority(value[1])))
            replay_seen: set[tuple[str, str, str]] = set()
            for (
                ts_value,
                eventid,
                input_value,
                reason,
                username,
                password_value,
                attempt,
                auth_type,
                version,
                duration,
            ) in normalized_timeline:
                dt = time.localtime(ts_value)
                ms = int((ts_value - int(ts_value)) * 1000)
                stamp = f"{time.strftime('%H:%M:%S', dt)}.{ms:03d}"
                info_text = ""
                if eventid == "cloudsentinel.session.connect":
                    info_text = "[OPEN] Session opened"
                elif eventid == "cloudsentinel.session.closed":
                    duration_value = duration.strip()
                    info_text = (
                        f"[CLOSE] Session closed ({duration_value}s)"
                        if duration_value
                        else "[CLOSE] Session closed"
                    )
                elif eventid == "cloudsentinel.login.failed":
                    user = username.strip() or "unknown"
                    password = password_value.strip() or "unknown"
                    attempt_suffix = f" attempt {attempt}" if attempt > 0 else ""
                    method = auth_type.strip()
                    if method and method != "password":
                        info_text = f"[AUTH] Failed login for {user} / {password} via {method}{attempt_suffix}"
                    else:
                        info_text = f"[AUTH] Failed login for {user} / {password}{attempt_suffix}"
                elif eventid == "cloudsentinel.login.success":
                    user = username.strip() or "unknown"
                    password = password_value.strip() or "unknown"
                    info_text = f"[AUTH] Login success for {user} / {password}"
                elif eventid == "cloudsentinel.client.version":
                    version_value = version.strip() or client_version.strip()
                    info_text = f"[VERSION] {version_value}" if version_value else "[VERSION] Client banner observed"

                if info_text:
                    info_entry = {
                        "role": "honeypot",
                        "text": info_text[:2000],
                        "timestamp": stamp,
                    }
                    info_key = (info_entry["role"], info_entry["text"], info_entry["timestamp"])
                    if info_key not in replay_seen:
                        replay_seen.add(info_key)
                        replay.append(info_entry)
                    continue

                if eventid == "cloudsentinel.command.input" and input_value.strip():
                    if _is_noise_text(input_value):
                        continue
                    commands.append(input_value)
                    latest_input = input_value
                    attacker_entry = {
                        "role": "attacker",
                        "text": input_value[:2000],
                        "timestamp": stamp,
                    }
                    attacker_key = (attacker_entry["role"], attacker_entry["text"], attacker_entry["timestamp"])
                    if attacker_key not in replay_seen:
                        replay_seen.add(attacker_key)
                        replay.append(attacker_entry)
                elif eventid == "cloudsentinel.command.output":
                    display_reason = reason.strip()
                    if not display_reason:
                        continue
                    # Drop pure command-echo artifacts so replay shows real output only.
                    if latest_input:
                        attacker_text = latest_input.strip()
                        reply_text = display_reason.strip()
                        if reply_text == attacker_text:
                            continue
                        # Some handlers may echo command as first line before real text.
                        # If the whole output is just one echoed line, suppress it.
                        if "\n" not in reply_text and "\r" not in reply_text and reply_text.startswith(attacker_text):
                            continue
                    if _is_noise_text(display_reason):
                        continue
                    honeypot_entry = {
                        "role": "honeypot",
                        "text": display_reason[:2000],
                        "timestamp": stamp,
                        "response_mode": _derive_response_mode(eventid, "", display_reason, latest_input),
                    }
                    honeypot_key = (honeypot_entry["role"], honeypot_entry["text"], honeypot_entry["timestamp"])
                    if honeypot_key not in replay_seen:
                        replay_seen.add(honeypot_key)
                        replay.append(honeypot_entry)
            client = infer_client_software(client_version, hassh)
            if client == "unknown" and hassh:
                intel = hassh_db.lookup(hassh)
                intel_label = str(intel.get("client_software", "unknown"))
                if intel_label.lower() != "unknown":
                    client = intel_label
            if client == "unknown" and hassh:
                client = f"hassh:{hassh[:8]}"
            enriched = _enrichment_for_ip(src_ip, country, country_name)
            if city:
                enriched["city"] = city
            if latitude:
                enriched["latitude"] = latitude
            if longitude:
                enriched["longitude"] = longitude
            if timezone_name:
                enriched["timezone"] = timezone_name
            rows.append(
                {
                    "id": session_id or f"sess-{src_ip}-{int(last_ts)}",
                    "ip": src_ip,
                    "country": _display_country(enriched),
                    "countryCode": enriched.get("country_code", "XX"),
                    "countryName": enriched.get("country_name", "Unknown"),
                    "asn": enriched.get("asn", ""),
                    "isp": enriched.get("isp", ""),
                    "org": enriched.get("org", ""),
                    "services": enriched.get("services", ""),
                    "region": enriched.get("region", "Unknown"),
                    "city": enriched.get("city", "Unknown"),
                    "latitude": enriched.get("latitude", "0"),
                    "longitude": enriched.get("longitude", "0"),
                    "timezone": enriched.get("timezone", "UTC"),
                    "startTime": time.strftime("%H:%M:%S", time.localtime(first_ts)),
                    "duration": f"{duration_sec // 60}m {duration_sec % 60}s",
                    "startedAtEpochMs": int(latest_connect_ts * 1000),
                    "firstSeenEpochMs": int(first_ts * 1000),
                    "lastSeenEpochMs": int(last_ts * 1000),
                    "client": client,
                    "fingerprint": hassh,
                    "input": commands[:200],
                    "status": "Active" if is_active else "Closed",
                    "sessionCount": 1,
                    "riskScore": risk,
                    "soarAction": last_soar_action,
                    "mttbMs": max_mttb_ms,
                    "blockEffective": last_soar_action in {"iptables_block", "already_blocked"},
                    "mitreTechniques": techniques[:20],
                    "replay": _trim_replay_entries(replay, limit=400),
                    "source": "clickhouse",
                }
            )
        return rows
    except Exception:
        return []


def _events_max_limit() -> int:
    raw = os.getenv("CLOUDSENTINEL_EVENTS_MAX_LIMIT", "20000").strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = 20000
    return max(1, min(configured, 50000))


def _action_in(column: str, actions: frozenset[str]) -> str:
    values = ", ".join(f"'{action}'" for action in sorted(actions))
    return f"{column} IN ({values})"


def _load_recent_events_from_clickhouse(settings: Settings, limit: int = 100) -> list[dict[str, Any]]:
    if not settings.clickhouse.enabled:
        return []
    try:
        import clickhouse_connect

        safe_limit = max(1, min(int(limit), _events_max_limit()))
        query = f"""
            SELECT
                eventid,
                src_ip,
                country_code,
                country_name,
                city,
                latitude,
                longitude,
                timezone,
                input,
                username,
                password,
                hassh_md5,
                hassh_algorithms,
                version,
                reason,
                '' AS source,
                '' AS response_mode,
                cloudsentinel_mitre_techniques,
                cloudsentinel_soar_action,
                cloudsentinel_risk_score,
                mttb_ms,
                timestamp
            FROM {settings.clickhouse.table}
            WHERE {_truth_time_filter()}
              AND src_ip != ''
              AND src_ip != '0.0.0.0'
            ORDER BY timestamp DESC
            LIMIT {safe_limit}
        """
        client = clickhouse_connect.get_client(
            host=settings.clickhouse.host,
            port=settings.clickhouse.port,
            username=settings.clickhouse.username,
            password=secret_to_str(settings.clickhouse.password),
            database=settings.clickhouse.database,
        )
        result = client.query(query)
        events: list[dict[str, Any]] = []
        enrich_cache: dict[str, dict[str, str]] = {}
        for row in result.result_rows:
            ts = row[21]
            if hasattr(ts, "timestamp"):
                epoch = float(ts.replace(tzinfo=UTC).timestamp() if getattr(ts, "tzinfo", None) is None else ts.timestamp())
            else:
                epoch = time.time()
            eventid = str(row[0] or "")
            if _is_noise_event(eventid):
                continue
            ip = str(row[1] or "")
            cache_key = f"{ip}|{row[2] or 'XX'!s}|{row[3] or ''!s}"
            enriched = enrich_cache.get(cache_key)
            if enriched is None:
                enriched = _enrichment_for_ip(ip, str(row[2] or "XX"), str(row[3] or ""))
                enrich_cache[cache_key] = enriched
            for key, index in (("city", 4), ("latitude", 5), ("longitude", 6), ("timezone", 7)):
                value = str(row[index] or "")
                if value and value not in {"0", "Unknown"}:
                    enriched[key] = value
            input_value = str(row[8] or "")
            reason_value = str(row[14] or "")
            if _is_noise_text(input_value) and _is_noise_text(reason_value):
                continue
            source_value = str(row[15] or "")
            response_mode_value = str(row[16] or "")
            derived_mode = _derive_response_mode(eventid, source_value, reason_value, input_value)
            events.append(
                {
                    "id": f"{eventid or 'evt'}-{row[1] or ''!s}-{int(epoch * 1000)}",
                    "eventid": eventid,
                    "src_ip": ip,
                    "country_code": enriched.get("country_code", "XX"),
                    "country_name": enriched.get("country_name", "Unknown"),
                    "asn": enriched.get("asn", ""),
                    "isp": enriched.get("isp", ""),
                    "org": enriched.get("org", ""),
                    "services": enriched.get("services", ""),
                    "region": enriched.get("region", "Unknown"),
                    "city": enriched.get("city", "Unknown"),
                    "latitude": enriched.get("latitude", "0"),
                    "longitude": enriched.get("longitude", "0"),
                    "timezone": enriched.get("timezone", "UTC"),
                    "input": input_value,
                    "username": str(row[9] or ""),
                    "password": str(row[10] or ""),
                    "hassh_md5": str(row[11] or ""),
                    "hassh_algorithms": str(row[12] or ""),
                    "version": str(row[13] or ""),
                    "ja4s": "",
                    "reason": reason_value,
                    "source": source_value,
                    "response_mode": response_mode_value or derived_mode,
                    "cloudsentinel_mitre_techniques": [str(v) for v in (row[17] or []) if str(v)],
                    "cloudsentinel_soar_action": str(row[18] or "none"),
                    "cloudsentinel_risk_score": int(row[19] or 0),
                    "mttb_ms": float(row[20] or 0),
                    "timestamp": epoch,
                }
            )
        return events
    except Exception:
        return []


def _latest_mttb_from_clickhouse(settings: Settings) -> float:
    if not settings.clickhouse.enabled:
        return 0.0
    try:
        import clickhouse_connect

        query = f"""
            SELECT anyLast(mttb_ms)
            FROM {settings.clickhouse.table}
            WHERE {_truth_time_filter()}
              AND mttb_ms > 0
              AND cloudsentinel_soar_action != 'none'
        """
        client = clickhouse_connect.get_client(
            host=settings.clickhouse.host,
            port=settings.clickhouse.port,
            username=settings.clickhouse.username,
            password=secret_to_str(settings.clickhouse.password),
            database=settings.clickhouse.database,
        )
        result = client.query(query)
        if not result.result_rows:
            return 0.0
        return float(result.result_rows[0][0] or 0)
    except Exception:
        return 0.0


def _load_attack_distribution_from_clickhouse(settings: Settings) -> dict[str, int]:
    if not settings.clickhouse.enabled:
        return {
            "Brute Force": 0,
            "Command Injection": 0,
            "Port Scanning": 0,
            "Malware Upload": 0,
        }
    try:
        import clickhouse_connect

        query = f"""
            SELECT eventid, count() AS hits
            FROM {settings.clickhouse.table}
            WHERE {_truth_time_filter()}
              AND src_ip != ''
              AND src_ip != '0.0.0.0'
              AND eventid IN (
                  'cloudsentinel.login.failed',
                  'cloudsentinel.command.input',
                  'cloudsentinel.session.connect',
                  'cloudsentinel.http.request'
              )
            GROUP BY eventid
        """
        client = clickhouse_connect.get_client(
            host=settings.clickhouse.host,
            port=settings.clickhouse.port,
            username=settings.clickhouse.username,
            password=secret_to_str(settings.clickhouse.password),
            database=settings.clickhouse.database,
        )
        rows = client.query(query).result_rows
        counts = {str(row[0]): int(row[1] or 0) for row in rows}
        return {
            "Brute Force": counts.get("cloudsentinel.login.failed", 0),
            "Command Injection": counts.get("cloudsentinel.command.input", 0),
            "Port Scanning": counts.get("cloudsentinel.session.connect", 0),
            "Malware Upload": counts.get("cloudsentinel.http.request", 0),
        }
    except Exception:
        return {
            "Brute Force": 0,
            "Command Injection": 0,
            "Port Scanning": 0,
            "Malware Upload": 0,
        }


def _load_attack_graph_from_clickhouse(settings: Settings, limit: int = 60) -> dict[str, list[dict[str, Any]]]:
    if not settings.clickhouse.enabled:
        return {"nodes": [], "edges": []}
    try:
        import clickhouse_connect

        safe_limit = max(1, min(int(limit), 200))
        query = f"""
            SELECT
                src_ip,
                count() AS sessions,
                max(cloudsentinel_risk_score) AS risk,
                arrayDistinct(arrayFlatten(groupArray(cloudsentinel_mitre_techniques))) AS techniques,
                anyIf(hassh_md5, hassh_md5 != '') AS hassh_md5
            FROM {settings.clickhouse.table}
            WHERE {_truth_time_filter()}
              AND src_ip != ''
              AND src_ip != '0.0.0.0'
            GROUP BY src_ip
            ORDER BY risk DESC, sessions DESC
            LIMIT {safe_limit}
        """
        client = clickhouse_connect.get_client(
            host=settings.clickhouse.host,
            port=settings.clickhouse.port,
            username=settings.clickhouse.username,
            password=secret_to_str(settings.clickhouse.password),
            database=settings.clickhouse.database,
        )
        result_rows = client.query(query).result_rows
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for index, row in enumerate(result_rows):
            ip = str(row[0] or "")
            sessions = int(row[1] or 0)
            risk = int(row[2] or 0)
            techniques = [str(value) for value in (row[3] or []) if str(value).strip()]
            hassh = str(row[4] or "")
            node_id = f"ch-ip-{index}"
            nodes.append(
                {
                    "id": node_id,
                    "type": "attacker",
                    "label": ip,
                    "sessions": sessions,
                    "risk": risk,
                    "techniques": techniques[:10],
                }
            )
            edges.append(
                {
                    "id": f"ch-edge-{index}",
                    "source": node_id,
                    "target": "honeypot",
                    "label": f"{sessions} sessions",
                }
            )
            if hassh:
                hassh_id = f"hassh-{hassh}"
                if not any(node.get("id") == hassh_id for node in nodes):
                    nodes.append({"id": hassh_id, "type": "fingerprint", "label": hassh})
                edges.append(
                    {
                        "id": f"ch-hassh-{index}",
                        "source": node_id,
                        "target": hassh_id,
                        "label": "fingerprint",
                    }
                )
            for technique in techniques[:3]:
                tech_id = f"tech-{technique}"
                if not any(node.get("id") == tech_id for node in nodes):
                    nodes.append({"id": tech_id, "type": "technique", "label": technique})
                edges.append(
                    {
                        "id": f"ch-tech-{node_id}-{technique}",
                        "source": node_id,
                        "target": tech_id,
                    }
                )
        return {"nodes": nodes, "edges": edges}
    except Exception:
        return {"nodes": [], "edges": []}


def _load_truth_summary_from_clickhouse(settings: Settings) -> dict[str, Any] | None:
    if not settings.clickhouse.enabled:
        return None
    try:
        import clickhouse_connect

        query = f"""
            SELECT
                count() AS total_events,
                uniqExact(src_ip) AS unique_ips,
                uniqExactIf(
                    if(country_code != '', country_code, country_name),
                    if(country_code != '', country_code, country_name) != ''
                ) AS unique_countries,
                uniqExactIf(src_ip, timestamp >= now() - INTERVAL {ACTIVE_FRESHNESS_WINDOW_SECONDS} SECOND) AS active_sessions,
                countIf(eventid = 'cloudsentinel.session.connect') AS total_connections,
                countIf(eventid = 'cloudsentinel.login.failed') AS total_auth_failures,
                countIf(eventid = 'cloudsentinel.command.input') AS total_commands,
                uniqExactIf(
                    input,
                    eventid = 'cloudsentinel.command.input'
                    AND input != ''
                    AND positionCaseInsensitive(input, 'cloudsentinel.') = 0
                    AND positionCaseInsensitive(input, '[redacted]') = 0
                ) AS unique_commands,
                countIf({_action_in("cloudsentinel_soar_action", NEW_BLOCK_ACTIONS)}) AS total_blocks,
                uniqExactIf(src_ip, {_action_in("cloudsentinel_soar_action", ENFORCED_BLOCK_ACTIONS)}) AS blocked_ips_current,
                avgIf(mttb_ms, mttb_ms > 0 AND {_action_in("cloudsentinel_soar_action", NEW_BLOCK_ACTIONS)}) AS mttb_ms,
                avgIf(
                    toFloat64(cloudsentinel_risk_score),
                    cloudsentinel_risk_score > 0
                ) AS avg_risk
            FROM {settings.clickhouse.table}
            WHERE {_truth_time_filter()}
              AND src_ip != ''
              AND src_ip != '0.0.0.0'
        """
        client = clickhouse_connect.get_client(
            host=settings.clickhouse.host,
            port=settings.clickhouse.port,
            username=settings.clickhouse.username,
            password=secret_to_str(settings.clickhouse.password),
            database=settings.clickhouse.database,
        )
        result = client.query(query)
        if not result.result_rows:
            return None
        row = result.result_rows[0]
        total_connections = int(row[4] or 0)
        total_blocks = int(row[8] or 0)
        raw_block_rate = (float(total_blocks) / float(total_connections) * 100.0) if total_connections > 0 else 0.0
        block_rate = max(0.0, min(100.0, raw_block_rate))
        avg_risk_raw = float(row[11] or 0.0)
        avg_risk = max(0.0, min(100.0, avg_risk_raw))
        return {
            "total_events": int(row[0] or 0),
            "unique_ips": int(row[1] or 0),
            "unique_countries": int(row[2] or 0),
            "active_sessions": int(row[3] or 0),
            "total_connections": total_connections,
            "total_auth_failures": int(row[5] or 0),
            "total_commands": int(row[6] or 0),
            "unique_commands": int(row[7] or 0),
            "total_blocks": total_blocks,
            "blocked_ips_current": int(row[9] or 0),
            "mttb_ms": float(row[10] or 0.0),
            "avg_risk": avg_risk,
            "block_rate": block_rate,
        }
    except Exception:
        return None


def record_manual_block(
    settings: Settings,
    *,
    ip: str,
    reason: str,
    action: str,
    mttb_ms: float,
    started_at: float,
) -> None:
    """Persist a dashboard/mobile block so the ClickHouse truth summary counts it."""
    if not settings.clickhouse.enabled:
        return
    import clickhouse_connect

    completed = datetime.now(UTC)
    started = datetime.fromtimestamp(started_at, tz=UTC)
    row = {
        "eventid": "cloudsentinel.block.manual",
        "session": "manual",
        "sensor": "CloudSentinel",
        "src_ip": ip,
        "src_port": 0,
        "dst_ip": "",
        "dst_port": 0,
        "country_code": "",
        "country_name": "",
        "city": "",
        "continent": "",
        "latitude": "0",
        "longitude": "0",
        "timezone": "UTC",
        "username": "",
        "password": "",
        "auth_type": "password",
        "attempt": 0,
        "hassh_md5": "",
        "hassh_algorithms": "",
        "kexAlgs": [],
        "encCS": [],
        "macCS": [],
        "compCS": [],
        "version": "",
        "key_type": "",
        "input": "",
        "reason": reason,
        "cloudsentinel_risk_score": 0,
        "cloudsentinel_mitre_techniques": [],
        "cloudsentinel_soar_action": action,
        "detected_at": started,
        "block_started_at": started,
        "block_completed_at": completed,
        "mttb_ms": float(mttb_ms),
        "block_command": "",
        "block_stdout": "",
        "block_stderr": "",
        "duration": "",
        "timestamp": completed,
    }
    client = clickhouse_connect.get_client(
        host=settings.clickhouse.host,
        port=settings.clickhouse.port,
        username=settings.clickhouse.username,
        password=secret_to_str(settings.clickhouse.password),
        database=settings.clickhouse.database,
    )
    try:
        client.insert(
            settings.clickhouse.table,
            [list(row.values())],
            column_names=list(row),
        )
    finally:
        client.close()


def _load_war_room_evidence_from_clickhouse(settings: Settings) -> dict[str, Any]:
    if not settings.clickhouse.enabled:
        return {
            "source": "runtime",
            "authoritative": False,
            "last_online_at": 0,
            "last_attack_at": 0,
        }
    try:
        import clickhouse_connect

        attack_filters = ", ".join(f"'{event_id}'" for event_id in WAR_ROOM_ATTACK_EVENT_IDS)
        query = f"""
            SELECT
                maxIf(
                    toUnixTimestamp64Milli(timestamp),
                    src_ip != '' AND src_ip != '0.0.0.0'
                ) AS last_online_ms,
                maxIf(
                    toUnixTimestamp64Milli(timestamp),
                    src_ip != '' AND src_ip != '0.0.0.0'
                    AND eventid IN ({attack_filters})
                ) AS last_attack_ms
            FROM {settings.clickhouse.table}
            WHERE timestamp >= now() - INTERVAL {WAR_ROOM_EVIDENCE_LOOKBACK_MINUTES} MINUTE
        """
        client = clickhouse_connect.get_client(
            host=settings.clickhouse.host,
            port=settings.clickhouse.port,
            username=settings.clickhouse.username,
            password=secret_to_str(settings.clickhouse.password),
            database=settings.clickhouse.database,
        )
        rows = client.query(query).result_rows
        if not rows:
            return {
                "source": "clickhouse",
                "authoritative": True,
                "last_online_at": 0,
                "last_attack_at": 0,
            }
        return {
            "source": "clickhouse",
            "authoritative": True,
            "last_online_at": _as_int(rows[0][0]),
            "last_attack_at": _as_int(rows[0][1]),
        }
    except Exception:
        return {
            "source": "runtime",
            "authoritative": False,
            "last_online_at": 0,
            "last_attack_at": 0,
        }


async def load_recent_events_async(settings: Settings, limit: int = 100) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_load_recent_events_from_clickhouse, settings, limit)


async def load_truth_summary_async(settings: Settings) -> dict[str, Any] | None:
    return await asyncio.to_thread(_load_truth_summary_from_clickhouse, settings)


async def load_recent_sessions_async(
    settings: Settings,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if limit is None:
        return await asyncio.to_thread(_load_recent_sessions_from_clickhouse, settings)
    return await asyncio.to_thread(_load_recent_sessions_from_clickhouse, settings, limit)


async def load_attack_distribution_async(settings: Settings) -> dict[str, int]:
    return await asyncio.to_thread(_load_attack_distribution_from_clickhouse, settings)


async def load_attack_graph_async(settings: Settings, limit: int = 60) -> dict[str, list[dict[str, Any]]]:
    return await asyncio.to_thread(_load_attack_graph_from_clickhouse, settings, limit)


async def load_latest_mttb_async(settings: Settings) -> float:
    return await asyncio.to_thread(_latest_mttb_from_clickhouse, settings)


async def load_war_room_evidence_async(settings: Settings) -> dict[str, Any]:
    return await asyncio.to_thread(_load_war_room_evidence_from_clickhouse, settings)
