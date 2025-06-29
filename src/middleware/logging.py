"""Enhanced logging middleware with structured output."""

import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import traceback
from fastmcp import Context


class StructuredLogger:
    """Structured logging with context."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.configure_logger()
    
    def configure_logger(self):
        """Configure logger with structured format."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _add_context(self, record: Dict[str, Any], context: Dict[str, Any]):
        """Add context to log record."""
        record['timestamp'] = datetime.now(timezone.utc).isoformat()
        record.update(context)
        return record
    
    def info(self, message: str, **context):
        """Log info with context."""
        record = self._add_context({'message': message}, context)
        self.logger.info(json.dumps(record) if context else message)
    
    def error(self, message: str, exception: Optional[Exception] = None, **context):
        """Log error with context and exception."""
        record = self._add_context({'message': message}, context)
        
        if exception:
            record['exception'] = {
                'type': type(exception).__name__,
                'message': str(exception),
                'traceback': traceback.format_exc()
            }
        
        self.logger.error(json.dumps(record) if (context or exception) else message)
    
    def warning(self, message: str, **context):
        """Log warning with context."""
        record = self._add_context({'message': message}, context)
        self.logger.warning(json.dumps(record) if context else message)
    
    def create_middleware(self):
        """Create logging middleware."""
        def middleware(func):
            async def wrapper(ctx: Context, *args, **kwargs):
                start_time = datetime.now(timezone.utc)
                request_id = getattr(ctx, 'request_id', 'unknown')
                
                self.info(
                    f"Starting {func.__name__}",
                    operation=func.__name__,
                    request_id=request_id,
                    args_count=len(args),
                    kwargs_keys=list(kwargs.keys())
                )
                
                try:
                    result = await func(ctx, *args, **kwargs)
                    
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                    self.info(
                        f"Completed {func.__name__}",
                        operation=func.__name__,
                        request_id=request_id,
                        duration=duration,
                        success=True
                    )
                    
                    return result
                    
                except Exception as e:
                    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
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


class RequestLogger:
    """Simple request logging for MCP operations."""
    
    def __init__(self, logger_name: str = "mcp.requests"):
        self.logger = StructuredLogger(logger_name)
    
    async def log_request(self, ctx: Context, operation: str, **kwargs):
        """Log incoming request."""
        self.logger.info(
            f"Request: {operation}",
            operation=operation,
            client_id=getattr(ctx, 'client_id', 'unknown'),
            **kwargs
        )
    
    async def log_response(self, ctx: Context, operation: str, success: bool, duration: float, **kwargs):
        """Log operation response."""
        level = self.logger.info if success else self.logger.error
        level(
            f"Response: {operation} ({'success' if success else 'failed'})",
            operation=operation,
            success=success,
            duration=duration,
            client_id=getattr(ctx, 'client_id', 'unknown'),
            **kwargs
        )
