"""Query execution handler module."""

from typing import Dict, Any
from datetime import datetime
from fastmcp import Context

from .base import BaseHandler
from ..config import OutputFormat
from ..core.database import DatabaseError, SecurityError


class QueryHandler(BaseHandler):
    """Handle SQL query execution requests."""
    
    def __init__(self, app_config, db_manager, connection_pool, cache, rate_limiter):
        super().__init__(app_config, db_manager, connection_pool, cache, rate_limiter)
    
    async def execute_sql(self, query: str, ctx: Context, output_format: str = "csv") -> str:
        """
        Execute a SQL query on the database with advanced features.
        
        Args:
            query: SQL query to execute
            ctx: FastMCP context for logging and progress reporting
            output_format: Output format (csv, json, markdown, table)
            
        Returns:
            Query results in requested format
        """
        try:
            # Validate output format
            try:
                format_enum = OutputFormat(output_format.lower())
            except ValueError:
                format_enum = self.app_config.server.default_output_format
            
            # Check rate limit
            if not await self.check_rate_limit(ctx, "execute_sql"):
                return self.format_response(
                    {"error": "Rate limit exceeded"}, 
                    format_enum
                )
            
            await ctx.info(f"Executing SQL query: {query[:100]}...")
            await ctx.report_progress(0, 100, "Validating query")
            
            # Check cache for SELECT queries
            cache_key = None
            if self.cache and query.strip().upper().startswith('SELECT'):
                cache_key = f"query:{hash(query.strip())}"
                cached_result = await self.cache.get(cache_key)
                if cached_result:
                    await ctx.info("Retrieved query result from cache")
                    await ctx.report_progress(100, 100, "Query completed (cached)")
                    return self.format_response(cached_result, format_enum)
            
            await ctx.report_progress(25, 100, "Executing query")
            
            # Execute query
            result = await self.db_manager.execute_query(query)
            
            await ctx.report_progress(75, 100, "Processing results")
            
            response_data = {}
            
            if result["type"] == "select":
                if not result["rows"]:
                    await ctx.info("Query executed successfully but returned no rows")
                    response_data = {
                        "query_type": "select",
                        "columns": result.get("columns", []),
                        "rows": [],
                        "row_count": 0,
                        "message": "Query executed successfully but returned no rows"
                    }
                else:
                    response_data = {
                        "query_type": "select",
                        "columns": result["columns"],
                        "rows": result["rows"],
                        "row_count": result["row_count"],
                        "metadata": {
                            "execution_time": result.get("execution_time"),
                            "query_hash": hash(query.strip())
                        }
                    }
                    await ctx.info(f"Query returned {result['row_count']} rows")
            else:
                # Modification query
                response_data = {
                    "query_type": result["type"],
                    "message": result["message"],
                    "affected_rows": result.get("affected_rows", 0),
                    "metadata": {
                        "execution_time": result.get("execution_time")
                    }
                }
                await ctx.info(f"Query executed successfully. {result['message']}")
            
            # Cache SELECT query results
            if self.cache and cache_key and result["type"] == "select":
                await self.cache.set(cache_key, response_data)
            
            await ctx.report_progress(100, 100, "Query completed")
            return self.format_response(response_data, format_enum)
                
        except SecurityError as e:
            await ctx.warning(f"Security error executing query: {e}")
            return self.format_response({"error": f"Security error: {e}"}, format_enum)
        except DatabaseError as e:
            await ctx.error(f"Database error executing query: {e}")
            return self.format_response({"error": f"Database error: {e}"}, format_enum)
        except Exception as e:
            await ctx.error(f"Unexpected error executing query: {e}")
            return self.format_response({"error": f"Unexpected error: {e}"}, format_enum)
    
    async def execute_sql_stream(
        self, 
        query: str, 
        ctx: Context,
        batch_size: int = 1000
    ) -> str:
        """
        Execute a large SQL query with streaming results.
        
        Args:
            query: SQL query to execute
            ctx: FastMCP context for logging and progress reporting
            batch_size: Number of rows to process in each batch
            
        Returns:
            Streaming query results
        """
        try:
            if not self.app_config.server.enable_streaming:
                return self.format_response(
                    {"error": "Streaming is not enabled"}, 
                    OutputFormat.JSON
                )
            
            # Check rate limit
            if not await self.check_rate_limit(ctx, "execute_sql_stream"):
                return self.format_response(
                    {"error": "Rate limit exceeded"}, 
                    OutputFormat.JSON
                )
            
            await ctx.info(f"Executing streaming SQL query: {query[:100]}...")
            
            # Execute query with streaming
            result = await self.db_manager.execute_query_stream(query, batch_size)
            
            response_data = {
                "query_type": "streaming_select",
                "columns": result["columns"],
                "batch_size": batch_size,
                "total_batches": result.get("total_batches", "unknown"),
                "metadata": {
                    "execution_time": result.get("execution_time"),
                    "streaming_enabled": True
                }
            }
            
            await ctx.info(f"Streaming query initiated with batch size {batch_size}")
            return self.format_response(response_data, OutputFormat.JSON)
            
        except SecurityError as e:
            await ctx.warning(f"Security error executing streaming query: {e}")
            return self.format_response({"error": f"Security error: {e}"}, OutputFormat.JSON)
        except DatabaseError as e:
            await ctx.error(f"Database error executing streaming query: {e}")
            return self.format_response({"error": f"Database error: {e}"}, OutputFormat.JSON)
        except Exception as e:
            await ctx.error(f"Unexpected error executing streaming query: {e}")
            return self.format_response({"error": f"Unexpected error: {e}"}, OutputFormat.JSON)
