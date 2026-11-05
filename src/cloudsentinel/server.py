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
import hashlib
import logging
import os
import signal
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import asyncssh
import structlog

from .admin_api import create_admin_app
from .anomaly import CommandAnomalyDetector
from .auth import get_auth
from .commands import CommandAdapter
from .commands.base import commands as cmd_registry
from .config import Settings, load_settings
from .geoip import enrich as geo_enrich
from .hassh import HASSHDNA, calculate_hassh, fallback_hassh_from_version, infer_client_software
from .mitre import score_command
from .observability import setup_observability
from .pipeline import ClickHouseForwarder, EventPipeline
from .soar import SOAREngine
from .stream import LiveStream
from .tls import generate_self_signed_cert
from .vfs import VirtualFileSystem
from .vfs_agent import VFSAgent, VFSContext

logger = structlog.get_logger("cloudsentinel.server")
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_STAGE1_CONFIG = str(PACKAGE_ROOT / "configs" / "usas-production.yaml")
DEFAULT_STAGE1_ENV = str(PACKAGE_ROOT / ".env")

# ── Connection Rate Limiter ──────────────────────────────────────────


class ConnectionLimiter:
    """Sliding-window rate limiter: per-IP and global caps."""

    def __init__(self, max_per_ip: int = 30, max_total: int = 500, window: float = 60.0) -> None:
        self.max_per_ip = max_per_ip
        self.max_total = max_total
        self.window = window
        self._ips: defaultdict[str, list[float]] = defaultdict(list)
        self._total = 0
        self._lock = asyncio.Lock()

    def acquire_nowait(self, ip: str) -> bool:
        now = time.monotonic()
        self._ips[ip] = [t for t in self._ips[ip] if now - t < self.window]
        if len(self._ips[ip]) >= self.max_per_ip or self._total >= self.max_total:
            return False
        self._ips[ip].append(now)
        self._total += 1
        return True

    async def acquire(self, ip: str) -> bool:
        async with self._lock:
            return self.acquire_nowait(ip)

    def release_nowait(self, ip: str) -> None:
        self._total = max(0, self._total - 1)

    async def release(self, ip: str) -> None:
        async with self._lock:
            self.release_nowait(ip)

    @property
    def total(self) -> int:
        return self._total


# ── Helpers ──────────────────────────────────────────────────────────


def _split_algorithms(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, bytes):
        value = value.decode("utf-8", "ignore")
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(part) for part in value if str(part)]
    return [str(value)]


def _decode_alg_list(values: Any) -> list[str]:
    items: list[str] = []
    for value in (values or []):
        if isinstance(value, bytes):
            try:
                items.append(value.decode("ascii"))
            except Exception:
                items.append(value.decode("utf-8", "ignore"))
        else:
            items.append(str(value))
    return [item for item in items if item]


def extract_hassh(conn: asyncssh.SSHServerConnection) -> tuple[str | None, str | None]:
    """Best-effort HASSH extraction from AsyncSSH connection metadata."""

    # Primary path: parse AsyncSSH's cached client KEXINIT payload.
    # This contains the real client-offered algorithm lists required by HASSH.
    try:
        raw = getattr(conn, "_client_kexinit", b"")
        if isinstance(raw, bytes) and raw:
            from asyncssh.packet import SSHPacket

            pkt = SSHPacket(raw)
            _ = pkt.get_bytes(16)  # cookie
            client_kex = _decode_alg_list(pkt.get_namelist())
            _ = pkt.get_namelist()  # host key algs
            enc_cs = _decode_alg_list(pkt.get_namelist())
            _ = pkt.get_namelist()  # enc sc
            mac_cs = _decode_alg_list(pkt.get_namelist())
            _ = pkt.get_namelist()  # mac sc
            cmp_cs = _decode_alg_list(pkt.get_namelist())
            _ = pkt.get_namelist()  # cmp sc
            if client_kex:
                return calculate_hassh(
                    client_kex,
                    enc_cs or ["unknown"],
                    mac_cs or ["unknown"],
                    cmp_cs or ["none"],
                )
    except Exception:
        pass

    lookup_names = {
        "kex": ("kex_algs", "client_kex_algs", "kex_algorithms"),
        "enc": ("enc_algs", "client_enc_algs", "encryption_algs"),
        "mac": ("mac_algs", "client_mac_algs"),
        "cmp": ("cmp_algs", "client_cmp_algs", "compression_algs"),
    }

    found: dict[str, list[str]] = {}
    for key, names in lookup_names.items():
        values: list[str] = []
        for name in names:
            try:
                values = _split_algorithms(conn.get_extra_info(name))
            except Exception:
                values = []
            if values:
                break
        found[key] = values

    if not found["kex"]:
        # Fallback: build stable fingerprint from negotiated values if client
        # algorithm lists are unavailable.
        negotiated = [
            _split_algorithms(conn.get_extra_info("recv_cipher")),
            _split_algorithms(conn.get_extra_info("recv_mac")),
            _split_algorithms(conn.get_extra_info("recv_compression")),
        ]
        if any(negotiated):
            kex_name = "unknown-kex"
            try:
                kex_obj = getattr(conn, "_kex", None)
                algorithm = getattr(kex_obj, "algorithm", b"")
                if isinstance(algorithm, bytes):
                    kex_name = algorithm.decode("ascii", "ignore") or kex_name
                elif algorithm:
                    kex_name = str(algorithm)
            except Exception:
                pass
            return calculate_hassh(
                [kex_name],
                negotiated[0] or ["unknown"],
                negotiated[1] or ["unknown"],
                negotiated[2] or ["none"],
            )
        # Last-resort deterministic surrogate so dashboard never loses identity.
        try:
            client_version = str(conn.get_extra_info("client_version", "") or "unknown-client")
            server_version = str(conn.get_extra_info("server_version", "") or "unknown-server")
            return calculate_hassh(
                [f"client:{client_version}"],
                [f"server:{server_version}"],
                ["unknown"],
                ["none"],
            )
        except Exception:
            pass
        return None, None

    return calculate_hassh(
        found["kex"],
        found["enc"] or ["unknown"],
        found["mac"] or ["unknown"],
        found["cmp"] or ["none"],
    )


def extract_ja4s(conn: asyncssh.SSHServerConnection, hassh_algorithms: str | None) -> str | None:
    """Produce a JA4S-like SSH server profile from negotiated SSH metadata."""

    try:
        import ja4plus  # noqa: F401
    except Exception:
        pass

    try:
        server_version = str(conn.get_extra_info("server_version", ""))
        cipher = str(conn.get_extra_info("send_cipher", ""))
        mac = str(conn.get_extra_info("send_mac", ""))
        compression = str(conn.get_extra_info("send_compression", "none"))
        seed = "|".join(["ssh", server_version, cipher, mac, compression, hassh_algorithms or ""])
        return "ja4s_ssh_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    except Exception as exc:
        logger.debug("JA4S extraction failed: %s", exc)
        return None


def _load_or_create_host_key_sync(path: Path) -> asyncssh.SSHKey:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return asyncssh.read_private_key(str(path))

    key = asyncssh.generate_private_key("ssh-rsa")
    private_key = key.export_private_key()
    if isinstance(private_key, str):
        private_key = private_key.encode("utf-8")
    path.write_bytes(private_key)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


async def load_or_create_host_key(path: Path) -> asyncssh.SSHKey:
    return await asyncio.to_thread(_load_or_create_host_key_sync, path)


# ── TTY Logger ───────────────────────────────────────────────────────


class TTYLogger:
    """Persist full TTY session transcripts to disk (async I/O via aiofiles)."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._dir: Path | None = None
        self._log: list[tuple[float, bytes]] = []
        try:
            self._dir = Path(f"var/lib/cloudsentinel/tty/{session_id}")
            self._dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self._dir = None

    def record(self, data: bytes) -> None:
        self._log.append((time.time(), data))

    async def save_async(self) -> None:
        """Save TTY logs using async I/O (non-blocking on event loop)."""
        if not self._dir:
            return
        try:
            import aiofiles
            async with aiofiles.open(self._dir / "tty.log", "wb") as fh:
                for ts, data in self._log:
                    await fh.write(f"[{ts:.3f}] ".encode() + data + b"\n")
            async with aiofiles.open(self._dir / "tty.raw", "wb") as fh:
                for _, data in self._log:
                    await fh.write(data)
        except ImportError:
            # Fallback to sync I/O if aiofiles not installed
            logger.debug("aiofiles not available, using sync fallback")
            try:
                with open(self._dir / "tty.log", "wb") as fh:
                    for ts, data in self._log:
                        fh.write(f"[{ts:.3f}] ".encode() + data + b"\n")
                with open(self._dir / "tty.raw", "wb") as fh:
                    for _, data in self._log:
                        fh.write(data)
            except Exception as exc:
                logger.debug("TTY save failed: %s", exc)
        except Exception as exc:
            logger.debug("TTY save failed: %s", exc)

    def save(self) -> None:
        """Synchronous save wrapper (called from connection_lost)."""
        if not self._dir:
            return
        import asyncio as _asyncio
        try:
            loop = _asyncio.get_running_loop()
            loop.create_task(self.save_async())
        except RuntimeError:
            # No running loop, use sync fallback
            try:
                with open(self._dir / "tty.log", "wb") as fh:
                    for ts, data in self._log:
                        fh.write(f"[{ts:.3f}] ".encode() + data + b"\n")
                with open(self._dir / "tty.raw", "wb") as fh:
                    for _, data in self._log:
                        fh.write(data)
            except Exception as exc:
                logger.debug("TTY save failed: %s", exc)


# ── Fuzz Detection ───────────────────────────────────────────────────


def detect_fuzz(data: bytes, src_ip: str) -> bool:
    """Heuristic fuzz/DoS detection for SSH data streams."""
    if len(data) > 65536:
        logger.warning("Fuzz: oversized packet %db from %s", len(data), src_ip)
        return True
    if b"\x00" * 100 in data:
        logger.warning("Fuzz: null flood from %s", src_ip)
        return True
    return False


# ── SSH Server ───────────────────────────────────────────────────────


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

    # ── Connection lifecycle ──────────────────────────────────────

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

    # ── Auth ──────────────────────────────────────────────────────

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

    # ── Session ───────────────────────────────────────────────────

    def session_requested(self) -> asyncssh.SSHServerSession:
        return CloudSentinelSession(self)

    def connection_requested(self, *args: Any) -> bool:
        return False

    def server_requested(self, *args: Any) -> bool:
        return False

    # ── Event pipeline ────────────────────────────────────────────

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
        # 1. SOAR scoring + blocking
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

        # 2. Webhook alerting for high-risk events
        if soar_result.get("cloudsentinel_risk_score", 0) >= 70:
            try:
                from .webhook import get_notifier
                await get_notifier().send_alert(soar_result)
            except Exception as exc:
                logger.debug("Webhook dispatch failed: %s", exc)

        # 3. Pipeline (Redis/ClickHouse)
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

        # 4. Sanitized Socket.io feed for dashboard
        try:
            if self.stream is not None:
                self.stream.emit(soar_result)
        except Exception as exc:
            logger.debug("Live stream emit failed: %s", exc)


# ── SSH Session ──────────────────────────────────────────────────────


class CloudSentinelSession(asyncssh.SSHServerSession):
    """Interactive shell session: command registry → VFS agent fallback."""

    BANNER_DELAY: float = 0.08

    def __init__(self, server: CloudSentinelSSHServer) -> None:
        self.server = server
        self.chan: asyncssh.SSHServerChannel | None = None
        self.buffer = ""
        self.exec_command: str | None = None
        self._line_buffer = b""

        # VFS context for LLM-backed command responses
        context = VFSContext(
            hostname=server.settings.honeypot.hostname,
            os_version=server.settings.honeypot.os_version,
            username=server.settings.honeypot.prompt_user,
            cwd=server.settings.honeypot.prompt_path,
        )
        self.vfs = VFSAgent(server.settings.llm, context)
        # Fast local filesystem for command registry commands (ls/cat/pwd/etc).
        self._command_fs = VirtualFileSystem.build_default()
        self._anomaly_detector = server.anomaly_detector

    def connection_made(self, chan: asyncssh.SSHServerChannel) -> None:
        self.chan = chan

    def pty_requested(
        self,
        term_type: str,
        term_size: tuple[int, int, int, int],
        term_modes: dict[int, int],
    ) -> bool:
        return True

    def shell_requested(self) -> bool:
        return True

    def exec_requested(self, command: str) -> bool:
        self.exec_command = command
        return True

    def session_started(self) -> None:
        if self.exec_command is not None:
            asyncio.create_task(self._run_exec(self.exec_command))
            return
        self._write(f"{self.server.settings.honeypot.banner}\r\n")
        self._prompt()

    def data_received(self, data: str, datatype: asyncssh.DataType) -> None:
        raw = data.encode("utf-8", errors="replace")

        # Fuzz detection on raw bytes
        if detect_fuzz(raw, self.server.src_ip):
            self.server._fuzz_detected = True
            if self.chan:
                self.chan.exit(1)
            return

        # TTY logging
        self.server._tty_logger.record(raw)

        # Interactive line handling with basic terminal control codes
        for byte in raw:
            b = bytes([byte])

            if b == b"\x03":  # Ctrl-C
                self._line_buffer = b""
                self._write(b"^C\r\n")
                self._prompt()
                continue

            if b == b"\x04":  # Ctrl-D
                self._write(b"logout\r\n")
                if self.chan:
                    self.chan.exit(0)
                return

            if b == b"\t":  # Tab
                self._write(b"\x07")  # Bell = no completions
                continue

            if b in (b"\x7f", b"\x08"):  # Backspace
                if self._line_buffer:
                    self._line_buffer = self._line_buffer[:-1]
                    self._write(b"\b \b")
                continue

            if b in (b"\r", b"\n"):
                self._write(b"\r\n" if b == b"\r" else b"\n")
                if self._line_buffer:
                    line = self._line_buffer.decode("utf-8", errors="replace").strip()
                    self._line_buffer = b""
                    if line:
                        asyncio.create_task(self._run_interactive(line))
                    else:
                        self._prompt()
                else:
                    self._prompt()
                continue

            if 32 <= byte < 127:
                self._line_buffer += b
                self._write(b)

    def connection_lost(self, exc: Exception | None) -> None:
        asyncio.create_task(self.vfs.close())

    async def _run_exec(self, command: str) -> None:
        try:
            output = await self._execute(command)
            if output:
                self._write(output + "\n")
        finally:
            if self.chan is not None:
                try:
                    self.chan.exit(0)
                except (BrokenPipeError, OSError):
                    logger.debug("SSH exec channel already closed")

    async def _run_interactive(self, command: str) -> None:
        if command in {"exit", "logout"}:
            self._write("logout\r\n")
            if self.chan is not None:
                self.chan.exit(0)
            return

        output = await self._execute(command)
        if output:
            self._write(output.replace("\n", "\r\n") + "\r\n")
        self._prompt()

    async def _execute(self, command: str) -> str:
        """Execute command: command registry first, VFS agent fallback."""
        command = command.strip()[:1000]
        if not command:
            return ""

        # Emit command input for SOAR scoring + pipeline
        asyncio.create_task(self.server._emit_event("cloudsentinel.command.input", {
            "input": command,
            "username": self.server.username,
        }))
        honeytoken_hit = self._detect_honeytoken_access(command)
        if honeytoken_hit is not None:
            asyncio.create_task(self.server._emit_event("cloudsentinel.honeytoken.access", {
                "input": command,
                "username": self.server.username,
                "honeytoken_path": honeytoken_hit,
                "risk_score": 85,
                "mitre_techniques": ["T1555"],
                "mitre_names": {"T1555": "Credentials from Password Stores"},
            }))
        try:
            from .metrics import get_metrics
            get_metrics().record_command()
        except Exception:
            pass

        # 1. Try command registry (163+ fake Linux commands)
        try:
            import shlex
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()

        if parts:
            cmd_name = parts[0]

            # Handle cd — update VFS agent context
            if cmd_name in ("cd", "/usr/bin/cd"):
                return self._handle_cd(parts[1:])

            # Resolve from registry
            cls = self._resolve_command(cmd_name)
            if cls is not None:
                try:
                    adapter = CommandAdapter(
                        username=self.server.username,
                        hostname=self.server.settings.honeypot.hostname,
                        clientIP=self.server.src_ip,
                        realClientIP=self.server.src_ip,
                        logintime=self.server.started_at,
                        starttime=self.server.started_at,
                        cwd=self._adapter_cwd(),
                        fs=self._command_fs,
                    )
                    cmd_instance = cls(adapter, *parts[1:])
                    cmd_instance.start()
                    output = adapter.flush()

                    # Some registry commands can resolve but still produce no text in this
                    # adapter flow. Fall back to VFS policy to avoid blank replay/output.
                    if not str(output).strip():
                        output, response_mode = await self.vfs.run_command_with_mode(command)
                        mitre_annotation = score_command(command)
                        asyncio.create_task(self.server._emit_event("cloudsentinel.command.output", {
                            "input": command,
                            "output": str(output)[:2000],
                            "source": "vfs_agent",
                            "response_mode": response_mode,
                            "risk_score": mitre_annotation.get("risk_score", 0),
                            "mitre_techniques": mitre_annotation.get("mitre_techniques", []),
                        }))
                        return str(output)

                    asyncio.create_task(self.server._emit_event("cloudsentinel.command.output", {
                        "input": command,
                        "output": str(output)[:2000],
                        "source": "command_registry",
                        "response_mode": "command_registry",
                    }))
                    return str(output)
                except Exception as exc:
                    logger.debug("Command registry failed for %r: %s", command, exc)

        # 2. Fall back to VFS agent (LLM-backed or deterministic mock)
        try:
            output, response_mode = await self.vfs.run_command_with_mode(command)
            mitre_annotation = score_command(command)

            asyncio.create_task(self.server._emit_event("cloudsentinel.command.output", {
                "input": command,
                "output": output[:2000],
                "source": "vfs_agent",
                "response_mode": response_mode,
                "risk_score": mitre_annotation.get("risk_score", 0),
                "mitre_techniques": mitre_annotation.get("mitre_techniques", []),
            }))
            # Anomaly scoring
            if self._anomaly_detector is not None:
                anomaly = self._anomaly_detector.score(command)
                if anomaly["anomaly_score"] > 70:
                    logger.warning("Anomaly detected: score=%.1f cmd=%r", anomaly["anomaly_score"], command[:80])

            return output
        except Exception as exc:
            logger.warning("Command handling failed for %r: %s", command, exc)
            asyncio.create_task(self.server._emit_event("cloudsentinel.command.output", {
                "input": command,
                "output": "bash: command execution error",
                "source": "vfs_agent",
                "response_mode": "blocked",
            }))
            return "bash: command execution error"

    def _resolve_command(self, name: str) -> type | None:
        if name in cmd_registry:
            return cmd_registry[name]
        for prefix in ("/usr/bin/", "/bin/", "/usr/sbin/", "/sbin/"):
            if prefix + name in cmd_registry:
                return cmd_registry[prefix + name]
        return None

    def _adapter_cwd(self) -> str:
        cwd = (self.vfs.context.cwd or "").strip()
        if not cwd or cwd == "~":
            return "/root"
        return cwd

    def _handle_cd(self, args: list[str]) -> str:
        target = args[0] if args else "~"
        if not args or args[0] == "-":
            self.vfs.context.cwd = "~"
        else:
            if target == "..":
                if self.vfs.context.cwd not in ("/", "~"):
                    self.vfs.context.cwd = "/".join(self.vfs.context.cwd.split("/")[:-1]) or "/"
            elif target.startswith("/"):
                self.vfs.context.cwd = target
            elif target == "~":
                self.vfs.context.cwd = "~"
            else:
                self.vfs.context.cwd = self.vfs.context.cwd.rstrip("/") + "/" + target
        logger.debug("cd %s -> %s", target, self.vfs.context.cwd)
        return ""

    def _prompt(self) -> None:
        host = self.server.settings.honeypot.hostname
        user = self.server.settings.honeypot.prompt_user
        path = self.vfs.context.cwd
        self._write(f"{user}@{host}:{path}# ")

    def _write(self, text: str | bytes) -> None:
        if self.chan is not None:
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            try:
                self.chan.write(text)
            except (BrokenPipeError, OSError):
                logger.debug("SSH channel already closed during write")

    def _detect_honeytoken_access(self, command: str) -> str | None:
        normalized = command.lower()
        targets = (
            "/root/.aws/credentials",
            "usas_backup_credentials.txt",
            "research_grants_2026.txt",
            "/var/www/html/config.php",
            "/tmp/.hidden_miner_config",
            "/root/.ssh/id_rsa",
        )
        for token_path in targets:
            if token_path in normalized:
                return token_path
        return None


# ── HTTP Honeypot ────────────────────────────────────────────────────


async def start_http_honeypot(
    settings: Settings,
    pipeline: EventPipeline,
    soar: SOAREngine,
) -> None:
    try:
        import granian as _granian_http
        from granian.constants import Interfaces
        from granian.constants import Loops as GranianLoops
        _USE_GRANIAN_HTTP = True
    except ImportError:
        import uvicorn as _uvicorn_http
        _USE_GRANIAN_HTTP = False

    from .http_server import create_http_honeypot

    app = create_http_honeypot(pipeline, soar)
    http_port = getattr(settings.honeypot, "http_port", 8080)

    tls_kwargs: dict[str, Any] = {}
    if settings.honeypot.tls_enabled:
        cert = settings.honeypot.tls_cert_file
        key = settings.honeypot.tls_key_file
        if Path(cert).exists() and Path(key).exists():
            tls_kwargs = {"ssl_certfile": cert, "ssl_keyfile": key}
            logger.info("TLS enabled for HTTP honeypot: %s", cert)
        else:
            logger.warning("TLS cert/key not found, falling back to plain HTTP")

    proto = "https" if tls_kwargs else "http"
    if _USE_GRANIAN_HTTP:
        logger.info("HTTP honeypot (granian) listening on %s://%s:%s", proto, settings.honeypot.listen_host, http_port)
        await _granian_http.serve(
            app,
            host=settings.honeypot.listen_host,
            port=http_port,
            interface=Interfaces.ASGI,
            loop=GranianLoops.uvloop,
            ssl_certfile=tls_kwargs.get("ssl_certfile") if tls_kwargs else None,
            ssl_keyfile=tls_kwargs.get("ssl_keyfile") if tls_kwargs else None,
        )
    else:
        config = _uvicorn_http.Config(
            app,
            host=settings.honeypot.listen_host,
            port=http_port,
            log_level="warning",
            loop="asyncio",
            **tls_kwargs,
        )
        server = _uvicorn_http.Server(config)
        logger.info("HTTP honeypot (uvicorn) listening on %s://%s:%s", proto, settings.honeypot.listen_host, http_port)
        await server.serve()


# ── Admin API ────────────────────────────────────────────────────────


async def start_admin_api(
    settings: Settings,
    pipeline: EventPipeline,
    soar: Any = None,
    cert_path: str = "",
    key_path: str = "",
) -> None:
    admin_server = os.getenv("ADMIN_SERVER", "uvicorn").lower()
    if admin_server == "granian":
        try:
            import granian
            from granian.constants import Interfaces, Loops

            _USE_GRANIAN = True
        except ImportError:
            import uvicorn

            logger.warning("Granian requested but unavailable, falling back to uvicorn")
            _USE_GRANIAN = False
    else:
        import uvicorn

        _USE_GRANIAN = False

    app = create_admin_app(settings, pipeline, soar)

    tls_kwargs: dict[str, Any] = {}
    if cert_path and key_path and Path(cert_path).exists() and Path(key_path).exists():
        tls_kwargs = {"ssl_certfile": cert_path, "ssl_keyfile": key_path}
        logger.info("TLS enabled for admin API: %s", cert_path)
    elif settings.tls.enabled:
        # Auto-generate TLS cert if not provided
        from .tls import generate_self_signed_cert
        gen_cert, gen_key = generate_self_signed_cert(
            hostname=settings.honeypot.hostname,
            output_dir="var/lib/cloudsentinel/tls",
        )
        if gen_cert and gen_key:
            tls_kwargs = {"ssl_certfile": gen_cert, "ssl_keyfile": gen_key}
            logger.info("TLS auto-generated for admin API: %s", gen_cert)
    else:
        logger.warning("Admin API running without TLS - JWT tokens sent in plaintext")

    proto = "https" if tls_kwargs else "http"
    if _USE_GRANIAN:
        logger.info("Admin API (granian) listening on %s://%s:%s", proto, settings.admin.host, settings.admin.port)
        await granian.serve(
            app,
            host=settings.admin.host,
            port=settings.admin.port,
            interface=Interfaces.ASGI,
            loop=Loops.uvloop,
            ssl_certfile=tls_kwargs.get("ssl_certfile"),
            ssl_keyfile=tls_kwargs.get("ssl_keyfile"),
        )
    else:
        config = uvicorn.Config(
            app,
            host=settings.admin.host,
            port=settings.admin.port,
            log_level="info",
            loop="asyncio",
            **tls_kwargs,
        )
        server = uvicorn.Server(config)
        logger.info("Admin API (uvicorn) listening on %s://%s:%s", proto, settings.admin.host, settings.admin.port)
        await server.serve()


# ── Main ─────────────────────────────────────────────────────────────


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

    await stop_event.wait()

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
