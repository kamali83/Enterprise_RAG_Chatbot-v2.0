"""
Audit logging service for compliance and security tracking
"""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
from app.models.db_models import AuditLog
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuditAction:
    """Standard audit action types."""
    LOGIN = "login"
    LOGOUT = "logout"
    SIGNUP = "signup"
    PASSWORD_CHANGE = "password_change"
    UPLOAD_DOCUMENT = "upload_document"
    DELETE_DOCUMENT = "delete_document"
    REINDEX_DOCUMENTS = "reindex_documents"
    ASK_QUESTION = "ask_question"
    CREATE_CONVERSATION = "create_conversation"
    DELETE_CONVERSATION = "delete_conversation"
    RENAME_CONVERSATION = "rename_conversation"
    EXPORT_DATA = "export_data"
    ADMIN_ACCESS = "admin_access"


class ResourceType:
    """Standard resource types."""
    USER = "user"
    DOCUMENT = "document"
    CONVERSATION = "conversation"
    MESSAGE = "message"
    SYSTEM = "system"


class AuditLogService:
    """Service for creating and querying audit logs."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_action(
        self,
        user_id: int,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ):
        """
        Log an action for audit purposes.
        
        Args:
            user_id: ID of the user performing the action
            action: Type of action (see AuditAction)
            resource_type: Type of resource being acted upon
            resource_id: ID of the resource
            details: Additional details as dict
            ip_address: IP address of the request
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=json.dumps(details) if details else None,
                ip_address=ip_address,
            )
            
            self.db.add(audit_log)
            await self.db.commit()
            
            logger.info(
                f"Audit: {action}",
                extra={
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                }
            )
        
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            await self.db.rollback()
    
    async def get_user_audit_trail(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        """Get audit trail for a specific user."""
        from sqlalchemy import select, desc
        
        query = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.timestamp))
            .offset(offset)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_action_history(
        self,
        action: str,
        limit: int = 100,
    ) -> list:
        """Get all occurrences of a specific action."""
        from sqlalchemy import select, desc
        
        query = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_recent_activity(
        self,
        limit: int = 50,
        user_id: Optional[int] = None,
    ) -> list:
        """Get recent activity across the system."""
        from sqlalchemy import select, desc
        
        query = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_activity_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Get summary of activities by action type."""
        from sqlalchemy import select, func
        
        query = (
            select(AuditLog.action, func.count().label("count"))
            .where(AuditLog.timestamp >= start_date)
            .where(AuditLog.timestamp <= end_date)
            .group_by(AuditLog.action)
        )
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        
        result = await self.db.execute(query)
        return {row.action: row.count for row in result.all()}


def get_audit_log_service(db: AsyncSession) -> AuditLogService:
    """Get audit log service instance."""
    return AuditLogService(db)
