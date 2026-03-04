"""OpenTelemetry setup for traces, metrics, and log correlation."""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


class GatewayMetrics:
    """Application-level metrics for the LLM Gateway."""

    def __init__(self, meter: metrics.Meter) -> None:
        self.request_counter = meter.create_counter(
            "llm_gateway.requests",
            description="Total LLM requests",
            unit="1",
        )
        self.tokens_in_counter = meter.create_counter(
            "llm_gateway.tokens_in",
            description="Total input tokens",
            unit="tokens",
        )
        self.tokens_out_counter = meter.create_counter(
            "llm_gateway.tokens_out",
            description="Total output tokens",
            unit="tokens",
        )
        self.cost_counter = meter.create_counter(
            "llm_gateway.cost",
            description="Estimated cost in USD",
            unit="usd",
        )
        self.latency_histogram = meter.create_histogram(
            "llm_gateway.latency",
            description="Request latency in milliseconds",
            unit="ms",
        )
        self.routing_counter = meter.create_counter(
            "llm_gateway.routing_decisions",
            description="Routing decisions by strategy",
            unit="1",
        )

    def record_request(
        self,
        agent: str,
        pseudo_model: str,
        provider: str,
        model: str,
        strategy: str,
        tokens_in: int,
        tokens_out: int,
        cost: float,
        latency_ms: float,
    ) -> None:
        labels = {
            "agent": agent,
            "pseudo_model": pseudo_model,
            "provider": provider,
            "model": model,
        }
        self.request_counter.add(1, labels)
        self.tokens_in_counter.add(tokens_in, labels)
        self.tokens_out_counter.add(tokens_out, labels)
        self.cost_counter.add(cost, labels)
        self.latency_histogram.record(latency_ms, labels)
        self.routing_counter.add(1, {"strategy": strategy, "pseudo_model": pseudo_model})


def setup_telemetry(
    app: Any,
    service_name: str = "llm-gateway",
    otlp_endpoint: str = "http://localhost:4317",
) -> GatewayMetrics:
    """Initialize OpenTelemetry tracing, metrics, and FastAPI instrumentation."""

    resource = Resource.create({"service.name": service_name})

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    try:
        span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    except Exception as e:
        logger.warning("OTLP trace exporter unavailable: %s", e)
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    try:
        metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
        metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=15000)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    except Exception as e:
        logger.warning("OTLP metric exporter unavailable: %s", e)
        meter_provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(meter_provider)

    meter = metrics.get_meter("llm-gateway", "0.1.0")
    gateway_metrics = GatewayMetrics(meter)

    # Instrument FastAPI
    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception as e:
        logger.warning("FastAPI instrumentation failed: %s", e)

    logger.info("Telemetry initialized (endpoint=%s)", otlp_endpoint)
    return gateway_metrics
