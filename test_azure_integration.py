#!/usr/bin/env python3
"""
Quick database connectivity test for Azure SQL Database.
"""

import asyncio
import time
from pathlib import Path
import sys
sys.path.insert(0, 'src')

async def test_azure_database():
    """Test Azure database connectivity."""
    print("🔍 Testing Azure SQL Database connectivity...")
    
    # Test 1: Load configuration
    try:
        from config import load_config
        config = load_config(config_file='configs/azure.json')
        print("✅ Configuration loaded successfully")
        print(f"   Server: {config.database.server}")
        print(f"   Database: {config.database.database}")
        print(f"   Username: {config.database.username}")
        print(f"   Encrypt: {config.database.encrypt}")
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return False
    
    # Test 2: Create database manager
    try:
        from core.database import DatabaseManager
        db_manager = DatabaseManager(config.database, None)
        print("✅ Database manager created")
    except Exception as e:
        print(f"❌ Database manager creation failed: {e}")
        return False
    
    # Test 3: Test connection with timeout
    print("🔄 Testing database connection (30s timeout)...")
    try:
        start_time = time.time()
        result = await asyncio.wait_for(
            db_manager.test_connection(), 
            timeout=30.0
        )
        end_time = time.time()
        
        print(f"✅ Connection test completed in {end_time - start_time:.2f}s")
        print(f"   Result: {result}")
        
        if result.get('success'):
            print("🎉 Database connection successful!")
            return True
        else:
            print(f"❌ Connection failed: {result.get('error', 'Unknown error')}")
            return False
            
    except asyncio.TimeoutError:
        print("⏰ Connection test timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"❌ Connection test error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_handlers_with_mock():
    """Test handlers with mocked database responses."""
    print("\n🔍 Testing handlers with simulated data...")
    
    try:
        from config import load_config
        from handlers.health import HealthHandler
        from handlers.tables import TablesHandler
        from unittest.mock import AsyncMock
        from fastmcp import Context
        
        config = load_config(config_file='configs/azure.json')
        
        # Mock database manager
        mock_db = AsyncMock()
        mock_db.test_connection.return_value = {"success": True, "message": "Mock connection"}
        mock_db.get_tables.return_value = [
            {"name": "customers", "schema": "dbo"},
            {"name": "orders", "schema": "dbo"}
        ]
        
        # Test health handler
        health_handler = HealthHandler(config, mock_db, None, None, None)
        mock_ctx = AsyncMock(spec=Context)
        
        health_result = await health_handler.check_health(mock_ctx)
        print("✅ Health handler working")
        
        # Test tables handler
        tables_handler = TablesHandler(config, mock_db, None, None, None)
        tables_result = await tables_handler.list_tables(mock_ctx)
        print("✅ Tables handler working")
        
        return True
        
    except Exception as e:
        print(f"❌ Handler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_mcp_server():
    """Test MCP server creation."""
    print("\n🔍 Testing MCP server creation...")
    
    try:
        import server
        mcp_server = server.create_mcp_server()
        print(f"✅ MCP server created: {type(mcp_server)}")
        
        from fastmcp import FastMCP
        assert isinstance(mcp_server, FastMCP)
        print("✅ MCP server is FastMCP instance")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests."""
    print("🚀 Azure SQL Database Integration Tests")
    print("=" * 50)
    
    results = []
    
    # Test database connectivity
    db_success = await test_azure_database()
    results.append(("Database Connectivity", db_success))
    
    # Test handlers (with mocks)
    handler_success = await test_handlers_with_mock()
    results.append(("Handler Functionality", handler_success))
    
    # Test MCP server
    mcp_success = await test_mcp_server()
    results.append(("MCP Server Creation", mcp_success))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:<25} {status}")
        if success:
            passed += 1
    
    print("-" * 50)
    print(f"Passed: {passed}/{len(results)}")
    success_rate = (passed / len(results)) * 100
    print(f"Success Rate: {success_rate:.1f}%")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ MCP Server is ready for Azure SQL Database!")
    else:
        print(f"\n⚠️ {len(results) - passed} test(s) failed.")
        
        # If only database connectivity failed, that might be expected
        if not results[0][1] and all(r[1] for r in results[1:]):
            print("💡 Note: Database connectivity failed but handlers work.")
            print("   This might be due to network/firewall restrictions.")
            print("   The server architecture is functional.")

if __name__ == "__main__":
    asyncio.run(main())
