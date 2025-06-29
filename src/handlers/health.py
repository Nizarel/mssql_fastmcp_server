"""Health check handler."""

from typing import Dict, Any
from datetime import datetime, timezone
from fastmcp import Context

from .base import BaseHandler
from core.database import DatabaseError


class HealthHandler(BaseHandler):
    """Handle health check requests."""
    
    def __init__(self, app_config, db_manager, connection_pool, cache, rate_limiter):
        super().__init__(app_config, db_manager, connection_pool, cache, rate_limiter)
    
    async def check_health(self, ctx: Context) -> str:
        """Check server health and database connectivity."""
        try:
            if not self.app_config.server.enable_health_checks:
                return self.format_response(
                    {"status": "disabled", "message": "Health checks are disabled"},
                    self.get_output_format(ctx)
                )
            
            await ctx.info("Performing health check")
            
            health_data = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "server_info": {
                    "transport": self.app_config.server.transport.value,
                    "features": {
                        "caching": self.app_config.server.enable_caching,
                        "rate_limiting": self.app_config.server.enable_rate_limiting,
                        "streaming": self.app_config.server.enable_streaming
                    }
                }
            }
            
            # Check database connectivity
            if self.db_manager:
                db_health = await self.db_manager.test_connection()
                health_data["database"] = db_health
            
            # Check connection pool status
            if self.connection_pool:
                health_data["connection_pool"] = {
                    "size": self.connection_pool._size,
                    "max_size": self.connection_pool._max_size,
                    "available": self.connection_pool._pool.qsize()
                }
            
            # Check cache status
            if self.cache:
                health_data["cache"] = {
                    "size": len(self.cache.cache),
                    "max_size": self.cache.max_size,
                    "hit_rate": getattr(self.cache, 'hit_rate', 0.0)
                }
            
            return self.format_response(health_data, self.get_output_format(ctx))
            
        except Exception as e:
            await ctx.error(f"Health check failed: {e}")
            return self.format_response(
                {"status": "unhealthy", "error": str(e)},
                self.get_output_format(ctx)
            )
