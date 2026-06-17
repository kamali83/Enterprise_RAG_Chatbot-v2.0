"""
Tests for conversation endpoints
"""
import pytest
from httpx import AsyncClient


class TestConversations:
    """Test conversation endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_conversation(self, authenticated_client):
        """Test creating a new conversation."""
        client, tokens = authenticated_client
        
        response = await client.post("/api/conversations", json={
            "name": "Test Conversation"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Conversation"
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_get_conversations(self, authenticated_client):
        """Test getting all conversations."""
        client, tokens = authenticated_client
        
        # Create a conversation first
        await client.post("/api/conversations", json={"name": "Test Conv"})
        
        # Get conversations
        response = await client.get("/api/conversations")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    @pytest.mark.asyncio
    async def test_get_conversation_by_id(self, authenticated_client):
        """Test getting a specific conversation."""
        client, tokens = authenticated_client
        
        # Create conversation
        create_response = await client.post("/api/conversations", json={
            "name": "Test Conv"
        })
        conv_id = create_response.json()["id"]
        
        # Get conversation
        response = await client.get(f"/api/conversations/{conv_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv_id
    
    @pytest.mark.asyncio
    async def test_rename_conversation(self, authenticated_client):
        """Test renaming a conversation."""
        client, tokens = authenticated_client
        
        # Create conversation
        create_response = await client.post("/api/conversations", json={
            "name": "Original Name"
        })
        conv_id = create_response.json()["id"]
        
        # Rename
        response = await client.put(f"/api/conversations/{conv_id}", json={
            "name": "New Name"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
    
    @pytest.mark.asyncio
    async def test_delete_conversation(self, authenticated_client):
        """Test deleting a conversation."""
        client, tokens = authenticated_client
        
        # Create conversation
        create_response = await client.post("/api/conversations", json={
            "name": "To Delete"
        })
        conv_id = create_response.json()["id"]
        
        # Delete
        response = await client.delete(f"/api/conversations/{conv_id}")
        
        assert response.status_code == 200
        
        # Verify deletion
        get_response = await client.get(f"/api/conversations/{conv_id}")
        assert get_response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_add_message(self, authenticated_client):
        """Test adding a message to a conversation."""
        client, tokens = authenticated_client
        
        # Create conversation
        create_response = await client.post("/api/conversations", json={
            "name": "Test Conv"
        })
        conv_id = create_response.json()["id"]
        
        # Add message
        response = await client.post(f"/api/conversations/{conv_id}/messages", json={
            "sender": "user",
            "content": "Hello, bot!"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Hello, bot!"
        assert data["sender"] == "user"
    
    @pytest.mark.asyncio
    async def test_get_messages(self, authenticated_client):
        """Test getting messages from a conversation."""
        client, tokens = authenticated_client
        
        # Create conversation
        create_response = await client.post("/api/conversations", json={
            "name": "Test Conv"
        })
        conv_id = create_response.json()["id"]
        
        # Add message
        await client.post(f"/api/conversations/{conv_id}/messages", json={
            "sender": "user",
            "content": "Test message"
        })
        
        # Get messages
        response = await client.get(f"/api/conversations/{conv_id}/messages")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
