"""Small margin batch for HTTP error parsing and session helpers."""

from __future__ import annotations

import asyncio
import io
import urllib.error

import cloudsentinel.admin_api as admin_module
from cloudsentinel.config import load_settings
from cloudsentinel.hassh import HASSHDNA
from cloudsentinel.server import CloudSentinelSSHServer, CloudSentinelSession, ConnectionLimiter


def test_http_error_invalid_json(monkeypatch) -> None:
    def http_error(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError(
            "https://do.test",
            400,
            "bad",
            {},
            io.BytesIO(b"not-json"),
        )

    monkeypatch.setattr(admin_module.urllib.request, "urlopen", http_error)
    status, payload, error = asyncio.run(
        admin_module._http_json("GET", "https://do.test", "token")
    )
    assert status == 400
    assert payload == {}
    assert "not-json" in error


def test_read_allowed_skips_non_dict_rule() -> None:
    firewall = {
        "inbound_rules": [
            "bad",
            {"protocol": "tcp", "ports": "22", "sources": {"addresses": ["0.0.0.0/0"]}},
        ]
    }
    assert admin_module._do_read_allowed_ports(firewall, {22}) == {22}


def test_session_prompt_and_resolution() -> None:
    server = CloudSentinelSSHServer(
        load_settings("src/cloudsentinel/configs/usas-production.yaml", "src/cloudsentinel/.env"),
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        HASSHDNA(),
        ConnectionLimiter(max_total=1),
    )
    session = CloudSentinelSession(server)
    session.data_received("\r", None)
    assert session._resolve_command("cat")
