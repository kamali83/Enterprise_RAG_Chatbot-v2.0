"""
Authentication API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.core.security import verify_token
from app.models.schemas import UserCreate, UserLogin, UserResponse, Token
from app.services.auth_service import AuthenticationService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer()


def get_auth_service(db: AsyncSession = Depends(get_async_db)) -> AuthenticationService:
    """Get authentication service instance."""
    return AuthenticationService(db)


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    user_data: UserCreate,
    auth_service: AuthenticationService = Depends(get_auth_service),
):
    """Register a new user."""
    try:
        user = await auth_service.register_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    auth_service: AuthenticationService = Depends(get_auth_service),
):
    """Login and get access token."""
    try:
        tokens = await auth_service.login(credentials)
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_async_db),
) -> UserResponse:
    """Get current authenticated user."""
    auth_service = AuthenticationService(db)
    
    token = credentials.credentials
    username = verify_token(token)
    
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user = await auth_service.get_user_by_username(username)
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is inactive")
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
    )
