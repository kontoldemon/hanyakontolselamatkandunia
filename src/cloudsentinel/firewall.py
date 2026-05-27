"""
CloudSentinel Firewall Abstraction - iptables + nftables support.
Auto-detects available firewall backend at runtime.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Protocol

import structlog

logger = structlog.get_logger("cloudsentinel.firewall")

FIREWALL_BACKEND = os.getenv("CLOUDSENTINEL_FIREWALL_BACKEND", "auto")  # auto | iptables | nftables


class FirewallBackend(Protocol):
    async def block(self, ip: str) -> tuple[bool, str]: ...
    async def unblock(self, ip: str) -> tuple[bool, str]: ...
    async def is_blocked(self, ip: str) -> bool: ...
    @property
    def name(self) -> str: ...


class IPTablesBackend:
    """Traditional iptables backend (legacy, widely supported)."""

    def __init__(self, path: str = "/sbin/iptables") -> None:
        self.path = path
        self.chain = "INPUT"

    @property
    def name(self) -> str:
        return "iptables"

    async def block(self, ip: str) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.path, "-A", self.chain, "-s", ip, "-j", "DROP",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                logger.info("iptables DROP: %s", ip)
                return True, ""
            err = stderr.decode("utf-8", "replace")[:200] if stderr else "unknown"
            logger.error("iptables block failed for %s: %s", ip, err)
            return False, err
        except Exception as exc:
            return False, str(exc)

    async def unblock(self, ip: str) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.path, "-D", self.chain, "-s", ip, "-j", "DROP",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            return proc.returncode == 0, ""
        except Exception as exc:
            return False, str(exc)

    async def is_blocked(self, ip: str) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.path, "-C", self.chain, "-s", ip, "-j", "DROP",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            return proc.returncode == 0
        except Exception:
            return False


class NFTablesBackend:
    """Modern nftables backend (kernel-native, better performance)."""

    TABLE = "cloudsentinel"
    CHAIN = "dynamic_block"
    SET = "blocked_ips"

    def __init__(self, path: str = "/usr/sbin/nft") -> None:
        self.path = path
        self._initialized = False

    @property
    def name(self) -> str:
        return "nftables"

    async def _init(self) -> None:
        if self._initialized:
            return
        script = (
            f"add table inet {self.TABLE}; "
            f"add set inet {self.TABLE} {self.SET} {{ type ipv4_addr; flags timeout; }}; "
            f"add chain inet {self.TABLE} {self.CHAIN} {{ type filter hook input priority 0; }}; "
            f"add rule inet {self.TABLE} {self.CHAIN} ip saddr @{self.SET} drop"
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.path, "-c", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                self._initialized = True
                logger.info("nftables initialized: table=%s chain=%s", self.TABLE, self.CHAIN)
            else:
                logger.warning("nftables init returned %d (may already exist)", proc.returncode)
                self._initialized = True
        except Exception as exc:
            logger.error("nftables init failed: %s", exc)

    async def block(self, ip: str, ttl_seconds: int = 86400) -> tuple[bool, str]:
        await self._init()
        # Validate IP to prevent command injection
        import ipaddress
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return False, f"Invalid IP address: {ip}"
        try:
            cmd = f"add element inet {self.TABLE} {self.SET} {{ {ip} timeout {ttl_seconds}s }}"
            proc = await asyncio.create_subprocess_exec(
                self.path, "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                logger.info("nftables DROP: %s (ttl=%ds)", ip, ttl_seconds)
                return True, ""
            err = stderr.decode("utf-8", "replace")[:200] if stderr else "unknown"
            return False, err
        except Exception as exc:
            return False, str(exc)

    async def unblock(self, ip: str) -> tuple[bool, str]:
        await self._init()
        try:
            cmd = f"delete element inet {self.TABLE} {self.SET} {{ {ip} }}"
            proc = await asyncio.create_subprocess_exec(
                self.path, "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            return proc.returncode == 0, ""
        except Exception as exc:
            return False, str(exc)

    async def is_blocked(self, ip: str) -> bool:
        await self._init()
        try:
            cmd = f"get element inet {self.TABLE} {self.SET} {{ {ip} }}"
            proc = await asyncio.create_subprocess_exec(
                self.path, "-c", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            return proc.returncode == 0
        except Exception:
            return False


def create_firewall(backend: str = FIREWALL_BACKEND) -> FirewallBackend:
    """Auto-detect and return the best available firewall backend."""
    if backend == "nftables":
        return NFTablesBackend()
    if backend == "iptables":
        return IPTablesBackend()

    # Auto-detect: prefer nftables
    if shutil.which("nft"):
        logger.info("Firewall: nftables selected (auto-detected)")
        return NFTablesBackend()
    if shutil.which("iptables"):
        logger.info("Firewall: iptables selected (auto-detected)")
        return IPTablesBackend()
    logger.warning("No firewall backend found! SOAR blocks will be dry-run only.")
    return IPTablesBackend()  # Return iptables stub; _run_firewall will fail gracefully
