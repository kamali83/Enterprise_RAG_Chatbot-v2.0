"""
Repository dependencies for FastAPI
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.repositories.user_repository import UserRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository


def get_user_repository(db: AsyncSession = Depends(get_async_db)) -> UserRepository:
    """Get user repository instance."""
    return UserRepository(db)


def get_conversation_repository(
    db: AsyncSession = Depends(get_async_db)
) -> ConversationRepository:
    """Get conversation repository instance."""
    return ConversationRepository(db)


def get_message_repository(db: AsyncSession = Depends(get_async_db)) -> MessageRepository:
    """Get message repository instance."""
    return MessageRepository(db)
