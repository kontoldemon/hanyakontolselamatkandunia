"""Enforce the refactor dependency boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _calls_os_system(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "system"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
        ):
            return True
    return False


def test_sensor_does_not_import_control_plane() -> None:
    for path in (PACKAGE / "sensor").glob("*.py"):
        names = _imports(path)
        assert "admin_api" not in names, path
        assert "fastapi" not in names, path
        assert "subprocess" not in names, path


def test_commands_do_not_execute_host_commands() -> None:
    for path in (PACKAGE / "commands").glob("*.py"):
        names = _imports(path)
        assert "subprocess" not in names, path
        assert "fastapi" not in names, path
        assert "admin_api" not in names, path
        assert not _calls_os_system(path), path


def test_admin_routes_keep_auth_dependencies() -> None:
    from fastapi.routing import APIRoute

    from cloudsentinel.admin_api import create_admin_app
    from cloudsentinel.config import Settings
    from cloudsentinel.pipeline import EventPipeline

    app = create_admin_app(Settings(), EventPipeline(Settings().redis))
    public = {"/healthz", "/auth/login", "/mobile/pair"}
    protected_prefixes = (
        "/admin",
        "/sessions",
        "/events",
        "/truth-summary",
        "/war-room-state",
        "/stats",
        "/attack-distribution",
        "/attack-graph",
        "/anomaly-stats",
        "/llm",
        "/runtime-config",
        "/readiness",
        "/metrics",
        "/mobile/config",
        "/mobile/pairing-token",
        "/mobile/test-alert",
        "/mobile/devices",
    )
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(protected_prefixes):
            continue
        if route.path in public:
            continue
        dependency_names = {
            getattr(dependency.dependency, "__name__", "")
            for dependency in route.dependencies
        }
        assert "require_auth" in dependency_names, route.path
