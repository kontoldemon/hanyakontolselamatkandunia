"""Interactive SSH session and shell command routing."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import asyncssh
import structlog

from ..commands import CommandAdapter
from ..commands.base import commands as cmd_registry
from ..mitre import score_command
from ..vfs import VirtualFileSystem
from ..vfs_agent import VFSAgent, VFSContext
from .tty import detect_fuzz

if TYPE_CHECKING:
    from .ssh import CloudSentinelSSHServer

logger = structlog.get_logger("cloudsentinel.sensor.session")


def _split_unquoted(command: str, separators: tuple[str, ...]) -> list[str]:
    parts: list[str] = []
    start = 0
    index = 0
    quote: str | None = None
    escaped = False
    while index < len(command):
        char = command[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if char == "\\":
            escaped = True
            index += 1
            continue
        if quote:
            if char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        matched = next((sep for sep in separators if command.startswith(sep, index)), None)
        if matched:
            parts.append(command[start:index].strip())
            index += len(matched)
            start = index
            continue
        index += 1
    parts.append(command[start:].strip())
    return [part for part in parts if part]


def _strip_unquoted_redirects(command: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(command):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char in ("<", ">"):
            return command[:index].rstrip()
    return command


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
        self._command_fs = VirtualFileSystem.for_deception(
            server.settings.deception.level,
            server.settings.deception.seed_canary_keys,
        )
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
                if len(self._line_buffer) > 8192:
                    self.server._fuzz_detected = True
                    self._line_buffer = b""
                    if self.chan is not None:
                        self.chan.exit(1)
                    return
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

    async def _execute(self, command: str, stdin: str = "") -> str:
        """Execute command: command registry first, VFS agent fallback."""
        command = command.strip()[:1000]
        if not command:
            return ""

        if command in ("exit", "logout"):
            if self.chan is not None:
                self.chan.exit(0)
            return ""

        chain_segments = _split_unquoted(command, ("||", "&&", ";"))
        if chain_segments != [command]:
            outputs = []
            for segment in chain_segments:
                outputs.append(await self._execute(segment))
            return "\n".join(part for part in outputs if part)

        pipe_segments = _split_unquoted(command, ("|",))
        if pipe_segments != [command]:
            output = ""
            for segment in pipe_segments:
                output = await self._execute(segment, stdin=output)
            return output

        command = _strip_unquoted_redirects(command)
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
            from ..metrics import get_metrics
            get_metrics().record_command()
        except Exception:
            pass

        if self._anomaly_detector is not None:
            try:
                anomaly = self._anomaly_detector.score(command)
                if anomaly["anomaly_score"] > 70:
                    logger.warning(
                        "Anomaly detected: score=%.1f cmd=%r",
                        anomaly["anomaly_score"],
                        command[:80],
                    )
            except Exception as exc:
                logger.debug("Anomaly scoring failed: %s", exc)

        # Try command registry
        try:
            import shlex
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()

        if parts:
            cmd_name = parts[0]

            # Update VFS agent context for directory changes
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
                        stdin=stdin,
                    )
                    cmd_instance = cls(adapter, *parts[1:])
                    cmd_instance.start()
                    output = adapter.flush()

                    asyncio.create_task(self.server._emit_event("cloudsentinel.command.output", {
                        "input": command,
                        "output": str(output)[:2000],
                        "source": "command_registry",
                        "response_mode": "command_registry",
                    }))
                    return str(output)
                except Exception as exc:
                    logger.debug("Command registry failed for %r: %s", command, exc)

        # Fall back to VFS agent
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
