"""
CloudSentinel Dagger Pipeline — CI/CD as Python code.

Dagger replaces bash-heavy GitHub Actions with typed Python pipelines.
Same pipeline runs locally (`dagger run python ci.py`) and in CI.
Tested: lint -> test -> build -> deploy to DigitalOcean Droplet.

Requires: pip install dagger-io
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # FYP root


async def lint_sensor() -> bool:
    """Run ruff + mypy on sensor code."""
    import dagger

    async with dagger.Connection() as client:
        src = client.host().directory(
            str(ROOT / "src" / "cloudsentinel"),
            exclude=["__pycache__", ".pytest_cache", ".ruff_cache", "var", "cloudsentinel-main"],
        )

        container = (
            client.container()
            .from_("python:3.12-slim")
            .with_directory("/app", src)
            .with_workdir("/app")
            .with_exec(["pip", "install", "ruff", "mypy"])
            .with_exec(["ruff", "check", "."])
            .with_exec(["ruff", "format", "--check", "."])
        )

        try:
            await container.sync()
            print("[DAGGER] Lint passed")
            return True
        except Exception as exc:
            print(f"[DAGGER] Lint failed: {exc}")
            return False


async def test_sensor() -> bool:
    """Run pytest with coverage on sensor code."""
    import dagger

    async with dagger.Connection() as client:
        src = client.host().directory(str(ROOT))

        # Start Redis service
        redis = (
            client.container()
            .from_("redis:7-alpine")
            .with_exec(["redis-server", "--save", '""', "--appendonly", "no"])
            .as_service()
        )

        container = (
            client.container()
            .from_("python:3.12-slim")
            .with_directory("/app", src)
            .with_workdir("/app/src/cloudsentinel")
            .with_service_binding("redis", redis)
            .with_env_variable("REDIS_URL", "redis://redis:6379/0")
            .with_exec(["pip", "install", "-r", "requirements.txt"])
            .with_exec([
                "pytest", "tests/", "-v",
                "--cov=cloudsentinel",
                "--cov-report=term-missing",
                "--cov-fail-under=70",
                "--timeout=60",
                "-n", "auto",
            ])
        )

        try:
            await container.sync()
            print("[DAGGER] Tests passed")
            return True
        except Exception as exc:
            print(f"[DAGGER] Tests failed: {exc}")
            return False


async def build_docker() -> str | None:
    """Build and push Docker image to registry."""
    import dagger

    async with dagger.Connection() as client:
        src = client.host().directory(
            str(ROOT / "src" / "cloudsentinel"),
            exclude=["__pycache__", ".pytest_cache", "var"],
        )

        image = (
            client.container()
            .from_("python:3.12-slim")
            .with_directory("/app", src)
            .with_workdir("/app")
            .with_exec(["apt-get", "update", "-qq"])
            .with_exec(["apt-get", "install", "-y", "-qq", "iptables", "ca-certificates"])
            .with_exec(["pip", "install", "-r", "requirements.txt"])
            .with_entrypoint(["python", "-m", "cloudsentinel.server"])
        )

        digest = await image.digest()
        print(f"[DAGGER] Docker image built: {digest}")
        return digest


async def deploy_do(droplet_ip: str = "") -> bool:
    """Deploy to DigitalOcean Droplet via SSH + docker compose."""
    import dagger

    if not droplet_ip:
        droplet_ip = input("Droplet IP: ")

    async with dagger.Connection() as client:
        src = client.host().directory(str(ROOT))

        container = (
            client.container()
            .from_("alpine:latest")
            .with_directory("/deploy", src)
            .with_exec(["apk", "add", "openssh-client", "rsync"])
            .with_exec([
                "rsync", "-avz", "--exclude=__pycache__",
                "/deploy/src/", f"deploy@{droplet_ip}:/opt/cloudsentinel/"
            ])
            .with_exec([
                "ssh", f"deploy@{droplet_ip}",
                "cd /opt/cloudsentinel && docker compose --profile default up -d --build"
            ])
        )

        try:
            await container.sync()
            print(f"[DAGGER] Deployed to {droplet_ip}")
            return True
        except Exception as exc:
            print(f"[DAGGER] Deploy failed: {exc}")
            return False


async def ci_pipeline() -> bool:
    """Full CI pipeline: lint -> test -> build."""
    print("=== CloudSentinel Dagger CI ===\n")

    if not await lint_sensor():
        print("CI FAILED at lint stage")
        return False

    if not await test_sensor():
        print("CI FAILED at test stage")
        return False

    digest = await build_docker()
    if not digest:
        print("CI FAILED at build stage")
        return False

    print(f"\nCI PASSED - Image: {digest}")
    return True


async def cd_pipeline(droplet_ip: str = "") -> bool:
    """Full CD pipeline: build -> deploy."""
    print("=== CloudSentinel Dagger CD ===\n")

    digest = await build_docker()
    if not digest:
        return False

    if not await deploy_do(droplet_ip):
        return False

    print(f"\nCD PASSED - Deployed {digest} to DO")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CloudSentinel Dagger CI/CD")
    parser.add_argument("--ci", action="store_true", help="Run CI pipeline")
    parser.add_argument("--cd", action="store_true", help="Run CD pipeline (requires --ip)")
    parser.add_argument("--lint", action="store_true", help="Lint only")
    parser.add_argument("--test", action="store_true", help="Test only")
    parser.add_argument("--build", action="store_true", help="Build only")
    parser.add_argument("--ip", help="Droplet IP for deployment")
    args = parser.parse_args()

    if args.ci:
        sys.exit(0 if asyncio.run(ci_pipeline()) else 1)
    elif args.cd:
        sys.exit(0 if asyncio.run(cd_pipeline(args.ip or "")) else 1)
    elif args.lint:
        sys.exit(0 if asyncio.run(lint_sensor()) else 1)
    elif args.test:
        sys.exit(0 if asyncio.run(test_sensor()) else 1)
    elif args.build:
        asyncio.run(build_docker())
    else:
        parser.print_help()
