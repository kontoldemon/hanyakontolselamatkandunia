"""Cover observability paths when optional backends are absent."""

from __future__ import annotations

import sys

import pytest

from cloudsentinel import observability
from cloudsentinel.config import ObservabilitySettings


def test_observability_missing_optional_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)
    observability.setup_sentry("dsn")

    monkeypatch.setitem(sys.modules, "pyroscope", None)
    observability.setup_pyroscope("unit")

    settings = ObservabilitySettings(enabled=True, service_name="unit")
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    assert observability.setup_observability(settings) is not None
    assert observability.get_tracer() is not None
