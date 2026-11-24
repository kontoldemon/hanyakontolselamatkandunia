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
