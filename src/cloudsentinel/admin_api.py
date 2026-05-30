"""CloudSentinel Admin API with token/JWT auth and dashboard endpoints."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import subprocess
import time
from datetime import UTC
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, secret_to_str
from .geoip import enrich as geo_enrich
from .geoip import is_public_ip
from .hassh import HASSHDNA, fallback_hassh_from_version, infer_client_software
from .pipeline import EventPipeline

security = HTTPBearer(auto_error=False)
EXPOSURE_RULE_COMMENT = "cloudsentinel-dashboard-pause"
SYNTHETIC_ACTIVE_WINDOW_SECONDS = 180


def _strict_truth_mode_enabled() -> bool:
    raw = os.getenv("CLOUDSENTINEL_STRICT_TRUTH", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _is_allowlisted(ip: str, allowlist: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for value in allowlist:
        try:
            if addr in ipaddress.ip_network(str(value).strip(), strict=False):
                return True
        except ValueError:
            continue
    return False


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


async def _run_command(args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    result = await asyncio.to_thread(run)
    return (
        int(result.returncode),
        result.stdout or "",
        result.stderr or "",
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
                groupArray((timestamp, eventid, input, reason)) AS replay_timeline,
                arrayDistinct(arrayFlatten(groupArray(cloudsentinel_mitre_techniques))) AS techniques,
                max(cloudsentinel_risk_score) AS max_risk
            FROM {settings.clickhouse.table}
            WHERE timestamp >= now() - INTERVAL 24 HOUR
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

                    hassh = hashlib.md5(hassh_algorithms.encode("utf-8")).hexdigest()
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
            is_active = now - last_ts <= 180
            if is_active:
                duration_sec = max(0, int(now - latest_connect_ts))
            elif latest_close_ts >= latest_connect_ts > 0:
                duration_sec = max(0, int(latest_close_ts - latest_connect_ts))
            else:
                duration_sec = max(0, int(last_ts - first_ts))

            replay: list[dict[str, str]] = []
            commands: list[str] = []
            normalized_timeline: list[tuple[float, str, str, str]] = []
            latest_input = ""
            for item in timeline_items:
                try:
                    ts_raw, eventid, input_value, reason = item
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
                    )
                )

            normalized_timeline.sort(key=lambda value: (value[0], _event_sort_priority(value[1])))
            replay_seen: set[tuple[str, str, str]] = set()
            for ts_value, eventid, input_value, reason in normalized_timeline:
                dt = time.localtime(ts_value)
                ms = int((ts_value - int(ts_value)) * 1000)
                stamp = f"{time.strftime('%H:%M:%S', dt)}.{ms:03d}"
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
                    "replay": replay[:400],
                    "source": "clickhouse",
                }
            )
        return rows
    except Exception:
        return []


def _load_recent_events_from_clickhouse(settings: Settings, limit: int = 100) -> list[dict[str, Any]]:
    if not settings.clickhouse.enabled:
        return []
    try:
        import clickhouse_connect

        safe_limit = max(1, min(int(limit), 500))
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
            WHERE timestamp >= now() - INTERVAL 24 HOUR
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
            ts = row[20]
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
            reason_value = str(row[13] or "")
            if _is_noise_text(input_value) and _is_noise_text(reason_value):
                continue
            source_value = str(row[14] or "")
            response_mode_value = str(row[15] or "")
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
                    "hassh_md5": str(row[10] or ""),
                    "hassh_algorithms": str(row[11] or ""),
                    "version": str(row[12] or ""),
                    "ja4s": "",
                    "reason": reason_value,
                    "source": source_value,
                    "response_mode": response_mode_value or derived_mode,
                    "cloudsentinel_mitre_techniques": [str(v) for v in (row[16] or []) if str(v)],
                    "cloudsentinel_soar_action": str(row[17] or "none"),
                    "cloudsentinel_risk_score": int(row[18] or 0),
                    "mttb_ms": float(row[19] or 0),
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
            WHERE timestamp >= now() - INTERVAL 24 HOUR
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
            WHERE timestamp >= now() - INTERVAL 24 HOUR
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
            WHERE timestamp >= now() - INTERVAL 24 HOUR
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
                uniqExactIf(src_ip, timestamp >= now() - INTERVAL 3 MINUTE) AS active_sessions,
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
                countIf(positionCaseInsensitive(cloudsentinel_soar_action, 'block') > 0) AS total_blocks,
                uniqExactIf(src_ip, positionCaseInsensitive(cloudsentinel_soar_action, 'block') > 0) AS blocked_ips_current,
                avgIf(mttb_ms, mttb_ms > 0 AND positionCaseInsensitive(cloudsentinel_soar_action, 'block') > 0) AS mttb_ms,
                avgIf(
                    toFloat64(cloudsentinel_risk_score),
                    cloudsentinel_risk_score > 0
                ) AS avg_risk
            FROM {settings.clickhouse.table}
            WHERE timestamp >= now() - INTERVAL 24 HOUR
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


def create_admin_app(settings: Settings, pipeline: EventPipeline, soar: Any = None) -> FastAPI:
    app = FastAPI(
        title="CloudSentinel Admin API",
        version="2.0.0",
        docs_url="/docs" if settings.admin.enabled else None,
        redoc_url=None,
    )

    async def require_auth(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> bool:
        configured_token = secret_to_str(settings.admin.token)
        if configured_token:
            if credentials is None or credentials.credentials != configured_token:
                raise HTTPException(status_code=401, detail="Invalid or missing token")
            return True

        try:
            from .auth import get_auth

            auth = get_auth()
            if not auth.config.enabled:
                return True
            if credentials is None:
                raise HTTPException(status_code=401, detail="Missing authorization header")
            if auth.validate_token(credentials.credentials) is None:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            return True
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Authentication unavailable") from exc

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "ok": True,
            "hostname": settings.honeypot.hostname,
            "redis_connected": pipeline.connected,
            "pending_events": pipeline.pending_count,
        }

    @app.get("/readiness", dependencies=[Depends(require_auth)])
    async def readiness() -> dict[str, Any]:
        clickhouse_enabled = bool(getattr(settings.clickhouse, "enabled", False))
        return {
            "ok": pipeline.connected or pipeline.pending_count >= 0,
            "redis_connected": pipeline.connected,
            "pending_events": pipeline.pending_count,
            "clickhouse_enabled": clickhouse_enabled,
            "stream_enabled": bool(settings.stream.enabled),
        }

    @app.get("/metrics", dependencies=[Depends(require_auth)])
    async def metrics_endpoint():
        from fastapi import Response

        try:
            from .metrics import get_metrics

            metrics = get_metrics()
            return Response(content=metrics.render(), media_type=metrics.content_type)
        except Exception:
            return Response(
                content="# CloudSentinel metrics unavailable\n",
                media_type="text/plain",
            )

    @app.get("/metrics/json", dependencies=[Depends(require_auth)])
    async def metrics_json() -> dict[str, Any]:
        try:
            from .metrics import get_metrics

            metrics = get_metrics()
            mttb_value = metrics.mttb_ms or _latest_mttb_from_clickhouse(settings)
            return {
                "active_sessions": metrics.active_sessions,
                "mttb_ms": mttb_value,
                "total_connections": metrics.total_connections,
                "total_auth_failures": metrics.total_auth_failures,
                "total_auth_successes": metrics.total_auth_successes,
                "total_commands": metrics.total_commands,
                "total_blocks": metrics.total_blocks,
                "total_blocks_iptables": metrics.total_blocks_iptables,
                "blocked_ips_current": len(metrics.blocked_ips),
                "uptime_seconds": time.time() - metrics.start_time,
            }
        except Exception:
            return {"error": "metrics unavailable"}

    @app.get("/stats", dependencies=[Depends(require_auth)])
    async def stats() -> dict[str, Any]:
        data: dict[str, Any] = {
            "pending_events": pipeline.pending_count,
            "session_scores": dict(getattr(pipeline, "session_scores", {})),
        }
        try:
            from .metrics import get_metrics

            metrics = get_metrics()
            mttb_value = metrics.mttb_ms or _latest_mttb_from_clickhouse(settings)
            data.update(
                {
                    "active_sessions": metrics.active_sessions,
                    "total_connections": metrics.total_connections,
                    "total_auth_failures": metrics.total_auth_failures,
                    "total_auth_successes": metrics.total_auth_successes,
                    "total_commands": metrics.total_commands,
                    "total_blocks": metrics.total_blocks,
                    "total_blocks_iptables": metrics.total_blocks_iptables,
                    "mttb_ms": mttb_value,
                    "blocked_ips_current": len(metrics.blocked_ips),
                    "uptime_seconds": time.time() - metrics.start_time,
                }
            )
        except Exception:
            pass
        return data

    @app.get("/sessions", dependencies=[Depends(require_auth)])
    async def sessions() -> dict[str, Any]:
        strict_truth = _strict_truth_mode_enabled()
        sessions_list = _load_recent_sessions_from_clickhouse(settings)
        existing = {str(item.get("ip", "")) for item in sessions_list}
        if not strict_truth and soar is not None:
            now_ts = time.time()
            for ip, session_ids in getattr(soar, "_mem_ip_sessions", {}).items():
                if ip in existing:
                    continue
                profile = soar.get_ip_profile(ip) if hasattr(soar, "get_ip_profile") else {}
                last_seen = float(profile.get("last_seen") or profile.get("first_seen") or 0.0)
                # Avoid stale synthetic "active" rows with no recent evidence.
                if last_seen <= 0 or (now_ts - last_seen) > SYNTHETIC_ACTIVE_WINDOW_SECONDS:
                    continue
                first_seen = float(profile.get("first_seen") or last_seen or now_ts)
                duration_sec = max(0, int(now_ts - first_seen))
                enriched = _enrichment_for_ip(ip, "XX", "Unknown")
                sessions_list.append(
                    {
                        "id": f"sess-{ip}",
                        "ip": ip,
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
                        "startTime": time.strftime(
                            "%H:%M:%S",
                            time.localtime(first_seen),
                        ),
                        "duration": f"{duration_sec // 60}m {duration_sec % 60}s",
                        "startedAtEpochMs": int(first_seen * 1000),
                        "firstSeenEpochMs": int(first_seen * 1000),
                        "lastSeenEpochMs": int(last_seen * 1000),
                        "client": "unknown",
                        "fingerprint": "",
                        "input": [],
                        "status": "Active",
                        "sessionCount": len(session_ids),
                        "riskScore": profile.get("cumulative_risk", 0),
                        "soarAction": "none",
                        "mttbMs": 0.0,
                        "blockEffective": False,
                        "mitreTechniques": profile.get("techniques", []),
                        "replay": [],
                        "source": "memory",
                    }
                )
        return {
            "sessions": sessions_list,
            "source": "clickhouse" if strict_truth else ("mixed" if any(s.get("source") == "memory" for s in sessions_list) else "clickhouse"),
            "authoritative": strict_truth,
            "sourceBreakdown": {
                "sessions": "clickhouse",
                "memory_fallback_enabled": not strict_truth,
            },
        }

    @app.get("/events", dependencies=[Depends(require_auth)])
    async def events(limit: int = 100) -> dict[str, Any]:
        return {
            "events": _load_recent_events_from_clickhouse(settings, limit=limit),
            "source": "clickhouse",
            "authoritative": True,
            "sourceBreakdown": {"events": "clickhouse"},
        }

    @app.get("/truth-summary", dependencies=[Depends(require_auth)])
    async def truth_summary() -> dict[str, Any]:
        summary = _load_truth_summary_from_clickhouse(settings)
        if summary is None:
            return {
                "ok": False,
                "source": "runtime",
                "authoritative": False,
                "metrics": {},
                "sourceBreakdown": {"metrics": "runtime"},
            }
        return {
            "ok": True,
            "source": "clickhouse",
            "authoritative": True,
            "metrics": summary,
            "sourceBreakdown": {"metrics": "clickhouse"},
        }

    @app.post("/admin/block-ip", dependencies=[Depends(require_auth)])
    async def manual_block_ip(body: dict[str, Any]) -> dict[str, Any]:
        ip = str(body.get("ip") or "").strip()
        reason = str(body.get("reason") or "manual-dashboard")[:120]
        ttl = int(body.get("ttl") or settings.soar.block_ttl or 3600)
        try:
            ipaddress.ip_address(ip)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid IP address") from exc
        if _is_allowlisted(ip, settings.soar.allowlist):
            raise HTTPException(status_code=400, detail="IP is allowlisted")
        if not is_public_ip(ip):
            raise HTTPException(status_code=400, detail="Only public IPs can be blocked")

        started = time.time()
        firewall_path = settings.soar.firewall_path or "/sbin/iptables"
        check = [firewall_path, "-C", "INPUT", "-s", ip, "-j", "DROP"]
        add = [
            firewall_path,
            "-A",
            "INPUT",
            "-s",
            ip,
            "-m",
            "comment",
            "--comment",
            f"cloudsentinel-manual:{reason}",
            "-j",
            "DROP",
        ]
        existing_code, _, _ = await _run_command(check)
        if existing_code == 0:
            action = "already_blocked"
        else:
            code, _, stderr = await _run_command(add)
            if code != 0:
                raise HTTPException(status_code=500, detail=stderr[:200] or "Firewall block failed")
            action = "blocked"

        if soar is not None:
            try:
                await soar._mark_blocked(ip)
            except Exception:
                pass
        try:
            from .metrics import get_metrics

            metrics = get_metrics()
            metrics.record_block("manual_block")
            metrics.blocked_ips.add(ip)
            metrics.set_blocked_count(len(metrics.blocked_ips))
            metrics.set_mttb((time.time() - started) * 1000)
        except Exception:
            pass
        return {
            "ok": True,
            "ip": ip,
            "ttl": ttl,
            "reason": reason,
            "action": action,
            "mttb_ms": round((time.time() - started) * 1000, 3),
        }

    @app.post("/admin/exposure", dependencies=[Depends(require_auth)])
    async def exposure(body: dict[str, Any]) -> dict[str, Any]:
        enabled = _to_bool(body.get("enabled"))
        firewall_path = settings.soar.firewall_path or "/sbin/iptables"
        ports = sorted({22, int(settings.honeypot.ssh_port)})
        actions: list[dict[str, Any]] = []
        for port in ports:
            rule = [
                firewall_path,
                "-C",
                "INPUT",
                "-p",
                "tcp",
                "--dport",
                str(port),
                "-m",
                "comment",
                "--comment",
                EXPOSURE_RULE_COMMENT,
                "-j",
                "DROP",
            ]
            check_code, _, _ = await _run_command(rule)
            if enabled:
                if check_code == 0:
                    delete = rule.copy()
                    delete[1] = "-D"
                    code, _, stderr = await _run_command(delete)
                    actions.append({"port": port, "action": "removed", "ok": code == 0, "error": stderr[:200]})
                else:
                    actions.append({"port": port, "action": "already_open", "ok": True})
            elif check_code == 0:
                actions.append({"port": port, "action": "already_paused", "ok": True})
            else:
                add = rule.copy()
                add[1] = "-I"
                add.insert(3, "1")
                code, _, stderr = await _run_command(add)
                actions.append({"port": port, "action": "paused", "ok": code == 0, "error": stderr[:200]})

        paused = not enabled
        return {"ok": all(item["ok"] for item in actions), "enabled": enabled, "paused": paused, "actions": actions}

    @app.get("/attack-distribution", dependencies=[Depends(require_auth)])
    async def attack_distribution() -> list[dict[str, Any]]:
        strict_truth = _strict_truth_mode_enabled()
        metrics_data = _load_attack_distribution_from_clickhouse(settings)
        if not strict_truth:
            try:
                from .metrics import get_metrics

                metrics = get_metrics()
                metrics_data["Brute Force"] = max(
                    int(metrics_data.get("Brute Force", 0)),
                    int(metrics.total_auth_failures),
                )
                metrics_data["Command Injection"] = max(
                    int(metrics_data.get("Command Injection", 0)),
                    int(metrics.total_commands),
                )
            except Exception:
                pass
        return [
            {"name": "Brute Force", "value": metrics_data["Brute Force"], "fill": "#ef4444"},
            {
                "name": "Command Injection",
                "value": metrics_data["Command Injection"],
                "fill": "#f97316",
            },
            {"name": "Port Scanning", "value": metrics_data["Port Scanning"], "fill": "#eab308"},
            {"name": "Malware Upload", "value": metrics_data["Malware Upload"], "fill": "#8b5cf6"},
        ]

    @app.get("/attack-graph", dependencies=[Depends(require_auth)])
    async def attack_graph() -> dict[str, Any]:
        strict_truth = _strict_truth_mode_enabled()
        nodes: list[dict[str, Any]] = [
            {"id": "honeypot", "type": "honeypot", "label": settings.honeypot.hostname}
        ]
        edges: list[dict[str, Any]] = []
        used_soar = False

        if not strict_truth and soar is not None:
            used_soar = True
            for i, chain in enumerate(soar.get_attack_chains()):
                node_id = f"ip-{i}"
                nodes.append(
                    {
                        "id": node_id,
                        "type": "attacker",
                        "label": chain["ip"],
                        "sessions": chain["sessions"],
                        "risk": chain["risk"],
                        "techniques": chain["techniques"],
                    }
                )
                edges.append(
                    {
                        "id": f"edge-{i}",
                        "source": node_id,
                        "target": "honeypot",
                        "label": f"{chain['sessions']} sessions",
                    }
                )
                for tech in chain.get("techniques", [])[:3]:
                    tech_id = f"tech-{tech}"
                    if not any(node["id"] == tech_id for node in nodes):
                        nodes.append({"id": tech_id, "type": "technique", "label": tech})
                    edges.append(
                        {"id": f"edge-{node_id}-{tech_id}", "source": node_id, "target": tech_id}
                    )
        if len(nodes) <= 1:
            clickhouse_graph = _load_attack_graph_from_clickhouse(settings)
            nodes.extend(clickhouse_graph.get("nodes", []))
            edges.extend(clickhouse_graph.get("edges", []))
        return {
            "nodes": nodes,
            "edges": edges,
            "source": "clickhouse" if strict_truth else ("mixed" if used_soar else "clickhouse"),
            "authoritative": strict_truth,
            "sourceBreakdown": {
                "graph": "clickhouse" if strict_truth else ("mixed" if used_soar else "clickhouse")
            },
        }

    @app.get("/anomaly-stats", dependencies=[Depends(require_auth)])
    async def anomaly_stats() -> dict[str, Any]:
        try:
            from .anomaly import CommandAnomalyDetector  # noqa: F401

            return {"available": True, "note": "Anomaly detector active on sensor"}
        except Exception:
            return {"available": False}

    @app.get("/llm/status", dependencies=[Depends(require_auth)])
    async def llm_status() -> dict[str, Any]:
        api_key = secret_to_str(settings.llm.api_key)
        return {
            "available": bool(api_key),
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "fallback_models": settings.llm.fallback_models,
            "max_output_chars": settings.llm.max_output_chars,
            "features": {
                "command_vfs": True,
                "threat_summary": True,
                "deterministic_fallback": not bool(api_key),
            },
        }

    @app.post("/threat-summary", dependencies=[Depends(require_auth)])
    async def threat_summary(body: dict[str, Any]) -> dict[str, Any]:
        session_id = str(body.get("session_id") or body.get("id") or "latest")
        try:
            from .threat_reporter import generate_report

            report = await generate_report(
                session_id=session_id,
                redis_url=settings.redis.url,
                attacker_ip=str(body.get("attacker_ip") or body.get("ip") or ""),
                country=str(body.get("country") or "Unknown"),
                city=str(body.get("city") or "Unknown"),
                risk_score=int(body.get("risk_score") or 0),
                mitre_techniques=list(body.get("mitre_techniques") or []),
                hassh=str(body.get("hassh") or body.get("fingerprint") or ""),
                commands=list(body.get("commands") or body.get("input") or []),
            )
            return {"ok": True, "report": report.to_dict()}
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "report": {
                    "session_id": session_id,
                    "summary": "AI summary unavailable on sensor",
                    "primary_objective": "Unknown",
                    "confidence": 0,
                    "model_used": "none",
                },
            }

    @app.post("/llm/chat", dependencies=[Depends(require_auth)])
    async def llm_chat(body: dict[str, Any]) -> dict[str, Any]:
        prompt = str(body.get("prompt") or "")
        context = str(body.get("context") or "")
        try:
            from .threat_reporter import chat_with_agent
            response_text = await chat_with_agent(prompt, context)
            return {"ok": True, "response": response_text}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @app.post("/auth/login")
    async def login(body: dict[str, str]) -> dict[str, Any]:
        try:
            from .auth import get_auth

            auth = get_auth()
            if not auth.config.enabled:
                return {"message": "Auth not enabled", "token": "dev-mode"}
            username = body.get("username", "")
            password = body.get("password", "")
            expected_user = os.getenv("CLOUDSENTINEL_ADMIN_USER", "admin")
            expected_pass = os.getenv("CLOUDSENTINEL_ADMIN_PASS", "")
            if username != expected_user or password != expected_pass:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            return auth.create_login_token(username)
        except HTTPException:
            raise
        except Exception:
            return {"message": "Auth module unavailable", "token": "dev-mode"}

    return app
