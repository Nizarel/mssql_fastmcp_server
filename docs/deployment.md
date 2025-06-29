# Deployment Guide

## Overview

This guide covers deploying the MSSQL MCP Server in different environments using the modular architecture. The server supports multiple deployment scenarios from development to production.

## Prerequisites

### System Requirements

- Python 3.11 or higher
- Microsoft SQL Server 2016 or higher (or SQL Server on Linux/Docker)
- Required Python packages (see requirements.txt)

### Database Requirements

- SQL Server instance with network access enabled
- Database user with appropriate permissions
- Firewall rules allowing connections on SQL Server port (default 1433)

## Installation

### 1. Clone and Setup

```bash
git clone <repository-url>
cd mssql_fastmcp_server
pip install -r requirements.txt
```

### 2. Configure Database

Create a configuration file or set environment variables:

```bash
export MCP_PROFILE=production
export DB_SERVER=your-sql-server
export DB_DATABASE=your-database
export DB_USERNAME=your-username
export DB_PASSWORD=your-password
```

### 3. Test Connection

```bash
python scripts/health_check.py --profile production
```

## Deployment Options

### Option 1: Stdio Transport (MCP Client Integration)

Best for: Integration with MCP clients like Claude Desktop

```bash
# Start server with stdio transport
python -m mssql_mcp_server
```

Configuration example:
```json
{
  "server": {
    "transport": "stdio",
    "enable_caching": true,
    "enable_rate_limiting": false
  }
}
```

### Option 2: SSE Transport (Web Service)

Best for: Web applications, API access, monitoring dashboards

```bash
# Start server with SSE transport
MCP_PROFILE=production python -m mssql_mcp_server
```

Configuration example:
```json
{
  "server": {
    "transport": "sse",
    "sse_port": 8080,
    "enable_rate_limiting": true
  }
}
```

## Production Deployment

### Using Docker

1. **Build Docker Image**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/

# Create non-root user
RUN useradd -m mcp && chown -R mcp:mcp /app
USER mcp

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python scripts/health_check.py || exit 1

# Default command
CMD ["python", "-m", "src.mssql_mcp_server"]
```

2. **Docker Compose Setup**

```yaml
version: '3.8'

services:
  mcp-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - MCP_PROFILE=production
      - DB_SERVER=sql-server
      - DB_DATABASE=MyDatabase
      - DB_USERNAME=mcpuser
      - DB_PASSWORD=${DB_PASSWORD}
    depends_on:
      - sql-server
    restart: unless-stopped
    
  sql-server:
    image: mcr.microsoft.com/mssql/server:2022-latest
    environment:
      - ACCEPT_EULA=Y
      - SA_PASSWORD=${SA_PASSWORD}
    ports:
      - "1433:1433"
    volumes:
      - sqldata:/var/opt/mssql

volumes:
  sqldata:
```

### Using Systemd (Linux)

1. **Create Service File**

```ini
[Unit]
Description=MSSQL MCP Server
After=network.target

[Service]
Type=simple
User=mcp
Group=mcp
WorkingDirectory=/opt/mssql-mcp-server
Environment=MCP_PROFILE=production
Environment=DB_SERVER=localhost
Environment=DB_DATABASE=MyDatabase
Environment=DB_USERNAME=mcpuser
Environment=DB_PASSWORD=your-secure-password
ExecStart=/opt/mssql-mcp-server/venv/bin/python -m mssql_mcp_server
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

2. **Enable and Start Service**

```bash
sudo systemctl enable mssql-mcp-server
sudo systemctl start mssql-mcp-server
sudo systemctl status mssql-mcp-server
```

## Monitoring and Health Checks

### Health Check Endpoint

The server provides a health check function for monitoring:

```bash
# Check server health
python scripts/health_check.py

# Example response
{
  "status": "healthy",
  "timestamp": "2025-06-29T10:30:00Z",
  "database": {
    "success": true,
    "response_time": 0.045
  },
  "connection_pool": {
    "current_size": 5,
    "available": 3
  }
}
```

### Monitoring with External Tools

#### Prometheus Integration

Add metrics endpoint to your monitoring setup:

```python
# Custom metrics collector integration
from prometheus_client import Counter, Histogram, Gauge

query_count = Counter('mcp_queries_total', 'Total queries executed')
query_duration = Histogram('mcp_query_duration_seconds', 'Query execution time')
active_connections = Gauge('mcp_active_connections', 'Active database connections')
```

#### Log Monitoring

Configure log aggregation for production monitoring:

```json
{
  "server": {
    "log_level": "WARNING",
    "structured_logging": true
  }
}
```

## Performance Tuning

### Connection Pool Optimization

```json
{
  "server": {
    "connection_pool": {
      "min_connections": 10,
      "max_connections": 50,
      "connection_timeout": 30
    }
  }
}
```

### Cache Configuration

```json
{
  "server": {
    "cache": {
      "max_size": 1000,
      "ttl_seconds": 1800
    }
  }
}
```

### Rate Limiting

```json
{
  "server": {
    "rate_limit": {
      "requests_per_minute": 300,
      "burst_limit": 50
    }
  }
}
```

## Security Hardening

### Database Security

1. **Create dedicated database user:**

```sql
CREATE LOGIN mcpuser WITH PASSWORD = 'SecurePassword123!';
CREATE USER mcpuser FOR LOGIN mcpuser;

-- Grant minimum required permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO mcpuser;
```

2. **Enable encryption:**

```json
{
  "database": {
    "encrypt": true,
    "trust_server_certificate": false
  }
}
```

### Network Security

1. **Configure firewall rules**
2. **Use private networks where possible**
3. **Enable SQL Server authentication logging**

### Application Security

1. **Enable rate limiting in production**
2. **Use strong passwords and rotate regularly**
3. **Monitor failed authentication attempts**
4. **Keep dependencies updated**

## Troubleshooting

### Common Issues

#### Connection Timeouts

```bash
# Check SQL Server is running
sqlcmd -S localhost -U sa -P password -Q "SELECT @@VERSION"

# Test network connectivity
telnet sql-server 1433
```

#### Permission Errors

```sql
-- Check user permissions
SELECT 
    p.permission_name,
    p.state_desc,
    s.name as schema_name
FROM sys.database_permissions p
JOIN sys.schemas s ON p.major_id = s.schema_id
WHERE grantee_principal_id = USER_ID('mcpuser');
```

#### Memory Issues

1. Reduce connection pool size
2. Lower cache limits
3. Decrease max_rows setting
4. Enable streaming for large queries

### Debug Mode

Enable debug logging for troubleshooting:

```json
{
  "server": {
    "log_level": "DEBUG"
  }
}
```

## Backup and Recovery

### Configuration Backup

1. Back up configuration files
2. Document environment variables
3. Store database connection details securely

### Database Backup

Ensure regular database backups are configured:

```sql
-- Example backup command
BACKUP DATABASE MyDatabase 
TO DISK = 'C:\Backups\MyDatabase.bak'
WITH FORMAT, INIT;
```

## Scaling Considerations

### Horizontal Scaling

1. Deploy multiple server instances behind a load balancer
2. Use shared cache (Redis) for multiple instances
3. Monitor database connection limits

### Vertical Scaling

1. Increase connection pool sizes
2. Add more memory for caching
3. Optimize database queries and indexes

## Migration Guide

### Upgrading from Legacy Architecture

1. **Backup current configuration**
2. **Test new modular architecture** in development
3. **Update configuration files** to new format
4. **Deploy with minimal downtime** using rolling updates
5. **Monitor performance** after upgrade
