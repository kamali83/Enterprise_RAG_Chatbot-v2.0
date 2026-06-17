"""
Database connection and session management
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.core.config import settings
import re

# Check if using SQLite
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

# Synchronous engine for general use
if IS_SQLITE:
    sync_engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    sync_engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
    )

# Async engine for async operations
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

if IS_SQLITE:
    async_engine = create_async_engine(
        settings.DATABASE_ASYNC_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    async_engine = create_async_engine(
        settings.DATABASE_ASYNC_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()


def get_db() -> Session:
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncSession:
    """Dependency for FastAPI to get async database session."""
    async with async_session_maker() as session:
        yield session


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=sync_engine)
