"""
Health check and monitoring API routes
"""
from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from app.core.config import settings
from app.core.logging import get_logger
from app.services.cache_service import get_cache_service, CacheService
from app.services.document_service import get_document_stats
from app.models.schemas import HealthResponse
from sqlalchemy import text
from app.core.database import sync_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    cache_service: CacheService = Depends(get_cache_service),
):
    """Check health status of all services."""
    # Check database
    db_status = "healthy"
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check Redis
    redis_status = "healthy"
    if not await cache_service.health_check():
        redis_status = "unhealthy"
    
    # Check vector store
    import os
    vector_store_status = "healthy" if os.path.exists("faiss_index/index.faiss") else "not_initialized"
    
    # Overall status
    overall_status = "healthy"
    if db_status == "unhealthy" or redis_status == "unhealthy":
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        database=db_status,
        redis=redis_status,
        llm_provider=settings.LLM_PROVIDER,
    )


@router.get("/metrics")
async def metrics():
    """Expose Prometheus metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/stats/documents")
async def document_stats():
    """Get document statistics."""
    return get_document_stats()
