"""
Message repository for database operations
"""
from typing import List, Optional
from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db_models import Message
from app.repositories.base import RepositoryBase


class MessageRepository(RepositoryBase[Message]):
    """Repository for Message model operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Message, db)
    
    async def get_by_conversation(
        self,
        conversation_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Message]:
        """Get all messages for a conversation."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(asc(Message.timestamp))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_last_message(self, conversation_id: int) -> Optional[Message]:
        """Get the last message in a conversation."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.timestamp))
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def count_by_conversation(self, conversation_id: int) -> int:
        """Count messages in a conversation."""
        from sqlalchemy import func
        result = await self.db.execute(
            select(func.count()).where(Message.conversation_id == conversation_id)
        )
        return result.scalar()
