"""
CloudSentinel SOAR Task Queue — arq (Redis-backed durable task execution).

Replaces raw asyncio.create_task for SOAR blocking actions.
If the sensor crashes mid-block, arq retries on restart.
Requires: pip install arq
"""

from __future__ import annotations

import asyncio
import structlog
from typing import Any

logger = structlog.get_logger("cloudsentinel.arq")


class SOARWorker:
    """Arq worker that processes SOAR blocking tasks from Redis queue."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self.redis_url = redis_url
        self._worker: Any = None
        self._pool: Any = None

    async def start(self) -> None:
        try:
            from arq import create_pool
            from arq.worker import func

            self._pool = await create_pool(self.redis_url)

            @func
            async def block_ip(ctx: dict, ip: str, reason: str = "", ttl: int = 86400) -> dict:
                """Durable IP blocking — survives sensor restarts."""
                import subprocess
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "/sbin/iptables", "-A", "INPUT", "-s", ip, "-j", "DROP",
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
                    if proc.returncode == 0:
                        logger.info("arq: blocked %s (%s)", ip, reason)
                        return {"status": "blocked", "ip": ip, "ttl": ttl}
                    err = stderr.decode()[:200] if stderr else "unknown"
                    logger.error("arq: block failed for %s: %s", ip, err)
                    return {"status": "failed", "ip": ip, "error": err}
                except Exception as exc:
                    logger.error("arq: block exception for %s: %s", ip, exc)
                    raise

            @func
            async def unblock_ip(ctx: dict, ip: str) -> dict:
                import subprocess
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "/sbin/iptables", "-D", "INPUT", "-s", ip, "-j", "DROP",
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    )
                    await asyncio.wait_for(proc.communicate(), timeout=5.0)
                    return {"status": "unblocked", "ip": ip}
                except Exception as exc:
                    logger.error("arq: unblock failed for %s: %s", ip, exc)
                    raise

            logger.info("arq SOAR worker started on %s", self.redis_url)
        except ImportError:
            logger.debug("arq not installed — using asyncio.create_task fallback")
            self._pool = None

    async def enqueue_block(self, ip: str, reason: str = "", ttl: int = 86400) -> Any:
        if self._pool is None:
            return None
        return await self._pool.enqueue_job("block_ip", ip, reason, ttl)

    async def enqueue_unblock(self, ip: str) -> Any:
        if self._pool is None:
            return None
        return await self._pool.enqueue_job("unblock_ip", ip)

    async def stop(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
