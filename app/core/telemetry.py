"""
OpenTelemetry distributed tracing configuration
"""
from typing import Optional
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def setup_opentelemetry(app=None):
    """
    Setup OpenTelemetry for distributed tracing.
    
    Args:
        app: FastAPI application instance
    """
    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry is disabled")
        return
    
    logger.info("Setting up OpenTelemetry")
    
    # Create resource with service info
    resource = Resource.create({
        "service.name": settings.APP_NAME,
        "service.version": settings.APP_VERSION,
        "deployment.environment": "production" if not settings.DEBUG else "development",
    })
    
    # Set up tracer provider
    tracer_provider = TracerProvider(resource=resource)
    
    # Add OTLP exporter (for Jaeger/Tempo)
    try:
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_ENDPOINT,
            insecure=True,
        )
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        logger.info(f"OTLP exporter configured: {settings.OTEL_EXPORTER_ENDPOINT}")
    except Exception as e:
        logger.error(f"Failed to configure OTLP exporter: {e}")
    
    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)
    
    # Get tracer
    tracer = trace.get_tracer(__name__)
    
    # Instrument FastAPI
    if app:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation enabled")
    
    # Instrument SQLAlchemy
    try:
        SQLAlchemyInstrumentor().instrument()
        logger.info("SQLAlchemy instrumentation enabled")
    except Exception as e:
        logger.error(f"SQLAlchemy instrumentation failed: {e}")
    
    # Instrument Redis
    try:
        RedisInstrumentor().instrument()
        logger.info("Redis instrumentation enabled")
    except Exception as e:
        logger.error(f"Redis instrumentation failed: {e}")
    
    # Instrument HTTP requests
    try:
        RequestsInstrumentor().instrument()
        logger.info("Requests instrumentation enabled")
    except Exception as e:
        logger.error(f"Requests instrumentation failed: {e}")
    
    logger.info("OpenTelemetry setup complete")
    
    return tracer


def get_current_span():
    """Get the current active span."""
    return trace.get_current_span()


def add_span_attribute(key: str, value):
    """Add an attribute to the current span."""
    span = get_current_span()
    if span.is_recording():
        span.set_attribute(key, value)


def add_event(name: str, attributes: Optional[dict] = None):
    """Add an event to the current span."""
    span = get_current_span()
    if span.is_recording():
        span.add_event(name, attributes=attributes)
