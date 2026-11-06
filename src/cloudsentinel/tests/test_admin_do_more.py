"""Cover the DigitalOcean exposure toggle success and failure paths."""

from __future__ import annotations

import asyncio

import cloudsentinel.admin_api as admin_module
from cloudsentinel.config import load_settings


def _settings():
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    return settings


def _prepare(monkeypatch, responses):
    monkeypatch.setattr(admin_module, "_do_firewall_id", lambda: "fw-1")
    monkeypatch.setattr(admin_module, "_do_token", lambda: "token")
    monkeypatch.setattr(admin_module, "_do_api_base", lambda: "https://do.test")
    monkeypatch.setattr(admin_module, "_exposure_target_ports", lambda _settings: [22])
    queue = list(responses)

    async def fake_http(_method: str, _url: str, _token: str, payload=None, **_kwargs):
        return queue.pop(0)

    monkeypatch.setattr(admin_module, "_http_json", fake_http)
    return _settings()


def _rule(port: str = "22") -> dict:
    return {"protocol": "tcp", "ports": port, "sources": {"addresses": ["0.0.0.0/0"]}}


def test_digitalocean_open_success(monkeypatch) -> None:
    before = {"firewall": {"name": "fw", "inbound_rules": [], "outbound_rules": [], "droplet_ids": [], "tags": []}}
    after = {"firewall": {"name": "fw", "inbound_rules": [_rule()], "outbound_rules": [], "droplet_ids": [], "tags": []}}
    settings = _prepare(monkeypatch, [(200, before, ""), (202, {}, ""), (200, after, "")])
    result = asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))
    assert result["ok"] is True
    assert result["actions"][0]["action"] == "opened"


def test_digitalocean_pause_success(monkeypatch) -> None:
    before = {"firewall": {"name": "fw", "inbound_rules": [_rule()], "outbound_rules": [], "droplet_ids": [], "tags": []}}
    after = {"firewall": {"name": "fw", "inbound_rules": [], "outbound_rules": [], "droplet_ids": [], "tags": []}}
    settings = _prepare(monkeypatch, [(200, before, ""), (202, {}, ""), (200, after, "")])
    result = asyncio.run(admin_module._toggle_exposure_digitalocean(False, settings))
    assert result["ok"] is True
    assert result["actions"][0]["action"] == "paused"


def test_digitalocean_error_responses(monkeypatch) -> None:
    settings = _prepare(monkeypatch, [(500, {}, "read failed")])
    assert asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))["ok"] is False

    settings = _prepare(monkeypatch, [(200, {}, "")])
    assert asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))["ok"] is False

    settings = _prepare(monkeypatch, [(200, {"firewall": {"inbound_rules": "bad"}}, "")])
    assert asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))["ok"] is False

    before = {"firewall": {"name": "fw", "inbound_rules": [], "outbound_rules": [], "droplet_ids": [], "tags": []}}
    settings = _prepare(monkeypatch, [(200, before, ""), (500, {}, "update failed")])
    assert asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))["ok"] is False

    settings = _prepare(monkeypatch, [(200, before, ""), (202, {}, ""), (500, {}, "verify failed")])
    assert asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))["ok"] is False

    settings = _prepare(monkeypatch, [(200, before, ""), (202, {}, ""), (200, {}, "")])
    assert asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))["ok"] is False

    after = {"firewall": {"name": "fw", "inbound_rules": [], "outbound_rules": [], "droplet_ids": [], "tags": []}}
    settings = _prepare(
        monkeypatch,
        [(200, before, ""), (202, {}, ""), (200, after, ""), (202, {}, "")],
    )
    result = asyncio.run(admin_module._toggle_exposure_digitalocean(True, settings))
    assert result["ok"] is False
    assert "rollback" in result["error"]
