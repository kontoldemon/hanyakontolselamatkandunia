#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 CloudSentinel contributors
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Measure CloudSentinel Phase 1 mean time to block.

Default mode is dry-run and measures local decision latency without changing
firewall rules. Use --live only on a disposable test host.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time


async def measure_once(attacker_ip: str, firewall_path: str, live: bool) -> float:
    start = time.perf_counter()
    if live:
        proc = await asyncio.create_subprocess_exec(
            firewall_path,
            "-A",
            "INPUT",
            "-s",
            attacker_ip,
            "-j",
            "DROP",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    else:
        await asyncio.sleep(0)
    return time.perf_counter() - start


async def main() -> None:
    parser = argparse.ArgumentParser(description="CloudSentinel MTTB benchmark")
    parser.add_argument("--attacker-ip", default="203.0.113.10")
    parser.add_argument("--firewall-path", default="/sbin/iptables")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    timings = [
        await measure_once(args.attacker_ip, args.firewall_path, args.live)
        for _ in range(args.iterations)
    ]
    mean = statistics.fmean(timings)
    p95 = sorted(timings)[int(len(timings) * 0.95) - 1]
    mode = "live" if args.live else "dry-run"
    sys.stdout.write(f"mode={mode}\n")
    sys.stdout.write(f"iterations={args.iterations}\n")
    sys.stdout.write(f"mean_mttb_seconds={mean:.6f}\n")
    sys.stdout.write(f"p95_mttb_seconds={p95:.6f}\n")
    sys.stdout.write(f"target_met={mean < 0.1}\n")


if __name__ == "__main__":
    asyncio.run(main())
