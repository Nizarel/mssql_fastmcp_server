"""
MSSQL MCP Server using FastMCP 2.9.2.

A Model Context Protocol server that provides secure access to Microsoft SQL Server databases.
Built with FastMCP for improved performance and developer experience.
"""

import logging
from typing import Any, List
import asyncio
from fastmcp import FastMCP, Context

from .config import load_database_config, load_server_config
from .database import DatabaseManager, DatabaseError, SecurityError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for lazy initialization
db_config = None
server_config = None
db_manager = None

def get_db_manager():
    """Get database manager with lazy initialization."""
    global db_config, server_config, db_manager
    
    if db_manager is None:
        try:
            db_config = load_database_config()
            server_config = load_server_config()
            db_manager = DatabaseManager(db_config)
            logger.info(f"Database config loaded: {db_manager.get_connection_info()}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    return db_manager, server_config

# Initialize FastMCP server with improved configuration
mcp = FastMCP(
    name="Microsoft SQL Server MCP",
    instructions="Provides secure access to Microsoft SQL Server databases with tools for querying, schema inspection, and data analysis."
)


@mcp.resource("mssql://tables", name="Database Tables", description="List all available tables in the database")
async def list_tables(ctx: Context) -> str:
    """List all available tables in the database."""
    try:
        await ctx.info("Retrieving list of database tables")
        db_manager, _ = get_db_manager()
        tables = await db_manager.get_tables()
        
        if not tables:
            await ctx.warning("No tables found in the database")
            return "No tables found in the database."
        
        await ctx.info(f"Found {len(tables)} tables")
        result = ["Available tables:"]
        result.extend([f"- {table}" for table in tables])
        return "\n".join(result)
        
    except DatabaseError as e:
        await ctx.error(f"Failed to list tables: {e}")
        return f"Error listing tables: {e}"


@mcp.resource("mssql://table/{table_name}", name="Table Data", description="Read data from a specific table")
async def read_table(table_name: str, ctx: Context) -> str:
    """
    Read data from a specific table.
    
    Args:
        table_name: Name of the table to read
        ctx: FastMCP context for logging and progress reporting
        
    Returns:
        Table data in CSV format
    """
    try:
        await ctx.info(f"Reading data from table: {table_name}")
        await ctx.report_progress(0, 100, "Starting table read")
        
        db_manager, server_config = get_db_manager()
        columns, rows = await db_manager.read_table_data(table_name, server_config.max_rows)
        
        await ctx.report_progress(50, 100, "Processing table data")
        
        if not rows:
            await ctx.warning(f"Table '{table_name}' is empty or does not exist")
            return f"Table '{table_name}' is empty or does not exist."
        
        # Format as CSV
        result = [",".join(columns)]
        result.extend([",".join(str(cell) if cell is not None else "" for cell in row) for row in rows])
        
        await ctx.report_progress(100, 100, "Table read completed")
        
        footer = f"\n\nShowing {len(rows)} rows (limit: {server_config.max_rows})"
        await ctx.info(f"Successfully read {len(rows)} rows from table {table_name}")
        
        return "\n".join(result) + footer
        
    except SecurityError as e:
        await ctx.error(f"Security error reading table {table_name}: {e}")
        return f"Security error: {e}"
    except DatabaseError as e:
        await ctx.error(f"Database error reading table {table_name}: {e}")
        return f"Database error: {e}"


@mcp.tool()
async def execute_sql(query: str, ctx: Context) -> str:
    """
    Execute a SQL query on the database.
    
    Args:
        query: SQL query to execute
        ctx: FastMCP context for logging and progress reporting
        
    Returns:
        Query results or execution status
    """
    try:
        await ctx.info(f"Executing SQL query: {query[:100]}...")
        await ctx.report_progress(0, 100, "Validating query")
        
        db_manager, _ = get_db_manager()
        result = await db_manager.execute_query(query)
        
        await ctx.report_progress(50, 100, "Processing results")
        
        if result["type"] == "select":
            if not result["rows"]:
                await ctx.info("Query executed successfully but returned no rows")
                return "Query executed successfully but returned no rows."
            
            # Format SELECT results as CSV
            output = [",".join(result["columns"])]
            output.extend([
                ",".join(str(cell) if cell is not None else "" for cell in row) 
                for row in result["rows"]
            ])
            
            footer = f"\n\nReturned {result['row_count']} rows"
            await ctx.info(f"Query returned {result['row_count']} rows")
            await ctx.report_progress(100, 100, "Query completed")
            return "\n".join(output) + footer
        
        else:
            # Modification query
            await ctx.info(f"Query executed successfully. {result['message']}")
            await ctx.report_progress(100, 100, "Query completed")
            return result["message"]
            
    except SecurityError as e:
        await ctx.warning(f"Security error executing query: {e}")
        return f"Security error: {e}"
    except DatabaseError as e:
        await ctx.error(f"Database error executing query: {e}")
        return f"Database error: {e}"


@mcp.tool()
async def get_table_schema(table_name: str, ctx: Context) -> str:
    """
    Get the schema information for a specific table.
    
    Args:
        table_name: Name of the table to describe
        ctx: FastMCP context for logging and progress reporting
        
    Returns:
        Table schema information
    """
    try:
        await ctx.info(f"Retrieving schema for table: {table_name}")
        
        # Validate table name first
        from .database import validate_table_name
        safe_table = validate_table_name(table_name)
        
        # Query for table schema
        schema_query = f"""
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            CHARACTER_MAXIMUM_LENGTH,
            NUMERIC_PRECISION,
            NUMERIC_SCALE
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = '{table_name.split('.')[-1]}'
        ORDER BY ORDINAL_POSITION
        """
        
        db_manager, _ = get_db_manager()
        result = await db_manager.execute_query(schema_query)
        
        if not result["rows"]:
            await ctx.warning(f"Table '{table_name}' not found or has no columns")
            return f"Table '{table_name}' not found or has no columns."
        
        # Format schema information
        output = [f"Schema for table '{table_name}':", ""]
        output.append("Column Name | Data Type | Nullable | Default | Max Length | Precision | Scale")
        output.append("-" * 80)
        
        for row in result["rows"]:
            col_name, data_type, nullable, default, max_len, precision, scale = row
            max_len = max_len if max_len is not None else ""
            precision = precision if precision is not None else ""
            scale = scale if scale is not None else ""
            default = default if default is not None else ""
            
            output.append(f"{col_name} | {data_type} | {nullable} | {default} | {max_len} | {precision} | {scale}")
        
        await ctx.info(f"Retrieved schema for table {table_name} with {len(result['rows'])} columns")
        return "\n".join(output)
        
    except SecurityError as e:
        await ctx.warning(f"Security error getting schema for {table_name}: {e}")
        return f"Security error: {e}"
    except DatabaseError as e:
        await ctx.error(f"Database error getting schema for {table_name}: {e}")
        return f"Database error: {e}"


@mcp.tool()
async def list_databases(ctx: Context) -> str:
    """
    List all databases on the server (requires appropriate permissions).
    
    Args:
        ctx: FastMCP context for logging and progress reporting
        
    Returns:
        List of available databases
    """
    try:
        await ctx.info("Listing available databases")
        
        query = """
        SELECT name 
        FROM sys.databases 
        WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
        ORDER BY name
        """
        
        db_manager, _ = get_db_manager()
        result = await db_manager.execute_query(query)
        
        if not result["rows"]:
            await ctx.warning("No user databases found or insufficient permissions")
            return "No user databases found or insufficient permissions."
        
        output = ["Available databases:"]
        output.extend([f"- {row[0]}" for row in result["rows"]])
        
        await ctx.info(f"Found {len(result['rows'])} user databases")
        return "\n".join(output)
        
    except DatabaseError as e:
        await ctx.error(f"Database error listing databases: {e}")
        return f"Database error: {e}"


async def main():
    """Main entry point to run the MCP server."""
    logger.info("Starting Microsoft SQL Server MCP server with FastMCP...")
    
    try:
        # Initialize database manager
        db_manager, server_config = get_db_manager()
        logger.info(f"Server configuration: Command='{server_config.command_name}', MaxRows={server_config.max_rows}")
        
        # Test database connection
        tables = await db_manager.get_tables()
        logger.info(f"Database connection successful. Found {len(tables)} tables.")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise
    
    # Run the server
    await mcp.run()


def get_mcp_server():
    """Get the FastMCP server instance for testing."""
    return mcp


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
