"""Administrative operations handler module."""

from typing import Dict, Any
from datetime import datetime
from fastmcp import Context

from .base import BaseHandler
from ..config import OutputFormat


class AdminHandler(BaseHandler):
    """Handle administrative and server management requests."""
    
    def __init__(self, app_config, db_manager, connection_pool, cache, rate_limiter):
        super().__init__(app_config, db_manager, connection_pool, cache, rate_limiter)
    
    async def get_server_info(self, ctx: Context) -> str:
        """
        Get detailed server and configuration information.
        
        Args:
            ctx: FastMCP context for logging and progress reporting
            
        Returns:
            Server information in JSON format
        """
        try:
            await ctx.info("Retrieving server information")
            
            server_info = {
                "server_name": "MSSQL MCP Server",
                "version": "2.0.0",
                "transport": self.app_config.server.transport.value,
                "features": {
                    "caching": self.app_config.server.enable_caching,
                    "rate_limiting": self.app_config.server.enable_rate_limiting,
                    "health_checks": self.app_config.server.enable_health_checks,
                    "streaming": self.app_config.server.enable_streaming
                },
                "configuration": {
                    "max_rows": self.app_config.server.max_rows,
                    "query_timeout": self.app_config.server.query_timeout,
                    "max_concurrent_queries": self.app_config.server.max_concurrent_queries,
                    "default_output_format": self.app_config.server.default_output_format.value
                },
                "database": {
                    "server": self.app_config.database.server,
                    "database": self.app_config.database.database,
                    "port": self.app_config.database.port,
                    "encrypt": self.app_config.database.encrypt
                }
            }
            
            if self.connection_pool:
                server_info["connection_pool"] = {
                    "min_connections": self.connection_pool._min_size,
                    "max_connections": self.connection_pool._max_size,
                    "current_size": self.connection_pool._size,
                    "available": self.connection_pool._pool.qsize()
                }
            
            if self.cache:
                server_info["cache"] = {
                    "max_size": self.cache.max_size,
                    "current_size": len(self.cache.cache),
                    "ttl_seconds": self.cache.ttl
                }
            
            if self.rate_limiter:
                server_info["rate_limiting"] = {
                    "requests_per_minute": self.rate_limiter.rate,
                    "burst_limit": self.rate_limiter.burst
                }
            
            return self.format_response(server_info, OutputFormat.JSON)
            
        except Exception as e:
            await ctx.error(f"Error retrieving server info: {e}")
            return self.format_response({"error": f"Error: {e}"}, OutputFormat.JSON)
    
    async def cache_stats(self, ctx: Context) -> str:
        """
        Get cache statistics and performance metrics.
        
        Args:
            ctx: FastMCP context for logging
            
        Returns:
            Cache statistics in JSON format
        """
        try:
            await ctx.info("Retrieving cache statistics")
            
            if not self.cache:
                return self.format_response(
                    {"message": "Cache is not enabled"},
                    OutputFormat.JSON
                )
            
            stats = await self.cache.stats()
            
            cache_info = {
                "cache_enabled": True,
                "statistics": stats,
                "performance": {
                    "hit_rate": getattr(self.cache, 'hit_rate', 0.0),
                    "total_requests": getattr(self.cache, 'total_requests', 0),
                    "cache_hits": getattr(self.cache, 'cache_hits', 0)
                }
            }
            
            return self.format_response(cache_info, OutputFormat.JSON)
            
        except Exception as e:
            await ctx.error(f"Error getting cache stats: {e}")
            return self.format_response({"error": str(e)}, OutputFormat.JSON)
    
    async def clear_cache(self, ctx: Context) -> str:
        """
        Clear the query cache.
        
        Args:
            ctx: FastMCP context for logging
            
        Returns:
            Cache clear status
        """
        try:
            await ctx.info("Clearing cache")
            
            if not self.cache:
                return self.format_response(
                    {"message": "Cache is not enabled"},
                    OutputFormat.JSON
                )
            
            await self.cache.clear()
            
            result = {
                "message": "Cache cleared successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await ctx.info("Cache cleared successfully")
            return self.format_response(result, OutputFormat.JSON)
            
        except Exception as e:
            await ctx.error(f"Error clearing cache: {e}")
            return self.format_response({"error": str(e)}, OutputFormat.JSON)
    
    async def connection_pool_stats(self, ctx: Context) -> str:
        """
        Get connection pool statistics and status.
        
        Args:
            ctx: FastMCP context for logging
            
        Returns:
            Connection pool statistics in JSON format
        """
        try:
            await ctx.info("Retrieving connection pool statistics")
            
            if not self.connection_pool:
                return self.format_response(
                    {"message": "Connection pool is not enabled"},
                    OutputFormat.JSON
                )
            
            pool_stats = {
                "enabled": True,
                "min_size": self.connection_pool._min_size,
                "max_size": self.connection_pool._max_size,
                "current_size": self.connection_pool._size,
                "available": self.connection_pool._pool.qsize(),
                "in_use": self.connection_pool._size - self.connection_pool._pool.qsize(),
                "utilization_percent": round(
                    (self.connection_pool._size - self.connection_pool._pool.qsize()) / 
                    self.connection_pool._max_size * 100, 2
                ) if self.connection_pool._max_size > 0 else 0
            }
            
            return self.format_response(pool_stats, OutputFormat.JSON)
            
        except Exception as e:
            await ctx.error(f"Error getting connection pool stats: {e}")
            return self.format_response({"error": str(e)}, OutputFormat.JSON)
