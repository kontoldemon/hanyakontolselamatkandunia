"""SSH honeypot server: accepts any credential and binds session telemetry."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import asyncssh
import structlog

from ..anomaly import CommandAnomalyDetector
from ..config import Settings
from ..geoip import enrich as geo_enrich
from ..hassh import HASSHDNA, hassh_action_applies, infer_client_software
from ..mobile_push import MobilePushService
from ..pipeline import EventPipeline
from ..soar import ENFORCED_BLOCK_ACTIONS, NEW_BLOCK_ACTIONS, SOAREngine
from ..stream import LiveStream
from .fingerprint import extract_hassh, extract_ja4s
from .limits import ConnectionLimiter
from .session import CloudSentinelSession
from .tty import TTYLogger

logger = structlog.get_logger("cloudsentinel.sensor.ssh")
_mobile_service: MobilePushService | None = None


def _mobile_alert_service() -> MobilePushService:
    global _mobile_service
    if _mobile_service is None:
        _mobile_service = MobilePushService()
    return _mobile_service


async def _dispatch_mobile_alert(event: dict) -> None:
    try:
        service = _mobile_alert_service()
        service.refresh()
        if not service.list_devices():
            return
        await service.dispatch_alert(event)
    except Exception as exc:
        logger.debug("mobile_alert_dispatch_failed", error=str(exc))


class CloudSentinelSSHServer(asyncssh.SSHServer):
    """Accepts any credential; binds per-connection telemetry, SOAR, and VFS."""

    def __init__(
        self,
        settings: Settings,
        pipeline: EventPipeline,
        soar: SOAREngine,
        hassh_dna: HASSHDNA,
        limiter: ConnectionLimiter,
        stream: LiveStream | None = None,
        anomaly_detector: CommandAnomalyDetector | None = None,
    ) -> None:
        self.settings = settings
        self.pipeline = pipeline
        self.soar = soar
        self.hassh_dna = hassh_dna
        self.limiter = limiter
        self.stream = stream
        self.anomaly_detector = anomaly_detector
        self.session_id = uuid.uuid4().hex[:12]
        self.conn: asyncssh.SSHServerConnection | None = None
        self.src_ip = ""
        self.src_port = 0
        self.username = ""
        self.password = ""
        self.hassh: str | None = None
        self.hassh_algorithms: str | None = None
        self.ja4s: str | None = None
        self.client_version: str | None = None
        self.started_at = time.time()
        self._auth_attempts = 0
        self._fuzz_detected = False
        self._accepted = False
        self._tty_logger = TTYLogger(self.session_id)

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        self.conn = conn
        peer = conn.get_extra_info("peername")
        if peer:
            self.src_ip = str(peer[0])
            self.src_port = int(peer[1])

        if not self.limiter.acquire_nowait(self.src_ip):
            logger.warning("Rate limit: rejecting %s (total=%d)", self.src_ip, self.limiter.total)
            conn.close()
            return
        self._accepted = True

        logger.info(
            "ssh connect session=%s src=%s:%s total=%d",
            self.session_id, self.src_ip, self.src_port, self.limiter.total,
        )
        # Record metrics
        try:
            from ..metrics import get_metrics
            get_metrics().record_connect()
        except Exception:
            pass
        asyncio.create_task(self._emit_event("cloudsentinel.session.connect", {}))

    def connection_lost(self, exc: Exception | None) -> None:
        duration = time.time() - self.started_at
        if (
            self.hassh is None
            and self.conn is not None
            and self.settings.fingerprinting.enable_hassh
        ):
            try:
                version = str(self.conn.get_extra_info("client_version", "") or "")
                if version and not self.client_version:
                    self.client_version = version
                self.hassh, self.hassh_algorithms = extract_hassh(self.conn)
            except Exception:
                self.hassh = None
            if self.hassh_algorithms and self.hassh_algorithms.startswith(("client:", "unknown-kex")):
                self.hassh = None
                self.hassh_algorithms = None
            if self.hassh:
                self.hassh_dna.record_sighting(self.hassh, self.src_ip)
                asyncio.create_task(self._emit_event("cloudsentinel.client.version", {
                    "version": self.client_version or "",
                    "hassh_md5": self.hassh,
                    "hassh_algorithms": self.hassh_algorithms or "",
                    "client": infer_client_software(self.client_version or "", self.hassh),
                    "reason": "hassh_kex_capture",
                }))
        if self._accepted:
            self.limiter.release_nowait(self.src_ip)
            self._accepted = False
        self._tty_logger.save()

        event = {
            "eventid": "cloudsentinel.session.closed",
            "session": self.session_id,
            "src_ip": self.src_ip,
            "src_port": self.src_port,
            "timestamp": time.time(),
            "duration": f"{duration:.1f}",
            "sensor": "CloudSentinel",
        }
        event.update(geo_enrich(self.src_ip))
        asyncio.create_task(self._process_event(event))

        logger.info(
            "ssh close session=%s duration=%.2fs attempts=%d",
            self.session_id, duration, self._auth_attempts,
        )
        try:
            from ..metrics import get_metrics
            get_metrics().record_disconnect()
        except Exception:
            pass

    def begin_auth(self, username: str) -> bool:
        if not self._accepted:
            return False
        if self._fuzz_detected:
            return False
        if self.limiter.total >= self.limiter.max_total:
            return False

        # Session timeout (30 min idle)
        elapsed = time.time() - self.started_at
        if elapsed > 1800:
            logger.info("Session timeout: %s after %.0fs", self.src_ip, elapsed)
            return False

        self.username = username
        if (
            self.conn is not None
            and self.hassh is None
            and self.settings.fingerprinting.enable_hassh
        ):
            self.hassh, self.hassh_algorithms = extract_hassh(self.conn)
            if self.hassh_algorithms and self.hassh_algorithms.startswith(("client:", "unknown-kex")):
                self.hassh = None
                self.hassh_algorithms = None

            if self.hassh:
                logger.info("HASSH: %s from %s", self.hassh, self.src_ip)
                self.hassh_dna.record_sighting(self.hassh, self.src_ip)
                intel = self.hassh_dna.lookup(self.hassh)
                if intel.get("threat_level") == "critical":
                    logger.warning(
                        "KNOWN BOTNET: %s from %s", intel.get("botnet_family"), self.src_ip
                    )
                if hassh_action_applies(
                    self.settings.deception.hassh_action,
                    self.settings.deception.hassh_threshold,
                    intel,
                ):
                    logger.warning(
                        "HASSH DROP: %s from %s", intel.get("client_software"), self.src_ip
                    )
                    asyncio.create_task(self._emit_event("cloudsentinel.login.failed", {
                        "username": username,
                        "auth_type": "hassh",
                        "reason": "malicious_hassh",
                        "hassh_md5": self.hassh,
                    }))
                    if self.conn is not None:
                        self.conn.close()
                    return False

        if self.conn is not None and self.ja4s is None and self.settings.fingerprinting.enable_ja4s:
            self.ja4s = extract_ja4s(self.conn, self.hassh_algorithms)

        if self.conn is not None and self.client_version is None:
            try:
                self.client_version = str(self.conn.get_extra_info("client_version", ""))
                if self.client_version:
                    asyncio.create_task(self._emit_event("cloudsentinel.client.version", {
                        "version": self.client_version,
                        "hassh_md5": self.hassh or "",
                        "hassh_algorithms": self.hassh_algorithms or "",
                        "client": infer_client_software(self.client_version, self.hassh or ""),
                    }))
            except Exception:
                pass

        return True

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        self.username = username
        self.password = password
        self._auth_attempts += 1

        # Max 20 auth attempts per session
        if self._auth_attempts > 20:
            logger.warning("Max auth attempts exceeded: %s (%d)", self.src_ip, self._auth_attempts)
            return False

        # Data-collection mode: always allow on first password attempt.
        # Keep auth-failed signals for non-password methods only.
        return True

    def validate_public_key(self, username: str, key: asyncssh.SSHKey) -> bool:
        self.username = username
        self._auth_attempts += 1
        try:
            kt = key.get_algorithm().decode()
        except Exception:
            kt = "unknown"

        asyncio.create_task(self._emit_event("cloudsentinel.login.failed", {
            "username": username,
            "auth_type": "publickey",
            "key_type": kt,
            "attempt": self._auth_attempts,
        }))
        try:
            from ..metrics import get_metrics
            get_metrics().record_auth_fail()
        except Exception:
            pass
        return False

    def kbdint_auth_supported(self) -> bool:
        return False

    def public_key_auth_supported(self) -> bool:
        return True

    def auth_completed(self) -> None:
        logger.info("Auth success: %s from %s", self.username, self.src_ip)
        asyncio.create_task(self._emit_event("cloudsentinel.login.success", {
            "username": self.username,
            "password": self.password,
        }))
        try:
            from ..metrics import get_metrics
            get_metrics().record_auth_success()
        except Exception:
            pass

    def session_requested(self) -> asyncssh.SSHServerSession:
        return CloudSentinelSession(self)

    def connection_requested(self, *args: Any) -> bool:
        return False

    def server_requested(self, *args: Any) -> bool:
        return False

    def _build_base_event(self, eventid: str, extra: dict | None = None) -> dict:
        ev: dict[str, Any] = {
            "eventid": eventid,
            "session": self.session_id,
            "src_ip": self.src_ip,
            "src_port": self.src_port,
            "timestamp": time.time(),
            "sensor": "CloudSentinel",
        }
        if self.hassh:
            ev["hassh_md5"] = self.hassh
            ev["hassh_algorithms"] = self.hassh_algorithms
        if self.ja4s:
            ev["ja4s"] = self.ja4s
        if extra:
            ev.update(extra)
        ev.update(geo_enrich(self.src_ip))
        return ev

    async def _emit_event(self, eventid: str, extra: dict | None = None) -> None:
        event = self._build_base_event(eventid, extra)
        await self._process_event(event)

    async def _process_event(self, event: dict) -> None:
        soar_result = await self.soar.process_event(self.session_id, event)
        action = soar_result.get("cloudsentinel_soar_action", "none")
        try:
            from ..metrics import get_metrics
            metrics = get_metrics()
            if action in NEW_BLOCK_ACTIONS:
                metrics.record_block(str(action))
                metrics.set_mttb(self.soar.mttb_ms)
            if action in ENFORCED_BLOCK_ACTIONS:
                blocked_ips = set(getattr(self.soar, "_mem_blocked_ips", set()))
                ip = str(soar_result.get("src_ip") or "")
                if ip:
                    blocked_ips.add(ip)
                metrics.blocked_ips = blocked_ips
                metrics.set_blocked_count(len(blocked_ips))
        except Exception:
            pass
        if action not in ("none", "detect_only", "dry_run_block"):
            logger.warning(
                "SOAR BLOCK: %s risk=%s action=%s",
                self.src_ip, soar_result.get("cloudsentinel_risk_score"), action,
            )
            if action == "iptables_block" and self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass

        if soar_result.get("cloudsentinel_risk_score", 0) >= 70:
            try:
                from ..webhook import get_notifier
                await get_notifier().send_alert(soar_result)
            except Exception as exc:
                logger.debug("Webhook dispatch failed: %s", exc)

        try:
            from ..pipeline import EventEnvelope
            envelope = EventEnvelope(
                event_type=soar_result.get("eventid", event.get("eventid", "unknown")),
                session_id=self.session_id,
                src_ip=self.src_ip,
                src_port=self.src_port,
                timestamp=soar_result.get("timestamp", time.time()),
                payload=soar_result,
            )
            await self.pipeline.emit(envelope)
        except Exception as exc:
            logger.debug("Pipeline emit failed: %s", exc)

        try:
            if self.stream is not None:
                self.stream.emit(soar_result)
        except Exception as exc:
            logger.debug("Live stream emit failed: %s", exc)

        asyncio.create_task(_dispatch_mobile_alert(soar_result))
