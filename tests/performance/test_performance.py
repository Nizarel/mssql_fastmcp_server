"""
Performance tests for the MSSQL MCP Server.
Tests to ensure the modular structure doesn't impact performance.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor


class TestPerformanceBaselines:
    """Test performance baselines for various operations."""
    
    @pytest.mark.asyncio
    async def test_handler_initialization_speed(self, mock_config, mock_database_manager):
        """Test that handler initialization is fast."""
        from handlers import HealthHandler, TablesHandler, QueryHandler, SchemaHandler, AdminHandler
        
        start_time = time.time()
        
        # Initialize all handlers
        health_handler = HealthHandler(mock_config, mock_database_manager, None, None, None)
        tables_handler = TablesHandler(mock_config, mock_database_manager, None, None, None)
        query_handler = QueryHandler(mock_config, mock_database_manager, None, None, None)
        schema_handler = SchemaHandler(mock_config, mock_database_manager, None, None, None)
        admin_handler = AdminHandler(mock_config, mock_database_manager, None, None, None)
        
        end_time = time.time()
        
        # Handler initialization should be very fast (< 50ms)
        initialization_time = end_time - start_time
        assert initialization_time < 0.05, f"Handler initialization took {initialization_time:.3f}s, expected < 0.05s"
        
        # Verify all handlers are properly initialized
        assert health_handler is not None
        assert tables_handler is not None
        assert query_handler is not None
        assert schema_handler is not None
        assert admin_handler is not None
    
    @pytest.mark.asyncio
    async def test_cache_performance(self):
        """Test cache performance under load."""
        from core.cache import LRUCache
        
        cache = LRUCache(max_size=1000, ttl=300)
        
        # Test cache set performance
        start_time = time.time()
        
        for i in range(100):
            await cache.set(f"key_{i}", f"value_{i}")
        
        set_time = time.time() - start_time
        
        # 100 cache sets should be fast (< 100ms)
        assert set_time < 0.1, f"Cache set operations took {set_time:.3f}s, expected < 0.1s"
        
        # Test cache get performance
        start_time = time.time()
        
        for i in range(100):
            result = await cache.get(f"key_{i}")
            assert result == f"value_{i}"
        
        get_time = time.time() - start_time
        
        # 100 cache gets should be very fast (< 50ms)
        assert get_time < 0.05, f"Cache get operations took {get_time:.3f}s, expected < 0.05s"
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test cache performance under concurrent access."""
        from core.cache import LRUCache
        
        cache = LRUCache(max_size=1000, ttl=300)
        
        async def cache_worker(worker_id: int, operations: int):
            """Worker function for concurrent cache operations."""
            for i in range(operations):
                key = f"worker_{worker_id}_key_{i}"
                value = f"worker_{worker_id}_value_{i}"
                
                # Set and immediately get
                await cache.set(key, value)
                result = await cache.get(key)
                assert result == value
        
        start_time = time.time()
        
        # Run 10 concurrent workers, each doing 20 operations
        tasks = [cache_worker(i, 20) for i in range(10)]
        await asyncio.gather(*tasks)
        
        concurrent_time = time.time() - start_time
        
        # 200 total operations with 10 concurrent workers should complete quickly
        assert concurrent_time < 1.0, f"Concurrent cache operations took {concurrent_time:.3f}s, expected < 1.0s"
    
    @pytest.mark.asyncio
    async def test_rate_limiter_performance(self):
        """Test rate limiter performance."""
        from core.rate_limiter import RateLimiter
        
        rate_limiter = RateLimiter(rate=1000, burst=100)
        
        start_time = time.time()
        
        # Test 100 rate limit checks
        for i in range(100):
            result = await rate_limiter.check(f"test_key_{i}")
            assert result is True  # Should all be allowed
        
        check_time = time.time() - start_time
        
        # 100 rate limit checks should be fast (< 100ms)
        assert check_time < 0.1, f"Rate limit checks took {check_time:.3f}s, expected < 0.1s"
    
    @pytest.mark.asyncio
    async def test_response_formatting_performance(self):
        """Test response formatting performance."""
        from core.response_formatter import ResponseFormatter
        from config import OutputFormat
        
        # Create test data of varying sizes
        small_data = {"rows": [["test", 1]], "columns": ["name", "id"], "row_count": 1}
        medium_data = {
            "rows": [["test", i] for i in range(100)], 
            "columns": ["name", "id"], 
            "row_count": 100
        }
        large_data = {
            "rows": [["test", i] for i in range(1000)], 
            "columns": ["name", "id"], 
            "row_count": 1000
        }
        
        formatter = ResponseFormatter()
        
        # Test small data formatting speed
        start_time = time.time()
        for _ in range(50):
            formatter.format(small_data, OutputFormat.JSON)
            formatter.format(small_data, OutputFormat.CSV)
            formatter.format(small_data, OutputFormat.MARKDOWN)
        small_format_time = time.time() - start_time
        
        # Test medium data formatting speed
        start_time = time.time()
        for _ in range(10):
            formatter.format(medium_data, OutputFormat.JSON)
            formatter.format(medium_data, OutputFormat.CSV)
        medium_format_time = time.time() - start_time
        
        # Test large data formatting speed
        start_time = time.time()
        formatter.format(large_data, OutputFormat.JSON)
        formatter.format(large_data, OutputFormat.CSV)
        large_format_time = time.time() - start_time
        
        # Performance assertions
        assert small_format_time < 0.5, f"Small data formatting took {small_format_time:.3f}s, expected < 0.5s"
        assert medium_format_time < 1.0, f"Medium data formatting took {medium_format_time:.3f}s, expected < 1.0s"
        assert large_format_time < 2.0, f"Large data formatting took {large_format_time:.3f}s, expected < 2.0s"
    
    @pytest.mark.asyncio
    async def test_handler_operation_latency(self, mock_config, mock_database_manager, mock_context):
        """Test handler operation latency."""
        from handlers.health import HealthHandler
        from handlers.tables import TablesHandler
        
        # Setup mocks
        mock_database_manager.test_connection.return_value = {"success": True}
        mock_database_manager.get_tables.return_value = [
            {"name": f"table_{i}", "schema": "dbo"} for i in range(10)
        ]
        
        health_handler = HealthHandler(mock_config, mock_database_manager, None, None, None)
        tables_handler = TablesHandler(mock_config, mock_database_manager, None, None, None)
        
        # Test health check latency
        start_time = time.time()
        for _ in range(10):
            await health_handler.check_health(mock_context)
        health_time = time.time() - start_time
        
        # Test table listing latency
        start_time = time.time()
        for _ in range(10):
            await tables_handler.list_tables(mock_context)
        tables_time = time.time() - start_time
        
        # Handler operations should be fast
        assert health_time < 0.5, f"Health checks took {health_time:.3f}s, expected < 0.5s"
        assert tables_time < 0.5, f"Table listings took {tables_time:.3f}s, expected < 0.5s"


class TestMemoryUsage:
    """Test memory usage and efficiency."""
    
    @pytest.mark.asyncio
    async def test_cache_memory_efficiency(self):
        """Test that cache doesn't consume excessive memory."""
        from core.cache import LRUCache
        import sys
        
        # Create cache with known size
        cache = LRUCache(max_size=100, ttl=300)
        
        # Add data to cache
        test_data = {"large_data": ["x" * 1000 for _ in range(100)]}
        
        for i in range(100):
            await cache.set(f"key_{i}", test_data)
        
        # Cache should respect size limits
        cache_size = len(cache._cache)
        assert cache_size <= 100, f"Cache size {cache_size} exceeded limit of 100"
    
    @pytest.mark.asyncio
    async def test_handler_memory_efficiency(self, mock_config, mock_database_manager):
        """Test that handlers don't leak memory."""
        from handlers import HealthHandler, TablesHandler, QueryHandler, SchemaHandler, AdminHandler
        
        # Create and destroy handlers multiple times
        for _ in range(10):
            health_handler = HealthHandler(mock_config, mock_database_manager, None, None, None)
            tables_handler = TablesHandler(mock_config, mock_database_manager, None, None, None)
            query_handler = QueryHandler(mock_config, mock_database_manager, None, None, None)
            schema_handler = SchemaHandler(mock_config, mock_database_manager, None, None, None)
            admin_handler = AdminHandler(mock_config, mock_database_manager, None, None, None)
            
            # Clear references
            del health_handler, tables_handler, query_handler, schema_handler, admin_handler
        
        # Test should complete without memory issues
        assert True


class TestConcurrencyPerformance:
    """Test performance under concurrent load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_handler_operations(self, mock_config, mock_database_manager, mock_context):
        """Test handler performance under concurrent load."""
        from handlers.health import HealthHandler
        
        # Setup mock
        mock_database_manager.test_connection.return_value = {"success": True}
        
        handler = HealthHandler(mock_config, mock_database_manager, None, None, None)
        
        async def health_check_worker():
            """Worker function for concurrent health checks."""
            return await handler.check_health(mock_context)
        
        start_time = time.time()
        
        # Run 20 concurrent health checks
        tasks = [health_check_worker() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        concurrent_time = time.time() - start_time
        
        # All tasks should complete successfully
        assert len(results) == 20
        for result in results:
            assert result is not None
        
        # Concurrent operations should complete reasonably fast
        assert concurrent_time < 2.0, f"Concurrent operations took {concurrent_time:.3f}s, expected < 2.0s"
    
    @pytest.mark.asyncio
    async def test_rate_limiter_under_load(self):
        """Test rate limiter performance under high load."""
        from core.rate_limiter import RateLimiter
        
        rate_limiter = RateLimiter(rate=100, burst=50)
        
        async def rate_limit_worker(worker_id: int):
            """Worker function for rate limit testing."""
            results = []
            for i in range(20):
                result = await rate_limiter.check(f"worker_{worker_id}_key_{i}")
                results.append(result)
            return results
        
        start_time = time.time()
        
        # Run 10 concurrent workers
        tasks = [rate_limit_worker(i) for i in range(10)]
        all_results = await asyncio.gather(*tasks)
        
        load_time = time.time() - start_time
        
        # Should complete within reasonable time
        assert load_time < 3.0, f"Rate limiter under load took {load_time:.3f}s, expected < 3.0s"
        
        # Check results
        total_requests = sum(len(results) for results in all_results)
        allowed_requests = sum(sum(results) for results in all_results)
        
        assert total_requests == 200  # 10 workers * 20 requests each
        assert allowed_requests <= total_requests  # Some should be rate limited


class TestScalabilityBaselines:
    """Test scalability characteristics."""
    
    @pytest.mark.asyncio
    async def test_large_data_handling(self):
        """Test handling of large datasets."""
        from core.response_formatter import ResponseFormatter
        from config import OutputFormat
        
        # Create large dataset
        large_rows = [["user", i, f"email{i}@test.com", "active"] for i in range(5000)]
        large_data = {
            "rows": large_rows,
            "columns": ["name", "id", "email", "status"],
            "row_count": 5000
        }
        
        formatter = ResponseFormatter()
        
        start_time = time.time()
        
        # Format large dataset
        json_result = formatter.format(large_data, OutputFormat.JSON)
        csv_result = formatter.format(large_data, OutputFormat.CSV)
        
        format_time = time.time() - start_time
        
        # Should handle large data within reasonable time
        assert format_time < 5.0, f"Large data formatting took {format_time:.3f}s, expected < 5.0s"
        
        # Results should be properly formatted
        assert json_result is not None
        assert csv_result is not None
        assert len(json_result) > 0
        assert len(csv_result) > 0
    
    @pytest.mark.asyncio
    async def test_connection_pool_performance(self):
        """Test connection pool performance characteristics."""
        from core.connection_pool import ConnectionPool
        
        # Mock connection parameters
        mock_params = {
            'server': 'localhost',
            'database': 'test',
            'user': 'test',
            'password': 'test'
        }
        
        with patch('pymssql.connect') as mock_connect:
            mock_connect.return_value = MagicMock()
            
            pool = ConnectionPool(mock_params, min_size=2, max_size=10, timeout=30)
            
            start_time = time.time()
            
            # Test concurrent connection requests
            async def get_connection_worker():
                conn = await pool.get_connection()
                await asyncio.sleep(0.1)  # Simulate work
                await pool.return_connection(conn)
                return True
            
            # Run 20 concurrent connection requests
            tasks = [get_connection_worker() for _ in range(20)]
            results = await asyncio.gather(*tasks)
            
            pool_time = time.time() - start_time
            
            # All requests should succeed
            assert all(results)
            
            # Connection pool should handle concurrent requests efficiently
            assert pool_time < 3.0, f"Connection pool operations took {pool_time:.3f}s, expected < 3.0s"
            
            await pool.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
