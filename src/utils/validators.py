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


class TableNameValidator:
    """Validate table names for security."""
    
    @staticmethod
    def validate_table_name(table_name: str) -> str:
        """
        Validate and sanitize table name.
        
        Args:
            table_name: The table name to validate
            
        Returns:
            Sanitized table name
            
        Raises:
            ValueError: If table name is invalid
        """
        if not table_name or not table_name.strip():
            raise ValueError("Table name cannot be empty")
        
        # Remove extra whitespace
        table_name = table_name.strip()
        
        # Check for basic SQL injection patterns
        dangerous_patterns = [
            r'[;\'"]',  # SQL injection characters
            r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)\b',  # DDL/DML keywords
            r'--',  # SQL comments
            r'/\*'  # Multi-line comments
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, table_name, re.IGNORECASE):
                raise ValueError(f"Table name contains invalid characters or keywords: {table_name}")
        
        # Validate format (allow schema.table format)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$', table_name):
            raise ValueError(f"Invalid table name format: {table_name}")
        
        return table_name


# Convenience functions that match the import expectations
def validate_sql_query(query: str, allow_ddl: bool = False, allow_dml: bool = True, max_length: int = 10000) -> Optional[str]:
    """
    Convenience function to validate SQL query.
    
    Args:
        query: SQL query to validate
        allow_ddl: Whether to allow DDL operations
        allow_dml: Whether to allow DML operations
        max_length: Maximum query length
        
    Returns:
        Error message if invalid, None if valid
    """
    return QueryValidator.validate_query(query, allow_ddl, allow_dml, max_length)


def sanitize_table_name(table_name: str) -> str:
    """
    Convenience function to sanitize table name.
    
    Args:
        table_name: The table name to sanitize
        
    Returns:
        Sanitized table name
        
    Raises:
        ValueError: If table name is invalid
    """
    return TableNameValidator.validate_table_name(table_name)
