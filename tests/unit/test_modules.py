"""
Unit tests for individual modules of the MSSQL MCP Server.
Tests specific functionality of each component in isolation.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone


class TestConfigModule:
    """Test configuration module functionality."""
    
    def test_output_format_enum(self):
        """Test OutputFormat enum values."""
        from config import OutputFormat
        
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.CSV.value == "csv"
        assert OutputFormat.MARKDOWN.value == "markdown"
        assert OutputFormat.TABLE.value == "table"
    
    def test_transport_type_enum(self):
        """Test TransportType enum values."""
        from config import TransportType
        
        assert TransportType.STDIO.value == "stdio"
        assert TransportType.SSE.value == "sse"
    
    def test_log_level_enum(self):
        """Test LogLevel enum values."""
        from config import LogLevel
        
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"


class TestUtilsModule:
    """Test utility functions."""
    
    def test_format_timestamp(self):
        """Test timestamp formatting."""
        from utils.helpers import format_timestamp
        
        # Test with None (should use current time)
        result = format_timestamp()
        assert isinstance(result, str)
        assert 'T' in result  # ISO format
        
        # Test with specific datetime
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = format_timestamp(dt)
        assert result == "2024-01-01T12:00:00+00:00"
    
    def test_sanitize_sql_identifier(self):
        """Test SQL identifier sanitization."""
        from utils.helpers import sanitize_sql_identifier
        
        # Valid identifier
        assert sanitize_sql_identifier("table_name") == "table_name"
        
        # Remove invalid characters
        assert sanitize_sql_identifier("table-name!") == "tablename"
        
        # Handle number prefix
        assert sanitize_sql_identifier("123table") == "_123table"
    
    def test_validate_connection_string(self):
        """Test connection string validation."""
        from utils.helpers import validate_connection_string
        
        # Valid connection string
        valid_conn = "server=localhost;database=test;user=admin;password=pass"
        assert validate_connection_string(valid_conn) is True
        
        # Missing required parameters
        invalid_conn = "user=admin;password=pass"
        assert validate_connection_string(invalid_conn) is False
        
        # Dangerous keywords
        dangerous_conn = "server=localhost;database=test;drop table users"
        assert validate_connection_string(dangerous_conn) is False
    
    def test_generate_cache_key(self):
        """Test cache key generation."""
        from utils.helpers import generate_cache_key
        
        key1 = generate_cache_key("table", "users", "limit", 10)
        key2 = generate_cache_key("table", "users", "limit", 10)
        key3 = generate_cache_key("table", "orders", "limit", 10)
        
        # Same inputs should produce same key
        assert key1 == key2
        # Different inputs should produce different keys
        assert key1 != key3
        
        # Key should be a hash string
        assert isinstance(key1, str)
        assert len(key1) == 64  # SHA256 hex string


class TestValidators:
    """Test validation utilities."""
    
    def test_table_name_validator(self):
        """Test table name validation."""
        from utils.validators import TableNameValidator
        
        # Valid table names
        assert TableNameValidator.validate_table_name("users") == "users"
        assert TableNameValidator.validate_table_name("dbo.users") == "dbo.users"
        
        # Test with invalid characters (should raise exception or sanitize)
        with pytest.raises(Exception):
            TableNameValidator.validate_table_name("users'; DROP TABLE")
    
    def test_query_validator(self):
        """Test SQL query validation."""
        from utils.validators import QueryValidator
        
        # Valid SELECT query
        valid_query = "SELECT * FROM users WHERE id = 1"
        result = QueryValidator.validate_query(valid_query)
        assert result is None or len(result) == 0  # No validation errors
        
        # Dangerous query with DDL
        dangerous_query = "SELECT * FROM users; DROP TABLE users;"
        result = QueryValidator.validate_query(dangerous_query, allow_ddl=False)
        assert result is not None  # Should have validation errors


class TestCacheModule:
    """Test caching functionality."""
    
    @pytest.mark.asyncio
    async def test_lru_cache_basic_operations(self):
        """Test basic LRU cache operations."""
        from core.cache import LRUCache
        
        cache = LRUCache(max_size=3, ttl=300)
        
        # Test set and get
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"
        
        # Test non-existent key
        result = await cache.get("nonexistent")
        assert result is None
        
        # Test cache size limit
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        await cache.set("key4", "value4")  # Should evict key1
        
        result = await cache.get("key1")
        assert result is None  # Should be evicted
        
        result = await cache.get("key4")
        assert result == "value4"
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test cache clearing."""
        from core.cache import LRUCache
        
        cache = LRUCache(max_size=10, ttl=300)
        
        # Add some data
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        # Clear cache
        await cache.clear()
        
        # Verify cache is empty
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_within_limit(self):
        """Test that rate limiter allows requests within limit."""
        from core.rate_limiter import RateLimiter
        
        # High rate limit for testing
        limiter = RateLimiter(rate=100, burst=10)
        
        # Should allow requests within limit
        for i in range(5):
            result = await limiter.check_rate_limit("test_key")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_over_limit(self):
        """Test that rate limiter blocks requests over limit."""
        from core.rate_limiter import RateLimiter
        
        # Very low rate limit for testing
        limiter = RateLimiter(rate=1, burst=2)  # Allow 2 initial requests
        
        # First two requests should be allowed (burst)
        result1 = await limiter.check_rate_limit("test_key")
        assert result1 is True
        
        result2 = await limiter.check_rate_limit("test_key")
        assert result2 is True
        
        # Third immediate request should be blocked
        result3 = await limiter.check_rate_limit("test_key")
        assert result3 is False


class TestResponseFormatter:
    """Test response formatting functionality."""
    
    def test_mcp_response_creation(self):
        """Test MCPResponse creation and serialization."""
        from core.response_formatter import MCPResponse
        
        # Success response
        response = MCPResponse(success=True, data={"test": "data"})
        
        assert response.success is True
        assert response.data == {"test": "data"}
        assert response.error is None
        
        # Convert to JSON
        json_str = response.to_json()
        assert '"success": true' in json_str
        assert '"test": "data"' in json_str
    
    def test_mcp_response_error(self):
        """Test MCPResponse error handling."""
        from core.response_formatter import MCPResponse
        
        # Error response
        response = MCPResponse(success=False, error="Test error")
        
        assert response.success is False
        assert response.error == "Test error"
        assert response.data is None
        
        # Convert to JSON
        json_str = response.to_json()
        assert '"success": false' in json_str
        assert '"error": "Test error"' in json_str


class TestHandlerBase:
    """Test base handler functionality."""
    
    @pytest.mark.asyncio
    async def test_base_handler_initialization(self, mock_config, mock_database_manager):
        """Test base handler initialization."""
        from handlers.base import BaseHandler
        
        handler = BaseHandler(
            mock_config, mock_database_manager, None, None, None
        )
        
        assert handler.app_config == mock_config
        assert handler.db_manager == mock_database_manager
        assert handler.connection_pool is None
        assert handler.cache is None
        assert handler.rate_limiter is None
    
    @pytest.mark.asyncio
    async def test_base_handler_rate_limit_check(self, mock_config, mock_database_manager):
        """Test rate limit checking in base handler."""
        from handlers.base import BaseHandler
        
        # Create mock rate limiter
        mock_rate_limiter = AsyncMock()
        mock_rate_limiter.check_rate_limit.return_value = True
        
        handler = BaseHandler(
            mock_config, mock_database_manager, None, None, mock_rate_limiter
        )
        
        # Create mock context
        mock_ctx = AsyncMock()
        
        # Test rate limit check
        result = await handler.check_rate_limit(mock_ctx, "test_operation")
        
        assert result is True
        mock_rate_limiter.check_rate_limit.assert_called_once()
    
    def test_base_handler_format_response(self, mock_config, mock_database_manager):
        """Test response formatting in base handler."""
        from handlers.base import BaseHandler
        from config import OutputFormat
        
        handler = BaseHandler(
            mock_config, mock_database_manager, None, None, None
        )
        
        test_data = {"test": "data", "count": 1}
        
        # Test JSON formatting
        result = handler.format_response(test_data, OutputFormat.JSON)
        assert '"test": "data"' in result
        
        # Test CSV formatting
        result = handler.format_response(test_data, OutputFormat.CSV)
        assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
