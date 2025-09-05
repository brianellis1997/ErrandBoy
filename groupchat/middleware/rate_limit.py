"""Rate limiting middleware"""

import asyncio
import time
from collections import defaultdict
from typing import Callable, Dict, Tuple

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from groupchat.config import settings


class InMemoryRateLimiter:
    """In-memory rate limiter fallback when Redis is not available"""
    
    def __init__(self):
        # Store: {client_id: (request_count, window_start_time)}
        self.clients: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, time.time()))
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, client_id: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """Check if request is allowed. Returns (allowed, remaining, reset_time)"""
        async with self._lock:
            current_time = time.time()
            count, window_start = self.clients[client_id]
            
            # Reset window if expired
            if current_time - window_start >= window_seconds:
                count = 0
                window_start = current_time
            
            # Check if allowed
            if count >= limit:
                reset_time = int(window_start + window_seconds)
                return False, 0, reset_time
            
            # Increment and store
            count += 1
            self.clients[client_id] = (count, window_start)
            
            remaining = limit - count
            reset_time = int(window_start + window_seconds)
            return True, remaining, reset_time


class RedisRateLimiter:
    """Redis-based rate limiter for distributed systems"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def is_allowed(self, client_id: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """Check if request is allowed using Redis sliding window"""
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(client_id, 0, window_start)
        
        # Count current requests
        pipe.zcard(client_id)
        
        # Add current request
        pipe.zadd(client_id, {str(current_time): current_time})
        
        # Set expiry
        pipe.expire(client_id, window_seconds)
        
        results = await pipe.execute()
        current_requests = results[1]
        
        if current_requests >= limit:
            reset_time = current_time + window_seconds
            return False, 0, reset_time
        
        remaining = limit - current_requests - 1
        reset_time = current_time + window_seconds
        return True, remaining, reset_time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with Redis and in-memory fallback"""
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        enable_rate_limiting: bool = True,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.enable_rate_limiting = enable_rate_limiting
        self.redis_limiter = None
        self.memory_limiter = InMemoryRateLimiter()
        self._redis_available = False
    
    async def _setup_redis(self):
        """Setup Redis connection if available"""
        if settings.redis_url and not hasattr(self, '_redis_setup_attempted'):
            self._redis_setup_attempted = True
            try:
                redis_client = redis.from_url(str(settings.redis_url))
                await redis_client.ping()
                self.redis_limiter = RedisRateLimiter(redis_client)
                self._redis_available = True
            except Exception:
                self._redis_available = False
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Use X-Forwarded-For if available, otherwise client host
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to requests"""
        if not self.enable_rate_limiting:
            return await call_next(request)
        
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)
        
        await self._setup_redis()
        
        client_id = self._get_client_id(request)
        limiter = self.redis_limiter if self._redis_available else self.memory_limiter
        
        # Check minute limit
        allowed_minute, remaining_minute, reset_minute = await limiter.is_allowed(
            f"{client_id}:minute", self.requests_per_minute, 60
        )
        
        # Check hour limit
        allowed_hour, remaining_hour, reset_hour = await limiter.is_allowed(
            f"{client_id}:hour", self.requests_per_hour, 3600
        )
        
        # Use the most restrictive limit
        allowed = allowed_minute and allowed_hour
        remaining = min(remaining_minute, remaining_hour)
        reset_time = min(reset_minute, reset_hour)
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit-Minute": str(self.requests_per_minute),
                    "X-RateLimit-Limit-Hour": str(self.requests_per_hour),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - int(time.time())),
                },
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response