#!/usr/bin/env python3
"""Simple test of the flattened structure."""

import sys
import os

sys.path.insert(0, 'src')

def test_imports():
    print("Testing flattened structure imports...")
    
    try:
        from config import AppConfig
        print("✅ Config imported")
    except Exception as e:
        print(f"❌ Config failed: {e}")
        return False
    
    try:
        from core.database import DatabaseManager
        print("✅ Core database imported")
    except Exception as e:
        print(f"❌ Core database failed: {e}")
        return False
    
    try:
        from handlers.base import BaseHandler
        print("✅ Base handler imported")
    except Exception as e:
        print(f"❌ Base handler failed: {e}")
        return False
    
    try:
        from handlers.health import HealthHandler
        print("✅ Health handler imported")
    except Exception as e:
        print(f"❌ Health handler failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n🎉 All imports working!")
    else:
        print("\n❌ Some imports failed")
