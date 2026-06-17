"""
Tests for authentication endpoints
"""
import pytest
from httpx import AsyncClient


class TestAuthentication:
    """Test authentication endpoints."""
    
    @pytest.mark.asyncio
    async def test_signup_success(self, client: AsyncClient, test_user_data):
        """Test successful user registration."""
        response = await client.post("/api/auth/signup", json=test_user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_signup_duplicate_username(self, client: AsyncClient, test_user_data):
        """Test registration with duplicate username."""
        # First registration
        await client.post("/api/auth/signup", json=test_user_data)
        
        # Second registration with same username
        response = await client.post("/api/auth/signup", json=test_user_data)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user_data):
        """Test successful login."""
        # Register user first
        await client.post("/api/auth/signup", json=test_user_data)
        
        # Login
        response = await client.post("/api/auth/login", json={
            "username": test_user_data["username"],
            "password": test_user_data["password"],
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "wrongpassword",
        })
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, authenticated_client):
        """Test getting current authenticated user."""
        client, tokens = authenticated_client
        
        # Access a protected endpoint (conversations list)
        response = await client.get("/api/conversations")
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client: AsyncClient):
        """Test accessing protected endpoint without authentication."""
        response = await client.get("/api/conversations")
        
        assert response.status_code == 403
