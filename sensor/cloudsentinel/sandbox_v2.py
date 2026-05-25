"""
CloudSentinel Sandbox v2 - gVisor/Firecracker/Docker execution engines.
Supports multiple isolation runtimes for payload detonation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from typing import Protocol

logger = logging.getLogger("cloudsentinel.sandbox")

RUNTIME = os.getenv("CLOUDSENTINEL_SANDBOX_RUNTIME", "docker")  # docker | gvisor | firecracker
SANDBOX_MEMORY = os.getenv("CLOUDSENTINEL_SANDBOX_MEMORY", "128m")
SANDBOX_CPUS = os.getenv("CLOUDSENTINEL_SANDBOX_CPUS", "0.5")
SANDBOX_TIMEOUT = float(os.getenv("CLOUDSENTINEL_SANDBOX_TIMEOUT", "30.0"))


class SandboxExecutor(Protocol):
    async def execute(self, command: str, cwd: str) -> tuple[int, str]: ...


class DockerSandbox:
    """Standard Docker sandbox with network isolation."""

    def __init__(self, image: str = "ubuntu:22.04") -> None:
        self.image = image
        self.memory = SANDBOX_MEMORY
        self.cpus = SANDBOX_CPUS
        self.timeout = SANDBOX_TIMEOUT

    async def execute(self, command: str, cwd: str) -> tuple[int, str]:
        workdir = cwd if cwd.startswith("/") else f"/root/{cwd.removeprefix('~/')}"
        workdir = workdir.replace("~", "/root")

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", self.memory,
            "--cpus", self.cpus,
            "--pids-limit", "50",
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
            "--read-only",
            "-w", workdir,
            self.image,
            "sh", "-c", command,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
            return proc.returncode or 0, stdout.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            return 124, "Sandbox timeout exceeded."
        except Exception as exc:
            logger.error("Sandbox execution failed: %s", exc)
            return 1, f"Sandbox error: {exc}"


class GVisorSandbox:
    """gVisor (runsc) sandbox - kernel-level isolation without VM overhead."""

    def __init__(self, image: str = "ubuntu:22.04") -> None:
        self.image = image
        self.memory = SANDBOX_MEMORY
        self.cpus = SANDBOX_CPUS
        self.timeout = SANDBOX_TIMEOUT
        self._available = shutil.which("runsc") is not None

    async def execute(self, command: str, cwd: str) -> tuple[int, str]:
        if not self._available:
            return 1, "gVisor (runsc) not installed. Install: https://gvisor.dev/docs/user_guide/install/"

        workdir = cwd if cwd.startswith("/") else f"/root/{cwd.removeprefix('~/')}"
        workdir = workdir.replace("~", "/root")

        cmd = [
            "docker", "run", "--rm",
            "--runtime", "runsc",
            "--network", "none",
            "--memory", self.memory,
            "--cpus", self.cpus,
            "--pids-limit", "50",
            "-w", workdir,
            self.image,
            "sh", "-c", command,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
            return proc.returncode or 0, stdout.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            return 124, "gVisor sandbox timeout."
        except Exception as exc:
            logger.error("gVisor execution failed: %s", exc)
            return 1, f"gVisor error: {exc}"


class FirecrackerSandbox:
    """Firecracker microVM sandbox via firectl (lightweight VMM)."""

    def __init__(self) -> None:
        self.timeout = SANDBOX_TIMEOUT
        self._available = (
            shutil.which("firecracker") is not None
            and shutil.which("firectl") is not None
        )

    async def execute(self, command: str, cwd: str) -> tuple[int, str]:
        if not self._available:
            return 1, "Firecracker not installed. See: https://github.com/firecracker-microvm/firecracker"

        return 1, "Firecracker sandbox requires VM image setup. Use gVisor for now."


def create_sandbox(runtime: str = RUNTIME) -> SandboxExecutor:
    """Factory: return the appropriate sandbox for the configured runtime."""
    if runtime == "gvisor":
        return GVisorSandbox()
    elif runtime == "firecracker":
        return FirecrackerSandbox()
    else:
        return DockerSandbox()
