"""Tables handler for listing and reading table data."""

from typing import Dict, Any
from fastmcp import Context

from .base import BaseHandler
from ..core.database import DatabaseError, SecurityError


class TablesHandler(BaseHandler):
    """Handle table-related operations."""
    
    def __init__(self, app_config, db_manager, connection_pool, cache, rate_limiter):
        super().__init__(app_config, db_manager, connection_pool, cache, rate_limiter)
    
    async def list_tables(self, ctx: Context) -> str:
        """List all available tables in the database with caching support."""
        try:
            # Check rate limit
            if not await self.check_rate_limit(ctx, "list_tables"):
                return self.format_response(
                    {"error": "Rate limit exceeded"}, 
                    self.get_output_format(ctx)
                )
            
            await ctx.info("Retrieving list of database tables")
            
            # Check cache first
            cache_key = "tables_list"
            if self.cache:
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    await ctx.info("Retrieved tables from cache")
                    return self.format_response(cached_result, self.get_output_format(ctx))
            
            # Get tables from database
            tables = await self.db_manager.get_tables()
            
            if not tables:
                await ctx.warning("No tables found in the database")
                result = {"tables": [], "count": 0, "message": "No tables found"}
            else:
                await ctx.info(f"Found {len(tables)} tables")
                result = {
                    "tables": tables,
                    "count": len(tables),
                    "message": f"Found {len(tables)} tables"
                }
            
            # Cache the result
            if self.cache:
                await self.cache.set(cache_key, result)
            
            return self.format_response(result, self.get_output_format(ctx))
            
        except DatabaseError as e:
            await ctx.error(f"Failed to list tables: {e}")
            return self.format_response({"error": str(e)}, self.get_output_format(ctx))
    
    async def read_table(self, table_name: str, ctx: Context) -> str:
        """
        Read data from a specific table with advanced features.
        
        Args:
            table_name: Name of the table to read
            ctx: FastMCP context for logging and progress reporting
            
        Returns:
            Table data in requested format
        """
        try:
            # Check rate limit
            if not await self.check_rate_limit(ctx, f"read_table:{table_name}"):
                return self.format_response(
                    {"error": "Rate limit exceeded"}, 
                    self.get_output_format(ctx)
                )
            
            await ctx.info(f"Reading data from table: {table_name}")
            await ctx.report_progress(0, 100, "Starting table read")
            
            # Check cache first
            cache_key = f"table_data:{table_name}:{self.app_config.server.max_rows}"
            if self.cache:
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    await ctx.info("Retrieved table data from cache")
                    await ctx.report_progress(100, 100, "Table read completed (cached)")
                    return self.format_response(cached_result, self.get_output_format(ctx))
            
            await ctx.report_progress(25, 100, "Querying database")
            
            # Get data from database
            columns, rows = await self.db_manager.read_table_data(table_name, self.app_config.server.max_rows)
            
            await ctx.report_progress(75, 100, "Processing table data")
            
            if not rows:
                await ctx.warning(f"Table '{table_name}' is empty or does not exist")
                result = {
                    "table_name": table_name,
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "message": f"Table '{table_name}' is empty or does not exist"
                }
            else:
                result = {
                    "table_name": table_name,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "metadata": {
                        "limit": self.app_config.server.max_rows,
                        "truncated": len(rows) >= self.app_config.server.max_rows
                    }
                }
            
            # Cache the result
            if self.cache:
                await self.cache.set(cache_key, result)
            
            await ctx.report_progress(100, 100, "Table read completed")
            await ctx.info(f"Successfully read {len(rows)} rows from table {table_name}")
            
            return self.format_response(result, self.get_output_format(ctx))
            
        except SecurityError as e:
            await ctx.error(f"Security error reading table {table_name}: {e}")
            return self.format_response({"error": f"Security error: {e}"}, self.get_output_format(ctx))
        except DatabaseError as e:
            await ctx.error(f"Database error reading table {table_name}: {e}")
            return self.format_response({"error": f"Database error: {e}"}, self.get_output_format(ctx))
