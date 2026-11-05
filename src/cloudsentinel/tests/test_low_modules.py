"""Cover low-coverage utility modules and optional dependency fallbacks."""

from __future__ import annotations

import asyncio
import builtins
import json
import sys
import types
from pathlib import Path

import pytest

import cloudsentinel.attack_graph as attack_graph_module
import cloudsentinel.geoip as geoip
import cloudsentinel.metrics as metrics_module
from cloudsentinel.attack_graph import AttackGraph
from cloudsentinel.config import ObservabilitySettings


def test_metrics_prometheus_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    path = Path(metrics_module.__file__)
    source = path.read_text(encoding="utf-8")
    code = compile(source, str(path), "exec")
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "prometheus_client" or name.startswith("prometheus_client."):
            raise ModuleNotFoundError(name)
        return real_import(name, globals, locals, fromlist, level)

    namespace: dict = {"__name__": "cloudsentinel.metrics_fallback", "__file__": str(path)}
    monkeypatch.setattr(builtins, "__import__", fake_import)
    exec(code, namespace)
    monkeypatch.undo()

    namespace["uptime_seconds"].set_function(lambda: 3.0)
    payload = namespace["generate_latest"](namespace["_registry"])
    assert b"cloudsentinel_uptime_seconds" in payload
    fallback_metrics = namespace["Metrics"]()
    fallback_metrics.record_connect()
    fallback_metrics.record_auth_fail()
    fallback_metrics.record_command()
    fallback_metrics.record_block("blocked")
    fallback_metrics.record_event("unit")
    fallback_metrics.set_mttb(12.0)
    fallback_metrics.set_blocked_count(1)
    fallback_metrics.set_pipeline_status(True, 2)
    assert fallback_metrics.render()
    assert fallback_metrics.content_type


def test_honeyfs_seed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from cloudsentinel.honeyfs_seed import is_text_content, main, seed_honeyfs

    assert is_text_content(b"hello") is True
    assert is_text_content(b"\xff\xfe") is False

    output = tmp_path / "honeyfs"
    (output / "etc").mkdir(parents=True)
    (output / "etc" / "stale").write_text("old")
    (output / "custom").mkdir()
    count = seed_honeyfs(output)
    assert count > 0
    assert (output / "custom").exists()

    monkeypatch.setattr(sys, "argv", ["honeyfs_seed", "--output", str(tmp_path / "out2")])
    main()


def test_geoip_enrichment(monkeypatch: pytest.MonkeyPatch) -> None:
    geoip._geoip_http_cache.clear()
    assert geoip.is_public_ip("8.8.8.8") is True
    assert geoip.is_public_ip("10.0.0.1") is False
    assert geoip.is_public_ip("not-an-ip") is False
    assert geoip._enrich_fallback("10.0.0.1")["country_code"] == "PV"
    assert geoip._enrich_fallback("not-an-ip")["country_code"] == "XX"

    payload = {
        "success": True,
        "country_code": "us",
        "country": "United States",
        "city": "Ashburn",
        "region": "Virginia",
        "continent_code": "NA",
        "latitude": 39.0,
        "longitude": -77.5,
        "timezone": {"id": "America/New_York"},
        "connection": {"asn": 1, "isp": "ISP", "org": "ORG", "type": "hosting"},
    }

    class FakeResponse:
        def __init__(self, body: dict) -> None:
            self.body = body

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

        def read(self) -> bytes:
            return json.dumps(self.body).encode()

    monkeypatch.setattr(geoip.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    enriched = geoip._enrich_http("8.8.8.8")
    assert enriched is not None
    assert enriched["country_code"] == "US"
    assert geoip._enrich_http("8.8.8.8") is enriched
    assert geoip._enrich_http("10.0.0.1") is None

    monkeypatch.setattr(
        geoip.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse({"success": False}),
    )
    geoip._geoip_http_cache.clear()
    assert geoip._enrich_http("8.8.4.4") is None

    class Country:
        iso_code = "US"
        name = "United States"

    class City:
        name = "Ashburn"

    class Continent:
        code = "NA"

    class Location:
        latitude = 39.0
        longitude = -77.5
        time_zone = "UTC"

    class CityResponse:
        country = Country()
        city = City()
        continent = Continent()
        location = Location()

    class FakeReader:
        def city(self, _ip: str) -> CityResponse:
            return CityResponse()

    monkeypatch.setattr(geoip, "_get_reader", lambda: FakeReader())
    monkeypatch.setattr(geoip, "_enrich_http", lambda _ip: None)
    assert geoip.enrich("8.8.8.8")["country_code"] == "US"
    assert geoip.enrich("10.0.0.1")["country_code"] == "PV"

    class BrokenReader:
        def city(self, _ip: str) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(geoip, "_get_reader", lambda: BrokenReader())
    assert geoip.enrich("8.8.8.8")["country_code"] == "XX"

    monkeypatch.setattr(geoip, "_get_reader", lambda: None)
    monkeypatch.setattr(geoip, "enrich", lambda _ip: {"country_code": "OK"})
    assert asyncio.run(geoip.enrich_async("8.8.8.8"))["country_code"] == "OK"


def test_attack_graph_full(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    prune_graph = AttackGraph(max_nodes=1, prune_after_seconds=-1)
    prune_graph.add_event({"src_ip": "1.1.1.1", "session": "p"})
    prune_graph.add_event({"src_ip": "2.2.2.2", "session": "p"})
    assert prune_graph.get_stats()["total_nodes"] <= 1

    graph = AttackGraph(max_nodes=100)
    graph.add_event(
        {
            "src_ip": "1.2.3.4",
            "session": "s1",
            "eventid": "cloudsentinel.login.failed",
            "username": "root",
            "password": "toor",
        }
    )
    graph.add_event(
        {
            "src_ip": "1.2.3.4",
            "session": "s2",
            "hassh_md5": "a" * 32,
            "eventid": "cloudsentinel.command.input",
            "input": "ssh root@5.6.7.8",
            "cloudsentinel_mitre_techniques": ["T1021.004"],
        }
    )
    graph.add_event(
        {
            "src_ip": "1.2.3.4",
            "session": "s3",
            "eventid": "cloudsentinel.command.input",
            "input": "scp file 9.9.9.9:/tmp",
            "cloudsentinel_mitre_techniques": ["T1021.004"],
        }
    )
    for command in ("nc 9.9.9.10 22", "ncat 9.9.9.11 22", "socat tcp:9.9.9.12:22"):
        graph.add_event(
            {
                "src_ip": "1.2.3.4",
                "session": "s4",
                "eventid": "cloudsentinel.command.input",
                "input": command,
            }
        )
    graph.add_event(
        {
            "src_ip": "1.2.3.4",
            "session": "s5",
            "eventid": "cloudsentinel.login.failed",
            "username": "root",
        }
    )
    graph.add_event(
        {
            "src_ip": "8.8.8.8",
            "session": "s6",
            "eventid": "cloudsentinel.command.input",
            "input": "ssh root@1.2.3.4",
        }
    )

    assert graph.get_stats()["lateral_moves"] >= 5
    assert graph.compute_centrality()
    assert graph.detect_communities() is not None
    assert graph.find_pivot_points(min_degree=1)
    assert graph.shortest_attack_path("1.2.3.4", "5.6.7.8") is not None
    graph.save(str(tmp_path / "graph.json"))
    assert (tmp_path / "graph.json").exists()

    fallback = AttackGraph()
    fallback.add_event({"src_ip": "1.2.3.4", "session": "s", "eventid": "cloudsentinel.command.input"})
    monkeypatch.setitem(sys.modules, "networkx", None)
    assert fallback.compute_centrality()
    assert fallback.detect_communities() == []
    assert fallback.find_pivot_points() == []
    assert fallback.shortest_attack_path("1.2.3.4", "8.8.8.8") is None


def test_observability_enabled_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from cloudsentinel import observability

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    observability.setup_sentry()
    fake_pyro = types.ModuleType("pyroscope")

    def fail_configure(**_kwargs: object) -> None:
        raise RuntimeError("pyro down")

    fake_pyro.configure = fail_configure
    monkeypatch.setitem(sys.modules, "pyroscope", fake_pyro)
    observability.setup_pyroscope("unit")

    assert observability.setup_observability(ObservabilitySettings(enabled=False))

    def add_module(name: str) -> types.ModuleType:
        module = types.ModuleType(name)
        monkeypatch.setitem(sys.modules, name, module)
        if "." in name:
            parent_name, _, child = name.rpartition(".")
            parent = sys.modules.get(parent_name)
            if parent is not None:
                setattr(parent, child, module)
        return module

    otel = add_module("opentelemetry")
    trace = add_module("opentelemetry.trace")
    otel.trace = trace
    trace.set_tracer_provider = lambda _provider: None
    trace.get_tracer = lambda _name: "tracer"

    exporter = add_module("opentelemetry.exporter")
    otlp = add_module("opentelemetry.exporter.otlp")
    proto = add_module("opentelemetry.exporter.otlp.proto")
    http = add_module("opentelemetry.exporter.otlp.proto.http")
    exporter.otlp = otlp
    otlp.proto = proto
    proto.http = http
    trace_exporter = add_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    http.trace_exporter = trace_exporter
    trace_exporter.OTLPSpanExporter = lambda **_kwargs: "otlp"

    sdk = add_module("opentelemetry.sdk")
    resources = add_module("opentelemetry.sdk.resources")
    sdk.resources = resources
    resources.Resource = type("Resource", (), {"create": staticmethod(lambda _attrs: "resource")})

    sdk_trace = add_module("opentelemetry.sdk.trace")
    sdk.trace = sdk_trace
    sdk_trace.TracerProvider = type(
        "TracerProvider",
        (),
        {
            "__init__": lambda self, **_kwargs: None,
            "add_span_processor": lambda self, _processor: None,
        },
    )
    sdk_export = add_module("opentelemetry.sdk.trace.export")
    sdk_trace.export = sdk_export
    sdk_export.BatchSpanProcessor = lambda exporter: exporter
    sdk_export.ConsoleSpanExporter = lambda: "console"

    instrumentation = add_module("opentelemetry.instrumentation")
    sdk.instrumentation = instrumentation
    redis_instr = add_module("opentelemetry.instrumentation.redis")
    instrumentation.redis = redis_instr
    redis_instr.RedisInstrumentor = type(
        "RedisInstrumentor", (), {"instrument": lambda self: None}
    )
    aiohttp_instr = add_module("opentelemetry.instrumentation.aiohttp_client")
    instrumentation.aiohttp_client = aiohttp_instr
    aiohttp_instr.AioHttpClientInstrumentor = type(
        "AioHttpClientInstrumentor", (), {"instrument": lambda self: None}
    )

    settings = ObservabilitySettings(
        enabled=True,
        service_name="unit",
        otlp_endpoint="http://collector:4318",
        console_exporter=True,
    )
    assert observability.setup_observability(settings) == "tracer"
    assert observability.get_tracer() == "tracer"
