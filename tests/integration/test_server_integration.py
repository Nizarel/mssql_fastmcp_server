"""
Integration tests for the MSSQL MCP Server.
Tests the complete server functionality end-to-end.
"""

import pytest
import asyncio
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import server components
from server import (
    initialize_server, cleanup_server, health_endpoint,
    create_mcp_server, get_mcp_server
)
from config import load_config, TransportType, OutputFormat
from core.database import DatabaseManager
from core.connection_pool import ConnectionPool
from handlers import HealthHandler, TablesHandler, QueryHandler, SchemaHandler, AdminHandler


class TestServerIntegration:
    """Integration tests for the complete server functionality."""
    
    @pytest.fixture
    async def mock_config(self):
        """Create a mock configuration for testing."""
        with patch('server.load_config') as mock_load:
            mock_config = MagicMock()
            mock_config.server.transport = TransportType.STDIO
            mock_config.server.log_level.value = "INFO"
            mock_config.server.enable_caching = True
            mock_config.server.enable_rate_limiting = True
            mock_config.server.enable_health_checks = True
            mock_config.server.connection_pool.max_connections = 5
            mock_config.server.connection_pool.min_connections = 1
            mock_config.server.connection_pool.connection_timeout = 30
            mock_config.server.rate_limit.requests_per_minute = 60
            mock_config.server.rate_limit.burst_limit = 10
            mock_config.server.cache.max_size = 100
            mock_config.server.cache.ttl_seconds = 300
            mock_config.database.get_pymssql_params.return_value = {
                'server': 'localhost',
                'database': 'test',
                'user': 'test',
                'password': 'test'
            }
            mock_load.return_value = mock_config
            yield mock_config
    
    @pytest.fixture
    async def mock_db_manager(self):
        """Create a mock database manager."""
        mock_db = AsyncMock(spec=DatabaseManager)
        mock_db.test_connection.return_value = {"success": True}
        mock_db.execute_query.return_value = {
            "rows": [[1, "test_table", "dbo", "2024-01-01"]],
            "columns": ["id", "name", "schema", "created"],
            "row_count": 1
        }
        return mock_db
    
    @pytest.fixture
    async def mock_connection_pool(self):
        """Create a mock connection pool."""
        mock_pool = AsyncMock(spec=ConnectionPool)
        mock_pool.get_connection.return_value = MagicMock()
        mock_pool.return_connection = AsyncMock()
        mock_pool.close = AsyncMock()
        return mock_pool
    
    @pytest.mark.asyncio
    async def test_server_initialization(self, mock_config, mock_db_manager, mock_connection_pool):
        """Test complete server initialization."""
        with patch('server.DatabaseManager', return_value=mock_db_manager), \
             patch('server.ConnectionPool', return_value=mock_connection_pool), \
             patch('server.logger') as mock_logger:
            
            await initialize_server()
            
            # Verify components were initialized
            assert mock_db_manager.test_connection.called
            mock_logger.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, mock_config):
        """Test the health check endpoint."""
        with patch('server.app_config', mock_config), \
             patch('server.db_manager') as mock_db, \
             patch('server.metrics_collector') as mock_metrics:
            
            mock_db.test_connection.return_value = {"success": True}
            mock_metrics.get_summary.return_value = {"requests": 10}
            
            result = await health_endpoint()
            
            assert result["status"] == "healthy"
            assert "timestamp" in result
            assert result["transport"] == "stdio"
            assert result["architecture"] == "modular_handlers"
    
    @pytest.mark.asyncio
    async def test_mcp_server_creation(self):
        """Test MCP server creation and configuration."""
        server = create_mcp_server()
        
        assert server is not None
        assert hasattr(server, 'run_stdio')
        assert hasattr(server, 'run_sse')
    
    @pytest.mark.asyncio
    async def test_handler_integration(self, mock_config, mock_db_manager):
        """Test that all handlers are properly integrated."""
        with patch('server.DatabaseManager', return_value=mock_db_manager), \
             patch('server.ConnectionPool'), \
             patch('server.initialize_server'):
            
            # Test handler initialization
            health_handler = HealthHandler(mock_config, mock_db_manager, None, None, None)
            tables_handler = TablesHandler(mock_config, mock_db_manager, None, None, None)
            query_handler = QueryHandler(mock_config, mock_db_manager, None, None, None)
            schema_handler = SchemaHandler(mock_config, mock_db_manager, None, None, None)
            admin_handler = AdminHandler(mock_config, mock_db_manager, None, None, None)
            
            assert health_handler is not None
            assert tables_handler is not None
            assert query_handler is not None
            assert schema_handler is not None
            assert admin_handler is not None
    
    @pytest.mark.asyncio
    async def test_cleanup_server(self):
        """Test server cleanup functionality."""
        mock_pool = AsyncMock()
        mock_cache = AsyncMock()
        
        with patch('server.connection_pool', mock_pool), \
             patch('server.cache', mock_cache), \
             patch('server.logger') as mock_logger:
            
            await cleanup_server()
            
            mock_pool.close.assert_called_once()
            mock_cache.clear.assert_called_once()
            mock_logger.info.assert_called()


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture
    async def initialized_server(self):
        """Initialize server for E2E tests."""
        with patch('server.load_config') as mock_load, \
             patch('server.DatabaseManager') as mock_db_class, \
             patch('server.ConnectionPool') as mock_pool_class:
            
            # Setup mocks
            mock_config = MagicMock()
            mock_config.server.transport = TransportType.STDIO
            mock_config.server.log_level.value = "INFO"
            mock_config.server.enable_caching = True
            mock_config.server.enable_rate_limiting = True
            mock_config.server.enable_health_checks = True
            mock_config.server.connection_pool.max_connections = 5
            mock_config.server.connection_pool.min_connections = 1
            mock_config.server.connection_pool.connection_timeout = 30
            mock_config.server.rate_limit.requests_per_minute = 60
            mock_config.server.rate_limit.burst_limit = 10
            mock_config.server.cache.max_size = 100
            mock_config.server.cache.ttl_seconds = 300
            mock_config.database.get_pymssql_params.return_value = {
                'server': 'localhost',
                'database': 'test',
                'user': 'test',
                'password': 'test'
            }
            mock_load.return_value = mock_config
            
            mock_db = AsyncMock()
            mock_db.test_connection.return_value = {"success": True}
            mock_db_class.return_value = mock_db
            
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            
            await initialize_server()
            
            yield {
                'config': mock_config,
                'db_manager': mock_db,
                'connection_pool': mock_pool
            }
    
    @pytest.mark.asyncio
    async def test_complete_query_workflow(self, initialized_server):
        """Test a complete SQL query workflow."""
        from fastmcp import Context
        from server import execute_sql
        
        # Mock database response
        initialized_server['db_manager'].execute_query.return_value = {
            "rows": [["John", 25], ["Jane", 30]],
            "columns": ["name", "age"],
            "row_count": 2
        }
        
        # Create mock context
        ctx = AsyncMock(spec=Context)
        
        # Execute query
        result = await execute_sql("SELECT name, age FROM users", ctx, "json")
        
        # Verify result
        assert result is not None
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert len(result_data["data"]["rows"]) == 2
    
    @pytest.mark.asyncio
    async def test_table_operations_workflow(self, initialized_server):
        """Test complete table operations workflow."""
        from fastmcp import Context
        from server import list_tables_resource, read_table_resource
        
        # Mock table listing
        initialized_server['db_manager'].execute_query.return_value = {
            "rows": [["users", "dbo", "2024-01-01"], ["orders", "dbo", "2024-01-01"]],
            "columns": ["table_name", "schema", "created"],
            "row_count": 2
        }
        
        ctx = AsyncMock(spec=Context)
        
        # Test table listing
        tables_result = await list_tables_resource(ctx)
        assert tables_result is not None
        
        # Test reading specific table
        initialized_server['db_manager'].execute_query.return_value = {
            "rows": [["John", 25], ["Jane", 30]],
            "columns": ["name", "age"],
            "row_count": 2
        }
        
        table_data = await read_table_resource("users", ctx)
        assert table_data is not None
    
    @pytest.mark.asyncio
    async def test_schema_operations_workflow(self, initialized_server):
        """Test schema operations workflow."""
        from fastmcp import Context
        from server import get_table_schema, list_databases
        
        # Mock schema response
        initialized_server['db_manager'].execute_query.return_value = {
            "rows": [
                ["id", "int", "NO", None, None, 10, 0, 1],
                ["name", "varchar", "YES", None, 50, None, None, 2]
            ],
            "columns": ["column_name", "data_type", "is_nullable", "default", "max_length", "precision", "scale", "position"],
            "row_count": 2
        }
        
        ctx = AsyncMock(spec=Context)
        
        # Test schema retrieval
        schema_result = await get_table_schema("users", ctx, "json")
        assert schema_result is not None
        
        # Test database listing
        initialized_server['db_manager'].execute_query.return_value = {
            "rows": [["testdb", 1, datetime.now(), "SQL_Latin1_General_CP1_CI_AS"]],
            "columns": ["name", "database_id", "create_date", "collation_name"],
            "row_count": 1
        }
        
        db_result = await list_databases(ctx, "json")
        assert db_result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
