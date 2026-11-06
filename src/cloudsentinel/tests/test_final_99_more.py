"""Final tenacity, command, and entry-point branches."""

from __future__ import annotations

import builtins
import sys
from pathlib import Path

import cloudsentinel.pipeline as pipeline_module
import cloudsentinel.threat_reporter as threat_module
from cloudsentinel.commands.base import commands
from cloudsentinel.vfs import VirtualFileSystem


def test_pipeline_tenacity_fallback(monkeypatch) -> None:
    path = Path(pipeline_module.__file__)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "tenacity" or name.startswith("tenacity."):
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    import types

    module = types.ModuleType("cloudsentinel.pipeline_fallback")
    module.__package__ = "cloudsentinel"
    module.__file__ = str(path)
    monkeypatch.setitem(sys.modules, "cloudsentinel.pipeline_fallback", module)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    exec(code, module.__dict__)
    monkeypatch.undo()
    assert module._TENACITY is False
    assert module.retry()(lambda: None)() is None


def test_command_issue_and_ssh() -> None:
    class Protocol:
        def __init__(self) -> None:
            self.fs = VirtualFileSystem()
            self.cwd = "/root"
            self.username = "root"
            self.clientIP = "8.8.8.8"
            self.environ = {}
            self.out: list[bytes] = []

        def write(self, data: str | bytes) -> None:
            self.out.append(data.encode() if isinstance(data, str) else data)

        def write_stdout(self, data: bytes) -> None:
            self.out.append(data)

        def write_stderr(self, data: bytes) -> None:
            self.out.append(data)

    protocol = Protocol()
    commands["/etc/issue.net"](protocol).call()
    commands["/usr/bin/ssh"](protocol).call()
    assert protocol.out


def test_threat_reporter_entry(monkeypatch) -> None:
    path = Path(threat_module.__file__)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    namespace = {
        "__name__": "__main__",
        "__package__": "cloudsentinel",
        "__file__": str(path),
    }
    exec(code, namespace)
