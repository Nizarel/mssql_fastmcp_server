"""Rate limiting for MCP server requests."""

import time
import asyncio
from typing import Dict, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, rate: int = 60, burst: int = 10):
        """
        Initialize rate limiter.
        
        Args:
            rate: Requests per minute
            burst: Maximum burst size
        """
        self.rate = rate
        self.burst = burst
        self.buckets: Dict[str, float] = defaultdict(lambda: float(burst))
        self.last_update: Dict[str, float] = defaultdict(time.time)
        self._lock = asyncio.Lock()
    
    async def check_rate_limit(self, key: str = "global") -> bool:
        """
        Check if request is within rate limit.
        
        Args:
            key: Rate limit key (e.g., user ID, IP, or "global")
            
        Returns:
            True if request is allowed, False otherwise
        """
        async with self._lock:
            now = time.time()
            time_passed = now - self.last_update[key]
            self.last_update[key] = now
            
            # Add tokens based on time passed
            tokens_to_add = time_passed * (self.rate / 60.0)
            self.buckets[key] = min(self.burst, self.buckets[key] + tokens_to_add)
            
            # Check if we have tokens available
            if self.buckets[key] >= 1:
                self.buckets[key] -= 1
                return True
            
            return False
    
    async def wait_if_needed(self, key: str = "global"):
        """Wait if rate limit is exceeded."""
        while not await self.check_rate_limit(key):
            wait_time = 60.0 / self.rate
            logger.warning(f"Rate limit exceeded for {key}, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)


# Create a decorator for rate limiting
def rate_limited(rate: int = 60, burst: int = 10):
    """Decorator to add rate limiting to MCP tools."""
    limiter = RateLimiter(rate, burst)
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract context if available
            ctx = kwargs.get('ctx')
            key = "global"  # Could be enhanced to use user ID from context
            
            await limiter.wait_if_needed(key)
            return await func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator
