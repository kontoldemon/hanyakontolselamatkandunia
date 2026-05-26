"""Sandbox execution engine for CloudSentinel payloads."""

from __future__ import annotations

import asyncio
import structlog
from typing import Protocol

logger = structlog.get_logger("cloudsentinel.sandbox")


class SandboxExecutor(Protocol):
    async def execute(self, command: str, cwd: str) -> tuple[int, str]:
        """Execute a command safely and return (exit_code, output)."""
        ...


class DockerSandbox:
    """Executes commands in an ephemeral, network-isolated Docker container."""

    def __init__(self, image: str = "ubuntu:22.04", memory: str = "100m", cpus: str = "0.5") -> None:
        self.image = image
        self.memory = memory
        self.cpus = cpus

    async def execute(self, command: str, cwd: str) -> tuple[int, str]:
        # Normalize cwd
        if cwd == "~":
            workdir = "/root"
        elif cwd.startswith("~/"):
            workdir = "/root/" + cwd[2:]
        elif cwd.startswith("/"):
            workdir = cwd
        else:
            workdir = f"/root/{cwd}"

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",  # Isolated
            "--memory", self.memory,
            "--cpus", self.cpus,
            "-w", workdir,
            self.image,
            "sh", "-c", command
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
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