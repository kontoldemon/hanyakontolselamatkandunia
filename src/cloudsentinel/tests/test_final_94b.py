"""Final config and secret branches to clear 94%."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

import cloudsentinel.config as config
from cloudsentinel._secrets import InfisicalProvider
from cloudsentinel.config import SandboxSettings, SecretStr, load_settings


def test_config_final_branches(monkeypatch, tmp_path) -> None:
    settings = load_settings(
        "src/cloudsentinel/configs/usas-production.yaml",
        "src/cloudsentinel/.env",
    )
    assert isinstance(settings.is_production, bool)
    assert isinstance(settings.is_development, bool)
    assert isinstance(settings.full_telemetry_enabled, bool)
    assert SandboxSettings(cpus=None).cpus == "0.5"

    bad = tmp_path / "bad.yaml"
    bad.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ValueError):
        config._read_yaml(bad)

    monkeypatch.setattr(config, "_SETTINGS_CACHE", None)
    assert config.get_settings() is not None
    assert isinstance(config.get("admin", "token"), str)

    settings.soar.active_profile = "local"
    settings.admin.enabled = True
    settings.admin.token = SecretStr("")
    monkeypatch.setenv("CLOUDSENTINEL_AUTH_ENABLED", "true")
    monkeypatch.setenv("CLOUDSENTINEL_AUTH_SECRET", "")
    with pytest.raises(ValueError):
        config.validate_settings(settings)


def test_infisical_unavailable() -> None:
    provider = InfisicalProvider()
    provider._available = False
    asyncio.run(provider._ensure_authenticated())
