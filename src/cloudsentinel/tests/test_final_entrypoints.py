"""Final CLI and validation entry-point fallbacks."""

from __future__ import annotations

import asyncio
import builtins
from pathlib import Path

import cloudsentinel.cli as cli_module
import cloudsentinel.validate_phase1 as validate_module


def test_cli_without_typer(monkeypatch) -> None:
    path = Path(cli_module.__file__)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "typer" or name.startswith("rich"):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    namespace = {
        "__name__": "cloudsentinel.cli_fallback",
        "__package__": "cloudsentinel",
        "__file__": str(path),
    }
    monkeypatch.setattr(builtins, "__import__", fake_import)
    exec(code, namespace)
    monkeypatch.undo()
    assert namespace["_HAS_CLI"] is False


def test_validate_entrypoint(monkeypatch) -> None:
    path = Path(validate_module.__file__)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    real_run = asyncio.run

    def close(coro):
        coro.close()

    monkeypatch.setattr(asyncio, "run", close)
    try:
        exec(code, {"__name__": "__main__", "__package__": "cloudsentinel", "__file__": str(path)})
    finally:
        monkeypatch.setattr(asyncio, "run", real_run)
