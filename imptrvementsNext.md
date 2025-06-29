Collecting workspace informationAfter reviewing your MSSQL MCP Server codebase, I can see this is a well-structured implementation with modern features. Here are my optimization recommendations and best practice suggestions:

## 1. Code Structure Optimizations

### A. Modularize the Server File
The server.py file is over 1000 lines. Consider splitting it into smaller, focused modules:

````python
"""MCP request handlers."""

from .health import HealthHandler
from .tables import TablesHandler
from .query import QueryHandler
from .schema import SchemaHandler
from .admin import AdminHandler

__all__ = ['HealthHandler', 'TablesHandler', 'QueryHandler', 'SchemaHandler', 'AdminHandler']
````

````python
"""Base handler with common functionality."""

from typing import Optional, Dict, Any
from fastmcp import Context
from ..config import AppConfig, OutputFormat
from ..response_formatter import MCPResponse

class BaseHandler:
    """Base handler with common functionality."""
    
    def __init__(self, app_config: AppConfig, db_manager, cache, rate_limiter):
        self.app_config = app_config
        self.db_manager = db_manager
        self.cache = cache
        self.rate_limiter = rate_limiter
    
    async def check_rate_limit(self, ctx: Context, operation: str) -> bool:
        """Check rate limit for operation."""
        if not self.app_config.server.enable_rate_limiting or not self.rate_limiter:
            return True
        
        client_id = getattr(ctx, 'client_id', 'anonymous')
        key = f"{client_id}:{operation}"
        
        allowed = await self.rate_limiter.check_rate_limit(key)
        if not allowed:
            await ctx.warning(f"Rate limit exceeded for operation: {operation}")
            return False
        
        return True
    
    def get_output_format(self, ctx: Context) -> OutputFormat:
        """Extract output format from context or use default."""
        if hasattr(ctx, 'params') and isinstance(ctx.params, dict):
            format_str = ctx.params.get('output_format', self.app_config.server.default_output_format.value)
        else:
            format_str = self.app_config.server.default_output_format.value
        
        try:
            return OutputFormat(format_str)
        except ValueError:
            return self.app_config.server.default_output_format
````

### B. Improve Connection Pool Implementation

````python
"""Enhanced connection pool with health monitoring."""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import pymssql
from queue import Queue, Empty, Full
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ConnectionStats:
    """Connection statistics."""
    created_at: datetime
    last_used: datetime
    queries_executed: int = 0
    errors_count: int = 0
    total_execution_time: float = 0.0
    
    @property
    def age(self) -> float:
        """Connection age in seconds."""
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def idle_time(self) -> float:
        """Idle time in seconds."""
        return (datetime.now() - self.last_used).total_seconds()


class PooledConnection:
    """Wrapper for pooled database connection with statistics."""
    
    def __init__(self, conn: pymssql.Connection):
        self.conn = conn
        self.stats = ConnectionStats(
            created_at=datetime.now(),
            last_used=datetime.now()
        )
        self._lock = threading.Lock()
    
    def is_alive(self) -> bool:
        """Check if connection is still alive."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            return False
    
    def close(self):
        """Close the underlying connection."""
        try:
            self.conn.close()
        except Exception:
            pass


class EnhancedConnectionPool:
    """Enhanced connection pool with monitoring and auto-recovery."""
    
    def __init__(
        self,
        connection_params: Dict[str, Any],
        min_size: int = 2,
        max_size: int = 10,
        timeout: float = 30.0,
        idle_timeout: float = 300.0,
        max_lifetime: float = 3600.0,
        health_check_interval: float = 60.0
    ):
        self._params = connection_params
        self._min_size = min_size
        self._max_size = max_size
        self._timeout = timeout
        self._idle_timeout = idle_timeout
        self._max_lifetime = max_lifetime
        self._health_check_interval = health_check_interval
        
        self._pool: Queue[PooledConnection] = Queue(maxsize=max_size)
        self._size = 0
        self._lock = threading.Lock()
        self._closed = False
        self._stats = {
            'connections_created': 0,
            'connections_closed': 0,
            'connections_reused': 0,
            'health_checks_passed': 0,
            'health_checks_failed': 0
        }
        
        # Start background health check task
        self._health_check_task = None
        
        # Pre-create minimum connections
        for _ in range(min_size):
            self._create_connection()
    
    def _create_connection(self) -> Optional[PooledConnection]:
        """Create a new database connection."""
        try:
            with self._lock:
                if self._size >= self._max_size:
                    return None
                self._size += 1
                self._stats['connections_created'] += 1
            
            conn = pymssql.connect(**self._params)
            pooled_conn = PooledConnection(conn)
            self._pool.put(pooled_conn)
            logger.debug(f"Created new connection. Pool size: {self._size}")
            return pooled_conn
        except Exception as e:
            with self._lock:
                self._size -= 1
            logger.error(f"Failed to create connection: {e}")
            raise
    
    def _should_retire_connection(self, pooled_conn: PooledConnection) -> bool:
        """Check if connection should be retired."""
        # Check age
        if pooled_conn.stats.age > self._max_lifetime:
            logger.debug("Connection exceeded max lifetime")
            return True
        
        # Check idle time
        if pooled_conn.stats.idle_time > self._idle_timeout:
            logger.debug("Connection exceeded idle timeout")
            return True
        
        # Check health
        if not pooled_conn.is_alive():
            logger.debug("Connection health check failed")
            return True
        
        return False
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        pooled_conn = None
        start_time = time.time()
        
        try:
            while True:
                try:
                    # Try to get from pool
                    pooled_conn = self._pool.get(timeout=0.1)
                    
                    # Check if connection should be retired
                    if self._should_retire_connection(pooled_conn):
                        pooled_conn.close()
                        with self._lock:
                            self._size -= 1
                            self._stats['connections_closed'] += 1
                        
                        # Create replacement
                        self._create_connection()
                        continue
                    
                    # Update stats
                    pooled_conn.stats.last_used = datetime.now()
                    with self._lock:
                        self._stats['connections_reused'] += 1
                    
                    yield pooled_conn.conn
                    break
                    
                except Empty:
                    # Check if we can create more connections
                    if self._size < self._max_size:
                        self._create_connection()
                    
                    # Check timeout
                    if time.time() - start_time > self._timeout:
                        raise TimeoutError(f"Failed to acquire connection within {self._timeout}s")
                    
                    await asyncio.sleep(0.1)
                    
        finally:
            if pooled_conn:
                try:
                    self._pool.put_nowait(pooled_conn)
                except Full:
                    # Pool is full, close the connection
                    pooled_conn.close()
                    with self._lock:
                        self._size -= 1
    
    async def start_health_checks(self):
        """Start background health check task."""
        self._health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def _health_check_loop(self):
        """Background task to check connection health."""
        while not self._closed:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._perform_health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _perform_health_check(self):
        """Perform health check on idle connections."""
        connections_to_check = []
        
        # Get all connections from pool
        try:
            while True:
                conn = self._pool.get_nowait()
                connections_to_check.append(conn)
        except Empty:
            pass
        
        # Check each connection
        for pooled_conn in connections_to_check:
            if self._should_retire_connection(pooled_conn):
                pooled_conn.close()
                with self._lock:
                    self._size -= 1
                    self._stats['connections_closed'] += 1
                    self._stats['health_checks_failed'] += 1
                
                # Create replacement
                self._create_connection()
            else:
                # Put back in pool
                try:
                    self._pool.put_nowait(pooled_conn)
                    with self._lock:
                        self._stats['health_checks_passed'] += 1
                except Full:
                    pooled_conn.close()
                    with self._lock:
                        self._size -= 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                'current_size': self._size,
                'min_size': self._min_size,
                'max_size': self._max_size,
                'available': self._pool.qsize(),
                'in_use': self._size - self._pool.qsize(),
                **self._stats
            }
    
    async def close(self):
        """Close all connections in the pool."""
        self._closed = True
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
        
        # Close all connections
        while not self._pool.empty():
            try:
                pooled_conn = self._pool.get_nowait()
                pooled_conn.close()
            except Empty:
                break
        
        self._size = 0
        logger.info("Connection pool closed")
````

### C. Enhanced Cache with Metrics

````python
"""Enhanced caching with hit rate tracking and memory management."""

import asyncio
import time
import hashlib
import json
import sys
from typing import Any, Optional, Dict, Tuple
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    timestamp: float
    size: int
    hits: int = 0
    
    @property
    def age(self) -> float:
        """Age in seconds."""
        return time.time() - self.timestamp


@dataclass
class CacheStats:
    """Cache statistics."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests


class EnhancedLRUCache:
    """Enhanced LRU cache with size limits and metrics."""
    
    def __init__(
        self,
        max_entries: int = 1000,
        max_size_mb: float = 100.0,
        ttl: int = 300,
        enable_compression: bool = True
    ):
        self.max_entries = max_entries
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.ttl = ttl
        self.enable_compression = enable_compression
        
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.stats = CacheStats()
        self._lock = asyncio.Lock()
        self._cleanup_task = None
    
    def _make_key(self, query: str) -> str:
        """Generate cache key from query."""
        return hashlib.sha256(query.encode()).hexdigest()
    
    def _estimate_size(self, obj: Any) -> int:
        """Estimate object size in bytes."""
        try:
            if isinstance(obj, (str, bytes)):
                return len(obj)
            elif isinstance(obj, (list, tuple)):
                return sum(self._estimate_size(item) for item in obj)
            elif isinstance(obj, dict):
                return sum(self._estimate_size(k) + self._estimate_size(v) 
                          for k, v in obj.items())
            else:
                # Rough estimate for other types
                return sys.getsizeof(obj)
        except Exception:
            return 1000  # Default size
    
    async def get(self, query: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            self.stats.total_requests += 1
            key = self._make_key(query)
            
            if key not in self.cache:
                self.stats.cache_misses += 1
                return None
            
            entry = self.cache[key]
            
            # Check if expired
            if entry.age > self.ttl:
                del self.cache[key]
                self.stats.total_size_bytes -= entry.size
                self.stats.cache_misses += 1
                return None
            
            # Update access order and stats
            self.cache.move_to_end(key)
            entry.hits += 1
            self.stats.cache_hits += 1
            
            logger.debug(f"Cache hit for query: {query[:50]}... (hits: {entry.hits})")
            return entry.value
    
    async def set(self, query: str, value: Any):
        """Set value in cache."""
        async with self._lock:
            key = self._make_key(query)
            size = self._estimate_size(value)
            
            # Check if value is too large
            if size > self.max_size_bytes * 0.1:  # Don't cache items > 10% of max size
                logger.warning(f"Value too large to cache: {size} bytes")
                return
            
            # Remove existing entry if present
            if key in self.cache:
                old_entry = self.cache[key]
                self.stats.total_size_bytes -= old_entry.size
                del self.cache[key]
            
            # Evict entries if necessary
            while (len(self.cache) >= self.max_entries or 
                   self.stats.total_size_bytes + size > self.max_size_bytes):
                if not self.cache:
                    break
                
                # Remove oldest entry
                oldest_key, oldest_entry = self.cache.popitem(last=False)
                self.stats.total_size_bytes -= oldest_entry.size
                self.stats.evictions += 1
                logger.debug(f"Evicted cache entry (age: {oldest_entry.age:.1f}s)")
            
            # Add new entry
            entry = CacheEntry(value=value, timestamp=time.time(), size=size)
            self.cache[key] = entry
            self.stats.total_size_bytes += size
            
            logger.debug(f"Cached result for query: {query[:50]}... (size: {size} bytes)")
    
    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            self.stats.total_size_bytes = 0
            logger.info("Cache cleared")
    
    async def cleanup_expired(self):
        """Remove expired entries."""
        async with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self.cache.items():
                if current_time - entry.timestamp > self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                entry = self.cache[key]
                del self.cache[key]
                self.stats.total_size_bytes -= entry.size
                self.stats.evictions += 1
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def start_cleanup_task(self, interval: int = 60):
        """Start background cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval))
    
    async def _cleanup_loop(self, interval: int):
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(interval)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        async with self._lock:
            entries_by_age = {}
            entries_by_hits = {}
            
            for key, entry in self.cache.items():
                # Group by age buckets
                age_bucket = int(entry.age / 60)  # Minutes
                entries_by_age[f"{age_bucket}min"] = entries_by_age.get(f"{age_bucket}min", 0) + 1
                
                # Group by hit count
                hit_bucket = min(entry.hits // 10 * 10, 100)  # 0, 10, 20, ..., 100+
                hit_key = f"{hit_bucket}+" if hit_bucket >= 100 else str(hit_bucket)
                entries_by_hits[hit_key] = entries_by_hits.get(hit_key, 0) + 1
            
            return {
                "total_entries": len(self.cache),
                "total_size_mb": round(self.stats.total_size_bytes / 1024 / 1024, 2),
                "max_size_mb": round(self.max_size_bytes / 1024 / 1024, 2),
                "utilization_percent": round(self.stats.total_size_bytes / self.max_size_bytes * 100, 1),
                "hit_rate": round(self.stats.hit_rate * 100, 1),
                "total_requests": self.stats.total_requests,
                "cache_hits": self.stats.cache_hits,
                "cache_misses": self.stats.cache_misses,
                "evictions": self.stats.evictions,
                "ttl_seconds": self.ttl,
                "entries_by_age": entries_by_age,
                "entries_by_hits": entries_by_hits
            }
````

## 2. Project Structure Best Practices

### A. Recommended Directory Structure

```
mssql_fastmcp_server/
├── src/
│   └── mssql_mcp_server/
│       ├── __init__.py
│       ├── __main__.py          # Entry point
│       ├── server.py            # Main server setup
│       ├── config.py            # Configuration
│       ├── handlers/            # Request handlers
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── health.py
│       │   ├── tables.py
│       │   ├── query.py
│       │   ├── schema.py
│       │   └── admin.py
│       ├── core/               # Core components
│       │   ├── __init__.py
│       │   ├── database.py
│       │   ├── connection_pool.py
│       │   ├── cache.py
│       │   ├── rate_limiter.py
│       │   └── response_formatter.py
│       ├── middleware/         # Middleware components
│       │   ├── __init__.py
│       │   ├── auth.py
│       │   ├── logging.py
│       │   └── metrics.py
│       └── utils/             # Utilities
│           ├── __init__.py
│           ├── validators.py
│           └── helpers.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── performance/
├── scripts/
│   ├── setup_db.py
│   └── health_check.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
│   ├── api.md
│   ├── configuration.md
│   └── deployment.md
└── configs/
    ├── development.json
    ├── staging.json
    └── production.json
```

### B. Add Middleware Layer

````python
"""Metrics collection middleware."""

import time
import asyncio
from typing import Dict, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a specific operation."""
    count: int = 0
    total_time: float = 0.0
    errors: int = 0
    last_error: Optional[str] = None
    last_execution: Optional[datetime] = None
    
    @property
    def avg_time(self) -> float:
        """Average execution time."""
        return self.total_time / self.count if self.count > 0 else 0.0


class MetricsCollector:
    """Collect and report metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, OperationMetrics] = defaultdict(OperationMetrics)
        self._lock = asyncio.Lock()
    
    async def record_operation(
        self,
        operation: str,
        duration: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Record operation metrics."""
        async with self._lock:
            metric = self.metrics[operation]
            metric.count += 1
            metric.total_time += duration
            metric.last_execution = datetime.now()
            
            if not success:
                metric.errors += 1
                metric.last_error = error
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        async with self._lock:
            return {
                operation: {
                    "count": metric.count,
                    "total_time": round(metric.total_time, 3),
                    "avg_time": round(metric.avg_time, 3),
                    "errors": metric.errors,
                    "error_rate": round(metric.errors / metric.count * 100, 1) if metric.count > 0 else 0,
                    "last_error": metric.last_error,
                    "last_execution": metric.last_execution.isoformat() if metric.last_execution else None
                }
                for operation, metric in self.metrics.items()
            }
    
    def create_middleware(self):
        """Create middleware decorator."""
        def middleware(func: Callable):
            async def wrapper(*args, **kwargs):
                operation = func.__name__
                start_time = time.time()
                error = None
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    error = str(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    await self.record_operation(
                        operation=operation,
                        duration=duration,
                        success=(error is None),
                        error=error
                    )
            
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        
        return middleware
````

### C. Add Configuration Validation

````python
"""Configuration and input validators."""

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ValidationError:
    """Validation error details."""
    field: str
    message: str
    value: Any


class ConfigValidator:
    """Validate configuration values."""
    
    @staticmethod
    def validate_server_config(config: Dict[str, Any]) -> List[ValidationError]:
        """Validate server configuration."""
        errors = []
        
        # Validate max_rows
        max_rows = config.get('max_rows', 1000)
        if not isinstance(max_rows, int) or max_rows < 1:
            errors.append(ValidationError('max_rows', 'Must be positive integer', max_rows))
        elif max_rows > 100000:
            errors.append(ValidationError('max_rows', 'Cannot exceed 100000', max_rows))
        
        # Validate query_timeout
        query_timeout = config.get('query_timeout', 30)
        if not isinstance(query_timeout, int) or query_timeout < 1:
            errors.append(ValidationError('query_timeout', 'Must be positive integer', query_timeout))
        elif query_timeout > 300:
            errors.append(ValidationError('query_timeout', 'Cannot exceed 300 seconds', query_timeout))
        
        # Validate transport
        transport = config.get('transport', 'stdio')
        if transport not in ['stdio', 'sse']:
            errors.append(ValidationError('transport', 'Must be stdio or sse', transport))
        
        # Validate SSE settings if SSE transport
        if transport == 'sse':
            sse_port = config.get('sse_port', 8080)
            if not isinstance(sse_port, int) or sse_port < 1024 or sse_port > 65535:
                errors.append(ValidationError('sse_port', 'Must be valid port (1024-65535)', sse_port))
        
        return errors
    
    @staticmethod
    def validate_database_config(config: Dict[str, Any]) -> List[ValidationError]:
        """Validate database configuration."""
        errors = []
        
        # Required fields
        required_fields = ['server', 'database', 'username', 'password']
        for field in required_fields:
            if not config.get(field):
                errors.append(ValidationError(field, 'Required field', None))
        
        # Validate server format
        server = config.get('server', '')
        if server and not re.match(r'^[a-zA-Z0-9.-]+(\\\w+)?$', server):
            errors.append(ValidationError('server', 'Invalid server format', server))
        
        # Validate port
        port = config.get('port', 1433)
        if not isinstance(port, int) or port < 1 or port > 65535:
            errors.append(ValidationError('port', 'Must be valid port (1-65535)', port))
        
        return errors


class QueryValidator:
    """Enhanced query validation."""
    
    # Dangerous keywords that should be blocked
    DANGEROUS_KEYWORDS = [
        'xp_cmdshell', 'sp_configure', 'sp_addlogin', 'sp_password',
        'sp_addsrvrolemember', 'sp_droplogin', 'sp_adduser', 'sp_dropuser',
        'SHUTDOWN', 'RECONFIGURE', 'sp_OA', 'sp_MS', 'xp_'
    ]
    
    # DDL keywords
    DDL_KEYWORDS = [
        'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME'
    ]
    
    # DML keywords
    DML_KEYWORDS = [
        'INSERT', 'UPDATE', 'DELETE', 'MERGE'
    ]
    
    @classmethod
    def validate_query(
        cls,
        query: str,
        allow_ddl: bool = False,
        allow_dml: bool = True,
        max_length: int = 10000
    ) -> Optional[str]:
        """
        Validate SQL query for security and permissions.
        
        Returns error message if invalid, None if valid.
        """
        if not query or not query.strip():
            return "Empty query not allowed"
        
        # Check length
        if len(query) > max_length:
            return f"Query too long (max {max_length} characters)"
        
        # Remove comments and normalize
        cleaned_query = cls._remove_comments(query)
        query_upper = cleaned_query.upper()
        
        # Check for dangerous keywords
        for keyword in cls.DANGEROUS_KEYWORDS:
            if keyword.upper() in query_upper:
                return f"Query contains dangerous keyword: {keyword}"
        
        # Check DDL permissions
        if not allow_ddl:
            for keyword in cls.DDL_KEYWORDS:
                if re.search(rf'\b{keyword}\b', query_upper):
                    return f"DDL operations not allowed: {keyword}"
        
        # Check DML permissions
        if not allow_dml:
            for keyword in cls.DML_KEYWORDS:
                if re.search(rf'\b{keyword}\b', query_upper):
                    return f"DML operations not allowed: {keyword}"
        
        # Check for multiple statements
        if cls._has_multiple_statements(cleaned_query):
            return "Multiple statements not allowed"
        
        return None
    
    @staticmethod
    def _remove_comments(query: str) -> str:
        """Remove SQL comments from query."""
        # Remove single-line comments
        query = re.sub(r'--[^\n]*', '', query)
        # Remove multi-line comments
        query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        return query
    
    @staticmethod
    def _has_multiple_statements(query: str) -> bool:
        """Check if query contains multiple statements."""
        # Simple check for semicolons outside of strings
        in_string = False
        string_char = None
        
        for i, char in enumerate(query):
            if char in ("'", '"') and (i == 0 or query[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
            elif char == ';' and not in_string:
                # Check if there's non-whitespace after the semicolon
                remainder = query[i+1:].strip()
                if remainder:
                    return True
        
        return False
````

## 3. Performance Optimizations

### A. Add Query Plan Caching

````python
"""Query optimization and plan caching."""

import hashlib
from typing import Dict, Optional, Any
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    """Cached query execution plan."""
    query_hash: str
    parameterized_query: str
    execution_count: int = 0
    total_time: float = 0.0
    avg_rows: float = 0.0
    
    @property
    def avg_time(self) -> float:
        """Average execution time."""
        return self.total_time / self.execution_count if self.execution_count > 0 else 0.0


class QueryOptimizer:
    """Optimize queries and cache execution plans."""
    
    def __init__(self, max_plans: int = 1000):
        self.max_plans = max_plans
        self.plans: Dict[str, QueryPlan] = {}
        self._lock = asyncio.Lock()
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for plan caching."""
        # Remove extra whitespace
        normalized = ' '.join(query.split())
        # Convert to uppercase for comparison
        normalized = normalized.upper()
        return normalized
    
    def _parameterize_query(self, query: str) -> str:
        """Convert literals to parameters for plan reuse."""
        # Replace number literals
        parameterized = re.sub(r'\b\d+\b', '?', query)
        # Replace string literals
        parameterized = re.sub(r"'[^']*'", '?', parameterized)
        return parameterized
    
    async def get_or_create_plan(self, query: str) -> QueryPlan:
        """Get cached plan or create new one."""
        async with self._lock:
            normalized = self._normalize_query(query)
            query_hash = hashlib.md5(normalized.encode()).hexdigest()
            
            if query_hash in self.plans:
                return self.plans[query_hash]
            
            # Create new plan
            parameterized = self._parameterize_query(normalized)
            plan = QueryPlan(
                query_hash=query_hash,
                parameterized_query=parameterized
            )
            
            # Evict oldest plan if at capacity
            if len(self.plans) >= self.max_plans:
                # Remove least used plan
                least_used = min(self.plans.values(), key=lambda p: p.execution_count)
                del self.plans[least_used.query_hash]
            
            self.plans[query_hash] = plan
            return plan
    
    async def update_plan_stats(
        self,
        query: str,
        execution_time: float,
        row_count: int
    ):
        """Update plan statistics after execution."""
        plan = await self.get_or_create_plan(query)
        async with self._lock:
            plan.execution_count += 1
            plan.total_time += execution_time
            plan.avg_rows = (
                (plan.avg_rows * (plan.execution_count - 1) + row_count) / 
                plan.execution_count
            )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        async with self._lock:
            total_executions = sum(p.execution_count for p in self.plans.values())
            
            return {
                "cached_plans": len(self.plans),
                "total_executions": total_executions,
                "most_used_queries": [
                    {
                        "query": plan.parameterized_query[:100],
                        "executions": plan.execution_count,
                        "avg_time": round(plan.avg_time, 3),
                        "avg_rows": round(plan.avg_rows, 1)
                    }
                    for plan in sorted(
                        self.plans.values(),
                        key=lambda p: p.execution_count,
                        reverse=True
                    )[:10]
                ]
            }
````

### B. Add Batch Processing

````python
"""Batch processing for bulk operations."""

import asyncio
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """Batch request item."""
    id: str
    operation: str
    params: Dict[str, Any]
    callback: Optional[Callable] = None


@dataclass
class BatchResult:
    """Batch operation result."""
    id: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0


class BatchProcessor:
    """Process multiple operations in batches."""
    
    def __init__(
        self,
        batch_size: int = 100,
        batch_timeout: float = 1.0,
        max_concurrent_batches: int = 3
    ):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_concurrent_batches = max_concurrent_batches
        
        self._queue: asyncio.Queue[BatchRequest] = asyncio.Queue()
        self._processing = False
        self._semaphore = asyncio.Semaphore(max_concurrent_batches)
        self._processor_task = None
    
    async def start(self):
        """Start batch processor."""
        self._processing = True
        self._processor_task = asyncio.create_task(self._process_loop())
        logger.info("Batch processor started")
    
    async def stop(self):
        """Stop batch processor."""
        self._processing = False
        if self._processor_task:
            await self._processor_task
        logger.info("Batch processor stopped")
    
    async def submit(self, request: BatchRequest) -> asyncio.Future:
        """Submit request for batch processing."""
        future = asyncio.Future()
        request.callback = lambda result: future.set_result(result)
        await self._queue.put(request)
        return future
    
    async def _process_loop(self):
        """Main processing loop."""
        while self._processing:
            batch = await self._collect_batch()
            if batch:
                asyncio.create_task(self._process_batch(batch))
    
    async def _collect_batch(self) -> List[BatchRequest]:
        """Collect requests into a batch."""
        batch = []
        deadline = asyncio.get_event_loop().time() + self.batch_timeout
        
        while len(batch) < self.batch_size:
            try:
                timeout = max(0, deadline - asyncio.get_event_loop().time())
                request = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout
                )
                batch.append(request)
            except asyncio.TimeoutError:
                break
        
        return batch
    
    async def _process_batch(self, batch: List[BatchRequest]):
        """Process a batch of requests."""
        async with self._semaphore:
            logger.debug(f"Processing batch of {len(batch)} requests")
            
            # Group by operation type
            operations = {}
            for request in batch:
                if request.operation not in operations:
                    operations[request.operation] = []
                operations[request.operation].append(request)
            
            # Process each operation type
            results = []
            for operation, requests in operations.items():
                op_results = await self._execute_operation(operation, requests)
                results.extend(op_results)
            
            # Deliver results
            for request, result in zip(batch, results):
                if request.callback:
                    request.callback(result)
    
    async def _execute_operation(
        self,
        operation: str,
        requests: List[BatchRequest]
    ) -> List[BatchResult]:
        """Execute batch operation."""
        # This would be implemented based on specific operations
        # For now, return placeholder results
        return [
            BatchResult(
                id=req.id,
                success=True,
                data={"operation": operation, "params": req.params}
            )
            for req in requests
        ]
````

## 4. Security Enhancements

### A. Add Authentication Middleware

````python
"""Authentication and authorization middleware."""

import jwt
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class User:
    """User information."""
    id: str
    username: str
    roles: List[str]
    permissions: List[str]


class AuthMiddleware:
    """JWT-based authentication middleware."""
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        token_expiry: int = 3600
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry = token_expiry
    
    def generate_token(self, user: User) -> str:
        """Generate JWT token for user."""
        payload = {
            "user_id": user.id,
            "username": user.username,
            "roles": user.roles,
            "permissions": user.permissions,
            "exp": datetime.utcnow() + timedelta(seconds=self.token_expiry),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[User]:
        """Verify JWT token and return user."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            return User(
                id=payload["user_id"],
                username=payload["username"],
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", [])
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def require_permission(self, permission: str):
        """Decorator to require specific permission."""
        def decorator(func):
            async def wrapper(ctx, *args, **kwargs):
                # Extract user from context
                user = getattr(ctx, 'user', None)
                if not user:
                    await ctx.error("Authentication required")
                    return {"error": "Authentication required"}
                
                if permission not in user.permissions:
                    await ctx.error(f"Permission denied: {permission} required")
                    return {"error": f"Permission denied: {permission} required"}
                
                return await func(ctx, *args, **kwargs)
            
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        
        return decorator
````

## 5. Monitoring and Observability

### A. Add Comprehensive Logging

````python
"""Enhanced logging middleware with structured output."""

import logging
import json
from typing import Any, Dict
from datetime import datetime
import traceback
from pythonjsonlogger import jsonlogger

class StructuredLogger:
    """Structured logging with context."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
        # Configure JSON formatter
        formatter = jsonlogger.JsonFormatter(
            fmt='%(timestamp)s %(level)s %(name)s %(message)s',
            rename_fields={'levelname': 'level'}
        )
        
        # Add handler if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _add_context(self, record: Dict[str, Any], context: Dict[str, Any]):
        """Add context to log record."""
        record['timestamp'] = datetime.utcnow().isoformat()
        record.update(context)
        return record
    
    def info(self, message: str, **context):
        """Log info with context."""
        record = self._add_context({'message': message}, context)
        self.logger.info(json.dumps(record))
    
    def error(self, message: str, exception: Optional[Exception] = None, **context):
        """Log error with context and exception."""
        record = self._add_context({'message': message}, context)
        
        if exception:
            record['exception'] = {
                'type': type(exception).__name__,
                'message': str(exception),
                'traceback': traceback.format_exc()
            }
        
        self.logger.error(json.dumps(record))
    
    def create_middleware(self):
        """Create logging middleware."""
        def middleware(func):
            async def wrapper(ctx, *args, **kwargs):
                start_time = datetime.utcnow()
                request_id = getattr(ctx, 'request_id', 'unknown')
                
                self.info(
                    f"Starting {func.__name__}",
                    operation=func.__name__,
                    request_id=request_id,
                    args=str(args)[:200],
                    kwargs=str(kwargs)[:200]
                )
                
                try:
                    result = await func(ctx, *args, **kwargs)
                    
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    self.info(
                        f"Completed {func.__name__}",
                        operation=func.__name__,
                        request_id=request_id,
                        duration=duration,
                        success=True
                    )
                    
                    return result
                    
                except Exception as e:
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    self.error(
                        f"Failed {func.__name__}",
                        exception=e,
                        operation=func.__name__,
                        request_id=request_id,
                        duration=duration,
                        success=False
                    )
                    raise
            
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        
        return middleware
````

## 6. Testing Infrastructure

### A. Add Test Fixtures

````python
"""Pytest fixtures for testing."""

import pytest
import asyncio
from typing import AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

from mssql_mcp_server.config import AppConfig, DatabaseConfig, ServerConfig
from mssql_mcp_server.core.database import DatabaseManager
from mssql_mcp_server.core.connection_pool import EnhancedConnectionPool
from mssql_mcp_server.core.cache import EnhancedLRUCache
from mssql_mcp_server.core.rate_limiter import RateLimiter


@pytest.fixture
def mock_config() -> AppConfig:
    """Create mock configuration."""
    db_config = DatabaseConfig(
        server="localhost",
        database="testdb",
        username="testuser",
        password="testpass",
        port=1433
    )
    
    server_config = ServerConfig(
        max_rows=100,
        enable_caching=True,
        enable_rate_limiting=True
    )
    
    return AppConfig(database=db_config, server=server_config)


@pytest.fixture
async def mock_connection_pool() -> AsyncGenerator[EnhancedConnectionPool, None]:
    """Create mock connection pool."""
    pool = MagicMock(spec=EnhancedConnectionPool)
    pool.acquire = AsyncMock()
    pool.get_stats = AsyncMock(return_value={"current_size": 5})
    
    yield pool
    
    if hasattr(pool, 'close'):
        await pool.close()


@pytest.fixture
async def cache() -> AsyncGenerator[EnhancedLRUCache, None]:
    """Create test cache."""
    cache = EnhancedLRUCache(max_entries=10, max_size_mb=1.0, ttl=60)
    await cache.start_cleanup_task()
    
    yield cache
    
    await cache.stop_cleanup_task()
    await cache.clear()


@pytest.fixture
async def rate_limiter() -> RateLimiter:
    """Create test rate limiter."""
    return RateLimiter(rate=60, burst=10)


@pytest.fixture
async def db_manager(
    mock_config: AppConfig,
    mock_connection_pool: EnhancedConnectionPool
) -> DatabaseManager:
    """Create test database manager."""
    return DatabaseManager(mock_config.database, mock_connection_pool)
````

### B. Add Performance Tests

````python
"""Load testing for MCP server."""

import asyncio
import time
from typing import List, Dict, Any
import statistics
from dataclasses import dataclass
import pytest

from mssql_mcp_server.core.cache import EnhancedLRUCache
from mssql_mcp_server.core.rate_limiter import RateLimiter


@dataclass
class LoadTestResult:
    """Load test results."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    min_time: float
    max_time: float
    avg_time: float
    median_time: float
    p95_time: float
    p99_time: float
    requests_per_second: float


class LoadTester:
    """Load testing utility."""
    
    async def run_load_test(
        self,
        func: callable,
        num_requests: int,
        concurrency: int,
        *args,
        **kwargs
    ) -> LoadTestResult:
        """Run load test on a function."""
        semaphore = asyncio.Semaphore(concurrency)
        times = []
        errors = 0
        
        async def run_single():
            async with semaphore:
                start = time.time()
                try:
                    await func(*args, **kwargs)
                    return time.time() - start
                except Exception:
                    nonlocal errors
                    errors += 1
                    return None
        
        start_time = time.time()
        results = await asyncio.gather(
            *[run_single() for _ in range(num_requests)],
            return_exceptions=True
        )
        total_time = time.time() - start_time
        
        # Filter out errors and exceptions
        times = [r for r in results if isinstance(r, float)]
        times.sort()
        
        return LoadTestResult(
            total_requests=num_requests,
            successful_requests=len(times),
            failed_requests=errors,
            total_time=total_time,
            min_time=min(times) if times else 0,
            max_time=max(times) if times else 0,
            avg_time=statistics.mean(times) if times else 0,
            median_time=statistics.median(times) if times else 0,
            p95_time=times[int(len(times) * 0.95)] if times else 0,
            p99_time=times[int(len(times) * 0.99)] if times else 0,
            requests_per_second=len(times) / total_time if total_time > 0 else 0
        )


@pytest.mark.asyncio
async def test_cache_performance():
    """Test cache performance under load."""
    cache = EnhancedLRUCache(max_entries=1000, max_size_mb=10.0)
    tester = LoadTester()
    
    # Test data
    test_queries = [f"SELECT * FROM table_{i % 100}" for i in range(1000)]
    test_data = {"columns": ["id", "name"], "rows": [[1, "test"]] * 100}
    
    async def cache_operation():
        import random
        query = random.choice(test_queries)
        
        # 70% reads, 30% writes
        if random.random() < 0.7:
            await cache.get(query)
        else:
            await cache.set(query, test_data)
    
    result = await tester.run_load_test(
        cache_operation,
        num_requests=10000,
        concurrency=100
    )
    
    print(f"Cache Performance Test Results:")
    print(f"  Total requests: {result.total_requests}")
    print(f"  Successful: {result.successful_requests}")
    print(f"  Failed: {result.failed_requests}")
    print(f"  RPS: {result.requests_per_second:.2f}")
    print(f"  Avg time: {result.avg_time*1000:.2f}ms")
    print(f"  P95 time: {result.p95_time*1000:.2f}ms")
    print(f"  P99 time: {result.p99_time*1000:.2f}ms")
    
    # Assert performance requirements
    assert result.requests_per_second > 1000  # At least 1000 RPS
    assert result.avg_time < 0.01  # Average under 10ms
    assert result.p99_time < 0.05  # P99 under 50ms


@pytest.mark.asyncio
async def test_rate_limiter_performance():
    """Test rate limiter performance."""
    limiter = RateLimiter(rate=6000, burst=100)  # 100 RPS
    tester = LoadTester()
    
    async def rate_limit_operation():
        return await limiter.check_rate_limit("test_client")
    
    result = await tester.run_load_test(
        rate_limit_operation,
        num_requests=1000,
        concurrency=50
    )
    
    print(f"\nRate Limiter Performance Test Results:")
    print(f"  Total requests: {result.total_requests}")
    print(f"  RPS: {result.requests_per_second:.2f}")
    print(f"  Avg time: {result.avg_time*1000:.2f}ms")
    
    # Rate limiter should be very fast
    assert result.avg_time < 0.001  # Under 1ms
````

## 7. Deployment Best Practices

### A. Add Health Check Endpoint

````python
"""Comprehensive health check handler."""

from typing import Dict, Any
from datetime import datetime
import psutil
import asyncio

from .base import BaseHandler


class HealthHandler(BaseHandler):
    """Handle health check requests."""
    
    async def check_health(self, ctx) -> Dict[str, Any]:
        """Comprehensive health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "checks": {}
        }
        
        # Database health
        db_health = await self._check_database_health()
        health_status["checks"]["database"] = db_health
        
        # Connection pool health
        if self.connection_pool:
            pool_health = await self._check_pool_health()
            health_status["checks"]["connection_pool"] = pool_health
        
        # Cache health
        if self.cache:
            cache_health = await self._check_cache_health()
            health_status["checks"]["cache"] = cache_health
        
        # System resources
        system_health = self._check_system_health()
        health_status["checks"]["system"] = system_health
        
        # Overall status
        all_healthy = all(
            check.get("healthy", False)
            for check in health_status["checks"].values()
        )
        health_status["status"] = "healthy" if all_healthy else "unhealthy"
        
        return health_status
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            result = await self.db_manager.test_connection()
            return {
                "healthy": result["success"],
                "response_time_ms": result.get("response_time", 0) * 1000,
                "details": result
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    async def _check_pool_health(self) -> Dict[str, Any]:
        """Check connection pool health."""
        try:
            stats = await self.connection_pool.get_stats()
            
            # Check if pool is exhausted
            utilization = stats["in_use"] / stats["max_size"] * 100
            
            return {
                "healthy": utilization < 90,  # Warn if > 90% utilized
                "utilization_percent": utilization,
                "stats": stats
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    async def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache health."""
        try:
            stats = await self.cache.get_stats()
            
            return {
                "healthy": True,
                "hit_rate_percent": stats["hit_rate"],
                "utilization_percent": stats["utilization_percent"],
                "stats": stats
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    def _check_system_health(self) -> Dict[str, Any]:
        """Check system resources."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "healthy": cpu_percent < 90 and memory.percent < 90,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "details": {
                    "cpu_count": psutil.cpu_count(),
                    "memory_total_gb": round(memory.total / 1024**3, 2),
                    "memory_available_gb": round(memory.available / 1024**3, 2),
                    "disk_total_gb": round(disk.total / 1024**3, 2),
                    "disk_free_gb": round(disk.free / 1024**3, 2)
                }
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
````

### B. Production-Ready Dockerfile

````dockerfile
# Multi-stage build for production
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    unixodbc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    mkdir -p /app && \
    chown -R mcp:mcp /app

USER mcp
WORKDIR /app

# Copy application
COPY --chown=mcp:mcp src/ ./src/
COPY --chown=mcp:mcp configs/ ./configs/

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Set environment
ENV PYTHONUNBUFFERED=1
ENV MCP_CONFIG_FILE=/app/configs/production.json

# Run as non-root
EXPOSE 8080
CMD ["python", "-m", "mssql_mcp_server"]
````

## Summary

These optimizations and best practices will help you build a more robust, scalable, and maintainable MCP server:

1. **Code Structure**: Modularized handlers, improved separation of concerns
2. **Performance**: Enhanced connection pooling, intelligent caching, batch processing
3. **Security**: Input validation, authentication middleware, query sanitization
4. **Monitoring**: Structured logging, metrics collection, comprehensive health checks
5. **Testing**: Comprehensive fixtures, load testing, performance benchmarks
6. **Deployment**: Production-ready Docker images, health endpoints, graceful shutdown

The key improvements focus on:
- Better resource management (connection pooling, caching)
- Enhanced observability (structured logging, metrics)
- Improved security (validation, authentication)
- Production readiness (health checks, Docker optimization)
- Maintainability (modular structure, comprehensive testing)