"""
MSSQL MCP Server using FastMCP 2.9.2 - Refactored with Modular Handlers.

A modern Model Context Protocol server that provides secure access to Microsoft SQL Server databases.
Built with FastMCP and implements modern MCP best practices including:
- Multi-transport support (stdio/SSE)
- Modular handler architecture
- Connection pooling
- Rate limiting 
- Response caching
- Structured output formats
- Health checks and monitoring
- Advanced error handling
"""

import os
import sys
import logging
import atexit
from typing import Optional
from datetime import datetime

from fastmcp import FastMCP, Context

from config import (
    AppConfig, load_config, get_config, TransportType, OutputFormat, LogLevel
)
from core.database import DatabaseManager
from core.connection_pool import ConnectionPool
from core.rate_limiter import RateLimiter
from core.cache import LRUCache
from core.response_formatter import MCPResponse

# Import all handlers
from handlers import (
    HealthHandler, TablesHandler, QueryHandler, 
    SchemaHandler, AdminHandler
)

# Import middleware
from middleware import metrics_collector, StructuredLogger, RequestLogger

# Global application state
app_config: Optional[AppConfig] = None
db_manager: Optional[DatabaseManager] = None
connection_pool: Optional[ConnectionPool] = None
rate_limiter: Optional[RateLimiter] = None
cache: Optional[LRUCache] = None
logger = None

# Handler instances
health_handler: Optional[HealthHandler] = None
tables_handler: Optional[TablesHandler] = None
query_handler: Optional[QueryHandler] = None
schema_handler: Optional[SchemaHandler] = None
admin_handler: Optional[AdminHandler] = None

# Middleware instances
request_logger: Optional[RequestLogger] = None

async def ensure_initialized():
    """Ensure server components are initialized."""
    global app_config, db_manager, connection_pool, rate_limiter, cache, logger
    global health_handler, tables_handler, query_handler, schema_handler, admin_handler
    global request_logger

    if app_config is not None:  # Already initialized
        return

    # Load configuration
    profile = os.getenv("MCP_PROFILE")
    config_file = os.getenv("MCP_CONFIG_FILE")
    app_config = load_config(profile, config_file)

    # Configure logging
    log_level = app_config.server.log_level
    if hasattr(log_level, 'value'):
        log_level_str = log_level.value
    else:
        log_level_str = str(log_level)
    logging.basicConfig(
        level=getattr(logging, log_level_str),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)
    logger.info("Initializing MSSQL MCP Server with modular architecture")

    # Safe transport value extraction
    transport_value = app_config.server.transport
    if hasattr(transport_value, 'value'):
        transport_str = transport_value.value
    else:
        transport_str = str(transport_value)
    logger.info(f"Transport: {transport_str}")
    logger.info(f"Features: caching={app_config.server.enable_caching}, "
               f"rate_limiting={app_config.server.enable_rate_limiting}, "
               f"health_checks={app_config.server.enable_health_checks}")

    # Initialize connection pool
    if app_config.server.connection_pool.max_connections > 0:
        try:
            connection_pool = ConnectionPool(
                connection_params=app_config.database.get_pymssql_params(),
                min_size=app_config.server.connection_pool.min_connections,
                max_size=app_config.server.connection_pool.max_connections,
                timeout=app_config.server.connection_pool.connection_timeout
            )
            logger.info(f"Connection pool initialized: "
                       f"{app_config.server.connection_pool.min_connections}-"
                       f"{app_config.server.connection_pool.max_connections} connections")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    # Initialize database manager
    db_manager = DatabaseManager(app_config.database, connection_pool)

    # Initialize rate limiter
    if app_config.server.enable_rate_limiting:
        rate_limiter = RateLimiter(
            rate=app_config.server.rate_limit.requests_per_minute,
            burst=app_config.server.rate_limit.burst_limit
        )
        logger.info(f"Rate limiter initialized: "
                   f"{app_config.server.rate_limit.requests_per_minute} rpm, "
                   f"burst {app_config.server.rate_limit.burst_limit}")

    # Initialize cache
    if app_config.server.enable_caching:
        cache = LRUCache(
            max_size=app_config.server.cache.max_size,
            ttl=app_config.server.cache.ttl_seconds
        )
        logger.info(f"Cache initialized: max_size={app_config.server.cache.max_size}, "
                   f"ttl={app_config.server.cache.ttl_seconds}s")

    # Test database connection
    try:
        test_result = await db_manager.test_connection()
        if test_result["success"]:
            logger.info("Database connection test successful")
        else:
            logger.error(f"Database connection test failed: {test_result.get('error')}")
            raise Exception(f"Connection test failed: {test_result.get('error')}")
    except Exception as e:
        logger.error(f"Failed to test database connection: {e}")
        raise

    # Initialize middleware
    request_logger = RequestLogger("mcp.requests")

    # Initialize handler instances
    health_handler = HealthHandler(app_config, db_manager, connection_pool, cache, rate_limiter)
    tables_handler = TablesHandler(app_config, db_manager, connection_pool, cache, rate_limiter)
    query_handler = QueryHandler(app_config, db_manager, connection_pool, cache, rate_limiter)
    schema_handler = SchemaHandler(app_config, db_manager, connection_pool, cache, rate_limiter)
    admin_handler = AdminHandler(app_config, db_manager, connection_pool, cache, rate_limiter)
    logger.info("All handlers initialized successfully")

async def cleanup_components():
    """Cleanup server resources."""
    global connection_pool, cache, logger
    
    if logger:
        logger.info("Cleaning up server resources...")
    
    if connection_pool:
        await connection_pool.close()
        if logger:
            logger.info("Connection pool closed")
    
    if cache:
        await cache.clear()
        if logger:
            logger.info("Cache cleared")
    
    if logger:
        logger.info("Server cleanup completed")

# Register cleanup function
atexit.register(lambda: cleanup_components())

# Create FastMCP server instance
mcp = FastMCP(
    name="Microsoft SQL Server MCP",
    instructions=(
        "Advanced MCP server for Microsoft SQL Server with modern modular architecture:\n"
        "• Multi-transport support (stdio/SSE)\n"
        "• Modular handler architecture for maintainability\n"
        "• Connection pooling for performance\n"
        "• Rate limiting and caching\n"
        "• Multiple output formats (CSV, JSON, Markdown)\n"
        "• Health monitoring and structured responses\n"
        "• Secure query execution with validation\n"
        "• Comprehensive metrics and logging"
    )
)

# ==============================================================================
# MCP RESOURCES - Using Handler Pattern
# ==============================================================================

@mcp.resource("mssql://health", name="Server Health", description="Check server health and status")
async def health_check_resource(ctx: Context) -> str:
    """Check server health and database connectivity."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "health_check")
    
    start_time = datetime.utcnow()
    try:
        result = await health_handler.check_health(ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "health_check", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "health_check", False, duration, error=str(e))
        raise

@mcp.resource("mssql://tables", name="Database Tables", description="List all available tables in the database")
async def list_tables_resource(ctx: Context) -> str:
    """List all available tables in the database with caching support."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "list_tables")
    
    start_time = datetime.utcnow()
    try:
        result = await tables_handler.list_tables(ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_tables", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_tables", False, duration, error=str(e))
        raise

@mcp.resource("mssql://table/{table_name}", name="Table Data", description="Read data from a specific table")
async def read_table_resource(ctx: Context, table_name: str) -> str:
    """Read data from a specific table with pagination and formatting."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "read_table", table_name=table_name)
    
    start_time = datetime.utcnow()
    try:
        result = await tables_handler.read_table(table_name, ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "read_table", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "read_table", False, duration, error=str(e))
        raise

@mcp.resource("mssql://schema/{table_name}", name="Table Schema", description="Get schema information for a table")
async def table_schema_resource(ctx: Context, table_name: str) -> str:
    """Get detailed schema information for a table."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "table_schema", table_name=table_name)
    
    start_time = datetime.utcnow()
    try:
        result = await schema_handler.get_table_schema(table_name, ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "table_schema", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "table_schema", False, duration, error=str(e))
        raise

@mcp.resource("mssql://databases", name="Database List", description="List all accessible databases")
async def list_databases_resource(ctx: Context) -> str:
    """List all accessible databases on the server."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "list_databases")
    
    start_time = datetime.utcnow()
    try:
        result = await schema_handler.list_databases(ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_databases", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_databases", False, duration, error=str(e))
        raise

# ==============================================================================
# MCP TOOLS - Interactive Operations
# ==============================================================================

@mcp.tool(name="execute_sql", description="Execute a SQL query on the database")
async def execute_sql_tool(ctx: Context, query: str, output_format: str = "csv") -> str:
    """
    Execute a SQL query and return results.
    
    Args:
        query: The SQL query to execute
        output_format: Output format (csv, json, markdown, table)
    """
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "execute_sql", query=query[:100])
    
    start_time = datetime.utcnow()
    try:
        result = await query_handler.execute_sql(query, ctx, output_format)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "execute_sql", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "execute_sql", False, duration, error=str(e))
        raise

@mcp.tool(name="read_table", description="Read data from a database table with optional pagination")
async def read_table_tool(ctx: Context, table_name: str, limit: int = 100, offset: int = 0, output_format: str = "csv") -> str:
    """
    Read data from a database table.
    
    Args:
        table_name: Name of the table to read
        limit: Maximum number of rows to return (default: 100)
        offset: Number of rows to skip (default: 0)
        output_format: Output format (csv, json, markdown, table)
    """
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "read_table_tool", table_name=table_name, limit=limit, offset=offset)
    
    start_time = datetime.utcnow()
    try:
        result = await tables_handler.read_table(table_name, ctx, limit, offset, output_format)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "read_table_tool", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "read_table_tool", False, duration, error=str(e))
        raise

@mcp.tool(name="get_table_schema", description="Get schema information for a database table")
async def get_table_schema_tool(ctx: Context, table_name: str, output_format: str = "markdown") -> str:
    """
    Get schema information for a table.
    
    Args:
        table_name: Name of the table
        output_format: Output format (markdown, json, csv, table)
    """
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "get_table_schema", table_name=table_name)
    
    start_time = datetime.utcnow()
    try:
        result = await schema_handler.get_table_schema(table_name, ctx, output_format)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "get_table_schema", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "get_table_schema", False, duration, error=str(e))
        raise

@mcp.tool(name="list_tables", description="List all tables in the database")
async def list_tables_tool(ctx: Context, output_format: str = "json") -> str:
    """
    List all tables in the database.
    
    Args:
        output_format: Output format (json, csv, markdown, table)
    """
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "list_tables_tool")
    
    start_time = datetime.utcnow()
    try:
        result = await tables_handler.list_tables(ctx, output_format)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_tables_tool", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_tables_tool", False, duration, error=str(e))
        raise

@mcp.tool(name="list_databases", description="List all accessible databases")
async def list_databases_tool(ctx: Context, output_format: str = "json") -> str:
    """
    List all accessible databases on the server.
    
    Args:
        output_format: Output format (json, csv, markdown, table)
    """
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "list_databases_tool")
    
    start_time = datetime.utcnow()
    try:
        result = await schema_handler.list_databases(ctx, output_format)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_databases_tool", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_databases_tool", False, duration, error=str(e))
        raise

# ==============================================================================
# ADMINISTRATIVE TOOLS
# ==============================================================================

@mcp.tool(name="server_info", description="Get server configuration and status information")
async def server_info_tool(ctx: Context) -> str:
    """Get detailed server configuration and status information."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "server_info")
    
    start_time = datetime.utcnow()
    try:
        result = await admin_handler.get_server_info(ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "server_info", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "server_info", False, duration, error=str(e))
        raise

@mcp.tool(name="cache_stats", description="Get cache statistics and information")
async def cache_stats_tool(ctx: Context) -> str:
    """Get cache statistics and information."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "cache_stats")
    
    start_time = datetime.utcnow()
    try:
        result = await admin_handler.cache_stats(ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "cache_stats", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "cache_stats", False, duration, error=str(e))
        raise

@mcp.tool(name="clear_cache", description="Clear the query cache")
async def clear_cache_tool(ctx: Context) -> str:
    """Clear the query cache."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "clear_cache")
    
    start_time = datetime.utcnow()
    try:
        result = await admin_handler.clear_cache(ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "clear_cache", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "clear_cache", False, duration, error=str(e))
        raise

@mcp.tool(name="connection_pool_stats", description="Get connection pool statistics")
async def connection_pool_stats_tool(ctx: Context) -> str:
    """Get connection pool statistics."""
    await ensure_initialized()
    
    if request_logger:
        await request_logger.log_request(ctx, "connection_pool_stats")
    
    start_time = datetime.utcnow()
    try:
        result = await admin_handler.connection_pool_stats(ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "connection_pool_stats", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "connection_pool_stats", False, duration, error=str(e))
        raise

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    """Main entry point for the server."""
    try:
        # Let FastMCP handle transport detection and run appropriately
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        if logger:
            logger.error(f"Server error: {e}", exc_info=True)
        else:
            print(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
