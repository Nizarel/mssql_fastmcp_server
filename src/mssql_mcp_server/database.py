"""Database operations for MSSQL MCP Server."""

import re
import logging
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Tuple, Optional
from contextlib import asynccontextmanager
import pymssql
from .config import DatabaseConfig, get_connection_params

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
    """Manages database connections and operations."""
    
    def __init__(self, config: DatabaseConfig):
        """
        Initialize database manager.
        
        Args:
            config: Database configuration
        """
        self.config = config
        self._connection_params = get_connection_params(config)
        
    @asynccontextmanager
    async def get_connection(self):
        """
        Async context manager for database connections.
        
        Yields:
            Database connection
            
        Raises:
            DatabaseError: If connection fails
        """
        conn = None
        try:
            logger.debug("Establishing database connection")
            # Since pymssql is synchronous, we'll run it in a thread pool
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                conn = await loop.run_in_executor(executor, lambda: pymssql.connect(**self._connection_params))
            yield conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseError(f"Failed to connect to database: {e}")
        finally:
            if conn:
                logger.debug("Closing database connection")
                conn.close()
    
    async def get_tables(self) -> List[str]:
        """
        Get list of user tables in the database.
        
        Returns:
            List of table names
            
        Raises:
            DatabaseError: If query fails
        """
        try:
            async with self.get_connection() as conn:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    cursor = conn.cursor()
                    await loop.run_in_executor(executor, cursor.execute, """
                        SELECT TABLE_NAME 
                        FROM INFORMATION_SCHEMA.TABLES 
                        WHERE TABLE_TYPE = 'BASE TABLE'
                        ORDER BY TABLE_NAME
                    """)
                    tables = [row[0] for row in cursor.fetchall()]
                    logger.info(f"Found {len(tables)} tables: {tables}")
                    return tables
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            raise DatabaseError(f"Failed to retrieve tables: {e}")
    
    async def read_table_data(self, table_name: str, limit: int = 100) -> Tuple[List[str], List[List[Any]]]:
        """
        Read data from a table.
        
        Args:
            table_name: Name of the table to read
            limit: Maximum number of rows to return
            
        Returns:
            Tuple of (column_names, rows)
            
        Raises:
            DatabaseError: If query fails
            SecurityError: If table name is invalid
        """
        safe_table = validate_table_name(table_name)
        
        try:
            async with self.get_connection() as conn:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    cursor = conn.cursor()
                    query = f"SELECT TOP {limit} * FROM {safe_table}"
                    logger.debug(f"Executing query: {query}")
                    await loop.run_in_executor(executor, cursor.execute, query)
                    
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    
                    logger.info(f"Retrieved {len(rows)} rows from table {table_name}")
                    return columns, rows
        except Exception as e:
            logger.error(f"Failed to read table {table_name}: {e}")
            raise DatabaseError(f"Failed to read table data: {e}")
    
    async def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Dictionary with query results
            
        Raises:
            DatabaseError: If query execution fails
            SecurityError: If query is invalid or dangerous
        """
        validate_sql_query(query)
        
        try:
            async with self.get_connection() as conn:
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    cursor = conn.cursor()
                    logger.debug(f"Executing query: {query[:100]}...")
                    await loop.run_in_executor(executor, cursor.execute, query)
                    
                    query_type = query.strip().upper()
                    
                    # Handle SELECT queries
                    if query_type.startswith("SELECT"):
                        columns = [desc[0] for desc in cursor.description] if cursor.description else []
                        rows = cursor.fetchall()
                        
                        logger.info(f"SELECT query returned {len(rows)} rows")
                        return {
                            "type": "select",
                            "columns": columns,
                            "rows": rows,
                            "row_count": len(rows)
                        }
                    
                    # Handle modification queries (INSERT, UPDATE, DELETE)
                    else:
                        conn.commit()
                        affected_rows = cursor.rowcount
                        
                        logger.info(f"Query executed successfully. Rows affected: {affected_rows}")
                        return {
                            "type": "modification",
                            "affected_rows": affected_rows,
                            "message": f"Query executed successfully. Rows affected: {affected_rows}"
                        }
                        
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise DatabaseError(f"Query execution failed: {e}")
    
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
