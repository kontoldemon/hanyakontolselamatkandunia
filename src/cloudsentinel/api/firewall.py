"""Operator-side firewall command helpers."""

from __future__ import annotations

import asyncio
import ipaddress
import subprocess

from ..config import Settings


def _is_allowlisted(ip: str, allowlist: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for value in allowlist:
        try:
            if addr in ipaddress.ip_network(str(value).strip(), strict=False):
                return True
        except ValueError:
            continue
    return False


async def _run_command(args: list[str], timeout: float = 5.0) -> tuple[int, str, str]:
    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    result = await asyncio.to_thread(run)
    return (
        int(result.returncode),
        result.stdout or "",
        result.stderr or "",
    )


_MANUAL_UNBLOCK_TASKS: set[asyncio.Task[None]] = set()


def _manual_block_args(firewall_path: str, action: str, ip: str, reason: str) -> list[str]:
    return [
        firewall_path,
        action,
        "INPUT",
        "-s",
        ip,
        "-m",
        "comment",
        "--comment",
        f"cloudsentinel-manual:{reason}",
        "-j",
        "DROP",
    ]


async def _schedule_manual_unblock(
    ip: str,
    reason: str,
    ttl: int,
    firewall_path: str,
) -> None:
    await asyncio.sleep(max(0, ttl))
    await _run_command(_manual_block_args(firewall_path, "-D", ip, reason))


def _spawn_manual_unblock(ip: str, reason: str, ttl: int, firewall_path: str) -> None:
    task = asyncio.create_task(_schedule_manual_unblock(ip, reason, ttl, firewall_path))
    _MANUAL_UNBLOCK_TASKS.add(task)
    task.add_done_callback(_MANUAL_UNBLOCK_TASKS.discard)


def _exposure_firewall_paths(settings: Settings) -> list[str]:
    ordered = [
        str(settings.soar.firewall_path or "/sbin/iptables"),
        "/usr/sbin/iptables-legacy",
        "/usr/sbin/iptables",
        "/usr/sbin/iptables-nft",
        "/sbin/iptables-legacy",
        "/sbin/iptables",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for item in ordered:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
