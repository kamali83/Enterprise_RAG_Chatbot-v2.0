"""
WebSocket Manager for real-time bidirectional communication

Features:
- Real-time chat with typing indicators
- Cancel generation capability
- Connection management
- Session state tracking
"""
from typing import Dict, List, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.websockets import WebSocketState
import asyncio
import json
from datetime import datetime
from app.core.logging import get_logger
from app.core.config import settings
from app.services.rag_service import get_rag_service
from app.services.feedback_service import get_feedback_service
from app.services.query_understanding import get_query_understanding_pipeline
from app.services.hybrid_retrieval import get_hybrid_retriever

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        # connection_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # user_id -> list of connection_ids
        self.user_connections: Dict[int, List[str]] = {}
        # connection_id -> session data
        self.sessions: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, connection_id: str, user_id: int) -> bool:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket instance
            connection_id: Unique connection identifier
            user_id: User ID

        Returns:
            True if connection successful
        """
        try:
            await websocket.accept()
            self.active_connections[connection_id] = websocket

            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(connection_id)

            # Initialize session
            self.sessions[connection_id] = {
                "user_id": user_id,
                "connected_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "conversation_id": None,
                "message_count": 0,
                "is_generating": False,
                "cancel_requested": False
            }

            logger.info(f"WebSocket connected: {connection_id} (user: {user_id})")

            # Send welcome message
            await self.send_personal_message(
                connection_id,
                {
                    "type": "connection_established",
                    "connection_id": connection_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            return True
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            return False

    def disconnect(self, connection_id: str):
        """
        Disconnect and clean up a connection.

        Args:
            connection_id: Connection to disconnect
        """
        if connection_id not in self.active_connections:
            return

        websocket = self.active_connections[connection_id]
        user_id = self.sessions.get(connection_id, {}).get("user_id")

        # Close WebSocket
        if websocket.client_state == WebSocketState.CONNECTED:
            asyncio.create_task(websocket.close())

        # Remove from active connections
        del self.active_connections[connection_id]

        # Remove from user connections
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].remove(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        # Remove session
        if connection_id in self.sessions:
            del self.sessions[connection_id]

        logger.info(f"WebSocket disconnected: {connection_id}")

    async def send_personal_message(self, connection_id: str, message: Dict[str, Any]):
        """
        Send a message to a specific connection.

        Args:
            connection_id: Target connection
            message: Message dict to send
        """
        if connection_id not in self.active_connections:
            return

        websocket = self.active_connections[connection_id]
        if websocket.client_state != WebSocketState.CONNECTED:
            return

        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            self.disconnect(connection_id)

    async def broadcast_to_user(self, user_id: int, message: Dict[str, Any]):
        """
        Broadcast message to all connections of a user.

        Args:
            user_id: Target user
            message: Message to broadcast
        """
        if user_id not in self.user_connections:
            return

        for connection_id in self.user_connections[user_id]:
            await self.send_personal_message(connection_id, message)

    async def update_session(self, connection_id: str, **kwargs):
        """Update session data for a connection."""
        if connection_id not in self.sessions:
            return

        self.sessions[connection_id].update(kwargs)
        self.sessions[connection_id]["last_activity"] = datetime.utcnow()

    def get_session(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get session data for a connection."""
        return self.sessions.get(connection_id)

    def request_cancel(self, connection_id: str):
        """Request cancellation of ongoing generation."""
        if connection_id in self.sessions:
            self.sessions[connection_id]["cancel_requested"] = True
            logger.info(f"Cancel requested for connection: {connection_id}")

    def get_active_connections_count(self) -> int:
        """Get total active connections."""
        return len(self.active_connections)

    def get_user_connections_count(self, user_id: int) -> int:
        """Get connections count for a user."""
        return len(self.user_connections.get(user_id, []))


# Global connection manager
manager = ConnectionManager()


class WebSocketChatHandler:
    """Handles WebSocket chat interactions."""

    def __init__(self):
        self.rag_service = get_rag_service()
        self.feedback_service = get_feedback_service()
        self.query_pipeline = get_query_understanding_pipeline()
        self.cancel_events: Dict[str, asyncio.Event] = {}

    async def handle_message(
        self,
        connection_id: str,
        message: Dict[str, Any]
    ):
        """
        Handle incoming WebSocket message.

        Args:
            connection_id: Connection ID
            message: Received message dict
        """
        session = manager.get_session(connection_id)
        if not session:
            logger.error(f"Session not found for connection: {connection_id}")
            return

        message_type = message.get("type")

        if message_type == "chat":
            await self.handle_chat_message(connection_id, session, message)
        elif message_type == "cancel":
            await self.handle_cancel(connection_id, session)
        elif message_type == "feedback":
            await self.handle_feedback(connection_id, session, message)
        elif message_type == "set_conversation":
            await self.handle_set_conversation(connection_id, session, message)
        elif message_type == "typing_start":
            await self.handle_typing_indicator(connection_id, session, message)
        elif message_type == "ping":
            await manager.send_personal_message(connection_id, {
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            logger.warning(f"Unknown message type: {message_type}")
            await manager.send_personal_message(connection_id, {
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            })

    async def handle_chat_message(
        self,
        connection_id: str,
        session: Dict[str, Any],
        message: Dict[str, Any]
    ):
        """Handle chat message and generate response."""
        query = message.get("query", "").strip()
        conversation_id = session.get("conversation_id")
        user_id = session.get("user_id")

        if not query:
            await manager.send_personal_message(connection_id, {
                "type": "error",
                "message": "Empty query"
            })
            return

        # Update session
        await manager.update_session(connection_id, is_generating=True, cancel_requested=False)

        # Create cancel event
        cancel_event = asyncio.Event()
        self.cancel_events[connection_id] = cancel_event

        try:
            # Send typing indicator
            await manager.send_personal_message(connection_id, {
                "type": "typing_start",
                "message": "Thinking..."
            })

            # Process query through understanding pipeline
            query_result = await self.query_pipeline.process(
                query,
                use_multi_query=False,
                use_hyde=False,
                rewrite=True
            )

            logger.info(f"Processing query: {query} (type: {query_result['query_type'].value})")

            # Get retrieval strategy from query classification
            retrieval_strategy = query_result.get("retrieval_strategy", {})

            # Retrieve documents using RAG service
            docs = self.rag_service.retrieve(
                query_result["final_query"],
                k=retrieval_strategy.get("k", 5)
            )

            if not docs:
                await manager.send_personal_message(connection_id, {
                    "type": "chat_response",
                    "query": query,
                    "answer": "I don't have enough information to answer that question. Please upload relevant documents.",
                    "sources": [],
                    "metadata": {"retrieved_count": 0}
                })
                return

            # Build context
            context_parts = []
            for i, doc in enumerate(docs):
                filename = doc.metadata.get('filename', 'Unknown')
                header = f"[Source: {filename}]"
                context_parts.append(f"{header}\n{doc.page_content[:500]}")

            context = "\n\n".join(context_parts)

            # Send typing complete
            await manager.send_personal_message(connection_id, {
                "type": "typing_end"
            })

            # Generate and stream response
            await self.stream_response(connection_id, query, context, cancel_event)

            # Update message count
            await manager.update_session(
                connection_id,
                message_count=session.get("message_count", 0) + 1
            )

        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            await manager.send_personal_message(connection_id, {
                "type": "error",
                "message": f"Error processing query: {str(e)}"
            })

        finally:
            await manager.update_session(connection_id, is_generating=False)
            if connection_id in self.cancel_events:
                del self.cancel_events[connection_id]

    async def stream_response(
        self,
        connection_id: str,
        query: str,
        context: str,
        cancel_event: asyncio.Event
    ):
        """Stream response tokens via WebSocket."""
        try:
            full_response = ""
            token_count = 0

            async for token in self.rag_service.generate_answer_stream(query, context):
                # Check for cancellation
                if cancel_event.is_set() or manager.sessions.get(connection_id, {}).get("cancel_requested"):
                    logger.info(f"Response streaming cancelled for {connection_id}")
                    await manager.send_personal_message(connection_id, {
                        "type": "cancelled",
                        "partial_response": full_response
                    })
                    return

                full_response += token
                token_count += 1

                # Send token (batch every 3 tokens for efficiency)
                if token_count % 3 == 0:
                    await manager.send_personal_message(connection_id, {
                        "type": "token",
                        "token": token
                    })
                await asyncio.sleep(0.01)  # Small delay for realistic typing

            # Send complete response
            await manager.send_personal_message(connection_id, {
                "type": "chat_response",
                "query": query,
                "answer": full_response,
                "sources": self.rag_service._extract_sources([]),  # TODO: Pass actual docs
                "metadata": {
                    "token_count": token_count,
                    "response_length": len(full_response)
                }
            })

            logger.info(f"Response streamed: {token_count} tokens")

        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            await manager.send_personal_message(connection_id, {
                "type": "error",
                "message": "Error generating response"
            })

    async def handle_cancel(self, connection_id: str, session: Dict[str, Any]):
        """Handle cancellation request."""
        logger.info(f"Cancellation requested for {connection_id}")

        # Set cancel flag
        manager.request_cancel(connection_id)

        # Signal cancel event
        if connection_id in self.cancel_events:
            self.cancel_events[connection_id].set()

        await manager.send_personal_message(connection_id, {
            "type": "cancel_acknowledged"
        })

    async def handle_feedback(self, connection_id: str, session: Dict[str, Any], message: Dict[str, Any]):
        """Handle feedback submission."""
        user_id = session.get("user_id")
        conversation_id = session.get("conversation_id")
        message_id = message.get("message_id")
        is_positive = message.get("is_positive", True)
        feedback_text = message.get("feedback_text", "")
        tags = message.get("tags", [])

        if not message_id:
            await manager.send_personal_message(connection_id, {
                "type": "error",
                "message": "message_id required for feedback"
            })
            return

        # Submit feedback
        self.feedback_service.submit_explicit_feedback(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            is_positive=is_positive,
            feedback_text=feedback_text,
            tags=tags
        )

        # Acknowledge
        await manager.send_personal_message(connection_id, {
            "type": "feedback_acknowledged",
            "message_id": message_id
        })

        logger.info(f"Feedback received for message {message_id}: {'positive' if is_positive else 'negative'}")

    async def handle_set_conversation(
        self,
        connection_id: str,
        session: Dict[str, Any],
        message: Dict[str, Any]
    ):
        """Handle conversation context switch."""
        conversation_id = message.get("conversation_id")

        await manager.update_session(connection_id, conversation_id=conversation_id)

        await manager.send_personal_message(connection_id, {
            "type": "conversation_set",
            "conversation_id": conversation_id
        })

        logger.info(f"Conversation set to {conversation_id} for connection {connection_id}")

    async def handle_typing_indicator(
        self,
        connection_id: str,
        session: Dict[str, Any],
        message: Dict[str, Any]
    ):
        """Handle typing indicator from user."""
        # Broadcast to other user connections
        user_id = session.get("user_id")
        if user_id:
            await manager.broadcast_to_user(user_id, {
                "type": "user_typing",
                "connection_id": connection_id
            })


# WebSocket router helper
class WebSocketRouter:
    """Router for WebSocket endpoints."""

    def __init__(self):
        self.chat_handler = WebSocketChatHandler()

    async def handle_websocket(self, websocket: WebSocket, connection_id: str, user_id: int):
        """Main WebSocket handler."""
        # Connect
        connected = await manager.connect(websocket, connection_id, user_id)
        if not connected:
            return

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()

                # Handle message
                await self.chat_handler.handle_message(connection_id, data)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            manager.disconnect(connection_id)


# Global router instance
websocket_router = WebSocketRouter()


def get_websocket_router() -> WebSocketRouter:
    """Get the WebSocket router instance."""
    return websocket_router


def get_connection_manager() -> ConnectionManager:
    """Get the connection manager instance."""
    return manager
