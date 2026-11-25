"""Final admin helper and entry-point branches."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import cloudsentinel.admin_api as admin_module
import cloudsentinel.mttb_benchmark as mttb_module
from cloudsentinel.config import load_settings




def test_mttb_main_entry(monkeypatch, tmp_path) -> None:
    async def no_start(_self: object) -> None:
        return None

    async def no_stop(_self: object) -> None:
        return None

    monkeypatch.setattr(mttb_module.SOAREngine, "start", no_start)
    monkeypatch.setattr(mttb_module.SOAREngine, "stop", no_stop)
    monkeypatch.setattr(
        sys,
        "argv",
        ["mttb_benchmark", "--iterations", "0"],
    )
    path = Path(mttb_module.__file__)
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    exec(code, {"__name__": "__main__", "__package__": mttb_module.__package__, "__file__": str(path)})
