"""
Conversations API routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.api.auth import get_current_user
from app.models.schemas import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)
from app.models.db_models import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.dependencies import (
    get_conversation_repository,
    get_message_repository,
)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """Create a new conversation."""
    conversation = await conv_repo.create({
        "user_id": current_user.id,
        "name": conversation_data.name,
    })
    return conversation


@router.get("", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Get all conversations for the current user."""
    conversations = await conv_repo.get_by_user(current_user.id, skip=skip, limit=limit)
    return conversations


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """Get a specific conversation."""
    conversation = await conv_repo.get_by_user_and_id(current_user.id, conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def rename_conversation(
    conversation_id: int,
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """Rename a conversation."""
    conversation = await conv_repo.get_by_user_and_id(current_user.id, conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    updated = await conv_repo.update(conversation_id, {"name": conversation_data.name})
    return updated


@router.delete("/{conversation_id}", status_code=200)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """Delete a conversation."""
    success = await conv_repo.delete_by_user_and_id(current_user.id, conversation_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"message": "Conversation deleted successfully"}


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def add_message(
    conversation_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    msg_repo: MessageRepository = Depends(get_message_repository),
):
    """Add a message to a conversation."""
    # Verify conversation ownership
    conversation = await conv_repo.get_by_user_and_id(current_user.id, conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    message = await msg_repo.create({
        "conversation_id": conversation_id,
        "sender": message_data.sender,
        "content": message_data.content,
    })

    return message


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    msg_repo: MessageRepository = Depends(get_message_repository),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """Get all messages in a conversation."""
    # Verify conversation ownership
    conversation = await conv_repo.get_by_user_and_id(current_user.id, conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await msg_repo.get_by_conversation(conversation_id, skip=skip, limit=limit)
    return messages
