"""CloudSentinel Observability — structlog, sentry, OpenTelemetry."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import nullcontext
from typing import Any

from .config import ObservabilitySettings

try:
    import orjson
except ImportError:
    import json as orjson


def setup_structlog() -> Any:
    """Initialize structlog for JSON-structured logging with orjson."""
    try:
        import structlog
        
        # Configure standard logging to redirect to structlog
        logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
        
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(serializer=orjson.dumps),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        return structlog.get_logger()
    except ImportError:
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger()

logger = setup_structlog()

def setup_sentry(dsn: str | None = None) -> None:
    """Initialize Sentry error tracking."""
    dsn = dsn or os.getenv("SENTRY_DSN", "")
    if not dsn:
        return

    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment=os.getenv("CLOUDSENTINEL_ENV", "production"),
            release=os.getenv("CLOUDSENTINEL_VERSION", "2.0.0"),
        )
        logger.info("Sentry initialized — error tracking active")
    except ImportError:
        logger.debug("sentry-sdk not installed")


def setup_pyroscope(service_name: str = "cloudsentinel") -> None:
    """Initialize Pyroscope continuous profiling."""
    try:
        import pyroscope
        pyroscope.configure(
            application_name=service_name,
            server_address=os.getenv("PYROSCOPE_SERVER", "http://localhost:4040"),
            sample_rate=100,
            detect_subprocesses=True,
            oncpu=True,
            native=True,
            report_pid=True,
            tags={"env": os.getenv("CLOUDSENTINEL_ENV", "production")},
        )
        logger.info("Pyroscope continuous profiling enabled")
    except ImportError:
        logger.debug("pyroscope-io not installed")
    except Exception as exc:
        logger.warning("Pyroscope init failed: %s", exc)


def setup_observability(settings: ObservabilitySettings) -> Any:
    """Initialize all observability backends."""
    setup_sentry()
    setup_pyroscope(settings.service_name)

    if not settings.enabled:
        return nullcontext()

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except Exception as exc:
        logger.warning("OpenTelemetry unavailable: %s", exc)
        return nullcontext()

    resource = Resource.create({"service.name": settings.service_name})
    provider = TracerProvider(resource=resource)
    if settings.otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint))
        )
    if settings.console_exporter:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    logger.info("OpenTelemetry enabled")

    # Auto-instrument Redis and aiohttp for zero-code distributed tracing
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
        logger.debug("OTel Redis auto-instrumentation enabled")
    except Exception:
        pass

    try:
        from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
        AioHttpClientInstrumentor().instrument()
        logger.debug("OTel aiohttp-client auto-instrumentation enabled")
    except Exception:
        pass
    return trace.get_tracer(settings.service_name)


def get_tracer() -> Any:
    try:
        from opentelemetry import trace
        return trace.get_tracer("cloudsentinel")
    except Exception:
        return nullcontext()
