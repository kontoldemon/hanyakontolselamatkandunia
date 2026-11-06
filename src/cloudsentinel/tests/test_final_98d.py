"""Final admin helper and entry-point branches."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import cloudsentinel.admin_api as admin_module
import cloudsentinel.mttb_benchmark as mttb_module
from cloudsentinel.config import load_settings


def test_exposure_target_skip_and_http_payload(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_TARGET_PORTS", ",")
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    admin_module._exposure_target_ports(settings)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return b"{}"

    monkeypatch.setattr(admin_module.urllib.request, "urlopen", lambda *_a, **_k: Response())
    status, payload, _error = asyncio.run(
        admin_module._http_json("POST", "https://do.test", "token", {"x": 1})
    )
    assert status == 200
    assert payload == {}


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
