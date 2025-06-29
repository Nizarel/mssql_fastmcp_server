# Configuration Guide

## Overview

The MSSQL MCP Server uses JSON configuration files to manage database connections, server settings, and feature flags. Configuration can be environment-specific (development, staging, production).

## Configuration Files

Configuration files are located in the `configs/` directory:

- `development.json` - Development environment settings
- `staging.json` - Staging environment settings  
- `production.json` - Production environment settings

## Environment Variables

Set these environment variables to control configuration:

- `MCP_PROFILE` - Configuration profile (development, staging, production)
- `MCP_CONFIG_FILE` - Path to custom configuration file

Environment variables in configuration files are expanded automatically (e.g., `${DB_PASSWORD}`).

## Configuration Structure

### Database Configuration

```json
{
  "database": {
    "server": "localhost",
    "database": "MyDatabase", 
    "username": "myuser",
    "password": "mypassword",
    "port": 1433,
    "encrypt": true,
    "trust_server_certificate": false
  }
}
```

**Parameters:**

- `server` - SQL Server hostname or IP address
- `database` - Database name to connect to
- `username` - Database username
- `password` - Database password (supports environment variables)
- `port` - SQL Server port (default: 1433)
- `encrypt` - Enable SSL encryption (recommended for production)
- `trust_server_certificate` - Trust self-signed certificates

### Server Configuration

```json
{
  "server": {
    "transport": "stdio",
    "max_rows": 1000,
    "query_timeout": 30,
    "max_concurrent_queries": 5,
    "enable_caching": true,
    "enable_rate_limiting": false,
    "enable_health_checks": true,
    "enable_streaming": false,
    "default_output_format": "csv",
    "log_level": "INFO"
  }
}
```

**Parameters:**

- `transport` - Communication transport: "stdio" or "sse"
- `sse_port` - Port for SSE transport (if transport is "sse")
- `max_rows` - Maximum rows returned per query
- `query_timeout` - Query execution timeout in seconds
- `max_concurrent_queries` - Maximum concurrent queries allowed
- `enable_caching` - Enable query result caching
- `enable_rate_limiting` - Enable request rate limiting
- `enable_health_checks` - Enable health check endpoints
- `enable_streaming` - Enable streaming for large results
- `default_output_format` - Default format: "csv", "json", "markdown", "table"
- `log_level` - Logging level: "DEBUG", "INFO", "WARNING", "ERROR"

### Connection Pool Configuration

```json
{
  "server": {
    "connection_pool": {
      "min_connections": 2,
      "max_connections": 10,
      "connection_timeout": 30,
      "pool_timeout": 30
    }
  }
}
```

**Parameters:**

- `min_connections` - Minimum connections to maintain in pool
- `max_connections` - Maximum connections allowed in pool
- `connection_timeout` - Timeout for establishing new connections
- `pool_timeout` - Timeout for acquiring connections from pool

### Cache Configuration

```json
{
  "server": {
    "cache": {
      "max_size": 100,
      "ttl_seconds": 300
    }
  }
}
```

**Parameters:**

- `max_size` - Maximum number of cached query results
- `ttl_seconds` - Time-to-live for cached results in seconds

### Rate Limiting Configuration

```json
{
  "server": {
    "rate_limit": {
      "requests_per_minute": 60,
      "burst_limit": 10
    }
  }
}
```

**Parameters:**

- `requests_per_minute` - Maximum requests per minute per client
- `burst_limit` - Maximum burst requests allowed

## Environment-Specific Settings

### Development

- Uses local database connections
- Minimal rate limiting
- Detailed logging
- Small connection pools
- Lower security settings for convenience

### Staging

- Mirrors production settings
- Enhanced logging
- Moderate connection pools
- Production-like security

### Production

- Secure database connections with encryption
- Strict rate limiting
- Optimized connection pools
- Minimal logging for performance
- Maximum security settings

## Security Considerations

### Database Security

1. **Use encrypted connections** in production (`encrypt: true`)
2. **Store passwords in environment variables**, not configuration files
3. **Use least-privilege database accounts**
4. **Enable server certificate validation** in production

### Network Security

1. **Use firewalls** to restrict database access
2. **Consider VPN or private networks** for database connections
3. **Monitor connection attempts** and failed authentications

### Application Security

1. **Enable rate limiting** to prevent abuse
2. **Validate all SQL queries** for injection attempts
3. **Log security events** for monitoring
4. **Use strong authentication** if implementing custom auth

## Monitoring Configuration

Configure these settings for production monitoring:

```json
{
  "server": {
    "enable_health_checks": true,
    "log_level": "WARNING",
    "connection_pool": {
      "min_connections": 10,
      "max_connections": 50
    },
    "rate_limit": {
      "requests_per_minute": 300,
      "burst_limit": 50
    }
  }
}
```

## Troubleshooting

### Connection Issues

1. Verify database server is accessible
2. Check firewall settings
3. Validate credentials
4. Test with SQL Server Management Studio first

### Performance Issues

1. Increase connection pool size
2. Enable caching for read-heavy workloads
3. Adjust query timeout for long-running queries
4. Monitor rate limiting effects

### Memory Issues

1. Reduce cache size
2. Lower max_rows limit
3. Decrease connection pool size
4. Enable streaming for large results

## Example Configurations

### Minimal Development Setup

```json
{
  "database": {
    "server": "localhost",
    "database": "TestDB",
    "username": "sa",
    "password": "Password123!",
    "encrypt": false,
    "trust_server_certificate": true
  },
  "server": {
    "transport": "stdio",
    "enable_caching": false,
    "enable_rate_limiting": false,
    "log_level": "DEBUG"
  }
}
```

### High-Performance Production Setup

```json
{
  "database": {
    "server": "${DB_SERVER}",
    "database": "${DB_DATABASE}",
    "username": "${DB_USERNAME}",
    "password": "${DB_PASSWORD}",
    "encrypt": true,
    "trust_server_certificate": false
  },
  "server": {
    "transport": "sse",
    "sse_port": 8080,
    "max_rows": 50000,
    "enable_caching": true,
    "enable_rate_limiting": true,
    "enable_streaming": true,
    "connection_pool": {
      "min_connections": 20,
      "max_connections": 100
    },
    "cache": {
      "max_size": 5000,
      "ttl_seconds": 3600
    }
  }
}
```
