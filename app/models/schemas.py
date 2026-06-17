"""
Pydantic schemas for API request/response validation
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============== Authentication Schemas ==============

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int


# ============== Conversation Schemas ==============

class ConversationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class ConversationCreate(ConversationBase):
    pass


class ConversationResponse(ConversationBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============== Message Schemas ==============

class MessageBase(BaseModel):
    content: str = Field(..., min_length=1)
    sender: str = Field(..., pattern="^(user|bot)$")


class MessageCreate(MessageBase):
    conversation_id: Optional[int] = None


class MessageResponse(MessageBase):
    id: int
    conversation_id: int
    timestamp: datetime
    extra_data: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============== RAG Schemas ==============

class SourceDocument(BaseModel):
    filename: str
    page: Optional[int] = None
    content: str
    relevance_score: float = 1.0


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[int] = None
    use_streaming: bool = False


class QueryResponse(BaseModel):
    answer: str
    sources: Optional[List[SourceDocument]] = None
    conversation_id: Optional[int] = None
    message_id: Optional[int] = None


class FeedbackCreate(BaseModel):
    message_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


# ============== Document Schemas ==============

class DocumentBase(BaseModel):
    filename: str
    file_type: str


class DocumentResponse(DocumentBase):
    id: int
    file_size: int
    uploaded_by: int
    uploaded_at: datetime
    is_indexed: bool
    
    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    filename: str
    file_size: int
    status: str
    reindex_status: str


# ============== Admin Schemas ==============

class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    resource_type: Optional[str]
    resource_id: Optional[int]
    ip_address: Optional[str]
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============== Health & Metrics ==============

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
    llm_provider: str
