"""
CloudSentinel Dev Reloader — auto-restart on code changes.

Usage:
    python -m cloudsentinel.dev       # Start sensor with hot-reload
    python -m cloudsentinel.dev --test # Watch + run tests on change

Requires: pip install watchfiles
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path


async def dev_server():
    """Start sensor with hot-reload on code changes."""
    try:
        from watchfiles import Change, awatch
    except ImportError:
        print("watchfiles not installed. Install with: pip install watchfiles")
        return

    PACKAGE_ROOT = Path(__file__).resolve().parent
    process: subprocess.Popen | None = None

    async def restart():
        nonlocal process
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        process = subprocess.Popen(
            [sys.executable, "-m", "cloudsentinel.server",
             "--config", "configs/usas-production.yaml",
             "--env", ".env"],
            cwd=str(PACKAGE_ROOT),
        )
        print(f"[dev] Sensor PID: {process.pid}")

    await restart()
    print("[dev] Watching for changes... (Ctrl+C to stop)")

    async for changes in awatch(PACKAGE_ROOT, watch_filter=lambda _, p: p.endswith(".py")):
        changed_files = [p for _, p in changes if "__pycache__" not in p]
        if changed_files:
            print(f"[dev] Changed: {', '.join(changed_files[:3])}")
            await restart()


async def dev_test():
    """Watch for changes and run tests automatically."""
    try:
        from watchfiles import awatch
    except ImportError:
        print("watchfiles not installed")
        return

    PACKAGE_ROOT = Path(__file__).resolve().parent

    async def run_tests():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short",
            cwd=str(PACKAGE_ROOT),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        sys.stdout.write(stdout.decode())
        if stderr:
            sys.stderr.write(stderr.decode())

    await run_tests()
    print("[dev] Watching for changes...")

    async for changes in awatch(PACKAGE_ROOT, watch_filter=lambda _, p: p.endswith(".py")):
        changed = [p for _, p in changes if "__pycache__" not in p]
        if changed:
            print(f"\n[dev] Changed: {', '.join(changed[:3])}")
            await run_tests()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run tests on change")
    args = parser.parse_args()

    if args.test:
        asyncio.run(dev_test())
    else:
        asyncio.run(dev_server())
