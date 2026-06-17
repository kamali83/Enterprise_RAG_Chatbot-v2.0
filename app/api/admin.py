"""
Admin API routes for audit logs and user management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.api.auth import get_current_user
from app.models.schemas import AuditLogResponse, UserResponse
from app.models.db_models import User as UserDB
from app.services.audit_service import AuditLogService, get_audit_log_service, AuditAction
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


async def get_admin_user(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> UserResponse:
    """Verify user is an admin."""
    from sqlalchemy import select
    
    result = await db.execute(select(UserDB).where(UserDB.id == current_user.id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return current_user


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    admin_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Get audit logs (admin only)."""
    audit_service = AuditLogService(db)
    
    if action:
        logs = await audit_service.get_action_history(action, limit=limit)
    elif user_id:
        logs = await audit_service.get_user_audit_trail(user_id, limit=limit, offset=offset)
    else:
        logs = await audit_service.get_recent_activity(limit=limit)
    
    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            timestamp=log.timestamp,
        )
        for log in logs
    ]


@router.get("/users")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    admin_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List all users (admin only)."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(UserDB).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at,
        }
        for user in users
    ]


@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    admin_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Toggle user active status (admin only)."""
    from sqlalchemy import select
    
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    await db.commit()
    
    # Log the action
    audit_service = AuditLogService(db)
    await audit_service.log_action(
        user_id=admin_user.id,
        action=AuditAction.ADMIN_ACCESS,
        resource_type="user",
        resource_id=user_id,
        details={"action": "toggle_active", "new_status": user.is_active},
    )
    
    return {"msg": f"User {user.username} is now {'active' if user.is_active else 'inactive'}"}


@router.put("/users/{user_id}/toggle-admin")
async def toggle_user_admin(
    user_id: int,
    admin_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Toggle user admin status (admin only)."""
    from sqlalchemy import select
    
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin status")
    
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_admin = not user.is_admin
    await db.commit()
    
    # Log the action
    audit_service = AuditLogService(db)
    await audit_service.log_action(
        user_id=admin_user.id,
        action=AuditAction.ADMIN_ACCESS,
        resource_type="user",
        resource_id=user_id,
        details={"action": "toggle_admin", "new_status": user.is_admin},
    )
    
    return {"msg": f"User {user.username} is now {'an admin' if user.is_admin else 'a regular user'}"}


@router.get("/stats/overview")
async def get_system_overview(
    admin_user: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Get system overview statistics (admin only)."""
    from sqlalchemy import func, select
    from app.models.db_models import Conversation, Message, Document
    
    # Get counts
    user_count = await db.execute(select(func.count(UserDB.id)))
    conversation_count = await db.execute(select(func.count(Conversation.id)))
    message_count = await db.execute(select(func.count(Message.id)))
    document_count = await db.execute(select(func.count(Document.id)))
    
    return {
        "total_users": user_count.scalar(),
        "total_conversations": conversation_count.scalar(),
        "total_messages": message_count.scalar(),
        "total_documents": document_count.scalar(),
    }
