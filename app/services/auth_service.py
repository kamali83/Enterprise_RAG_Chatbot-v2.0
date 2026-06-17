"""
Authentication service for user management
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from app.core.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from app.core.logging import get_logger
from app.models.db_models import User
from app.repositories.user_repository import UserRepository
from app.models.schemas import UserCreate, UserLogin

logger = get_logger(__name__)


class AuthenticationService:
    """Service for user authentication and management."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
    
    async def register_user(self, user_data: UserCreate) -> User:
        """Register a new user."""
        # Check if username exists
        if await self.user_repo.check_username_exists(user_data.username):
            raise ValueError("Username already exists")
        
        # Check if email exists (if provided)
        if user_data.email and await self.user_repo.check_email_exists(user_data.email):
            raise ValueError("Email already registered")
        
        # Create user
        user_dict = {
            "username": user_data.username,
            "email": user_data.email,
            "hashed_password": get_password_hash(user_data.password),
            "is_active": True,
            "is_admin": False,
        }
        
        user = await self.user_repo.create(user_dict)
        logger.info(f"User registered: {user.username}")
        
        return user
    
    async def authenticate_user(self, credentials: UserLogin) -> Optional[User]:
        """Authenticate a user with username and password."""
        user = await self.user_repo.get_by_username(credentials.username)
        
        if not user:
            logger.warning(f"Authentication failed: user not found - {credentials.username}")
            return None
        
        if not verify_password(credentials.password, user.hashed_password):
            logger.warning(f"Authentication failed: invalid password - {credentials.username}")
            return None
        
        if not user.is_active:
            logger.warning(f"Authentication failed: inactive user - {credentials.username}")
            return None
        
        logger.info(f"User authenticated: {user.username}")
        return user
    
    async def login(self, credentials: UserLogin) -> dict:
        """Login and return access token."""
        user = await self.authenticate_user(credentials)
        
        if not user:
            raise ValueError("Invalid credentials")
        
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username,
        }
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return await self.user_repo.get_by_username(username)
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return await self.user_repo.get(user_id)
    
    async def update_user(self, user_id: int, update_data: dict) -> Optional[User]:
        """Update user information."""
        # Remove sensitive fields from update
        update_data.pop("hashed_password", None)
        update_data.pop("is_admin", None)
        
        return await self.user_repo.update(user_id, update_data)
    
    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change user password."""
        user = await self.user_repo.get(user_id)
        
        if not user:
            return False
        
        if not verify_password(current_password, user.hashed_password):
            return False
        
        await self.user_repo.update(
            user_id,
            {"hashed_password": get_password_hash(new_password)}
        )
        
        logger.info(f"Password changed for user: {user.username}")
        return True


def get_authentication_service(db: AsyncSession) -> AuthenticationService:
    """Get authentication service instance."""
    return AuthenticationService(db)
