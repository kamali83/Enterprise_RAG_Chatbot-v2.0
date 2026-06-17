"""
Conversation repository for database operations
"""
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db_models import Conversation
from app.repositories.base import RepositoryBase


class ConversationRepository(RepositoryBase[Conversation]):
    """Repository for Conversation model operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Conversation, db)
    
    async def get_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Conversation]:
        """Get all conversations for a user."""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_by_user_and_id(self, user_id: int, conv_id: int) -> Optional[Conversation]:
        """Get a specific conversation for a user (ensures ownership)."""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id == conv_id)
            .where(Conversation.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def delete_by_user_and_id(self, user_id: int, conv_id: int) -> bool:
        """Delete a specific conversation for a user (ensures ownership)."""
        conv = await self.get_by_user_and_id(user_id, conv_id)
        if conv:
            await self.db.delete(conv)
            await self.db.commit()
            return True
        return False
