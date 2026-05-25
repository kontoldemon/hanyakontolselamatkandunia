"""CloudSentinel Observability — structlog, loguru, sentry, OpenTelemetry."""

from __future__ import annotations

import logging
import os
from contextlib import nullcontext
from typing import Any

from .config import ObservabilitySettings

logger = logging.getLogger("cloudsentinel.observability")


def setup_loguru() -> None:
    """Replace standard logging with loguru if available."""
    try:
        from loguru import logger as loguru_logger
        import sys

        loguru_logger.remove()
        loguru_logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            level="INFO",
            colorize=True,
        )
        loguru_logger.add(
            "var/log/cloudsentinel/sensor.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            rotation="10 MB",
            retention="7 days",
            compression="gz",
            level="DEBUG",
        )
        logger.info("loguru initialized — structured file logging with rotation")
    except ImportError:
        logger.debug("loguru not installed — using standard logging")


def setup_structlog() -> Any:
    """Initialize structlog for JSON-structured logging."""
    try:
        import structlog

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
                structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        logger.info("structlog initialized — JSON structured logging")
        return structlog.get_logger()
    except ImportError:
        logger.debug("structlog not installed")
        return None


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


def setup_observability(settings: ObservabilitySettings) -> Any:
    """Initialize all observability backends."""
    setup_loguru()
    setup_structlog()
    setup_sentry()

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
    return trace.get_tracer(settings.service_name)


def get_tracer() -> Any:
    try:
        from opentelemetry import trace
        return trace.get_tracer("cloudsentinel")
    except Exception:
        return nullcontext()
