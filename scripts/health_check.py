#!/usr/bin/env python3
"""
Health check script for the MSSQL MCP Server.
This script can be used by monitoring systems to check server health.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mssql_mcp_server.server import health_endpoint, initialize_server


async def main():
    """Main health check function."""
    try:
        # Initialize server components
        await initialize_server()
        
        # Check health
        health_data = await health_endpoint()
        
        # Print health data as JSON
        print(json.dumps(health_data, indent=2))
        
        # Exit with appropriate code
        if health_data.get("status") == "healthy":
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
