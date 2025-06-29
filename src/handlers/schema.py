"""Schema information handler module."""

from typing import Dict, Any
from datetime import datetime
from fastmcp import Context

from .base import BaseHandler
from config import OutputFormat
from core.database import DatabaseError, SecurityError


class SchemaHandler(BaseHandler):
    """Handle schema and database structure requests."""
    
    def __init__(self, app_config, db_manager, connection_pool, cache, rate_limiter):
        super().__init__(app_config, db_manager, connection_pool, cache, rate_limiter)
    
    async def get_table_schema(self, table_name: str, ctx: Context, output_format: str = "markdown") -> str:
        """
        Get the schema information for a specific table.
        
        Args:
            table_name: Name of the table to describe
            ctx: FastMCP context for logging and progress reporting
            output_format: Output format (csv, json, markdown, table)
            
        Returns:
            Table schema information in requested format
        """
        try:
            # Validate output format
            try:
                format_enum = OutputFormat(output_format.lower())
            except ValueError:
                format_enum = OutputFormat.MARKDOWN
            
            # Check rate limit
            if not await self.check_rate_limit(ctx, f"get_schema:{table_name}"):
                return self.format_response(
                    {"error": "Rate limit exceeded"}, 
                    format_enum
                )
            
            await ctx.info(f"Retrieving schema for table: {table_name}")
            
            # Check cache first
            cache_key = f"schema:{table_name}"
            if self.cache:
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    await ctx.info("Retrieved schema from cache")
                    return self.format_response(cached_result, format_enum)
            
            # Validate table name first
            from utils.validators import TableNameValidator
            safe_table = TableNameValidator.validate_table_name(table_name)
            
            # Query for table schema
            schema_query = f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                NUMERIC_SCALE,
                ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = '{table_name.split('.')[-1]}'
            ORDER BY ORDINAL_POSITION
            """
            
            result = await self.db_manager.execute_query(schema_query)
            
            if not result["rows"]:
                await ctx.warning(f"Table '{table_name}' not found or has no columns")
                response_data = {
                    "table_name": table_name,
                    "columns": [],
                    "rows": [],
                    "column_count": 0,
                    "error": f"Table '{table_name}' not found or has no columns"
                }
            else:
                # Process schema information
                schema_columns = ["Column", "Type", "Nullable", "Default", "Max Length", "Precision", "Scale", "Position"]
                schema_rows = []
                
                for row in result["rows"]:
                    col_name, data_type, nullable, default, max_len, precision, scale, position = row
                    schema_rows.append([
                        col_name,
                        data_type,
                        "YES" if nullable == "YES" else "NO",
                        default if default is not None else "",
                        str(max_len) if max_len is not None else "",
                        str(precision) if precision is not None else "",
                        str(scale) if scale is not None else "",
                        str(position)
                    ])
                
                response_data = {
                    "table_name": table_name,
                    "columns": schema_columns,
                    "rows": schema_rows,
                    "column_count": len(result["rows"]),
                    "metadata": {
                        "table_exists": True,
                        "schema_retrieved_at": datetime.utcnow().isoformat()
                    }
                }
            
            # Cache the result
            if self.cache:
                await self.cache.set(cache_key, response_data)
            
            await ctx.info(f"Retrieved schema for table {table_name} with {response_data['column_count']} columns")
            return self.format_response(response_data, format_enum)
            
        except SecurityError as e:
            await ctx.warning(f"Security error getting schema for {table_name}: {e}")
            return self.format_response({"error": f"Security error: {e}"}, format_enum)
        except DatabaseError as e:
            await ctx.error(f"Database error getting schema for {table_name}: {e}")
            return self.format_response({"error": f"Database error: {e}"}, format_enum)
        except Exception as e:
            await ctx.error(f"Unexpected error getting schema for {table_name}: {e}")
            return self.format_response({"error": f"Unexpected error: {e}"}, format_enum)
    
    async def list_databases(self, ctx: Context, output_format: str = "json") -> str:
        """
        List all databases on the server (requires appropriate permissions).
        
        Args:
            ctx: FastMCP context for logging and progress reporting
            output_format: Output format (csv, json, markdown, table)
            
        Returns:
            List of available databases in requested format
        """
        try:
            # Validate output format
            try:
                format_enum = OutputFormat(output_format.lower())
            except ValueError:
                format_enum = OutputFormat.JSON
            
            # Check rate limit
            if not await self.check_rate_limit(ctx, "list_databases"):
                return self.format_response(
                    {"error": "Rate limit exceeded"}, 
                    format_enum
                )
            
            await ctx.info("Listing available databases")
            
            # Check cache first
            cache_key = "databases_list"
            if self.cache:
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    await ctx.info("Retrieved databases from cache")
                    return self.format_response(cached_result, format_enum)
            
            # Query for databases
            query = """
            SELECT name, database_id, create_date, collation_name
            FROM sys.databases 
            WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
            ORDER BY name
            """
            
            result = await self.db_manager.execute_query(query)
            
            if not result["rows"]:
                await ctx.warning("No user databases found or insufficient permissions")
                response_data = {
                    "databases": [],
                    "count": 0,
                    "message": "No user databases found or insufficient permissions"
                }
            else:
                databases = []
                for row in result["rows"]:
                    databases.append({
                        "name": row[0],
                        "database_id": row[1],
                        "created": row[2].isoformat() if row[2] else None,
                        "collation": row[3]
                    })
                
                response_data = {
                    "databases": databases,
                    "count": len(databases),
                    "columns": ["name", "database_id", "created", "collation"],
                    "rows": [[db["name"], db["database_id"], db["created"], db["collation"]] for db in databases]
                }
            
            # Cache the result
            if self.cache:
                await self.cache.set(cache_key, response_data)
            
            await ctx.info(f"Found {response_data['count']} user databases")
            return self.format_response(response_data, format_enum)
            
        except DatabaseError as e:
            await ctx.error(f"Database error listing databases: {e}")
            return self.format_response({"error": f"Database error: {e}"}, format_enum)
        except Exception as e:
            await ctx.error(f"Unexpected error listing databases: {e}")
            return self.format_response({"error": f"Unexpected error: {e}"}, format_enum)
