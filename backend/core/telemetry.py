"""
core/telemetry.py
OpenTelemetry tracing setup — bootstraps SDK, instruments FastAPI,
and exports spans to Jaeger via OTLP/gRPC.

Falls back gracefully if OTLP endpoint is unreachable (no-op tracer).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_OTLP_ENDPOINT = os.environ.get("OTLP_ENDPOINT", "")  # e.g. grpc://jaeger:4317
_OTEL_ENABLED = bool(_OTLP_ENDPOINT)


def setup_telemetry(app, service_name: str = "log-analyzer-backend") -> None:
    """
    Instruments a FastAPI app with OpenTelemetry tracing.
    Exports to Jaeger via OTLP/gRPC when OTLP_ENDPOINT env-var is set.
    When the env-var is absent the function is a no-op (zero overhead).
    """
    if not _OTEL_ENABLED:
        logger.info(
            "OpenTelemetry disabled — set OTLP_ENDPOINT to enable",
            extra={"event": "otel_disabled"},
        )
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(endpoint=_OTLP_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI request/response spans
        FastAPIInstrumentor.instrument_app(app)

        # Auto-instrument all httpx calls (Ollama client)
        HTTPXClientInstrumentor().instrument()

        logger.info(
            "OpenTelemetry tracing enabled",
            extra={"event": "otel_enabled", "endpoint": _OTLP_ENDPOINT, "service": service_name},
        )

    except Exception as exc:  # pragma: no cover
        logger.warning(
            "OpenTelemetry setup failed — tracing disabled",
            extra={"event": "otel_error", "error": str(exc)},
        )


def get_tracer(name: str = "log-analyzer"):
    """Returns an OTel tracer. Safe to call even when tracing is disabled."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except Exception:
        return _NoopTracer()


class _NoopTracer:
    """Minimal no-op tracer used when OTel is not initialised."""

    def start_as_current_span(self, name, **_):  # noqa: ANN001
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield _NoopSpan()

        return _cm()


class _NoopSpan:
    def set_attribute(self, *_):
        pass

    def record_exception(self, *_):
        pass

    def set_status(self, *_):
        pass
