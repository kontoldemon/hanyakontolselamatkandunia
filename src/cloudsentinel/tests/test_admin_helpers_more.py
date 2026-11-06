"""Cover admin exposure parsing, health checks, and response-mode helpers."""

from __future__ import annotations

import asyncio
import sys
import types

import cloudsentinel.admin_api as admin_module
from cloudsentinel.config import load_settings


def test_exposure_port_parsing(monkeypatch) -> None:
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_ADMIN_PORTS", "bad,,0,70000,22")
    assert admin_module._exposure_admin_ports() == {22}
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_ADMIN_PORTS", "bad")
    assert admin_module._exposure_admin_ports() == {22}

    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_TARGET_PORTS", "bad,0,70000,2222")
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_ADMIN_PORTS", "22")
    assert admin_module._exposure_target_ports(settings) == [2222]
    monkeypatch.setenv("CLOUDSENTINEL_EXPOSURE_ALLOW_ADMIN_PORTS", "true")
    assert admin_module._exposure_target_ports(settings) == [2222]


def test_clickhouse_health(monkeypatch) -> None:
    fake = types.ModuleType("clickhouse_connect")

    class Result:
        result_rows = [(1,)]

    class Client:
        def query(self, _query: str) -> Result:
            return Result()

    fake.get_client = lambda **_kwargs: Client()
    monkeypatch.setitem(sys.modules, "clickhouse_connect", fake)
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    settings.clickhouse.enabled = True
    assert admin_module._clickhouse_health_sync(settings) is True

    async def healthy(_settings: object) -> bool:
        return True

    monkeypatch.setattr(admin_module, "_clickhouse_health_sync", lambda _settings: True)
    assert asyncio.run(admin_module._clickhouse_health(settings)) is True

    def broken(_settings: object) -> bool:
        raise RuntimeError("down")

    monkeypatch.setattr(admin_module, "_clickhouse_health_sync", broken)
    assert asyncio.run(admin_module._clickhouse_health(settings)) is False
    settings.clickhouse.enabled = False
    assert asyncio.run(admin_module._clickhouse_health(settings)) is None


def test_admin_helpers(monkeypatch) -> None:
    assert admin_module._is_allowlisted("bad-ip", ["10.0.0.0/8"]) is False
    assert admin_module._is_allowlisted("10.1.2.3", ["bad", "10.0.0.0/8"]) is True
    assert admin_module._display_country({"country_code": "US"}) == "US"
    assert admin_module._display_country({"country_code": "XX", "country_name": "Unknown"}) == "Unknown"
    monkeypatch.setattr(admin_module, "geo_enrich", lambda _ip: {"country_code": "XX", "country_name": "Unknown"})
    enriched = admin_module._enrichment_for_ip("8.8.8.8", "US", "United States")
    assert enriched["country_code"] == "US"
    assert enriched["country_name"] == "United States"
    assert admin_module._to_bool(True) is True
    assert admin_module._to_bool(1) is True
    assert admin_module._to_bool("yes") is True
    assert admin_module._to_bool("off") is False
    assert admin_module._to_bool("") is False
    assert admin_module._is_noise_text("") is False
    assert admin_module._is_noise_text("cloudsentinel.internal") is True
    assert admin_module._is_noise_text("[redacted]") is True
    assert admin_module._derive_response_mode("x", "command_registry", "", "") == "command_registry"
    assert admin_module._derive_response_mode("x", "blocked", "", "") == "blocked"
    assert admin_module._derive_response_mode("x", "", "command not found", "") == "blocked"
    assert admin_module._derive_response_mode("x", "", "", "ps aux") == "templated"
    assert admin_module._derive_response_mode("x", "", "", "ls") == "deterministic"
    assert admin_module._event_sort_priority("cloudsentinel.command.input") == 0
    assert admin_module._event_sort_priority("cloudsentinel.command.output") == 1
    assert admin_module._event_sort_priority("other") == 2
