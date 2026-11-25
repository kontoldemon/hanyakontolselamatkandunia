"""CloudSentinel Admin API with token/JWT auth and dashboard endpoints."""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import UTC
from typing import Any

import structlog
from pydantic import SecretStr
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, secret_to_str
from .eventgrid import publish_block
from .geoip import is_public_ip
from .pipeline import EventPipeline
from .api.routers.events import build_events_router
from .api.routers.analytics import build_analytics_router
from .api.routers.blocks import build_blocks_router
from .api.routers.auth_routes import build_auth_router
from .api.routers.exposure import build_exposure_router
from .api.routers.llm import build_llm_router
from .api.routers.sessions import build_sessions_router
from .api.routers.health import build_health_router
from .api.routers.mobile import build_mobile_router
from .mobile_push import MobilePushService
from .api.queries import (
    ACTIVE_FRESHNESS_WINDOW_SECONDS,
    SYNTHETIC_ACTIVE_WINDOW_SECONDS,
    WAR_ROOM_ACTIVE_FRESHNESS_MS,
    WAR_ROOM_ATTACK_EVENT_IDS,
    WAR_ROOM_EVIDENCE_LOOKBACK_MINUTES,
    _as_int,
    _derive_response_mode,
    _display_country,
    _enrichment_for_ip,
    _event_sort_priority,
    _is_noise_event,
    _is_noise_text,
    _latest_mttb_from_clickhouse,
    _load_attack_distribution_from_clickhouse,
    _load_attack_graph_from_clickhouse,
    _load_recent_events_from_clickhouse,
    _load_recent_sessions_from_clickhouse,
    _load_truth_summary_from_clickhouse,
    _load_war_room_evidence_from_clickhouse,
    _now_ms,
    _persistent_online_enabled,
    _state_to_public,
    _strict_truth_mode_enabled,
    _to_bool,
    _trim_replay_entries,
    _truth_time_filter,
    _truth_window_hours,
)

security = HTTPBearer(auto_error=False)
EXPOSURE_RULE_COMMENT = "cloudsentinel-dashboard-pause"
WAR_ROOM_ONLINE_GRACE_MS = 45_000
WAR_ROOM_ATTACK_COOLDOWN_MS = 90_000
WAR_ROOM_REDIS_TTL_SECONDS = 24 * 60 * 60
WAR_ROOM_DEGRADED_HOLD_MS = 60_000
WAR_ROOM_STATE_REDIS_KEY = "cloudsentinel:war_room_state:v1"
EXPOSURE_STATE_REDIS_KEY = "cloudsentinel:exposure_state:v1"
EXPOSURE_TOGGLE_COOLDOWN_MS = 8_000
HOT_CACHE_PREFIX = "cloudsentinel:hotcache:v1"
HOT_CACHE_TTL_SUMMARY_SECONDS = 5
HOT_CACHE_TTL_SESSIONS_SECONDS = 5
HOT_CACHE_TTL_ATTACK_DISTRIBUTION_SECONDS = 8
HOT_CACHE_TTL_ATTACK_GRAPH_SECONDS = 8
logger = structlog.get_logger("cloudsentinel.admin_api")


def _exposure_provider() -> str:
    return os.getenv("CLOUDSENTINEL_EXPOSURE_PROVIDER", "iptables").strip().lower()


def _do_api_base() -> str:
    return os.getenv("CLOUDSENTINEL_DO_API_BASE", "https://api.digitalocean.com/v2").rstrip("/")


def _do_firewall_id() -> str:
    return os.getenv("CLOUDSENTINEL_DO_FIREWALL_ID", "").strip()


def _do_token() -> str:
    return os.getenv("DIGITALOCEAN_TOKEN", "").strip()


def _exposure_admin_ports() -> set[int]:
    raw = os.getenv("CLOUDSENTINEL_EXPOSURE_ADMIN_PORTS", "22")
    ports: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = int(token)
        except ValueError:
            continue
        if 1 <= value <= 65535:
            ports.add(value)
    if not ports:
        ports.add(22)
    return ports


def _exposure_target_ports(settings: Settings) -> list[int]:
    raw = os.getenv("CLOUDSENTINEL_EXPOSURE_TARGET_PORTS", "").strip()
    requested: set[int] = set()
    if raw:
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                value = int(token)
            except ValueError:
                continue
            if 1 <= value <= 65535:
                requested.add(value)
    if not requested:
        requested.add(int(settings.honeypot.ssh_port))
    allow_admin_ports = os.getenv("CLOUDSENTINEL_EXPOSURE_ALLOW_ADMIN_PORTS", "0").strip().lower() in {"1", "true", "yes", "on"}
    if allow_admin_ports:
        return sorted(requested)
    admin_ports = _exposure_admin_ports()
    return sorted(port for port in requested if port not in admin_ports)






def _clickhouse_health_sync(settings: Settings) -> bool:
    import clickhouse_connect

    client = clickhouse_connect.get_client(
        host=settings.clickhouse.host,
        port=settings.clickhouse.port,
        username=settings.clickhouse.username,
        password=secret_to_str(settings.clickhouse.password),
        database=settings.clickhouse.database,
        connect_timeout=2,
        send_receive_timeout=2,
    )
    return bool(client.query("SELECT 1").result_rows)


async def _clickhouse_health(settings: Settings) -> bool | None:
    if not settings.clickhouse.enabled:
        return None
    try:
        return await asyncio.to_thread(_clickhouse_health_sync, settings)
    except Exception:
        return False






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


_MANUAL_UNBLOCK_TASKS: set[asyncio.Task[None]] = set()


def _manual_block_args(firewall_path: str, action: str, ip: str, reason: str) -> list[str]:
    return [
        firewall_path,
        action,
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


async def _schedule_manual_unblock(
    ip: str,
    reason: str,
    ttl: int,
    firewall_path: str,
) -> None:
    await asyncio.sleep(max(0, ttl))
    await _run_command(_manual_block_args(firewall_path, "-D", ip, reason))


def _spawn_manual_unblock(ip: str, reason: str, ttl: int, firewall_path: str) -> None:
    task = asyncio.create_task(_schedule_manual_unblock(ip, reason, ttl, firewall_path))
    _MANUAL_UNBLOCK_TASKS.add(task)
    task.add_done_callback(_MANUAL_UNBLOCK_TASKS.discard)


def _exposure_firewall_paths(settings: Settings) -> list[str]:
    ordered = [
        str(settings.soar.firewall_path or "/sbin/iptables"),
        "/usr/sbin/iptables-legacy",
        "/usr/sbin/iptables",
        "/usr/sbin/iptables-nft",
        "/sbin/iptables-legacy",
        "/sbin/iptables",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for item in ordered:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


async def _http_json(
    method: str, url: str, token: str, payload: dict[str, Any] | None = None, timeout: float = 7.0
) -> tuple[int, dict[str, Any], str]:
    body = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=body, method=method.upper(), headers=headers)

    def run() -> tuple[int, dict[str, Any], str]:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                return int(response.status), parsed if isinstance(parsed, dict) else {}, ""
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {}
            return int(exc.code), parsed if isinstance(parsed, dict) else {}, raw[:300]
        except Exception as exc:
            return 0, {}, str(exc)[:300]

    return await asyncio.to_thread(run)


def _do_rule_matches_port(rule: dict[str, Any], port: int) -> bool:
    ports = rule.get("ports")
    if isinstance(ports, list):
        return str(port) in {str(item) for item in ports}
    if isinstance(ports, str):
        value = ports.strip()
        if not value:
            return False
        if value == str(port):
            return True
        if "-" in value:
            try:
                start_s, end_s = value.split("-", 1)
                start_i = int(start_s.strip())
                end_i = int(end_s.strip())
                return start_i <= int(port) <= end_i
            except Exception:
                return False
    return False


def _do_rule_is_global(rule: dict[str, Any]) -> bool:
    sources = rule.get("sources", {})
    if not isinstance(sources, dict):
        return False
    addresses = sources.get("addresses")
    if not isinstance(addresses, list):
        return False
    normalized = {str(item).strip() for item in addresses}
    return "0.0.0.0/0" in normalized or "::/0" in normalized


def _do_rule_is_tcp(rule: dict[str, Any]) -> bool:
    return str(rule.get("protocol", "")).lower() == "tcp"


def _do_read_allowed_ports(firewall: dict[str, Any], target_ports: set[int]) -> set[int]:
    allowed: set[int] = set()
    inbound = firewall.get("inbound_rules", [])
    if not isinstance(inbound, list):
        return allowed
    for rule in inbound:
        if not isinstance(rule, dict):
            continue
        if not _do_rule_is_tcp(rule):
            continue
        if not _do_rule_is_global(rule):
            continue
        for port in target_ports:
            if _do_rule_matches_port(rule, port):
                allowed.add(port)
    return allowed


async def _toggle_exposure_digitalocean(enabled: bool, settings: Settings) -> dict[str, Any]:
    firewall_id = _do_firewall_id()
    token = _do_token()
    target_ports = _exposure_target_ports(settings)
    if not firewall_id:
        return {"ok": False, "error": "missing CLOUDSENTINEL_DO_FIREWALL_ID", "actions": []}
    if not token:
        return {"ok": False, "error": "missing DIGITALOCEAN_TOKEN", "actions": []}
    if not target_ports:
        return {"ok": False, "error": "no target ports after admin safety filter", "actions": []}

    target_set = set(target_ports)
    firewall_url = f"{_do_api_base()}/firewalls/{firewall_id}"
    status, before_json, before_err = await _http_json("GET", firewall_url, token)
    if status != 200:
        return {
            "ok": False,
            "error": f"digitalocean read failed status={status}",
            "details": before_err,
            "actions": [],
        }
    before_fw = before_json.get("firewall")
    if not isinstance(before_fw, dict):
        return {"ok": False, "error": "digitalocean payload missing firewall object", "actions": []}
    before_rules = before_fw.get("inbound_rules", [])
    if not isinstance(before_rules, list):
        return {"ok": False, "error": "digitalocean firewall inbound_rules invalid", "actions": []}
    before_allowed = _do_read_allowed_ports(before_fw, target_set)

    new_rules: list[dict[str, Any]] = []
    for rule in before_rules:
        if not isinstance(rule, dict):
            continue
        remove = (
            _do_rule_is_tcp(rule)
            and _do_rule_is_global(rule)
            and any(_do_rule_matches_port(rule, p) for p in target_set)
        )
        if not remove:
            new_rules.append(rule)
    if enabled:
        for port in sorted(target_set):
            if port not in before_allowed:
                new_rules.append(
                    {
                        "protocol": "tcp",
                        "ports": str(port),
                        "sources": {"addresses": ["0.0.0.0/0", "::/0"]},
                    }
                )

    put_payload = {
        "name": str(before_fw.get("name") or firewall_id),
        "inbound_rules": new_rules,
        "outbound_rules": before_fw.get("outbound_rules", []),
        "droplet_ids": before_fw.get("droplet_ids", []),
        "tags": before_fw.get("tags", []),
    }
    put_status, _, put_err = await _http_json("PUT", firewall_url, token, payload=put_payload)
    if put_status not in {200, 202}:
        return {
            "ok": False,
            "error": f"digitalocean update failed status={put_status}",
            "details": put_err,
            "actions": [],
        }

    verify_status, verify_json, verify_err = await _http_json("GET", firewall_url, token)
    if verify_status != 200:
        return {
            "ok": False,
            "error": f"digitalocean verify failed status={verify_status}",
            "details": verify_err,
            "actions": [],
        }
    verify_fw = verify_json.get("firewall")
    if not isinstance(verify_fw, dict):
        return {"ok": False, "error": "digitalocean verify payload invalid", "actions": []}
    after_allowed = _do_read_allowed_ports(verify_fw, target_set)
    expected_allowed = target_set if enabled else set()
    verified = after_allowed == expected_allowed
    if not verified:
        rollback_payload = {
            "name": str(before_fw.get("name") or firewall_id),
            "inbound_rules": before_rules,
            "outbound_rules": before_fw.get("outbound_rules", []),
            "droplet_ids": before_fw.get("droplet_ids", []),
            "tags": before_fw.get("tags", []),
        }
        rollback_status, _, rollback_err = await _http_json("PUT", firewall_url, token, payload=rollback_payload)
        return {
            "ok": False,
            "error": "digitalocean verify mismatch, rollback attempted",
            "details": rollback_err,
            "rollback_ok": rollback_status in {200, 202},
            "actions": [],
            "desired_enabled": enabled,
            "effective_enabled": len(before_allowed) > 0,
        }

    actions: list[dict[str, Any]] = []
    for port in sorted(target_set):
        if enabled:
            changed = port not in before_allowed
            actions.append({"port": port, "action": "opened" if changed else "already_open", "ok": True})
        else:
            changed = port in before_allowed
            actions.append({"port": port, "action": "paused" if changed else "already_paused", "ok": True})
    return {
        "ok": True,
        "actions": actions,
        "desired_enabled": enabled,
        "effective_enabled": enabled,
        "provider": "digitalocean",
    }






















def _compose_war_room_state(
    now_ms: int,
    persisted: dict[str, Any] | None,
    evidence: dict[str, Any],
    exposure: dict[str, Any] | None,
    degraded: bool,
    source: str,
    authoritative: bool,
) -> dict[str, Any]:
    current = persisted or {}
    persisted_last_online = _as_int(current.get("last_online_at"))
    persisted_last_attack = _as_int(current.get("last_attack_at"))
    evidence_last_online = _as_int(evidence.get("last_online_at"))
    evidence_last_attack = _as_int(evidence.get("last_attack_at"))
    last_online_at = max(persisted_last_online, evidence_last_online)
    last_attack_at = max(persisted_last_attack, evidence_last_attack)
    cooldown_until = (
        last_attack_at + WAR_ROOM_ATTACK_COOLDOWN_MS
        if last_attack_at > 0
        else 0
    )
    online_from_events = last_online_at > 0 and (now_ms - last_online_at) <= WAR_ROOM_ONLINE_GRACE_MS
    if _persistent_online_enabled():
        # Optional UX mode: keep online while authoritative data says sensor was seen at least once.
        online = (not degraded) and (
            online_from_events or (bool(authoritative) and last_online_at > 0)
        )
    else:
        online = online_from_events
    under_attack = online and cooldown_until > 0 and now_ms <= cooldown_until
    if not online:
        state = "offline"
    elif under_attack:
        state = "under_attack"
    else:
        state = "live"
    exposure_data = exposure or {}
    desired_enabled = _to_bool(exposure_data.get("desired_enabled", True))
    effective_enabled = _to_bool(exposure_data.get("effective_enabled", True))
    exposure_syncing = desired_enabled != effective_enabled
    if not effective_enabled:
        state = "offline"
    return {
        "ok": True,
        "state": state,
        "lastOnlineAt": last_online_at or None,
        "lastAttackAt": last_attack_at or None,
        "cooldownUntil": cooldown_until or None,
        "updatedAt": now_ms,
        "degraded": degraded,
        "authoritative": authoritative,
        "source": source,
        "sourceBreakdown": {
            "state": source,
            "onlineEvidence": evidence.get("source", source),
            "attackEvidence": evidence.get("source", source),
            "storage": "memory" if degraded else "redis",
        },
        "exposure": {
            "provider": str(exposure_data.get("provider") or _exposure_provider()),
            "desiredEnabled": desired_enabled,
            "effectiveEnabled": effective_enabled,
            "syncing": exposure_syncing,
            "updatedAt": _as_int(exposure_data.get("updated_at")),
        },
        "windows": {
            "onlineGraceMs": WAR_ROOM_ONLINE_GRACE_MS,
            "attackCooldownMs": WAR_ROOM_ATTACK_COOLDOWN_MS,
            "activeFreshnessMs": WAR_ROOM_ACTIVE_FRESHNESS_MS,
        },
    }




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
            if credentials is None or not hmac.compare_digest(
                credentials.credentials.encode(), configured_token.encode()
            ):
                raise HTTPException(status_code=401, detail="Invalid or missing token")
            return True

        try:
            from .auth import get_auth

            auth = get_auth()
            if not auth.config.enabled:
                raise HTTPException(
                    status_code=503,
                    detail="Admin authentication is not configured",
                )
            if credentials is None:
                raise HTTPException(status_code=401, detail="Missing authorization header")
            if auth.validate_token(credentials.credentials) is None:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            return True
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Authentication unavailable") from exc

    war_room_last_snapshot: dict[str, Any] | None = None
    war_room_last_refresh_ms = 0
    war_room_degraded_mode = False
    war_room_degraded_started_ms = 0
    war_room_state_transitions = 0
    war_room_degraded_transitions = 0
    war_room_direct_redis: Any = None

    async def _resolve_war_room_redis() -> tuple[Any, str]:
        nonlocal war_room_direct_redis
        pipeline_redis = getattr(pipeline, "_redis", None)
        if pipeline_redis is not None:
            return pipeline_redis, "pipeline"
        if war_room_direct_redis is not None:
            return war_room_direct_redis, "direct"
        import redis.asyncio as aioredis
        war_room_direct_redis = aioredis.from_url(
            settings.redis.url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        await war_room_direct_redis.ping()
        return war_room_direct_redis, "direct"

    async def _load_war_room_persisted_state() -> tuple[dict[str, Any], float, str]:
        redis_client, redis_mode = await _resolve_war_room_redis()
        started = time.perf_counter()
        raw = await redis_client.hgetall(WAR_ROOM_STATE_REDIS_KEY)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        if not raw:
            return {}, latency_ms, redis_mode
        return ({
            "state": _state_to_public(raw.get("state", "offline")),
            "last_online_at": _as_int(raw.get("last_online_at")),
            "last_attack_at": _as_int(raw.get("last_attack_at")),
            "cooldown_until": _as_int(raw.get("cooldown_until")),
            "updated_at": _as_int(raw.get("updated_at")),
        }, latency_ms, redis_mode)

    async def _load_exposure_state() -> dict[str, Any]:
        try:
            redis_client, _ = await _resolve_war_room_redis()
            raw = await redis_client.hgetall(EXPOSURE_STATE_REDIS_KEY)
            if not raw:
                return {}
            desired_enabled = _to_bool(raw.get("desired_enabled"))
            effective_enabled = _to_bool(raw.get("effective_enabled"))
            return {
                "provider": str(raw.get("provider") or _exposure_provider()),
                "desired_enabled": desired_enabled,
                "effective_enabled": effective_enabled,
                "updated_at": _as_int(raw.get("updated_at")),
                "last_toggle_at": _as_int(raw.get("last_toggle_at")),
            }
        except Exception:
            return {}

    async def _persist_exposure_state(
        *,
        provider: str,
        desired_enabled: bool,
        effective_enabled: bool,
        updated_at_ms: int | None = None,
        last_toggle_at_ms: int | None = None,
    ) -> None:
        redis_client, _ = await _resolve_war_room_redis()
        stamp = _as_int(updated_at_ms or _now_ms())
        last_toggle = _as_int(last_toggle_at_ms if last_toggle_at_ms is not None else stamp)
        await redis_client.hset(
            EXPOSURE_STATE_REDIS_KEY,
            mapping={
                "provider": provider,
                "desired_enabled": "1" if desired_enabled else "0",
                "effective_enabled": "1" if effective_enabled else "0",
                "updated_at": str(stamp),
                "last_toggle_at": str(last_toggle),
            },
        )
        await redis_client.expire(EXPOSURE_STATE_REDIS_KEY, WAR_ROOM_REDIS_TTL_SECONDS)

    async def _persist_war_room_state(payload: dict[str, Any]) -> tuple[float, str]:
        redis_client, redis_mode = await _resolve_war_room_redis()
        fields = {
            "state": str(payload.get("state") or "offline"),
            "last_online_at": str(_as_int(payload.get("lastOnlineAt"))),
            "last_attack_at": str(_as_int(payload.get("lastAttackAt"))),
            "cooldown_until": str(_as_int(payload.get("cooldownUntil"))),
            "updated_at": str(_as_int(payload.get("updatedAt"))),
            "degraded": "1" if bool(payload.get("degraded")) else "0",
        }
        started = time.perf_counter()
        await redis_client.hset(WAR_ROOM_STATE_REDIS_KEY, mapping=fields)
        await redis_client.expire(WAR_ROOM_STATE_REDIS_KEY, WAR_ROOM_REDIS_TTL_SECONDS)
        return round((time.perf_counter() - started) * 1000, 3), redis_mode

    def _hot_cache_key(name: str) -> str:
        return f"{HOT_CACHE_PREFIX}:{name}"

    async def _hot_cache_get(name: str) -> tuple[Any | None, str]:
        try:
            redis_client, redis_mode = await _resolve_war_room_redis()
            raw = await redis_client.get(_hot_cache_key(name))
            if not raw:
                return None, redis_mode
            return json.loads(raw), redis_mode
        except Exception:
            return None, "memory"

    async def _hot_cache_set(name: str, payload: Any, ttl_seconds: int) -> str:
        try:
            redis_client, redis_mode = await _resolve_war_room_redis()
            await redis_client.set(
                _hot_cache_key(name),
                json.dumps(payload, separators=(",", ":"), ensure_ascii=True),
                ex=max(1, int(ttl_seconds)),
            )
            return redis_mode
        except Exception:
            return "memory"

    async def _compute_war_room_state(force: bool = False) -> dict[str, Any]:
        nonlocal war_room_last_snapshot
        nonlocal war_room_last_refresh_ms
        nonlocal war_room_degraded_mode
        nonlocal war_room_degraded_started_ms
        nonlocal war_room_state_transitions
        nonlocal war_room_degraded_transitions

        now_ms = _now_ms()
        if (
            not force
            and war_room_last_snapshot is not None
            and (now_ms - war_room_last_refresh_ms) < 2000
        ):
            return war_room_last_snapshot

        war_room_last_refresh_ms = now_ms
        try:
            evidence = _load_war_room_evidence_from_clickhouse(settings)
            persisted, redis_read_latency_ms, redis_read_mode = await _load_war_room_persisted_state()
            exposure = await _load_exposure_state()
            state = _compose_war_room_state(
                now_ms=now_ms,
                persisted=persisted,
                evidence=evidence,
                exposure=exposure,
                degraded=False,
                source="clickhouse" if evidence.get("authoritative") else "runtime",
                authoritative=bool(evidence.get("authoritative")),
            )
            previous_state = (
                _state_to_public(str(persisted.get("state")))
                if persisted
                else _state_to_public(str((war_room_last_snapshot or {}).get("state")))
            )
            if state["state"] != previous_state:
                war_room_state_transitions += 1
                logger.info(
                    "war_room_state_transition",
                    prev_state=previous_state,
                    next_state=state["state"],
                    reason="evidence_refresh",
                    evidence_ts=max(_as_int(state.get("lastOnlineAt")), _as_int(state.get("lastAttackAt"))),
                    cooldown_until=_as_int(state.get("cooldownUntil")),
                )
            redis_write_latency_ms, redis_write_mode = await _persist_war_room_state(state)
            storage_mode = "redis" if redis_read_mode == "pipeline" and redis_write_mode == "pipeline" else "redis-direct"
            state["sourceBreakdown"] = {
                **dict(state.get("sourceBreakdown") or {}),
                "storage": storage_mode,
            }
            state["stats"] = {
                "stateTransitions": war_room_state_transitions,
                "degradedTransitions": war_room_degraded_transitions,
                "redisReadLatencyMs": redis_read_latency_ms,
                "redisWriteLatencyMs": redis_write_latency_ms,
            }
            war_room_last_snapshot = state
            if war_room_degraded_mode:
                war_room_degraded_mode = False
                war_room_degraded_started_ms = 0
                logger.info("war_room_state_degraded_recovered")
            return state
        except Exception as exc:
            if not war_room_degraded_mode:
                war_room_degraded_mode = True
                war_room_degraded_started_ms = now_ms
                war_room_degraded_transitions += 1
                logger.warning(
                    "war_room_state_degraded_enter",
                    error=str(exc),
                )

            hold_allowed = (
                war_room_last_snapshot is not None
                and (now_ms - war_room_degraded_started_ms) <= WAR_ROOM_DEGRADED_HOLD_MS
            )
            if hold_allowed and war_room_last_snapshot is not None:
                held = dict(war_room_last_snapshot)
                held["degraded"] = True
                held["authoritative"] = False
                held["source"] = "runtime"
                held["sourceBreakdown"] = {
                    **dict(held.get("sourceBreakdown") or {}),
                    "storage": "memory",
                    "state": "runtime",
                }
                held["stats"] = {
                    "stateTransitions": war_room_state_transitions,
                    "degradedTransitions": war_room_degraded_transitions,
                    "redisReadLatencyMs": 0.0,
                    "redisWriteLatencyMs": 0.0,
                }
                if "exposure" not in held:
                    held["exposure"] = {
                        "provider": _exposure_provider(),
                        "desiredEnabled": True,
                        "effectiveEnabled": True,
                        "syncing": False,
                        "updatedAt": 0,
                    }
                return held

            fallback = {
                "ok": True,
                "state": "offline",
                "lastOnlineAt": None,
                "lastAttackAt": None,
                "cooldownUntil": None,
                "updatedAt": now_ms,
                "degraded": True,
                "authoritative": False,
                "source": "runtime",
                "sourceBreakdown": {
                    "state": "runtime",
                    "onlineEvidence": "runtime",
                    "attackEvidence": "runtime",
                    "storage": "memory",
                },
                "exposure": {
                    "provider": _exposure_provider(),
                    "desiredEnabled": True,
                    "effectiveEnabled": True,
                    "syncing": False,
                    "updatedAt": 0,
                },
                "windows": {
                    "onlineGraceMs": WAR_ROOM_ONLINE_GRACE_MS,
                    "attackCooldownMs": WAR_ROOM_ATTACK_COOLDOWN_MS,
                    "activeFreshnessMs": WAR_ROOM_ACTIVE_FRESHNESS_MS,
                },
                "stats": {
                    "stateTransitions": war_room_state_transitions,
                    "degradedTransitions": war_room_degraded_transitions,
                    "redisReadLatencyMs": 0.0,
                    "redisWriteLatencyMs": 0.0,
                },
            }
            war_room_last_snapshot = fallback
            return fallback

    @app.on_event("shutdown")
    async def _close_war_room_redis() -> None:
        nonlocal war_room_direct_redis
        if war_room_direct_redis is not None:
            try:
                await war_room_direct_redis.aclose()
            except Exception:
                pass
            war_room_direct_redis = None

    app.include_router(
        build_health_router(settings, pipeline, require_auth, _clickhouse_health)
    )
    app.include_router(
        build_events_router(
            settings,
            require_auth,
            _compute_war_room_state,
            _hot_cache_get,
            _hot_cache_set,
            HOT_CACHE_TTL_SUMMARY_SECONDS,
        )
    )
    app.include_router(
        build_sessions_router(
            settings,
            require_auth,
            _compute_war_room_state,
            _hot_cache_get,
            _hot_cache_set,
            soar,
            HOT_CACHE_TTL_SESSIONS_SECONDS,
        )
    )
    app.include_router(
        build_analytics_router(
            settings,
            pipeline,
            require_auth,
            _hot_cache_get,
            _hot_cache_set,
            soar,
            HOT_CACHE_TTL_ATTACK_DISTRIBUTION_SECONDS,
            HOT_CACHE_TTL_ATTACK_GRAPH_SECONDS,
        )
    )
    blocks_router, mobile_block_handler = build_blocks_router(
        settings,
        require_auth,
        soar,
        _is_allowlisted,
        _manual_block_args,
        lambda args: _run_command(args),
        _spawn_manual_unblock,
        lambda **kwargs: publish_block(**kwargs),
    )
    app.include_router(blocks_router)
    app.include_router(build_llm_router(settings, require_auth))
    app.include_router(build_auth_router())
    app.include_router(
        build_exposure_router(
            settings,
            require_auth,
            _load_exposure_state,
            _persist_exposure_state,
            _exposure_provider,
            lambda config: _exposure_target_ports(config),
            lambda config: _exposure_firewall_paths(config),
            lambda args: _run_command(args),
            lambda enabled, config: _toggle_exposure_digitalocean(enabled, config),
            _to_bool,
            _now_ms,
            _as_int,
            EXPOSURE_TOGGLE_COOLDOWN_MS,
            EXPOSURE_RULE_COMMENT,
        )
    )

    mobile_push_service = MobilePushService()
    app.state.mobile_push_service = mobile_push_service
    app.include_router(
        build_mobile_router(
            settings=settings,
            require_auth=require_auth,
            mobile_service=mobile_push_service,
            block_ip_handler=mobile_block_handler,
        )
    )

    return app
