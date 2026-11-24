#!/usr/bin/env python3
"""
CloudSentinel Stage 1 — Unified async SSH + HTTP honeypot.

Merged architecture: ConnectionLimiter, fuzz detection, HASSH/JA4S
fingerprinting, SOAR engine, command registry integration, VFS agent
fallback, TTY logging, Redis Streams pipeline, ClickHouse forwarding,
and optional admin API + OpenTelemetry.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import signal
import time
import uuid
from pathlib import Path
from typing import Any

import asyncssh
import structlog

from .api.bootstrap import start_admin_api
from .anomaly import CommandAnomalyDetector
from .auth import get_auth
from .config import Settings, load_settings, secret_to_str
from .geoip import enrich as geo_enrich
from .hassh import HASSHDNA, fallback_hassh_from_version, infer_client_software
from .observability import setup_observability
from .pipeline import ClickHouseForwarder, EventPipeline
from .sensor.fingerprint import (
    _decode_alg_list,
    _load_or_create_host_key_sync,
    _split_algorithms,
    extract_hassh,
    extract_ja4s,
    load_or_create_host_key,
)
from .sensor.http import start_http_honeypot
from .sensor.limits import ConnectionLimiter
from .sensor.session import (
    CloudSentinelSession,
    _split_unquoted,
    _strip_unquoted_redirects,
)
from .sensor.tty import TTYLogger, detect_fuzz
from .soar import SOAREngine
from .stream import LiveStream
from .tls import generate_self_signed_cert

logger = structlog.get_logger("cloudsentinel.server")
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_STAGE1_CONFIG = str(PACKAGE_ROOT / "configs" / "usas-production.yaml")
DEFAULT_STAGE1_ENV = str(PACKAGE_ROOT / ".env")


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
            from .metrics import get_metrics
            get_metrics().record_connect()
        except Exception:
            pass
        asyncio.create_task(self._emit_event("cloudsentinel.session.connect", {}))

    def connection_lost(self, exc: Exception | None) -> None:
        duration = time.time() - self.started_at
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
            from .metrics import get_metrics
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

            if self.hassh:
                logger.info("HASSH: %s from %s", self.hassh, self.src_ip)
                self.hassh_dna.record_sighting(self.hassh, self.src_ip)
                intel = self.hassh_dna.lookup(self.hassh)
                if intel.get("threat_level") == "critical":
                    logger.warning(
                        "KNOWN BOTNET: %s from %s", intel.get("botnet_family"), self.src_ip
                    )

        if self.conn is not None and self.ja4s is None and self.settings.fingerprinting.enable_ja4s:
            self.ja4s = extract_ja4s(self.conn, self.hassh_algorithms)

        if self.conn is not None and self.client_version is None:
            try:
                self.client_version = str(self.conn.get_extra_info("client_version", ""))
                if self.client_version:
                    if not self.hassh:
                        self.hassh, self.hassh_algorithms = fallback_hassh_from_version(
                            self.client_version,
                            self.settings.honeypot.server_version,
                        )
                        self.hassh_dna.record_sighting(self.hassh, self.src_ip)
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
            from .metrics import get_metrics
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
            from .metrics import get_metrics
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
            from .metrics import get_metrics
            metrics = get_metrics()
            if action not in ("none", "detect_only"):
                metrics.record_block(str(action))
                metrics.set_mttb(self.soar.mttb_ms)
                blocked_ips = set(getattr(self.soar, "_mem_blocked_ips", set()))
                if action not in ("skip_allowlisted_ip", "skip_private_ip", "skip_no_ip", "block_failed"):
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
                from .webhook import get_notifier
                await get_notifier().send_alert(soar_result)
            except Exception as exc:
                logger.debug("Webhook dispatch failed: %s", exc)

        try:
            from .pipeline import EventEnvelope
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



def install_uvloop() -> None:
    try:
        import uvloop
        uvloop.install()
    except Exception:
        return


def setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    # Wire structlog for JSON-structured logging (all modules benefit)
    try:
        import structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        structlog.get_logger("cloudsentinel").info("structlog wired — %s logging", "console" if debug else "JSON")
    except ImportError:
        structlog.get_logger("cloudsentinel").debug("structlog not installed — using standard logging")


async def main() -> None:
    parser = argparse.ArgumentParser(description="CloudSentinel Stage 1 SSH honeypot")
    parser.add_argument("--config", default=DEFAULT_STAGE1_CONFIG)
    parser.add_argument("--env", default=DEFAULT_STAGE1_ENV)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--redis-url")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    setup_logging(args.debug)
    install_uvloop()
    settings = load_settings(args.config, args.env)
    if args.host:
        settings.honeypot.listen_host = args.host
    if args.port:
        settings.honeypot.ssh_port = args.port
    if args.redis_url:
        settings.redis.url = args.redis_url
    setup_observability(settings.observability)

    # Core infrastructure
    pipeline = EventPipeline(settings.redis, settings.nats, settings.kafka)
    forwarder = ClickHouseForwarder(settings.redis, settings.clickhouse)
    soar = SOAREngine(
        risk_threshold=settings.soar.risk_threshold,
        firewall_enabled=settings.soar.firewall_enabled,
        firewall_dry_run=settings.soar.firewall_dry_run,
        firewall_path=settings.soar.firewall_path,
        block_ttl=settings.soar.block_ttl,
        decay_rate=settings.soar.decay_rate,
        allowlist=settings.soar.allowlist,
        active_profile=settings.soar.active_profile,
        mttb_target_ms=settings.soar.mttb_target_ms,
        eventgrid_enabled=settings.soar.eventgrid_enabled,
        eventgrid_endpoint=settings.soar.eventgrid_topic_endpoint,
        eventgrid_key=secret_to_str(settings.soar.eventgrid_topic_key),
        redis_settings=settings.redis,
    )
    hassh_dna = HASSHDNA()
    limiter = ConnectionLimiter()
    anomaly_detector = CommandAnomalyDetector()

    # TLS auto-generation
    cert_path, key_path = "", ""
    if settings.honeypot.tls_enabled:
        cert_path, key_path = generate_self_signed_cert(
            hostname=settings.honeypot.hostname,
            org="Universiti Sultan Azlan Shah",
            output_dir="var/lib/cloudsentinel/tls",
        )
        if cert_path and not settings.honeypot.tls_cert_file:
            settings.honeypot.tls_cert_file = cert_path
            settings.honeypot.tls_key_file = key_path

    # Auth initialization
    auth = get_auth()
    if auth.config.enabled:
        logger.info("JWT auth enabled for admin API")

    stream: LiveStream | None = None

    # Start pipeline and SOAR
    try:
        await pipeline.start()
        await soar.start()
        # Update pipeline connectivity metric
        try:
            from .metrics import get_metrics
            get_metrics().set_pipeline_status(pipeline.connected, pipeline.pending_count)
        except Exception:
            pass
    except Exception as exc:
        logger.warning("Redis unavailable, telemetry buffered in WAL: %s", exc)
        try:
            from .metrics import get_metrics
            get_metrics().set_pipeline_status(False)
        except Exception:
            pass

    # Start ClickHouse forwarder
    try:
        await forwarder.start()
    except Exception as exc:
        logger.warning("ClickHouse forwarder disabled: %s", exc)

    # Optional admin API
    admin_task: asyncio.Task[None] | None = None
    if settings.admin.enabled:
        admin_task = asyncio.create_task(start_admin_api(settings, pipeline, soar, cert_path, key_path))

    # Optional Socket.io live stream
    if settings.stream.enabled:
        stream = LiveStream(
            host=settings.stream.host,
            port=settings.stream.port,
            cors_origin=settings.stream.cors_origin,
        )
        await stream.start()

    # Optional HTTP honeypot
    http_task: asyncio.Task[None] | None = None
    if getattr(settings.honeypot, "http_enabled", False):
        http_task = asyncio.create_task(start_http_honeypot(settings, pipeline, soar))

    # Optional DNS honeypot
    dns_task: asyncio.Task[None] | None = None
    if getattr(settings.honeypot, "dns_enabled", False):
        from .dns_honeypot import DNSHoneypot
        dns_hp = DNSHoneypot(host=settings.honeypot.listen_host)
        dns_task = asyncio.create_task(dns_hp.start())
        logger.info("DNS honeypot started on UDP 53")

    # SSH host key
    host_key_path = Path("var/lib/cloudsentinel/ssh_host_rsa_key")
    host_key = await load_or_create_host_key(host_key_path)

    # Create server factory
    def server_factory() -> CloudSentinelSSHServer:
        return CloudSentinelSSHServer(
            settings,
            pipeline,
            soar,
            hassh_dna,
            limiter,
            stream,
            anomaly_detector,
        )

    # Start SSH listener
    ssh_server = await asyncssh.create_server(
        server_factory,
        host=settings.honeypot.listen_host,
        port=settings.honeypot.ssh_port,
        server_host_keys=[host_key],
        server_version=settings.honeypot.server_version,
        login_timeout=float(os.getenv("CLOUDSENTINEL_LOGIN_TIMEOUT", "120")),
    )

    listen_addr = ssh_server.sockets[0].getsockname() if ssh_server.sockets else ("?", 0)
    logger.info(
        "CloudSentinel listening on %s:%s as %s",
        listen_addr[0], listen_addr[1], settings.honeypot.hostname,
    )

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutting down...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        # Teardown
        ssh_server.close()
        await ssh_server.wait_closed()

        if admin_task:
            admin_task.cancel()
        if http_task:
            http_task.cancel()
        if dns_task:
            dns_task.cancel()
        if stream:
            await stream.stop()

        # Save anomaly model state
        try:
            anomaly_detector.save()
        except Exception:
            pass

        await pipeline.stop()
        await soar.stop()
        await forwarder.stop()
        logger.info("CloudSentinel stopped")


if __name__ == "__main__":
    asyncio.run(main())
