"""API module initialization"""
from fastapi import APIRouter
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.rag import router as rag_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(conversations_router)
api_router.include_router(rag_router)
api_router.include_router(documents_router)
api_router.include_router(health_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
