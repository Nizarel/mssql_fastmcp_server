# Code Review and Improvement Proposals

### 1. **Transport Protocol Enhancement**

The current implementation uses the default stdio transport. According to MCP best practices, we should make the transport configurable and support multiple protocols:

````python
# ...existing imports...
from fastmcp.server import Server
from fastmcp.server.stdio import StdioTransport
from fastmcp.server.sse import SSETransport
import os

# ...existing code...

async def main():
    """Main entry point to run the MCP server."""
    logger.info("Starting Microsoft SQL Server MCP server with FastMCP...")
    
    try:
        # Initialize database manager
        db_manager, server_config = get_db_manager()
        logger.info(f"Server configuration: Command='{server_config.command_name}', MaxRows={server_config.max_rows}")
        
        # Test database connection
        tables = await db_manager.get_tables()
        logger.info(f"Database connection successful. Found {len(tables)} tables.")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise
    
    # Determine transport based on environment or configuration
    transport_type = os.getenv("MCP_TRANSPORT", "stdio").lower()
    
    if transport_type == "sse":
        # Server-Sent Events transport for web-based clients
        host = os.getenv("MCP_SSE_HOST", "localhost")
        port = int(os.getenv("MCP_SSE_PORT", "8080"))
        transport = SSETransport(host=host, port=port)
        logger.info(f"Using SSE transport on {host}:{port}")
    else:
        # Default to stdio transport
        transport = StdioTransport()
        logger.info("Using stdio transport")
    
    # Create and run the server with the selected transport
    server = Server(mcp, transport)
    await server.run()
````

### 2. **Error Handling and Response Formatting**

Improve error handling with structured responses:

````python
"""Response formatting utilities for consistent MCP responses."""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class MCPResponse:
    """Structured MCP response."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "timestamp": self.timestamp
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        if self.metadata is not None:
            result["metadata"] = self.metadata
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class TableFormatter:
    """Format table data for different output formats."""
    
    @staticmethod
    def to_csv(columns: List[str], rows: List[List[Any]]) -> str:
        """Format as CSV."""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        writer.writerows(rows)
        return output.getvalue()
    
    @staticmethod
    def to_json(columns: List[str], rows: List[List[Any]]) -> str:
        """Format as JSON."""
        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))
        return json.dumps(data, indent=2, default=str)
    
    @staticmethod
    def to_markdown(columns: List[str], rows: List[List[Any]], max_rows: int = 50) -> str:
        """Format as Markdown table."""
        if not rows:
            return "No data available."
        
        # Limit rows for readability
        display_rows = rows[:max_rows]
        
        # Build markdown table
        lines = []
        
        # Header
        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
        
        # Data rows
        for row in display_rows:
            row_str = " | ".join(str(cell) if cell is not None else "" for cell in row)
            lines.append(f"| {row_str} |")
        
        if len(rows) > max_rows:
            lines.append(f"\n*Showing {max_rows} of {len(rows)} rows*")
        
        return "\n".join(lines)
````

### 3. **Enhanced Tools with Better Context Usage**

Update the tools to use the response formatter and better progress reporting:

````python
# Add import at the top
from .response_formatter import MCPResponse, TableFormatter

# Update the execute_sql tool
@mcp.tool()
async def execute_sql(query: str, output_format: str = "csv", ctx: Context) -> str:
    """
    Execute a SQL query on the database.
    
    Args:
        query: SQL query to execute
        output_format: Output format (csv, json, markdown)
        ctx: FastMCP context for logging and progress reporting
        
    Returns:
        Query results in the specified format
    """
    try:
        await ctx.info(f"Executing SQL query: {query[:100]}...")
        await ctx.report_progress(0, 100, "Validating query")
        
        db_manager, _ = get_db_manager()
        
        # Validate query
        await ctx.report_progress(20, 100, "Query validation complete")
        
        # Execute query
        await ctx.report_progress(40, 100, "Executing query")
        result = await db_manager.execute_query(query)
        
        await ctx.report_progress(80, 100, "Formatting results")
        
        if result["type"] == "select":
            if not result["rows"]:
                response = MCPResponse(
                    success=True,
                    data="Query executed successfully but returned no rows.",
                    metadata={"row_count": 0, "query_type": "SELECT"}
                )
                await ctx.info("Query executed successfully but returned no rows")
                return response.to_json() if output_format == "json" else response.data
            
            # Format results based on output_format
            if output_format == "json":
                formatted_data = TableFormatter.to_json(result["columns"], result["rows"])
                response = MCPResponse(
                    success=True,
                    data=formatted_data,
                    metadata={
                        "row_count": result["row_count"],
                        "column_count": len(result["columns"]),
                        "query_type": "SELECT"
                    }
                )
                output = response.to_json()
            elif output_format == "markdown":
                output = TableFormatter.to_markdown(result["columns"], result["rows"])
            else:  # default to CSV
                output = TableFormatter.to_csv(result["columns"], result["rows"])
            
            await ctx.info(f"Query returned {result['row_count']} rows")
            await ctx.report_progress(100, 100, "Query completed")
            return output
        
        else:
            # Modification query
            response = MCPResponse(
                success=True,
                data=result["message"],
                metadata={
                    "affected_rows": result["affected_rows"],
                    "query_type": "MODIFICATION"
                }
            )
            await ctx.info(f"Query executed successfully. {result['message']}")
            await ctx.report_progress(100, 100, "Query completed")
            return response.to_json() if output_format == "json" else response.data
            
    except SecurityError as e:
        await ctx.error(f"Security error executing query: {e}")
        response = MCPResponse(success=False, error=f"Security error: {e}")
        return response.to_json() if output_format == "json" else response.error
    except DatabaseError as e:
        await ctx.error(f"Database error executing query: {e}")
        response = MCPResponse(success=False, error=f"Database error: {e}")
        return response.to_json() if output_format == "json" else response.error
````

### 4. **Connection Pool Management**

Implement connection pooling for better performance:

````python
"""Connection pool management for better performance."""

import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import pymssql
from queue import Queue, Empty
import threading
import time

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Thread-safe connection pool for pymssql."""
    
    def __init__(self, connection_params: Dict[str, Any], 
                 min_size: int = 2, 
                 max_size: int = 10,
                 timeout: float = 30.0):
        """
        Initialize connection pool.
        
        Args:
            connection_params: Parameters for pymssql.connect
            min_size: Minimum number of connections to maintain
            max_size: Maximum number of connections allowed
            timeout: Connection timeout in seconds
        """
        self._params = connection_params
        self._min_size = min_size
        self._max_size = max_size
        self._timeout = timeout
        self._pool = Queue(maxsize=max_size)
        self._size = 0
        self._lock = threading.Lock()
        self._closed = False
        
        # Pre-create minimum connections
        for _ in range(min_size):
            self._create_connection()
    
    def _create_connection(self) -> Optional[pymssql.Connection]:
        """Create a new database connection."""
        try:
            with self._lock:
                if self._size >= self._max_size:
                    return None
                self._size += 1
            
            conn = pymssql.connect(**self._params)
            self._pool.put(conn)
            logger.debug(f"Created new connection. Pool size: {self._size}")
            return conn
        except Exception as e:
            with self._lock:
                self._size -= 1
            logger.error(f"Failed to create connection: {e}")
            raise
    
    def get_connection(self) -> pymssql.Connection:
        """Get a connection from the pool."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        try:
            # Try to get from pool
            conn = self._pool.get(timeout=0.1)
            
            # Test if connection is alive
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            return conn
        except Empty:
            # Pool is empty, try to create new connection
            if self._size < self._max_size:
                conn = self._create_connection()
                if conn:
                    return self._pool.get()
            
            # Wait for a connection to be available
            return self._pool.get(timeout=self._timeout)
        except Exception:
            # Connection is dead, create a new one
            with self._lock:
                self._size -= 1
            self._create_connection()
            return self.get_connection()
    
    def release_connection(self, conn: pymssql.Connection):
        """Return a connection to the pool."""
        if self._closed:
            conn.close()
            return
        
        try:
            self._pool.put_nowait(conn)
        except:
            # Pool is full, close the connection
            conn.close()
            with self._lock:
                self._size -= 1
    
    def close(self):
        """Close all connections in the pool."""
        self._closed = True
        
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
        
        self._size = 0
        logger.info("Connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Async context manager for acquiring connections."""
        conn = None
        try:
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(None, self.get_connection)
            yield conn
        finally:
            if conn:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.release_connection, conn)
````

### 5. **Update Database Manager to Use Connection Pool**

````python
# Add import at the top
from .connection_pool import ConnectionPool

# Update DatabaseManager class
class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize database manager.
        
        Args:
            config: Database configuration
        """
        self.config = config
        self._connection_params = get_connection_params(config)
        
        # Initialize connection pool
        pool_min_size = int(os.getenv("MSSQL_POOL_MIN_SIZE", "2"))
        pool_max_size = int(os.getenv("MSSQL_POOL_MAX_SIZE", "10"))
        self._pool = ConnectionPool(
            self._connection_params,
            min_size=pool_min_size,
            max_size=pool_max_size
        )
        logger.info(f"Initialized connection pool (min={pool_min_size}, max={pool_max_size})")
    
    @asynccontextmanager
    async def get_connection(self):
        """
        Async context manager for database connections.
        
        Yields:
            Database connection
            
        Raises:
            DatabaseError: If connection fails
        """
        async with self._pool.acquire() as conn:
            yield conn
    
    def close(self):
        """Close the connection pool."""
        if hasattr(self, '_pool'):
            self._pool.close()
    
    def __del__(self):
        """Cleanup connection pool on deletion."""
        self.close()
````

### 6. **Add Health Check and Monitoring**

````python
# Add new tool for health checks
@mcp.tool()
async def health_check(ctx: Context) -> str:
    """
    Perform a health check on the database connection.
    
    Args:
        ctx: FastMCP context for logging
        
    Returns:
        Health status information
    """
    try:
        await ctx.info("Performing health check")
        start_time = time.time()
        
        db_manager, server_config = get_db_manager()
        
        # Test basic connectivity
        await ctx.report_progress(33, 100, "Testing database connection")
        async with db_manager.get_connection() as conn:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                cursor = conn.cursor()
                await loop.run_in_executor(executor, cursor.execute, "SELECT 1")
                cursor.close()
        
        # Get database version
        await ctx.report_progress(66, 100, "Getting database version")
        version_result = await db_manager.execute_query("SELECT @@VERSION")
        version = version_result["rows"][0][0] if version_result["rows"] else "Unknown"
        
        # Get connection pool status if available
        pool_status = {}
        if hasattr(db_manager, '_pool'):
            pool_status = {
                "pool_size": db_manager._pool._size,
                "pool_available": db_manager._pool._pool.qsize()
            }
        
        elapsed_time = time.time() - start_time
        
        response = MCPResponse(
            success=True,
            data={
                "status": "healthy",
                "database": db_manager.config.database,
                "server": db_manager.config.server,
                "version": version[:100] + "..." if len(version) > 100 else version,
                "response_time_ms": round(elapsed_time * 1000, 2),
                **pool_status
            },
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "server_config": {
                    "max_rows": server_config.max_rows,
                    "command_name": server_config.command_name
                }
            }
        )
        
        await ctx.report_progress(100, 100, "Health check completed")
        await ctx.info(f"Health check completed in {elapsed_time:.2f}s")
        return response.to_json()
        
    except Exception as e:
        await ctx.error(f"Health check failed: {e}")
        response = MCPResponse(
            success=False,
            error=f"Health check failed: {str(e)}",
            data={"status": "unhealthy"}
        )
        return response.to_json()
````

### 7. **Add Request Rate Limiting**

````python
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
````

### 8. **Configuration Enhancement**

Add environment-based configuration profiles:

````python
# Add at the end of the file

def load_config_profile() -> str:
    """Load configuration profile from environment."""
    return os.getenv("MCP_CONFIG_PROFILE", "production").lower()


def get_profile_settings(profile: str) -> Dict[str, Any]:
    """Get settings for a specific profile."""
    profiles = {
        "development": {
            "log_level": "DEBUG",
            "max_rows": 1000,
            "pool_min_size": 1,
            "pool_max_size": 5,
            "rate_limit": 600,  # 600 requests per minute
            "rate_burst": 20,
        },
        "production": {
            "log_level": "INFO", 
            "max_rows": 100,
            "pool_min_size": 2,
            "pool_max_size": 10,
            "rate_limit": 60,
            "rate_burst": 10,
        },
        "testing": {
            "log_level": "DEBUG",
            "max_rows": 10,
            "pool_min_size": 1,
            "pool_max_size": 2,
            "rate_limit": 1000,
            "rate_burst": 100,
        }
    }
    
    return profiles.get(profile, profiles["production"])


# Update ServerConfig to use profiles
@field_validator('max_rows')
def validate_max_rows(cls, v):
    profile = load_config_profile()
    profile_settings = get_profile_settings(profile)
    default_max = profile_settings["max_rows"]
    
    if v is None:
        return default_max
    if v < 1:
        raise ValueError("max_rows must be at least 1")
    if v > 10000:
        raise ValueError("max_rows cannot exceed 10000")
    return v
````

### 9. **Add Streaming Support for Large Results**

````python
# Add new tool for streaming large results
@mcp.tool()
async def execute_sql_stream(
    query: str, 
    batch_size: int = 1000,
    ctx: Context
) -> AsyncGenerator[str, None]:
    """
    Execute a SQL query and stream results in batches.
    
    Args:
        query: SQL query to execute
        batch_size: Number of rows per batch
        ctx: FastMCP context
        
    Yields:
        Batches of results as JSON strings
    """
    try:
        await ctx.info(f"Executing streaming query: {query[:100]}...")
        
        db_manager, _ = get_db_manager()
        
        # Validate query must be SELECT
        if not query.strip().upper().startswith("SELECT"):
            raise SecurityError("Streaming is only supported for SELECT queries")
        
        async with db_manager.get_connection() as conn:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                cursor = conn.cursor()
                await loop.run_in_executor(executor, cursor.execute, query)
                
                columns = [desc[0] for desc in cursor.description]
                total_rows = 0
                
                while True:
                    # Fetch batch
                    rows = await loop.run_in_executor(
                        executor, 
                        cursor.fetchmany, 
                        batch_size
                    )
                    
                    if not rows:
                        break
                    
                    total_rows += len(rows)
                    
                    # Format batch as JSON
                    batch_data = []
                    for row in rows:
                        batch_data.append(dict(zip(columns, row)))
                    
                    response = MCPResponse(
                        success=True,
                        data=batch_data,
                        metadata={
                            "batch_size": len(rows),
                            "total_rows_so_far": total_rows,
                            "columns": columns
                        }
                    )
                    
                    await ctx.report_progress(
                        total_rows, 
                        total_rows + 1000,  # Estimate
                        f"Streamed {total_rows} rows"
                    )
                    
                    yield response.to_json()
                
                # Final summary
                summary = MCPResponse(
                    success=True,
                    data={"streaming_complete": True},
                    metadata={
                        "total_rows": total_rows,
                        "columns": columns
                    }
                )
                yield summary.to_json()
                
    except Exception as e:
        await ctx.error(f"Streaming query failed: {e}")
        error_response = MCPResponse(
            success=False,
            error=str(e)
        )
        yield error_response.to_json()
````

### 10. **Add Caching Layer**

````python
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
````

## Summary of Improvements

1. **Multi-Transport Support**: Added support for both stdio and SSE transports
2. **Structured Responses**: Implemented consistent response formatting with metadata
3. **Connection Pooling**: Added efficient connection pool management
4. **Rate Limiting**: Implemented token bucket rate limiting
5. **Health Monitoring**: Added health check endpoint
6. **Streaming Support**: Added ability to stream large result sets
7. **Caching Layer**: Implemented LRU cache for frequently accessed data
8. **Configuration Profiles**: Added environment-based configuration profiles
9. **Better Error Handling**: Structured error responses with proper logging
10. **Output Formats**: Support for CSV, JSON, and Markdown output formats
