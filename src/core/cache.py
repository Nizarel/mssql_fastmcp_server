"""Simple caching layer for frequently accessed data."""

import asyncio
import time
import hashlib
import json
from typing import Any, Optional, Dict
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)


class LRUCache:
    """Least Recently Used cache implementation."""
    
    def __init__(self, max_size: int = 100, ttl: int = 300):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            ttl: Time to live in seconds
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()
    
    def _make_key(self, query: str) -> str:
        """Generate cache key from query."""
        return hashlib.md5(query.encode()).hexdigest()
    
    async def get(self, query: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            key = self._make_key(query)
            
            if key not in self.cache:
                return None
            
            value, timestamp = self.cache[key]
            
            # Check if expired
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return value
    
    async def set(self, query: str, value: Any):
        """Set value in cache."""
        async with self._lock:
            key = self._make_key(query)
            
            # Remove oldest if at capacity
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
            
            self.cache[key] = (value, time.time())
            logger.debug(f"Cached result for query: {query[:50]}...")
    
    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            logger.info("Cache cleared")
    
    async def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total_entries = len(self.cache)
            
            # Count expired entries
            current_time = time.time()
            expired = sum(
                1 for _, (_, timestamp) in self.cache.items()
                if current_time - timestamp > self.ttl
            )
            
            return {
                "total_entries": total_entries,
                "active_entries": total_entries - expired,
                "expired_entries": expired,
                "max_size": self.max_size,
                "ttl_seconds": self.ttl
            }
