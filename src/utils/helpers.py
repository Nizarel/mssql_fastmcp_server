"""Helper utilities for the MCP server."""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
from fastmcp import Context


def generate_cache_key(*args: Any) -> str:
    """Generate a consistent cache key from arguments."""
    key_data = "|".join(str(arg) for arg in args)
    return hashlib.sha256(key_data.encode()).hexdigest()


def sanitize_sql_identifier(identifier: str) -> str:
    """Sanitize SQL identifier (table name, column name, etc.)."""
    # Remove any characters that aren't alphanumeric, underscore, or dot
    sanitized = re.sub(r'[^a-zA-Z0-9_.]', '', identifier)
    
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    
    return sanitized


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format datetime as ISO string with UTC timezone."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.isoformat()


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_json_serialize(obj: Any) -> str:
    """Safely serialize object to JSON, handling datetime and other types."""
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    try:
        return json.dumps(obj, default=json_serializer, indent=2)
    except (TypeError, ValueError) as e:
        return json.dumps({"error": f"Serialization failed: {str(e)}"})


def extract_table_name_from_query(query: str) -> Optional[str]:
    """Extract table name from a SELECT query for caching purposes."""
    # Simple regex to extract table name from SELECT queries
    # This is a basic implementation and might not cover all cases
    query_upper = query.upper().strip()
    
    if not query_upper.startswith('SELECT'):
        return None
    
    # Look for FROM clause
    from_match = re.search(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_.]*)', query_upper)
    if from_match:
        return from_match.group(1).lower()
    
    return None


def get_output_format_from_context(ctx: Context):
    """Extract output format from context or use default."""
    from config import OutputFormat
    
    if hasattr(ctx, 'params') and isinstance(ctx.params, dict):
        format_str = ctx.params.get('output_format', 'json')
    else:
        format_str = 'json'
    
    try:
        return OutputFormat(format_str.lower())
    except ValueError:
        return OutputFormat.JSON


def mask_sensitive_data(data: Dict[str, Any], sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Mask sensitive data in dictionaries for logging."""
    if sensitive_keys is None:
        sensitive_keys = ['password', 'secret', 'key', 'token', 'auth']
    
    masked_data = {}
    for key, value in data.items():
        if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            masked_data[key] = "***"
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value, sensitive_keys)
        elif isinstance(value, list):
            masked_data[key] = [
                mask_sensitive_data(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked_data[key] = value
    
    return masked_data


def calculate_size_in_bytes(obj: Any) -> int:
    """Estimate the size of an object in bytes."""
    if isinstance(obj, str):
        return len(obj.encode('utf-8'))
    elif isinstance(obj, (int, float)):
        return 8  # Approximate size
    elif isinstance(obj, bool):
        return 1
    elif isinstance(obj, (list, tuple)):
        return sum(calculate_size_in_bytes(item) for item in obj)
    elif isinstance(obj, dict):
        return sum(
            calculate_size_in_bytes(k) + calculate_size_in_bytes(v)
            for k, v in obj.items()
        )
    elif obj is None:
        return 0
    else:
        # For other types, return a rough estimate
        return len(str(obj)) * 2


def validate_connection_string(connection_string: str) -> bool:
    """Validate database connection string format."""
    # Basic validation for SQL Server connection strings
    required_params = ['server', 'database']
    
    # Convert to lowercase for case-insensitive checking
    conn_lower = connection_string.lower()
    
    # Check for required parameters
    for param in required_params:
        if param not in conn_lower:
            return False
    
    # Check for dangerous keywords
    dangerous_keywords = ['drop', 'delete', 'truncate', 'alter', 'create']
    for keyword in dangerous_keywords:
        if keyword in conn_lower:
            return False
    
    return True


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        return f"{hours}h {remaining_minutes}m"


def is_select_query(query: str) -> bool:
    """Check if a query is a SELECT statement."""
    return query.strip().upper().startswith('SELECT')


def is_modification_query(query: str) -> bool:
    """Check if a query is a data modification statement."""
    query_upper = query.strip().upper()
    modification_keywords = ['INSERT', 'UPDATE', 'DELETE', 'MERGE']
    return any(query_upper.startswith(keyword) for keyword in modification_keywords)
