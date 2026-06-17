"""
Redis cache service for response caching
"""
import json
import hashlib
import redis.asyncio as redis
from typing import Optional, Any
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """Redis cache service for storing and retrieving responses."""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.default_ttl = settings.CACHE_TTL
    
    async def connect(self):
        """Initialize Redis connection."""
        try:
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )
            await self.redis.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")
    
    def _generate_key(self, prefix: str, *args) -> str:
        """Generate a cache key from arguments."""
        key_data = ":".join(str(arg) for arg in args)
        hash_key = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{hash_key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if not self.redis:
            return None
        
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache."""
        if not self.redis:
            return False
        
        try:
            await self.redis.set(key, json.dumps(value), ex=ttl or self.default_ttl)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self.redis:
            return False
        
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def get_query_response(self, query: str, user_id: int) -> Optional[dict]:
        """Get cached response for a query."""
        key = self._generate_key("query", user_id, query)
        return await self.get(key)
    
    async def set_query_response(self, query: str, user_id: int, response: dict) -> bool:
        """Cache a query response."""
        key = self._generate_key("query", user_id, query)
        return await self.set(key, response)
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """Invalidate all cache entries for a user."""
        if not self.redis:
            return False
        
        try:
            pattern = f"query:*:{user_id}:*"
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
            logger.info(f"Invalidated cache for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check Redis connection health."""
        if not self.redis:
            return False
        
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False


# Global cache instance
cache_service = CacheService()


async def get_cache_service() -> CacheService:
    """Dependency to get cache service instance."""
    return cache_service
