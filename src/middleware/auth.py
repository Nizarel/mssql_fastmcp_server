"""Authentication and authorization middleware."""

import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from fastmcp import Context
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
    """Authentication middleware for MCP operations."""
    
    def __init__(self, enable_auth: bool = False):
        self.enable_auth = enable_auth
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, User] = {}
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user credentials."""
        if not self.enable_auth:
            return None
        
        # In a real implementation, this would check against a database
        # For now, return a placeholder
        return User(
            id="anonymous",
            username="anonymous",
            roles=["read"],
            permissions=["read"]
        )
    
    async def authorize_operation(self, user: Optional[User], operation: str) -> bool:
        """Check if user is authorized for operation."""
        if not self.enable_auth:
            return True
        
        if not user:
            return False
        
        # Simple permission check
        required_permissions = {
            "execute_sql": ["read", "write"],
            "read_table": ["read"],
            "list_tables": ["read"],
            "get_schema": ["read"],
            "list_databases": ["read"],
            "cache_stats": ["admin"],
            "clear_cache": ["admin"],
            "server_info": ["admin"]
        }
        
        required = required_permissions.get(operation, ["read"])
        return any(perm in user.permissions for perm in required)
    
    def require_permission(self, permission: str):
        """Decorator to require specific permission."""
        def decorator(func):
            async def wrapper(ctx: Context, *args, **kwargs):
                if not self.enable_auth:
                    return await func(ctx, *args, **kwargs)
                
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
