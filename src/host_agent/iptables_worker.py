#!/usr/bin/env python3
"""
CloudSentinel Host Agent: iptables Worker

This script is designed to run natively on the DigitalOcean host
(outside of the Docker container, as root). It listens to the Redis
Pub/Sub channel for block events emitted by the stateless SOAREngine
and executes the iptables rules to block attackers at the host perimeter.

Usage:
  sudo python3 iptables_worker.py --redis redis://localhost:6379/0
"""

import argparse
import asyncio
import json
import logging
import subprocess
import time

import redis.asyncio as aioredis

logger = logging.getLogger("cloudsentinel.host_agent")

class IPTablesWorker:
    def __init__(self, redis_url: str, firewall_path: str = "/sbin/iptables"):
        self.redis_url = redis_url
        self.firewall_path = firewall_path
        self._unblock_tasks: dict[str, asyncio.Task] = {}

    async def _run_firewall(self, args: list[str]) -> tuple[int, str, str]:
        command = [self.firewall_path, *args]
        logger.debug("Executing: %s", " ".join(command))
        proc = await asyncio.create_subprocess_exec(
            *command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        out = stdout.decode("utf-8", "replace") if stdout else ""
        err = stderr.decode("utf-8", "replace") if stderr else ""
        return proc.returncode, out, err

    async def block_ip(self, ip: str, ttl: int):
        try:
            # Check if rule exists
            exists, _, _ = await self._run_firewall(["-C", "INPUT", "-s", ip, "-j", "DROP"])
            if exists == 0:
                logger.info("IP %s is already blocked.", ip)
                return

            # Apply rule
            result, out, err = await self._run_firewall(["-A", "INPUT", "-s", ip, "-j", "DROP"])
            if result == 0:
                logger.warning("Successfully blocked %s via iptables.", ip)
                if ttl > 0:
                    if ip in self._unblock_tasks:
                        old_task = self._unblock_tasks[ip]
                        if not old_task.done():
                            old_task.cancel()
                            logger.debug("Cancelled old unblock task for %s", ip)
                    task = asyncio.create_task(self._auto_unblock(ip, ttl))
                    self._unblock_tasks[ip] = task
            else:
                logger.error("Failed to block %s: %s", ip, err)
        except Exception as exc:
            logger.error("Error applying iptables rule for %s: %s", ip, exc)

    async def _auto_unblock(self, ip: str, ttl: int):
        await asyncio.sleep(ttl)
        try:
            proc = await asyncio.create_subprocess_exec(
                self.firewall_path, "-D", "INPUT", "-s", ip, "-j", "DROP",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                logger.info("Auto-unblocked %s after %ds", ip, ttl)
            else:
                logger.warning("Failed to auto-unblock %s", ip)
        except Exception as exc:
            logger.error("Auto-unblock error for %s: %s", ip, exc)
        self._unblock_tasks.pop(ip, None)

    async def run(self):
        logger.info("Starting CloudSentinel Host Agent on %s", self.redis_url)
        redis = aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe("cloudsentinel:soar:blocks")
        logger.info("Subscribed to Redis channel: cloudsentinel:soar:blocks")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    try:
                        event = json.loads(data)
                        if event.get("action") == "block":
                            ip = event.get("ip")
                            ttl = event.get("ttl", 86400)
                            if ip:
                                await self.block_ip(ip, ttl)
                    except json.JSONDecodeError:
                        logger.error("Failed to decode message: %s", data)
        except asyncio.CancelledError:
            logger.info("Worker shutting down...")
        finally:
            await pubsub.unsubscribe("cloudsentinel:soar:blocks")
            await redis.aclose()


def main():
    parser = argparse.ArgumentParser(description="CloudSentinel Host Agent Worker")
    parser.add_argument("--redis", default="redis://localhost:6379/0", help="Redis URL")
    parser.add_argument("--firewall-path", default="/sbin/iptables", help="Path to iptables")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    worker = IPTablesWorker(args.redis, args.firewall_path)
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()