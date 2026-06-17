"""
Base repository with common CRUD operations
"""
from typing import Generic, Type, TypeVar, Optional, List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class RepositoryBase(Generic[ModelType]):
    """Base repository with generic CRUD operations."""
    
    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db
    
    async def get(self, id: int) -> Optional[ModelType]:
        """Get a single record by ID."""
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> List[ModelType]:
        """Get multiple records with pagination."""
        query = select(self.model).offset(skip).limit(limit)
        
        if order_by and hasattr(self.model, order_by):
            column = getattr(self.model, order_by)
            query = query.order_by(column.desc() if desc else column.asc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new record."""
        # Filter out None values
        clean_obj_in = {k: v for k, v in obj_in.items() if v is not None}
        
        try:
            db_obj = self.model(**clean_obj_in)
            self.db.add(db_obj)
            await self.db.commit()
            await self.db.refresh(db_obj)
            return db_obj
        except Exception as e:
            import traceback
            print(f"REPOSITORY CREATE ERROR: {e}")
            print(f"Model: {self.model}")
            print(f"Data: {clean_obj_in}")
            print("TRACEBACK:")
            print(traceback.format_exc())
            await self.db.rollback()
            raise e
    
    async def update(self, id: int, obj_in: Dict[str, Any]) -> Optional[ModelType]:
        """Update a record by ID."""
        obj = await self.get(id)
        if obj:
            for field, value in obj_in.items():
                setattr(obj, field, value)
            await self.db.commit()
            await self.db.refresh(obj)
        return obj
    
    async def delete(self, id: int) -> bool:
        """Delete a record by ID."""
        obj = await self.get(id)
        if obj:
            await self.db.delete(obj)
            await self.db.commit()
            return True
        return False
    
    async def count(self) -> int:
        """Count total records."""
        result = await self.db.execute(select(func.count()).select_from(self.model))
        return result.scalar()
