"""
RAG (Question & Answer) API routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
import asyncio
import json
from app.api.auth import get_current_user
from app.models.schemas import QueryRequest, QueryResponse, SourceDocument
from app.models.db_models import User
from app.services.rag_service import get_rag_service, RAGService
from app.services.cache_service import get_cache_service, CacheService
from app.core.logging import get_logger
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.dependencies import (
    get_conversation_repository,
    get_message_repository,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["RAG"])


@router.get("/ask", response_model=QueryResponse)
async def ask_question(
    query: str,
    conversation_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
    cache_service: CacheService = Depends(get_cache_service),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
    msg_repo: MessageRepository = Depends(get_message_repository),
):
    """
    Ask a question and get an AI-powered answer based on uploaded documents.
    """
    # Check cache first
    cached_response = await cache_service.get_query_response(query, current_user.id)
    if cached_response:
        logger.info(f"Cache hit for query: {query[:50]}...")
        return QueryResponse(**cached_response)
    
    # Verify conversation if provided
    if conversation_id:
        conv = await conv_repo.get_by_user_and_id(current_user.id, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    
    try:
        # Perform RAG query
        result = await rag_service.query(query, use_reranking=False)
        
        # Save to conversation if conversation_id provided
        message_id = None
        if conversation_id and result["answer"]:
            # Save user question
            try:
                user_msg = await msg_repo.create({
                    "conversation_id": conversation_id,
                    "sender": "user",
                    "content": query,
                })
            except Exception as e:
                import traceback
                print(f"Could not save user message: {e}")
                print(traceback.format_exc())
            
            # Save bot answer
            try:
                bot_msg_data = {
                    "conversation_id": conversation_id,
                    "sender": "bot",
                    "content": result["answer"],
                }
                # Only add extra_data if sources exist
                if result.get("sources"):
                    import json
                    bot_msg_data["extra_data"] = json.dumps({"sources": result["sources"]})
                
                bot_msg = await msg_repo.create(bot_msg_data)
                message_id = bot_msg.id
            except Exception as e:
                import traceback
                print(f"Could not save bot message: {e}")
                print(traceback.format_exc())
        
        response = QueryResponse(
            answer=result["answer"],
            sources=[SourceDocument(**s) for s in result.get("sources", [])],
            conversation_id=conversation_id,
            message_id=message_id,
        )
        
        # Cache the response
        await cache_service.set_query_response(
            query,
            current_user.id,
            {
                "answer": result["answer"],
                "sources": result.get("sources", []),
            }
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Failed to process query")


@router.get("/ask_stream")
async def ask_question_stream(
    query: str,
    conversation_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
    conv_repo: ConversationRepository = Depends(get_conversation_repository),
):
    """
    Ask a question with streaming response (Server-Sent Events).
    """
    # Verify conversation if provided
    if conversation_id:
        conv = await conv_repo.get_by_user_and_id(current_user.id, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Retrieve documents
    docs = rag_service.retrieve(query)
    
    if not docs:
        async def no_context_stream():
            yield "data: I don't have enough information to answer that question.\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            no_context_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"}
        )
    
    # Build context
    context = "\n\n".join([doc.page_content for doc in docs])
    
    async def generate_stream():
        try:
            async for token in rag_service.generate_answer_stream(query, context):
                yield f"data: {token}\n\n"
                await asyncio.sleep(0.02)  # Small delay for better streaming experience
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: [ERROR]\n\n"
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/sources")
async def get_sources(
    current_user: User = Depends(get_current_user),
    rag_service: RAGService = Depends(get_rag_service),
):
    """Get list of all document sources in the knowledge base."""
    sources = rag_service.get_document_sources()
    return {"sources": sources}
