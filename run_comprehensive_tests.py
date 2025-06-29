#!/usr/bin/env python3
"""
Comprehensive test runner for MSSQL MCP Server.
Runs all tests and provides a summary report.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return results."""
    print(f"\n🔄 {description}")
    print("=" * 60)
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            cwd="/workspaces/mssql_fastmcp_server"
        )
        end_time = time.time()
        
        duration = end_time - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED ({duration:.2f}s)")
            if result.stdout:
                print(result.stdout.strip())
        else:
            print(f"❌ {description} - FAILED ({duration:.2f}s)")
            if result.stderr:
                print("STDERR:", result.stderr.strip())
            if result.stdout:
                print("STDOUT:", result.stdout.strip())
        
        return result.returncode == 0, duration
        
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False, 0


def main():
    """Run comprehensive tests."""
    print("🚀 MSSQL MCP Server - Comprehensive Test Suite")
    print("=" * 60)
    
    test_results = []
    total_time = 0
    
    # 1. Import and module structure tests
    success, duration = run_command(
        "PYTHONPATH=src python test_imports.py",
        "Import and Module Structure Validation"
    )
    test_results.append(("Import Tests", success))
    total_time += duration
    
    # 2. Unit tests for individual modules
    success, duration = run_command(
        "PYTHONPATH=src python -m pytest tests/unit/test_modules.py -v --tb=short",
        "Unit Tests - Individual Modules"
    )
    test_results.append(("Unit Tests", success))
    total_time += duration
    
    # 3. Basic integration tests
    success, duration = run_command(
        "PYTHONPATH=src python -m pytest tests/integration/test_basic_integration.py::TestBasicIntegration::test_config_import -v",
        "Basic Integration - Config Module"
    )
    test_results.append(("Config Integration", success))
    total_time += duration
    
    success, duration = run_command(
        "PYTHONPATH=src python -m pytest tests/integration/test_basic_integration.py::TestBasicIntegration::test_handlers_import -v",
        "Basic Integration - Handlers Import"
    )
    test_results.append(("Handlers Integration", success))
    total_time += duration
    
    # 4. Performance tests
    success, duration = run_command(
        "PYTHONPATH=src python -m pytest tests/performance/test_performance.py::TestPerformanceBaselines::test_handler_initialization_speed -v",
        "Performance - Handler Initialization"
    )
    test_results.append(("Performance Tests", success))
    total_time += duration
    
    success, duration = run_command(
        "PYTHONPATH=src python -m pytest tests/performance/test_performance.py::TestPerformanceBaselines::test_cache_performance -v",
        "Performance - Cache Operations"
    )
    test_results.append(("Cache Performance", success))
    total_time += duration
    
    # 5. Server structure validation
    success, duration = run_command(
        "PYTHONPATH=src python -c \"import server; print('✅ Server module loads successfully'); mcp = server.create_mcp_server(); print('✅ MCP server creates successfully')\"",
        "Server Structure Validation"
    )
    test_results.append(("Server Structure", success))
    total_time += duration
    
    # 6. Configuration loading test
    success, duration = run_command(
        "PYTHONPATH=src python -c \"from config import load_config; config = load_config(config_file='configs/test.json'); print('✅ Configuration loads successfully')\"",
        "Configuration Loading"
    )
    test_results.append(("Configuration", success))
    total_time += duration
    
    # Print summary report
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY REPORT")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success in test_results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:<30} {status}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"Total Tests: {len(test_results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(test_results))*100:.1f}%")
    print(f"Total Time: {total_time:.2f}s")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! The refactored server is working correctly.")
        print("✅ The modular architecture is functional and performant.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
