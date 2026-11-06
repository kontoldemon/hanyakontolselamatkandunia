"""Cover SOAR optional integration import fallbacks."""

from __future__ import annotations

import builtins
from pathlib import Path

import cloudsentinel.soar as soar


def test_soar_optional_import_fallbacks(monkeypatch) -> None:
    path = Path(soar.__file__)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        level = kwargs.get("level", args[3] if len(args) > 3 else 0)
        if level == 1 and name in {"misp_feed", "abuseipdb", "firewall"}:
            raise ModuleNotFoundError(name)
        return real_import(name, *args, **kwargs)

    namespace = {
        "__name__": "cloudsentinel.soar_fallback",
        "__package__": "cloudsentinel",
        "__file__": str(path),
    }
    monkeypatch.setattr(builtins, "__import__", fake_import)
    exec(code, namespace)
    monkeypatch.undo()

    assert namespace["_MISP_AVAILABLE"] is False
    assert namespace["_ABUSEIPDB_AVAILABLE"] is False
    assert namespace["_FIREWALL_AVAILABLE"] is False
    assert namespace["_get_misp"]() is None
    assert namespace["_get_abuseipdb"]() is None
    assert namespace["_create_firewall"]() is None
