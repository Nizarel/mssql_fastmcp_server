"""Entry point for running the MSSQL MCP server as a module."""

import sys
import logging
from . import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Server failed to start: {e}", exc_info=True)
        sys.exit(1)