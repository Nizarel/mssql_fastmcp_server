#!/usr/bin/env python3
"""
Test all module imports to ensure the codebase structure is correct.
"""

def test_core_imports():
    """Test core module imports."""
    try:
        import config
        print("✅ Config module imported successfully")
        
        from core.database import DatabaseManager
        print("✅ DatabaseManager imported successfully")
        
        from core.connection_pool import ConnectionPool
        print("✅ ConnectionPool imported successfully")
        
        from core.cache import LRUCache
        print("✅ LRUCache imported successfully")
        
        from core.rate_limiter import RateLimiter
        print("✅ RateLimiter imported successfully")
        
        from core.response_formatter import MCPResponse
        print("✅ MCPResponse imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Core imports failed: {e}")
        return False

def test_handler_imports():
    """Test handler module imports."""
    try:
        from handlers.base import BaseHandler
        print("✅ BaseHandler imported successfully")
        
        from handlers.health import HealthHandler
        print("✅ HealthHandler imported successfully")
        
        from handlers.tables import TablesHandler
        print("✅ TablesHandler imported successfully")
        
        from handlers.query import QueryHandler
        print("✅ QueryHandler imported successfully")
        
        from handlers.schema import SchemaHandler
        print("✅ SchemaHandler imported successfully")
        
        from handlers.admin import AdminHandler
        print("✅ AdminHandler imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Handler imports failed: {e}")
        return False

def test_middleware_imports():
    """Test middleware module imports."""
    try:
        from middleware.auth import AuthMiddleware
        print("✅ AuthMiddleware imported successfully")
        
        from middleware.logging import StructuredLogger, RequestLogger
        print("✅ Logging middleware imported successfully")
        
        from middleware.metrics import MetricsCollector, metrics_collector
        print("✅ MetricsCollector imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Middleware imports failed: {e}")
        return False

def test_utils_imports():
    """Test utility module imports."""
    try:
        from utils.validators import ConfigValidator, QueryValidator
        print("✅ Validators imported successfully")
        
        from utils.helpers import generate_cache_key, sanitize_sql_identifier
        print("✅ Helper functions imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Utils imports failed: {e}")
        return False

def test_server_import():
    """Test main server module import."""
    try:
        import server
        print("✅ Server module imported successfully")
        
        # Check for essential components
        assert hasattr(server, 'mcp'), "MCP server instance not found"
        assert hasattr(server, 'ensure_initialized'), "ensure_initialized function not found"
        assert hasattr(server, 'main'), "main function not found"
        
        print("✅ Server module structure validated")
        return True
    except Exception as e:
        print(f"❌ Server import failed: {e}")
        return False

def main():
    """Run all import tests."""
    print("🔍 Testing Module Imports")
    print("=" * 50)
    
    tests = [
        ("Core Modules", test_core_imports),
        ("Handler Modules", test_handler_imports),
        ("Middleware Modules", test_middleware_imports),
        ("Utility Modules", test_utils_imports),
        ("Server Module", test_server_import),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Testing {test_name}:")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} - PASSED")
            else:
                print(f"❌ {test_name} - FAILED")
        except Exception as e:
            print(f"❌ {test_name} - ERROR: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Import Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All module imports successful!")
        return 0
    else:
        print("⚠️ Some imports failed!")
        return 1

if __name__ == "__main__":
    exit(main())
