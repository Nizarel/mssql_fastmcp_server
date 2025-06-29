# MSSQL MCP Server API Reference

## Overview

The MSSQL MCP Server provides a Model Context Protocol interface for Microsoft SQL Server databases. It features a modular architecture with separate handlers for different types of operations.

## Architecture

The server is built with a modular handler architecture:

- **Handlers**: Modular components for different operations (health, tables, queries, schema, admin)
- **Core**: Database management, connection pooling, caching, rate limiting
- **Middleware**: Authentication, logging, metrics collection
- **Utils**: Validators and helper functions

## Resources

### Health Check
**Resource**: `mssql://health`

Returns server health and database connectivity status.

**Response Format**: JSON
```json
{
  "status": "healthy",
  "timestamp": "2025-06-29T10:30:00Z",
  "database": {
    "success": true,
    "response_time": 0.045
  },
  "connection_pool": {
    "current_size": 5,
    "available": 3,
    "utilization_percent": 40.0
  }
}
```

### Table Listing
**Resource**: `mssql://tables`

Lists all available tables in the database.

**Parameters**:
- `output_format` (optional): csv, json, markdown, table (default: json)

### Table Data
**Resource**: `mssql://table/{table_name}`

Reads data from a specific table.

**Parameters**:
- `table_name`: Name of the table to read
- `limit` (optional): Maximum number of rows to return
- `offset` (optional): Number of rows to skip
- `output_format` (optional): csv, json, markdown, table

## Tools

### execute_sql
Execute a SQL query on the database.

**Parameters**:
- `query` (required): SQL query to execute
- `output_format` (optional): csv, json, markdown, table (default: csv)

**Example**:
```sql
SELECT * FROM Users WHERE is_active = 1 ORDER BY created_at DESC
```

### get_table_schema
Get schema information for a specific table.

**Parameters**:
- `table_name` (required): Name of the table
- `output_format` (optional): csv, json, markdown, table (default: markdown)

**Response**: Column definitions including name, type, nullable, default values

### list_databases
List all databases on the server (requires permissions).

**Parameters**:
- `output_format` (optional): csv, json, markdown, table (default: json)

### get_server_info
Get detailed server and configuration information.

**Response**: Server version, features, configuration settings

### cache_stats
Get cache statistics and performance metrics.

**Response**: Hit rate, size, evictions, and other cache metrics

### clear_cache
Clear the query result cache.

**Response**: Confirmation of cache clear operation

### get_metrics
Get comprehensive server metrics.

**Response**: Operation counts, timing, error rates, system metrics

## Output Formats

### CSV
Comma-separated values format suitable for spreadsheet applications.

### JSON
Structured JSON format with metadata and typed data.

### Markdown
Human-readable table format using Markdown syntax.

### Table
Plain text table format for console display.

## Error Handling

All operations return structured error responses:

```json
{
  "success": false,
  "error": "Error description",
  "error_code": "SECURITY_ERROR",
  "timestamp": "2025-06-29T10:30:00Z"
}
```

Common error types:
- `SECURITY_ERROR`: Query validation or permission issues
- `DATABASE_ERROR`: SQL execution or connection problems
- `RATE_LIMIT_ERROR`: Too many requests
- `VALIDATION_ERROR`: Invalid parameters

## Security Features

- SQL injection prevention through parameterized queries
- Query validation and sanitization
- Rate limiting to prevent abuse
- Connection pooling for resource management
- Configurable permissions and restrictions

## Performance Features

- Query result caching with configurable TTL
- Connection pooling for efficient database access
- Rate limiting to prevent overload
- Streaming support for large result sets
- Comprehensive metrics and monitoring
