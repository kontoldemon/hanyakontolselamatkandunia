"""
CloudSentinel command framework.
Provides Command base class, registry, and ProtocolAdapter for server integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


class Command:
    """Base class for all CloudSentinel honeypot commands."""

    def __init__(self, protocol: Any, *args: str) -> None:
        self.protocol = protocol
        self.args: list[str] = list(args)
        self.environ: dict[str, str] = getattr(protocol, "environ", {})
        self.fs = getattr(protocol, "fs", None)
        self.input_data: bytes | None = None

    def write(self, text: str) -> None:
        """Write stdout to the protocol transport."""
        data = text.encode("utf-8") if isinstance(text, str) else text
        if hasattr(self.protocol, "write_stdout"):
            self.protocol.write_stdout(data)
        elif hasattr(self.protocol, "write"):
            self.protocol.write(data)

    def writeBytes(self, data: bytes) -> None:
        """Write raw bytes to the protocol transport."""
        if hasattr(self.protocol, "write"):
            self.protocol.write(data)

    def errorWrite(self, text: str) -> None:
        """Write stderr to the protocol transport."""
        data = text.encode("utf-8") if isinstance(text, str) else text
        if hasattr(self.protocol, "write_stderr"):
            self.protocol.write_stderr(data)
        elif hasattr(self.protocol, "write"):
            self.protocol.write(data)

    def start(self) -> None:
        """Execute the command and signal completion."""
        self.call()

    def call(self) -> None:
        """Override in subclasses with command logic."""
        pass

    def handle_CTRL_C(self) -> None:
        self.write("^C\n")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"


@dataclass
class CommandAdapter:
    """Protocol adapter bridging server session context to Command expectations.

    Commands expect a HoneyPotInteractiveProtocol-like object with:
      - write(data) / write_stdout(data) / write_stderr(data)
      - username, uid, gid, home, cwd, hostname
      - clientIP, realClientIP, logintime, starttime
      - environ dict, fs (VirtualFileSystem)
    """

    username: str = "root"
    uid: int = 0
    gid: int = 0
    home: str = "/root"
    cwd: str = "/root"
    hostname: str = "usas-prod-srv-01"
    clientIP: str = "0.0.0.0"
    realClientIP: str = "0.0.0.0"
    logintime: float = 0.0
    starttime: float = 0.0
    environ: dict[str, str] = field(default_factory=lambda: {
        "HOME": "/root", "LOGNAME": "root", "SHELL": "/bin/bash",
        "SHLVL": "1", "TMOUT": "1800", "UID": "0", "USER": "root",
        "PWD": "/root", "?": "0",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    })
    fs: Any = None
    _output_chunks: list[str] = field(default_factory=list, init=False, repr=False)

    def write(self, data: str | bytes) -> None:
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        self._output_chunks.append(data)

    def write_stdout(self, data: str | bytes) -> None:
        self.write(data)

    def write_stderr(self, data: str | bytes) -> None:
        self.write(data)

    def flush(self) -> str:
        """Return all captured output and reset buffer."""
        result = "".join(self._output_chunks)
        self._output_chunks.clear()
        return result


# Re-export for convenience
__all__ = ["Command", "CommandAdapter"]
