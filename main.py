"""
Main FastAPI Application
Enterprise RAG Chatbot v2.0
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db
from app.core.middleware import setup_middleware
from app.core.telemetry import setup_opentelemetry
from app.services.cache_service import cache_service
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service
from app.api import api_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Enterprise RAG Chatbot")
    
    # Setup logging
    setup_logging()
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Connect to Redis
    await cache_service.connect()
    
    # Initialize LLM service
    llm_service.initialize()
    
    # Initialize RAG service
    rag_service.initialize()
    
    # Setup OpenTelemetry
    setup_opentelemetry(app)
    
    logger.info(f"Application started successfully on port 8000")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await cache_service.disconnect()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise RAG-powered AI chatbot for intelligent document Q&A",
    lifespan=lifespan,
)

# Setup middleware
setup_middleware(app)

# Include API routes
app.include_router(api_router)

# Mount frontend
if os.path.exists("frontend"):
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/")
async def root():
    """Root endpoint - serves the frontend."""
    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")
    return {"message": "Enterprise RAG Chatbot API", "version": settings.APP_VERSION}


# Exception handlers
@app.exception_handler(500)
async def internal_server_error(request: Request, exc):
    logger.error(f"Internal server error: {exc}")
    return {"detail": "Internal server error"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
