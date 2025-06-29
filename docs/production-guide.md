# MSSQL MCP Server - Production Guide

## 🚀 Quick Start

### 1. MCP Client Configuration

Add to your MCP client config (e.g., Claude Desktop):

```json
{
  "servers": {
    "mssql-server": {
      "transport": "sse",
      "url": "https://your-container-app.azurecontainerapps.io",
      "env": {
        "MCP_PROFILE": "production"
      }
    }
  }
}
```

### 2. Environment Variables

Set these in Azure Container Apps:

```bash
MSSQL_SERVER=your-server.database.windows.net
MSSQL_DATABASE=YourDatabase
MSSQL_USERNAME=your-username
MSSQL_PASSWORD=your-password
MCP_PROFILE=production
```

### 3. Available MCP Resources

- `mssql://health` - Server health check
- `mssql://tables` - List all database tables
- `mssql://table/{name}` - Read data from specific table
- `mssql://schema/{name}` - Get table schema
- `mssql://databases` - List all databases

### 4. Available MCP Tools

- `execute_sql` - Execute custom SQL queries
- `read_table` - Read table data with pagination
- `get_table_schema` - Get detailed table schema
- `list_tables` - List all tables
- `list_databases` - List all databases
- `server_info` - Get server configuration
- `cache_stats` - Get cache statistics
- `clear_cache` - Clear query cache
- `connection_pool_stats` - Get connection pool info

### 5. Example Usage

```python
# Using FastMCP client
from fastmcp import Client

async with Client("sse://your-container-app.azurecontainerapps.io") as client:
    # List tables
    tables = await client.call_tool("list_tables", {"output_format": "json"})
    
    # Execute SQL
    results = await client.call_tool("execute_sql", {
        "query": "SELECT TOP 10 * FROM Users",
        "output_format": "csv"
    })
    
    # Get health status
    health = await client.read_resource("mssql://health")
```

## 🔧 Advanced Configuration

### Security
- Enable authentication in production
- Use Azure Key Vault for secrets
- Configure network security groups

### Performance
- Tune connection pool settings
- Configure cache TTL appropriately
- Monitor and adjust based on usage

### Monitoring
- Set up Application Insights
- Configure custom metrics
- Set up alerts for failures

## 🛠️ Troubleshooting

### Common Issues
1. **Connection timeouts** - Check network connectivity
2. **Authentication failures** - Verify credentials
3. **Performance issues** - Check connection pool settings

### Debug Mode
Set `MCP_PROFILE=development` for verbose logging.
