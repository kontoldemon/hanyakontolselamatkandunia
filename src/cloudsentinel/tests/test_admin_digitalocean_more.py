"""Cover admin DigitalOcean API helpers and rule parsing."""

from __future__ import annotations

import asyncio
import io
import json
import urllib.error

import cloudsentinel.admin_api as admin_module
from cloudsentinel.config import load_settings


class FakeResponse:
    status = 200

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_http_json_success_and_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_module.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse({"ok": True}),
    )
    status, payload, error = asyncio.run(admin_module._http_json("GET", "https://do.test", "token"))
    assert status == 200
    assert payload == {"ok": True}
    assert error == ""

    def http_error(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError(
            "https://do.test",
            400,
            "bad request",
            {},
            io.BytesIO(b'{"message":"bad"}'),
        )

    monkeypatch.setattr(admin_module.urllib.request, "urlopen", http_error)
    status, payload, error = asyncio.run(admin_module._http_json("GET", "https://do.test", "token"))
    assert status == 400
    assert "bad" in error

    def network_error(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr(admin_module.urllib.request, "urlopen", network_error)
    status, payload, error = asyncio.run(admin_module._http_json("GET", "https://do.test", "token"))
    assert status == 0
    assert payload == {}
    assert "network down" in error


def test_digitalocean_rule_helpers() -> None:
    assert admin_module._do_rule_matches_port({"ports": ["22", "80"]}, 22) is True
    assert admin_module._do_rule_matches_port({"ports": "22-24"}, 23) is True
    assert admin_module._do_rule_matches_port({"ports": "22-24"}, 30) is False
    assert admin_module._do_rule_matches_port({"ports": ""}, 22) is False
    assert admin_module._do_rule_matches_port({"ports": "bad-range"}, 22) is False
    assert admin_module._do_rule_matches_port({}, 22) is False
    assert admin_module._do_rule_is_global({"sources": {"addresses": ["0.0.0.0/0"]}}) is True
    assert admin_module._do_rule_is_global({"sources": {"addresses": ["10.0.0.0/8"]}}) is False
    assert admin_module._do_rule_is_global({"sources": "bad"}) is False
    assert admin_module._do_rule_is_global({"sources": {}}) is False
    assert admin_module._do_rule_is_tcp({"protocol": "TCP"}) is True
    assert admin_module._do_rule_is_tcp({"protocol": "udp"}) is False

    firewall = {
        "inbound_rules": [
            "bad",
            {"protocol": "udp", "ports": "22", "sources": {"addresses": ["0.0.0.0/0"]}},
            {"protocol": "tcp", "ports": "22", "sources": {"addresses": ["10.0.0.0/8"]}},
            {"protocol": "tcp", "ports": "22", "sources": {"addresses": ["0.0.0.0/0"]}},
        ]
    }
    assert admin_module._do_read_allowed_ports(firewall, {22}) == {22}
    assert admin_module._do_read_allowed_ports({"inbound_rules": "bad"}, {22}) == set()


def test_toggle_missing_configuration(monkeypatch) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    monkeypatch.setattr(admin_module, "_do_firewall_id", lambda: "")
    result = asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))
    assert result["ok"] is False

    monkeypatch.setattr(admin_module, "_do_firewall_id", lambda: "fw")
    monkeypatch.setattr(admin_module, "_do_token", lambda: "")
    result = asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))
    assert result["ok"] is False

    monkeypatch.setattr(admin_module, "_do_token", lambda: "token")
    monkeypatch.setattr(admin_module, "_exposure_target_ports", lambda _settings: [])
    result = asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))
    assert result["ok"] is False
