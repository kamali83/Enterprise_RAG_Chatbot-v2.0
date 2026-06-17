"""
Tests for RAG (Question & Answer) endpoints
"""
import pytest
from httpx import AsyncClient


class TestRAG:
    """Test RAG endpoints."""
    
    @pytest.mark.asyncio
    async def test_ask_question(self, authenticated_client):
        """Test asking a question."""
        client, tokens = authenticated_client
        
        response = await client.get("/api/ask", params={
            "query": "What is machine learning?"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
    
    @pytest.mark.asyncio
    async def test_ask_question_with_conversation(self, authenticated_client):
        """Test asking a question within a conversation."""
        client, tokens = authenticated_client
        
        # Create conversation
        conv_response = await client.post("/api/conversations", json={
            "name": "Test Conv"
        })
        conv_id = conv_response.json()["id"]
        
        # Ask question
        response = await client.get("/api/ask", params={
            "query": "What is AI?",
            "conversation_id": conv_id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["conversation_id"] == conv_id
    
    @pytest.mark.asyncio
    async def test_ask_question_streaming(self, authenticated_client):
        """Test streaming question response."""
        client, tokens = authenticated_client
        
        response = await client.get("/api/ask_stream", params={
            "query": "What is deep learning?"
        })
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"
        
        # Read some of the stream
        content = ""
        async for line in response.aiter_lines():
            content += line
            if "[DONE]" in line:
                break
        
        assert len(content) > 0
    
    @pytest.mark.asyncio
    async def test_get_sources(self, authenticated_client):
        """Test getting document sources."""
        client, tokens = authenticated_client
        
        response = await client.get("/api/sources")
        
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data


class TestHealth:
    """Test health check endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client: AsyncClient):
        """Test Prometheus metrics endpoint."""
        response = await client.get("/api/metrics")
        
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
