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
import asyncio
import logging
import signal
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager

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


async def initialize_server(profile: Optional[str] = None, config_file: Optional[str] = None) -> None:
    """Initialize server components with configuration."""
    global app_config, db_manager, connection_pool, rate_limiter, cache, logger
    global health_handler, tables_handler, query_handler, schema_handler, admin_handler
    global request_logger
    
    # Load configuration
    app_config = load_config(profile, config_file)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, app_config.server.log_level.value),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Initializing MSSQL MCP Server with modular architecture")
    logger.info(f"Transport: {app_config.server.transport.value}")
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


# Initialize FastMCP server with multi-transport support
def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server."""
    server = FastMCP(
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
    
    return server


# Create server instance
mcp = create_mcp_server()


# ==============================================================================
# MCP RESOURCES - Using Handler Pattern
# ==============================================================================

@mcp.resource("mssql://health", name="Server Health", description="Check server health and status")
async def health_check_resource(ctx: Context) -> str:
    """Check server health and database connectivity."""
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
async def read_table_resource(table_name: str, ctx: Context) -> str:
    """Read data from a specific table with advanced features."""
    if request_logger:
        await request_logger.log_request(ctx, "read_table", table_name=table_name)
    
    start_time = datetime.utcnow()
    try:
        result = await tables_handler.read_table(table_name, ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "read_table", True, duration, table_name=table_name)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "read_table", False, duration, table_name=table_name, error=str(e))
        raise


# ==============================================================================
# MCP TOOLS - Using Handler Pattern
# ==============================================================================

@mcp.tool()
async def execute_sql(query: str, ctx: Context, output_format: str = "csv") -> str:
    """
    Execute a SQL query on the database with advanced features.
    
    Args:
        query: SQL query to execute
        ctx: FastMCP context for logging and progress reporting
        output_format: Output format (csv, json, markdown, table)
        
    Returns:
        Query results in requested format
    """
    if request_logger:
        await request_logger.log_request(ctx, "execute_sql", query_length=len(query))
    
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


@mcp.tool()
async def get_table_schema(table_name: str, ctx: Context, output_format: str = "markdown") -> str:
    """
    Get the schema information for a specific table.
    
    Args:
        table_name: Name of the table to describe
        ctx: FastMCP context for logging and progress reporting
        output_format: Output format (csv, json, markdown, table)
        
    Returns:
        Table schema information in requested format
    """
    if request_logger:
        await request_logger.log_request(ctx, "get_table_schema", table_name=table_name)
    
    start_time = datetime.utcnow()
    try:
        result = await schema_handler.get_table_schema(table_name, ctx, output_format)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "get_table_schema", True, duration, table_name=table_name)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "get_table_schema", False, duration, table_name=table_name, error=str(e))
        raise


@mcp.tool()
async def list_databases(ctx: Context, output_format: str = "json") -> str:
    """
    List all databases on the server (requires appropriate permissions).
    
    Args:
        ctx: FastMCP context for logging and progress reporting
        output_format: Output format (csv, json, markdown, table)
        
    Returns:
        List of available databases in requested format
    """
    if request_logger:
        await request_logger.log_request(ctx, "list_databases")
    
    start_time = datetime.utcnow()
    try:
        result = await schema_handler.list_databases(ctx, output_format)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_databases", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "list_databases", False, duration, error=str(e))
        raise


@mcp.tool()
async def get_server_info(ctx: Context) -> str:
    """
    Get detailed server and configuration information.
    
    Args:
        ctx: FastMCP context for logging and progress reporting
        
    Returns:
        Server information in JSON format
    """
    if request_logger:
        await request_logger.log_request(ctx, "get_server_info")
    
    start_time = datetime.utcnow()
    try:
        result = await admin_handler.get_server_info(ctx)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "get_server_info", True, duration)
        
        return result
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "get_server_info", False, duration, error=str(e))
        raise


@mcp.tool()
async def cache_stats(ctx: Context) -> str:
    """
    Get cache statistics and performance metrics.
    
    Args:
        ctx: FastMCP context for logging
        
    Returns:
        Cache statistics in JSON format
    """
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


@mcp.tool()
async def clear_cache(ctx: Context) -> str:
    """
    Clear the query cache.
    
    Args:
        ctx: FastMCP context for logging
        
    Returns:
        Cache clear status
    """
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


@mcp.tool()
async def get_metrics(ctx: Context) -> str:
    """
    Get comprehensive server metrics.
    
    Args:
        ctx: FastMCP context for logging
        
    Returns:
        Server metrics in JSON format
    """
    if request_logger:
        await request_logger.log_request(ctx, "get_metrics")
    
    start_time = datetime.utcnow()
    try:
        metrics = await metrics_collector.get_metrics()
        
        # Add server-specific metrics
        if connection_pool:
            metrics["connection_pool"] = await admin_handler.connection_pool_stats(ctx)
        
        if cache:
            cache_metrics = await admin_handler.cache_stats(ctx)
            metrics["cache"] = cache_metrics
        
        response = MCPResponse(success=True, data=metrics)
        
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "get_metrics", True, duration)
        
        return response.to_json()
    except Exception as e:
        if request_logger:
            duration = (datetime.utcnow() - start_time).total_seconds()
            await request_logger.log_response(ctx, "get_metrics", False, duration, error=str(e))
        raise


# ==============================================================================
# SERVER LIFECYCLE MANAGEMENT
# ==============================================================================

async def cleanup_server():
    """Cleanup server resources."""
    global connection_pool, cache
    
    logger.info("Cleaning up server resources...")
    
    if connection_pool:
        await connection_pool.close()
        logger.info("Connection pool closed")
    
    if cache:
        await cache.clear()
        logger.info("Cache cleared")
    
    logger.info("Server cleanup completed")


async def run_stdio_server():
    """Run the server with stdio transport."""
    try:
        await initialize_server()
        logger.info("Starting MCP server with stdio transport...")
        await mcp.run_stdio()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    finally:
        await cleanup_server()


async def run_sse_server():
    """Run the server with SSE transport."""
    try:
        await initialize_server()
        port = app_config.server.sse_port
        logger.info(f"Starting MCP server with SSE transport on port {port}...")
        await mcp.run_sse(port=port, host="0.0.0.0")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    finally:
        await cleanup_server()


async def main():
    """Main entry point to run the MCP server with modular architecture."""
    # Parse command line arguments for configuration
    profile = os.getenv("MCP_PROFILE")
    config_file = os.getenv("MCP_CONFIG_FILE")
    
    # Load initial configuration to determine transport
    temp_config = load_config(profile, config_file)
    
    if temp_config.server.transport == TransportType.SSE:
        await run_sse_server()
    else:
        await run_stdio_server()


def get_mcp_server():
    """Get the FastMCP server instance for testing and external use."""
    return mcp


# Health check endpoint for external monitoring
async def health_endpoint():
    """Standalone health check function."""
    try:
        if not app_config:
            return {"status": "not_initialized", "error": "Server not initialized"}
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "transport": app_config.server.transport.value,
            "architecture": "modular_handlers"
        }
        
        if db_manager:
            db_health = await db_manager.test_connection()
            health_data["database"] = db_health
        
        if metrics_collector:
            summary = await metrics_collector.get_summary()
            health_data["metrics_summary"] = summary
        
        return health_data
        
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the server
    asyncio.run(main())
