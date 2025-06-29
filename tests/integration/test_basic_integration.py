"""
Basic integration tests for the MSSQL MCP Server modules.
Tests that all modules can be imported and basic functionality works.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestBasicIntegration:
    """Basic integration tests for module functionality."""
    
    def test_config_import(self):
        """Test that config module can be imported."""
        import config
        assert hasattr(config, 'load_config')
        assert hasattr(config, 'AppConfig')
        assert hasattr(config, 'TransportType')
    
    def test_database_module_import(self):
        """Test that database module can be imported."""
        from core.database import DatabaseManager, DatabaseError, SecurityError
        assert DatabaseManager is not None
        assert DatabaseError is not None
        assert SecurityError is not None
    
    def test_handlers_import(self):
        """Test that all handler modules can be imported."""
        from handlers.base import BaseHandler
        from handlers.health import HealthHandler
        from handlers.tables import TablesHandler
        from handlers.query import QueryHandler
        from handlers.schema import SchemaHandler
        from handlers.admin import AdminHandler
        
        assert BaseHandler is not None
        assert HealthHandler is not None
        assert TablesHandler is not None
        assert QueryHandler is not None
        assert SchemaHandler is not None
        assert AdminHandler is not None
    
    def test_middleware_import(self):
        """Test that middleware modules can be imported."""
        from middleware.auth import AuthMiddleware
        from middleware.logging import StructuredLogger, RequestLogger
        from middleware.metrics import metrics_collector
        
        assert AuthMiddleware is not None
        assert StructuredLogger is not None
        assert RequestLogger is not None
        assert metrics_collector is not None
    
    def test_utils_import(self):
        """Test that utility modules can be imported."""
        from utils.helpers import format_timestamp, validate_connection_string
        from utils.validators import TableNameValidator, QueryValidator
        
        assert format_timestamp is not None
        assert validate_connection_string is not None
        assert TableNameValidator is not None
        assert QueryValidator is not None
    
    @pytest.mark.asyncio
    async def test_handler_initialization(self, mock_config, mock_database_manager):
        """Test that handlers can be initialized properly."""
        from handlers.health import HealthHandler
        from handlers.tables import TablesHandler
        
        # Test handler initialization
        health_handler = HealthHandler(
            mock_config, mock_database_manager, None, None, None
        )
        tables_handler = TablesHandler(
            mock_config, mock_database_manager, None, None, None
        )
        
        assert health_handler.app_config == mock_config
        assert health_handler.db_manager == mock_database_manager
        assert tables_handler.app_config == mock_config
        assert tables_handler.db_manager == mock_database_manager
    
    @pytest.mark.asyncio
    async def test_health_handler_functionality(self, mock_config, mock_database_manager, mock_context):
        """Test basic health handler functionality."""
        from handlers.health import HealthHandler
        
        # Setup mock
        mock_database_manager.test_connection.return_value = {
            "success": True, 
            "message": "Connected"
        }
        
        handler = HealthHandler(mock_config, mock_database_manager, None, None, None)
        
        # Test health check
        result = await handler.check_health(mock_context)
        
        assert result is not None
        assert "healthy" in result.lower() or "success" in result.lower()
        mock_database_manager.test_connection.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_tables_handler_functionality(self, mock_config, mock_database_manager, mock_context):
        """Test basic tables handler functionality."""
        from handlers.tables import TablesHandler
        
        # Setup mock response
        mock_database_manager.get_tables.return_value = [
            {"name": "users", "schema": "dbo", "created": "2024-01-01"},
            {"name": "orders", "schema": "dbo", "created": "2024-01-01"}
        ]
        
        handler = TablesHandler(mock_config, mock_database_manager, None, None, None)
        
        # Test list tables
        result = await handler.list_tables(mock_context)
        
        assert result is not None
        mock_database_manager.get_tables.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_handler_functionality(self, mock_config, mock_database_manager, mock_context):
        """Test basic query handler functionality."""
        from handlers.query import QueryHandler
        
        # Setup mock response
        mock_database_manager.execute_query.return_value = {
            "rows": [["John", 25], ["Jane", 30]],
            "columns": ["name", "age"],
            "row_count": 2
        }
        
        handler = QueryHandler(mock_config, mock_database_manager, None, None, None)
        
        # Test SQL execution
        result = await handler.execute_sql("SELECT name, age FROM users", mock_context)
        
        assert result is not None
        mock_database_manager.execute_query.assert_called_once()
    
    def test_server_module_structure(self):
        """Test that server module has expected structure."""
        import server
        
        # Check for key functions
        assert hasattr(server, 'ensure_initialized')
        assert hasattr(server, 'cleanup_components')
        assert hasattr(server, 'main')
        
        # Check for MCP server instance
        assert hasattr(server, 'mcp')
        
        # Check for global state variables
        assert hasattr(server, 'app_config')
        assert hasattr(server, 'db_manager')
    
    @pytest.mark.asyncio
    async def test_mcp_server_creation(self):
        """Test MCP server creation."""
        import server
        
        # Check that the MCP server instance exists
        assert server.mcp is not None
        # Test that it's a FastMCP instance
        from fastmcp import FastMCP
        assert isinstance(server.mcp, FastMCP)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
