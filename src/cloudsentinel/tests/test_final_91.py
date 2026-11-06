"""Final branches for threat reporter, SOAR memory fallback, and OTel failures."""

from __future__ import annotations

import sys
import types

import pytest

import cloudsentinel.observability as observability
import cloudsentinel.soar as soar_module
import cloudsentinel.threat_reporter as reporter
from cloudsentinel.config import ObservabilitySettings
from cloudsentinel.soar import SOAREngine


@pytest.mark.asyncio
async def test_threat_report_redis_fetch(monkeypatch) -> None:
    async def fake_fetch(_session_id: str, _redis_url: str) -> dict:
        return {
            "attacker_ip": "8.8.8.8",
            "commands": ["id"],
            "risk_score": 50,
            "mitre_techniques": ["T1110"],
            "hassh": "h" * 32,
        }

    async def fake_llm(_prompt: str) -> dict:
        return {"summary": "report", "primary_objective": "test", "confidence": 0.9, "model_used": "mock"}

    monkeypatch.setattr(reporter, "fetch_session_data", fake_fetch)
    monkeypatch.setattr(reporter, "_call_litellm", fake_llm)
    report = await reporter.generate_report("s", redis_url="redis://unit")
    assert report.attacker_ip == "8.8.8.8"
    assert report.commands == ["id"]


@pytest.mark.asyncio
async def test_soar_memory_and_enrichment_errors(monkeypatch) -> None:
    engine = SOAREngine(risk_threshold=1000, firewall_enabled=False)
    assert await engine._get_failed_auth("s") == 0
    assert await engine._incr_failed_auth("s") == 1
    await engine._clear_failed_auth("s")
    engine._update_ip_profile("", "s", 1, set(), 1.0)
    stats = engine.get_session_stats("s")
    assert stats["failed_auth_count"] == 0

    monkeypatch.setattr(soar_module, "_MISP_AVAILABLE", True)
    monkeypatch.setattr(soar_module, "_ABUSEIPDB_AVAILABLE", True)

    def fail_misp() -> None:
        raise RuntimeError("misp down")

    def fail_abuse() -> None:
        raise RuntimeError("abuse down")

    monkeypatch.setattr(soar_module, "_get_misp", fail_misp)
    monkeypatch.setattr(soar_module, "_get_abuseipdb", fail_abuse)
    event = await engine.process_event(
        "s",
        {"eventid": "cloudsentinel.command.input", "src_ip": "8.8.8.8", "input": "id"},
    )
    assert event["cloudsentinel_soar_action"] == "none"


def _module(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    sys.modules[name] = module
    if "." in name:
        parent_name, _, child = name.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None:
            setattr(parent, child, module)
    return module


def test_observability_instrumentation_failures(monkeypatch) -> None:
    otel = _module("opentelemetry")
    trace = _module("opentelemetry.trace")
    otel.trace = trace
    trace.set_tracer_provider = lambda _provider: None
    trace.get_tracer = lambda _name: "tracer"

    exporter = _module("opentelemetry.exporter")
    otlp = _module("opentelemetry.exporter.otlp")
    proto = _module("opentelemetry.exporter.otlp.proto")
    http = _module("opentelemetry.exporter.otlp.proto.http")
    exporter.otlp = otlp
    otlp.proto = proto
    proto.http = http
    trace_exporter = _module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    http.trace_exporter = trace_exporter
    trace_exporter.OTLPSpanExporter = lambda **_kwargs: "otlp"

    sdk = _module("opentelemetry.sdk")
    resources = _module("opentelemetry.sdk.resources")
    sdk.resources = resources
    resources.Resource = type("Resource", (), {"create": staticmethod(lambda _attrs: "resource")})
    sdk_trace = _module("opentelemetry.sdk.trace")
    sdk.trace = sdk_trace
    sdk_trace.TracerProvider = type(
        "TracerProvider",
        (),
        {
            "__init__": lambda self, **_kwargs: None,
            "add_span_processor": lambda self, _processor: None,
        },
    )
    sdk_export = _module("opentelemetry.sdk.trace.export")
    sdk_trace.export = sdk_export
    sdk_export.BatchSpanProcessor = lambda exporter: exporter
    sdk_export.ConsoleSpanExporter = lambda: "console"

    instrumentation = _module("opentelemetry.instrumentation")
    sdk.instrumentation = instrumentation
    redis_instr = _module("opentelemetry.instrumentation.redis")
    instrumentation.redis = redis_instr
    redis_instr.RedisInstrumentor = type(
        "RedisInstrumentor", (), {"instrument": lambda self: (_ for _ in ()).throw(RuntimeError("redis instr"))}
    )
    aiohttp_instr = _module("opentelemetry.instrumentation.aiohttp_client")
    instrumentation.aiohttp_client = aiohttp_instr
    aiohttp_instr.AioHttpClientInstrumentor = type(
        "AioHttpClientInstrumentor", (), {"instrument": lambda self: (_ for _ in ()).throw(RuntimeError("aiohttp instr"))}
    )

    settings = ObservabilitySettings(enabled=True, service_name="unit")
    assert observability.setup_observability(settings) == "tracer"
