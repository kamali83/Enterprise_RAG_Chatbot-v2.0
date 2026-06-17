"""
Middleware for rate limiting, CORS, and monitoring
"""
from fastapi import Request, HTTPException
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.logging import get_logger
import time
import uuid

logger = get_logger(__name__)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Middleware to disable caching for specific paths."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/frontend") or request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests with correlation IDs."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID for request tracing
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        # Log request
        start_time = time.time()
        logger.info(
            f"Incoming request",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": get_remote_address(request),
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"Request completed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            }
        )
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to expose Prometheus metrics."""
    
    async def dispatch(self, request: Request, call_next):
        from prometheus_client import Counter, Histogram, Gauge
        import time
        
        # Define metrics
        REQUEST_COUNT = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'path', 'status']
        )
        
        REQUEST_DURATION = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'path']
        )
        
        REQUESTS_IN_PROGRESS = Gauge(
            'http_requests_in_progress',
            'Number of HTTP requests currently being processed'
        )
        
        # Track request
        start_time = time.time()
        REQUESTS_IN_PROGRESS.inc()
        
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as e:
            status = 500
            raise
        finally:
            duration = time.time() - start_time
            REQUESTS_IN_PROGRESS.dec()
            REQUEST_COUNT.labels(
                method=request.method,
                path=request.url.path,
                status=status
            ).inc()
            REQUEST_DURATION.labels(
                method=request.method,
                path=request.url.path
            ).observe(duration)
        
        return response


def setup_middleware(app):
    """Setup all middleware for the application."""
    from fastapi.middleware.cors import CORSMiddleware
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Rate limiting exception handler
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Custom middleware
    app.add_middleware(NoCacheMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    if settings.PROMETHEUS_ENABLED:
        app.add_middleware(PrometheusMetricsMiddleware)
    
    logger.info("Middleware setup complete")
