"""
Pytest configuration and fixtures for MSSQL MCP Server tests.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Set environment variables for testing
os.environ["MCP_PROFILE"] = "test"
os.environ["PYTEST_RUNNING"] = "1"

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    mock_config = MagicMock()
    
    # Server configuration
    mock_config.server.transport.value = "stdio"
    mock_config.server.log_level.value = "INFO"
    mock_config.server.enable_caching = True
    mock_config.server.enable_rate_limiting = True
    mock_config.server.enable_health_checks = True
    mock_config.server.sse_port = 8080
    
    # Connection pool configuration
    mock_config.server.connection_pool.max_connections = 5
    mock_config.server.connection_pool.min_connections = 1
    mock_config.server.connection_pool.connection_timeout = 30
    
    # Rate limiting configuration
    mock_config.server.rate_limit.requests_per_minute = 60
    mock_config.server.rate_limit.burst_limit = 10
    
    # Cache configuration
    mock_config.server.cache.max_size = 100
    mock_config.server.cache.ttl_seconds = 300
    
    # Database configuration
    mock_config.database.get_pymssql_params.return_value = {
        'server': 'localhost',
        'database': 'test',
        'user': 'test',
        'password': 'test'
    }
    
    return mock_config


@pytest.fixture
def mock_database_manager():
    """Create a mock database manager."""
    mock_db = AsyncMock()
    mock_db.test_connection.return_value = {"success": True, "message": "Connected"}
    mock_db.execute_query.return_value = {
        "rows": [],
        "columns": [],
        "row_count": 0
    }
    mock_db.get_tables.return_value = []
    return mock_db


@pytest.fixture
def mock_connection_pool():
    """Create a mock connection pool."""
    mock_pool = AsyncMock()
    mock_pool.get_connection.return_value = MagicMock()
    mock_pool.return_connection = AsyncMock()
    mock_pool.close = AsyncMock()
    return mock_pool


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_cache.set = AsyncMock()
    mock_cache.clear = AsyncMock()
    return mock_cache


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    mock_limiter = AsyncMock()
    mock_limiter.check.return_value = True
    return mock_limiter


@pytest.fixture
def mock_context():
    """Create a mock FastMCP context."""
    mock_ctx = AsyncMock()
    mock_ctx.info = AsyncMock()
    mock_ctx.error = AsyncMock()
    mock_ctx.warning = AsyncMock()
    return mock_ctx
