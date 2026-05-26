#!/usr/bin/env python3
"""CloudSentinel Phase 1 validation artifact generator."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .mitre import MITRE_TECHNIQUES


async def tcp_check(host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        writer.close()
        await writer.wait_closed()
        return {"ok": True, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


def http_json(url: str, token: str = "", timeout: float = 5.0) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def write_artifacts(report: dict[str, Any], artifacts_dir: Path) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "phase1-validation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# CloudSentinel Phase 1 Validation",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Target: {report['target']}",
        f"- Overall: {'PASS' if report['overall_pass'] else 'FAIL'}",
        f"- SSH honeypot: {'PASS' if report['checks']['ssh_honeypot']['ok'] else 'FAIL'}",
        f"- Management SSH: {'PASS' if report['checks']['management_ssh']['ok'] else 'FAIL'}",
        f"- Socket.io port: {'PASS' if report['checks']['socketio']['ok'] else 'FAIL'}",
        f"- MITRE mapped techniques: {report['checks']['mitre_coverage']['count']}",
    ]
    readiness = report["checks"].get("admin_readiness", {})
    if readiness:
        lines.extend([
            f"- Redis connected: {readiness.get('redis_connected')}",
            f"- ClickHouse ok: {readiness.get('clickhouse_ok')}",
            f"- Stream enabled: {readiness.get('stream_enabled')}",
        ])
    (artifacts_dir / "phase1-validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Validate CloudSentinel Phase 1 live gates")
    parser.add_argument("--host", default="188.166.184.42")
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument("--management-port", type=int, default=22222)
    parser.add_argument("--socket-port", type=int, default=3001)
    parser.add_argument("--admin-url", default="http://188.166.184.42:8080")
    parser.add_argument("--admin-token", default="")
    parser.add_argument("--artifacts-dir", default="artifacts")
    args = parser.parse_args()

    ssh, mgmt, socketio = await asyncio.gather(
        tcp_check(args.host, args.ssh_port),
        tcp_check(args.host, args.management_port),
        tcp_check(args.host, args.socket_port),
    )

    checks: dict[str, Any] = {
        "ssh_honeypot": ssh,
        "management_ssh": mgmt,
        "socketio": socketio,
        "mitre_coverage": {"ok": len(MITRE_TECHNIQUES) >= 15, "count": len(MITRE_TECHNIQUES)},
    }
    try:
        checks["admin_health"] = http_json(f"{args.admin_url.rstrip('/')}/healthz")
        checks["admin_readiness"] = http_json(f"{args.admin_url.rstrip('/')}/readiness", args.admin_token)
    except Exception as exc:
        checks["admin_error"] = str(exc)

    required = [
        checks["ssh_honeypot"].get("ok"),
        checks["management_ssh"].get("ok"),
        checks["socketio"].get("ok"),
        checks["mitre_coverage"].get("ok"),
        checks.get("admin_readiness", {}).get("ok", False),
    ]
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": args.host,
        "checks": checks,
        "overall_pass": all(required),
    }
    write_artifacts(report, Path(args.artifacts_dir))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
