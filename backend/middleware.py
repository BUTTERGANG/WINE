"""Security middleware — rate limiting and security utilities."""

import time
from collections import defaultdict
from functools import wraps

from fastapi import Request, HTTPException

from backend.config import settings


# Simple in-memory rate limiter
class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self):
        self._buckets: dict[str, dict] = defaultdict(lambda: {"tokens": 0, "last": 0})
    
    def _parse_limit(self, limit_str: str) -> tuple[int, int]:
        """Parse '5/minute' into (count, seconds)."""
        count, period = limit_str.split("/")
        periods = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
        return int(count), periods.get(period, 60)
    
    def is_allowed(self, key: str, limit_str: str) -> bool:
        """Check if request is allowed under rate limit."""
        count, period = self._parse_limit(limit_str)
        now = time.time()
        bucket = self._buckets[key]
        
        # Add tokens based on time passed
        elapsed = now - bucket["last"]
        bucket["tokens"] = min(count, bucket["tokens"] + elapsed * count / period)
        bucket["last"] = now
        
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False


_rate_limiter = RateLimiter()


def rate_limit(limit_str: str):
    """Decorator to rate limit an endpoint."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip rate limiting in debug/test mode
            if settings.debug or settings.test_mode:
                return await func(*args, **kwargs)
            
            # Extract request from args/kwargs
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request:
                # Use IP + path as key
                client_ip = request.client.host if request.client else "unknown"
                key = f"{client_ip}:{request.url.path}"
                
                if not _rate_limiter.is_allowed(key, limit_str):
                    raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
