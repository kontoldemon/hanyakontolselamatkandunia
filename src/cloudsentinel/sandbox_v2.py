"""
CloudSentinel Sandbox v2 - gVisor/Firecracker/Docker execution engines.
Supports multiple isolation runtimes for payload detonation.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any, Protocol

import structlog

logger = structlog.get_logger("cloudsentinel.sandbox")

RUNTIME = os.getenv("CLOUDSENTINEL_SANDBOX_RUNTIME", "gvisor")  # docker | gvisor | firecracker
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
        except TimeoutError:
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
        except TimeoutError:
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            return 124, "gVisor sandbox timeout."
        except Exception as exc:
            logger.error("gVisor execution failed: %s", exc)
            return 1, f"gVisor error: {exc}"



class DockerSDKSandbox:
    """Docker sandbox using the official Docker Python SDK.

    Replaces subprocess-based Docker commands with typed API calls.
    Better error handling, streaming output, and resource cleanup.

    Requires: pip install docker
    """

    def __init__(self, image: str = "ubuntu:22.04") -> None:
        self.image = image
        self.memory = SANDBOX_MEMORY
        self.cpus = SANDBOX_CPUS
        self.timeout = SANDBOX_TIMEOUT
        self._client: Any = None

    async def execute(self, command: str, cwd: str) -> tuple[int, str]:
        """Execute a command in an isolated Docker container via SDK."""
        try:
            import docker
            from docker.errors import DockerException

            if self._client is None:
                self._client = docker.from_env()

            workdir = cwd if cwd.startswith("/") else f"/root/{cwd.removeprefix('~/')}"
            workdir = workdir.replace("~", "/root")

            container = await asyncio.to_thread(
                self._client.containers.run,
                self.image,
                command=f"sh -c '{command}'",
                working_dir=workdir,
                network_mode="none",
                mem_limit=self.memory,
                nano_cpus=int(float(self.cpus) * 1e9),
                detach=True,
                remove=True,
            )

            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(container.wait, timeout=int(self.timeout)),
                    timeout=self.timeout,
                )
                logs = await asyncio.to_thread(container.logs)
                exit_code = result.get("StatusCode", 0)
                return exit_code, logs.decode("utf-8", errors="replace")
            except TimeoutError:
                await asyncio.to_thread(container.kill)
                return 124, "Sandbox timeout exceeded."

        except ImportError:
            logger.debug("docker SDK not installed — using subprocess fallback")
            from .sandbox import DockerSandbox as FallbackSandbox
            fb = FallbackSandbox(self.image)
            fb.memory = self.memory
            fb.cpus = self.cpus
            fb.timeout = self.timeout
            return await fb.execute(command, cwd)
        except Exception as exc:
            logger.error("Docker SDK sandbox error: %s", exc)
            return 1, f"Sandbox error: {exc}"



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
        sandbox = GVisorSandbox()
        if sandbox._available:
            return sandbox
        logger.warning("gVisor unavailable, falling back to Docker sandbox")
        return DockerSandbox()
    if runtime == "firecracker":
        return FirecrackerSandbox()
    return DockerSandbox()
