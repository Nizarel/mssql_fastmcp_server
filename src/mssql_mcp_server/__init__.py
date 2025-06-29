"""Microsoft SQL Server MCP Server package."""

import asyncio


def main():
    """Main entry point for the package."""
    from . import server
    asyncio.run(server.main())


# Package metadata
__version__ = "2.0.0"
__all__ = ['main']