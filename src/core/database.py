"""Database operations for MSSQL MCP Server."""

import re
import logging
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Tuple, Optional
from contextlib import asynccontextmanager
import pymssql
from config import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass


def validate_table_name(table_name: str) -> str:
    """
    Validate and escape table name to prevent SQL injection.
    
    Args:
        table_name: The table name to validate
        
    Returns:
        Escaped table name safe for SQL queries
        
    Raises:
        SecurityError: If table name contains invalid characters
    """
    # Allow only alphanumeric, underscore, and dot (for schema.table)
    if not re.match(r'^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)?$', table_name):
        raise SecurityError(f"Invalid table name: {table_name}")
    
    # Split schema and table if present
    parts = table_name.split('.')
    if len(parts) == 2:
        # Escape both schema and table name
        return f"[{parts[0]}].[{parts[1]}]"
    else:
        # Just table name
        return f"[{table_name}]"


def validate_sql_query(query: str) -> None:
    """
    Basic SQL query validation.
    
    Args:
        query: SQL query to validate
        
    Raises:
        SecurityError: If query contains potentially dangerous patterns
    """
    if not query or not query.strip():
        raise SecurityError("Empty query not allowed")
    
    # Check for multiple statements (dangerous)
    # Count semicolons not inside quotes
    in_quote = False
    quote_char = None
    semicolon_count = 0
    
    for char in query:
        if char in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = char
        elif char == quote_char and in_quote:
            in_quote = False
            quote_char = None
        elif char == ';' and not in_quote:
            semicolon_count += 1
    
    if semicolon_count > 0:
        raise SecurityError("Multiple statements not allowed")
    
    # Check for potentially dangerous patterns
    dangerous_patterns = [
        r'\bxp_cmdshell\b',
        r'\bsp_configure\b',
        r'\bEXEC\s+\(',
        r'\bEXECUTE\s+\(',
        r'\bDROP\s+DATABASE\b',
        r'\bDROP\s+TABLE\b',
        r'\bSHUTDOWN\b',
        r'--',  # SQL comments can be used for injection
        r'/\*',  # Block comments
    ]
    
    query_upper = query.upper()
    for pattern in dangerous_patterns:
        if re.search(pattern, query_upper, re.IGNORECASE):
            raise SecurityError(f"Query contains potentially dangerous pattern: {pattern}")


class DatabaseManager:
    """Manages database connections and operations with modern features."""
    
    def __init__(self, config, connection_pool=None):
        """
        Initialize database manager.
        
        Args:
            config: Database configuration
            connection_pool: Optional connection pool instance
        """
        self.config = config
        self.connection_pool = connection_pool
        self._connection_params = config.get_pymssql_params()
        
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test database connectivity and return status.
        
        Returns:
            Dict with success status and connection info
        """
        try:
            if self.connection_pool:
                async with self.connection_pool.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT @@VERSION, @@SERVERNAME, DB_NAME()")
                    row = cursor.fetchone()
                    
                    return {
                        "success": True,
                        "server_version": row[0] if row else "Unknown",
                        "server_name": row[1] if row and len(row) > 1 else "Unknown",
                        "database_name": row[2] if row and len(row) > 2 else "Unknown",
                        "connection_method": "pool"
                    }
            else:
                # Direct connection
                async with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT @@VERSION, @@SERVERNAME, DB_NAME()")
                    row = cursor.fetchone()
                    
                    return {
                        "success": True,
                        "server_version": row[0] if row else "Unknown",
                        "server_name": row[1] if row and len(row) > 1 else "Unknown", 
                        "database_name": row[2] if row and len(row) > 2 else "Unknown",
                        "connection_method": "direct"
                    }
                    
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "connection_method": "pool" if self.connection_pool else "direct"
            }

    @asynccontextmanager
    async def get_connection(self):
        """
        Async context manager for database connections.
        
        Uses connection pool if available, otherwise creates direct connection.
        """
        if self.connection_pool:
            async with self.connection_pool.get_connection() as conn:
                yield conn
        else:
            # Direct connection fallback
            conn = None
            try:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    conn = await loop.run_in_executor(executor, pymssql.connect, **self._connection_params)
                    yield conn
            except Exception as e:
                logger.error(f"Failed to create database connection: {e}")
                raise DatabaseError(f"Connection failed: {e}")
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception as e:
                        logger.warning(f"Error closing connection: {e}")

    def get_connection_info(self) -> str:
        """
        Get connection information string.
        
        Returns:
            String describing the database connection
        """
        return f"{self.config.server}/{self.config.database} (user: {self.config.username})"

    async def get_tables(self) -> list:
        """Return a list of user tables in the database."""
        query = """
        SELECT TABLE_SCHEMA + '.' + TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        try:
            async with self.get_connection() as conn:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    cursor = await loop.run_in_executor(executor, conn.cursor)
                    await loop.run_in_executor(executor, cursor.execute, query)
                    rows = await loop.run_in_executor(executor, cursor.fetchall)
                    cursor.close()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting tables: {e}")
            raise DatabaseError(f"Error getting tables: {e}")

    async def read_table_data(self, table_name: str, max_rows: int = 100) -> tuple:
        """Read data from a table, returning (columns, rows)."""
        from .database import validate_table_name
        safe_table = validate_table_name(table_name)
        query = f"SELECT TOP {max_rows} * FROM {safe_table}"
        try:
            async with self.get_connection() as conn:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    cursor = await loop.run_in_executor(executor, conn.cursor)
                    await loop.run_in_executor(executor, cursor.execute, query)
                    columns = [desc[0] for desc in cursor.description]
                    rows = await loop.run_in_executor(executor, cursor.fetchall)
                    cursor.close()
                return columns, rows
        except Exception as e:
            logger.error(f"Error reading table data: {e}")
            raise DatabaseError(f"Error reading table data: {e}")

    async def execute_query(self, query: str) -> dict:
        from .database import validate_sql_query
        validate_sql_query(query)
        try:
            async with self.get_connection() as conn:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    cursor = await loop.run_in_executor(executor, conn.cursor)
                    await loop.run_in_executor(executor, cursor.execute, query)
                    if cursor.description:
                        # SELECT
                        columns = [desc[0] for desc in cursor.description]
                        rows = await loop.run_in_executor(executor, cursor.fetchall)
                        row_count = len(rows)
                        cursor.close()
                        return {
                            "type": "select",
                            "columns": columns,
                            "rows": rows,
                            "row_count": row_count
                        }
                    else:
                        # DML
                        affected = cursor.rowcount
                        message = f"Query executed successfully. {affected} rows affected."
                        cursor.close()
                        return {
                            "type": "modification",
                            "message": message,
                            "affected_rows": affected
                        }
        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise DatabaseError(f"Error executing query: {e}")

    def get_connection_info(self) -> str:
        """
        Get safe connection information for logging.
        
        Returns:
            Connection info string without sensitive data
        """
        server_info = self.config.server
        if self.config.port:
            server_info += f":{self.config.port}"
        
        user_info = self.config.user if self.config.user else "Windows Auth"
        return f"{server_info}/{self.config.database} as {user_info}"
