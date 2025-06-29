# Microsoft SQL Server MCP Server

[![PyPI](https://img.shields.io/pypi/v/microsoft_sql_server_mcp)](https://pypi.org/project/microsoft_sql_server_mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<a href="https://glama.ai/mcp/servers/29cpe19k30">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/29cpe19k30/badge" alt="Microsoft SQL Server MCP server" />
</a>

A Model Context Protocol (MCP) server for secure SQL Server database access through Claude Desktop, built with **FastMCP 2.9.2** for modern async performance and enhanced developer experience.

## ✨ Key Features

- 🔍 **Database Discovery**: List tables, schemas, and databases
- 📊 **SQL Execution**: Execute queries with proper validation and security
- 🔐 **Multi-Auth Support**: SQL, Windows, and Azure AD authentication
- 🏢 **Platform Support**: LocalDB, SQL Server Express, and Azure SQL
- ⚡ **Async Performance**: Built on FastMCP 2.9.2 with async/await patterns
- 🛡️ **Security First**: SQL injection prevention and query validation
- 📝 **Rich Resources**: Discoverable table schemas and data resources
- 🔌 **Flexible Configuration**: Environment-based configuration with validation

## 🚀 Tools & Resources

### Tools

- `execute_sql` - Execute SQL queries with validation and logging
- `get_table_schema` - Retrieve detailed table schema information
- `list_databases` - Enumerate available databases on the server

### Resources

- `mssql://tables` - List all available tables
- `mssql://table/{table_name}` - Get specific table data and schema

## Quick Start

### Install with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mssql": {
      "command": "uvx",
      "args": ["microsoft_sql_server_mcp"],
      "env": {
        "MSSQL_SERVER": "localhost",
        "MSSQL_DATABASE": "your_database",
        "MSSQL_USER": "your_username",
        "MSSQL_PASSWORD": "your_password"
      }
    }
  }
}
```

## Configuration

### Basic SQL Authentication

```bash
MSSQL_SERVER=localhost          # Required
MSSQL_DATABASE=your_database    # Required
MSSQL_USER=your_username        # Required for SQL auth
MSSQL_PASSWORD=your_password    # Required for SQL auth
```

### Windows Authentication

```bash
MSSQL_SERVER=localhost
MSSQL_DATABASE=your_database
MSSQL_WINDOWS_AUTH=true         # Use Windows credentials
```

### Azure SQL Database

```bash
MSSQL_SERVER=your-server.database.windows.net
MSSQL_DATABASE=your_database
MSSQL_USER=your_username
MSSQL_PASSWORD=your_password
# Encryption is automatic for Azure
```

### Optional Settings

```bash
MSSQL_PORT=1433                 # Custom port (default: 1433)
MSSQL_ENCRYPT=true              # Force encryption
```

## Alternative Installation Methods

### Using pip

```bash
pip install microsoft_sql_server_mcp
```

Then in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mssql": {
      "command": "python",
      "args": ["-m", "mssql_mcp_server"],
      "env": { ... }
    }
  }
}
```


## 🔧 Development & Testing

### Running Tests

```bash
# Run refactoring validation tests
python test_refactor.py

# Run full test suite
python -m pytest tests/
```

### Example Usage

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration
nano .env

# Run example usage script
python example_usage.py
```

## 🛡️ Security Best Practices

- **Dedicated User**: Create a dedicated SQL user with minimal permissions
- **No Admin Access**: Never use admin/sa accounts in production
- **Windows Auth**: Use Windows Authentication when possible
- **Encryption**: Enable encryption for sensitive data connections
- **Query Validation**: All queries are validated against injection patterns
- **Secure Logging**: Sensitive data is masked in logs

## 🏗️ Architecture

This server is built with:

- **FastMCP 2.9.2**: Modern async MCP framework with context injection
- **Pydantic V2**: Configuration validation and data modeling
- **Thread Pool**: Async wrapper for synchronous pymssql operations
- **Security Layer**: SQL injection prevention and query validation
- **Comprehensive Logging**: Detailed logging with context awareness

## 📝 License

MIT
