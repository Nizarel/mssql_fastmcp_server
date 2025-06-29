"""Base handler with common functionality."""

from typing import Optional, Dict, Any
from fastmcp import Context

from config import AppConfig, OutputFormat
from core.response_formatter import MCPResponse


class BaseHandler:
    """Base handler with common functionality."""
    
    def __init__(self, app_config: AppConfig, db_manager, connection_pool, cache, rate_limiter):
        self.app_config = app_config
        self.db_manager = db_manager
        self.connection_pool = connection_pool
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
    
    def format_response(self, data: Any, output_format: OutputFormat, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Format response based on requested output format."""
        from core.response_formatter import TableFormatter
        
        response = MCPResponse(
            success=True,
            data=data,
            metadata=metadata or {}
        )
        
        if output_format == OutputFormat.JSON:
            return response.to_json()
        elif isinstance(data, dict) and "columns" in data and "rows" in data:
            # Table data
            display_rows = min(len(data["rows"]), self.app_config.server.max_rows)
            if output_format == OutputFormat.CSV:
                return TableFormatter.to_csv(data["columns"], data["rows"])
            elif output_format == OutputFormat.MARKDOWN:
                return TableFormatter.to_markdown(data["columns"], data["rows"], display_rows)
            elif output_format == OutputFormat.TABLE:
                return TableFormatter.to_markdown(data["columns"], data["rows"], display_rows)
        
        # Default to string representation
        return str(data)
