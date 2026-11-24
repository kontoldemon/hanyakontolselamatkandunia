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
import signal
from pathlib import Path

import asyncssh
import structlog

from .api.bootstrap import start_admin_api
from .anomaly import CommandAnomalyDetector
from .auth import get_auth
from .config import Settings, load_settings, secret_to_str
from .hassh import HASSHDNA
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
from .sensor.ssh import CloudSentinelSSHServer
from .sensor.tty import TTYLogger, detect_fuzz
from .soar import SOAREngine
from .stream import LiveStream
from .tls import generate_self_signed_cert

logger = structlog.get_logger("cloudsentinel.server")
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_STAGE1_CONFIG = str(PACKAGE_ROOT / "configs" / "usas-production.yaml")
DEFAULT_STAGE1_ENV = str(PACKAGE_ROOT / ".env")


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
