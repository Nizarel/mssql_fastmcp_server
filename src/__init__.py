"""Microsoft SQL Server MCP Server package."""

import asyncio


def main():
    """Main entry point for the package."""
    from server import main as server_main
    asyncio.run(server_main())


# Package metadata
__version__ = "2.0.0"
__all__ = ['main']