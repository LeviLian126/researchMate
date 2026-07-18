from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from fastapi import FastAPI

from researchmate_api.config import Settings


LOGGER = logging.getLogger("researchmate")


@dataclass
class ObservabilityRuntime:
    """Owns exporter lifecycle without making telemetry a business dependency."""

    tracer_provider: Any | None = None
    langfuse_client: Any | None = None

    def shutdown(self) -> None:
        if self.langfuse_client is not None:
            try:
                self.langfuse_client.flush()
            except Exception:  # pragma: no cover - exporter failures must not break shutdown
                LOGGER.exception("langfuse_flush_failed")
        if self.tracer_provider is not None:
            try:
                self.tracer_provider.shutdown()
            except Exception:  # pragma: no cover - exporter failures must not break shutdown
                LOGGER.exception("otel_shutdown_failed")


def configure_structured_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper()), format="%(message)s")


def log_event(event: str, **fields: Any) -> None:
    """Emit a bounded JSON event. Callers must never pass prompts, tokens, or document text."""

    LOGGER.info(json.dumps({"event": event, **fields}, separators=(",", ":"), default=str))


def configure_observability(app: FastAPI, settings: Settings) -> ObservabilityRuntime:
    runtime = ObservabilityRuntime()
    configure_structured_logging(settings.log_level)

    if settings.otel_enabled:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError as exc:  # fail closed when an operator explicitly enables tracing
            raise RuntimeError("OTEL_ENABLED requires the pinned OpenTelemetry packages") from exc

        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": settings.otel_service_name,
                    "deployment.environment.name": settings.app_env,
                }
            )
        )
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_traces_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        runtime.tracer_provider = provider

    if settings.langfuse_enabled:
        try:
            from langfuse import get_client
        except ImportError as exc:
            raise RuntimeError("LANGFUSE_ENABLED requires langfuse>=4,<5") from exc
        runtime.langfuse_client = get_client()

    app.state.observability = runtime
    return runtime


class _NoopObservation:
    def update(self, **_: Any) -> None:
        return None


@contextmanager
def provider_observation(
    settings: Settings,
    *,
    name: str,
    observation_type: str,
    model: str,
    metadata: dict[str, Any],
) -> Iterator[Any]:
    """Create a privacy-safe provider observation or a deterministic no-op locally."""

    if not settings.langfuse_enabled:
        yield _NoopObservation()
        return
    try:
        from langfuse import get_client

        client = get_client()
        manager = client.start_as_current_observation(
            name=name,
            as_type=observation_type,
            model=model,
            metadata=metadata,
        )
    except Exception:
        # An unavailable exporter is not allowed to block provider work.
        LOGGER.exception("provider_observation_failed")
        yield _NoopObservation()
        return
    # Exceptions from the provider call must propagate to its normal retry/error mapper.
    with manager as observation:
        yield observation
