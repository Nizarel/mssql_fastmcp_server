"""
Configuration management for MSSQL MCP Server.
Provides structured configuration with environment variable support and validation.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class TransportType(Enum):
    """Supported transport types for MCP server."""
    STDIO = "stdio"
    SSE = "sse"


class OutputFormat(Enum):
    """Supported output formats."""
    CSV = "csv"
    JSON = "json"
    MARKDOWN = "markdown"
    TABLE = "table"


class LogLevel(Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    server: str
    database: str
    username: str
    password: str
    port: int = 1433
    timeout: int = 30
    driver: str = "ODBC Driver 17 for SQL Server"
    encrypt: bool = True
    trust_server_certificate: bool = False
    connection_timeout: int = 30
    command_timeout: int = 30
    
    def get_connection_string(self) -> str:
        """Get the connection string for ODBC."""
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.server},{self.port};"
            f"DATABASE={self.database};"
            f"UID={self.username};"
            f"PWD={self.password};"
            f"Encrypt={'yes' if self.encrypt else 'no'};"
            f"TrustServerCertificate={'yes' if self.trust_server_certificate else 'no'};"
            f"Connection Timeout={self.connection_timeout};"
            f"Command Timeout={self.command_timeout};"
        )
    
    def get_pymssql_params(self) -> Dict[str, Any]:
        """Get connection parameters for pymssql."""
        return {
            'server': self.server,
            'database': self.database,
            'user': self.username,
            'password': self.password,
            'port': self.port,
            'timeout': self.timeout,
            'login_timeout': self.connection_timeout,
            'charset': 'UTF-8',
            'as_dict': False
        }


@dataclass
class ConnectionPoolConfig:
    """Connection pool configuration."""
    min_connections: int = 1
    max_connections: int = 10
    connection_timeout: int = 30
    idle_timeout: int = 300
    max_lifetime: int = 3600
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    enabled: bool = True
    requests_per_minute: int = 60
    burst_limit: int = 10
    window_size: int = 60


@dataclass
class CacheConfig:
    """Cache configuration."""
    enabled: bool = True
    max_size: int = 1000
    ttl_seconds: int = 300
    cleanup_interval: int = 60


@dataclass
class ServerConfig:
    """Server configuration."""
    # Basic server settings
    command_name: str = "mssql-mcp"
    max_rows: int = 1000
    log_level: LogLevel = LogLevel.INFO
    transport: TransportType = TransportType.STDIO
    default_output_format: OutputFormat = OutputFormat.CSV
    
    # Server features
    enable_health_checks: bool = True
    enable_streaming: bool = True
    enable_caching: bool = True
    enable_rate_limiting: bool = True
    
    # SSE specific settings
    sse_host: str = "localhost"
    sse_port: int = 8080
    sse_cors_origins: List[str] = field(default_factory=lambda: ["*"])
    
    # Security settings
    allowed_schemas: List[str] = field(default_factory=list)
    blocked_schemas: List[str] = field(default_factory=lambda: ["sys", "information_schema"])
    max_query_length: int = 10000
    enable_ddl: bool = False
    enable_dml: bool = True
    
    # Performance settings
    query_timeout: int = 30
    max_concurrent_queries: int = 5
    
    # Component configurations
    connection_pool: ConnectionPoolConfig = field(default_factory=ConnectionPoolConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


@dataclass
class AppConfig:
    """Application configuration combining all components."""
    database: DatabaseConfig
    server: ServerConfig = field(default_factory=ServerConfig)
    
    @classmethod
    def from_environment(cls, profile: Optional[str] = None) -> 'AppConfig':
        """Load configuration from environment variables."""
        profile_prefix = f"{profile.upper()}_" if profile else ""
        
        # Database configuration
        database_config = DatabaseConfig(
            server=os.getenv(f"{profile_prefix}DB_SERVER", os.getenv("DB_SERVER", "")),
            database=os.getenv(f"{profile_prefix}DB_DATABASE", os.getenv("DB_DATABASE", "")),
            username=os.getenv(f"{profile_prefix}DB_USERNAME", os.getenv("DB_USERNAME", "")),
            password=os.getenv(f"{profile_prefix}DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
            port=int(os.getenv(f"{profile_prefix}DB_PORT", os.getenv("DB_PORT", "1433"))),
            timeout=int(os.getenv(f"{profile_prefix}DB_TIMEOUT", os.getenv("DB_TIMEOUT", "30"))),
            driver=os.getenv(f"{profile_prefix}DB_DRIVER", os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")),
            encrypt=os.getenv(f"{profile_prefix}DB_ENCRYPT", os.getenv("DB_ENCRYPT", "true")).lower() == "true",
            trust_server_certificate=os.getenv(f"{profile_prefix}DB_TRUST_CERT", os.getenv("DB_TRUST_CERT", "false")).lower() == "true",
            connection_timeout=int(os.getenv(f"{profile_prefix}DB_CONNECTION_TIMEOUT", os.getenv("DB_CONNECTION_TIMEOUT", "30"))),
            command_timeout=int(os.getenv(f"{profile_prefix}DB_COMMAND_TIMEOUT", os.getenv("DB_COMMAND_TIMEOUT", "30")))
        )
        
        # Server configuration
        server_config = ServerConfig(
            command_name=os.getenv(f"{profile_prefix}SERVER_COMMAND", os.getenv("SERVER_COMMAND", "mssql-mcp")),
            max_rows=int(os.getenv(f"{profile_prefix}SERVER_MAX_ROWS", os.getenv("SERVER_MAX_ROWS", "1000"))),
            log_level=LogLevel(os.getenv(f"{profile_prefix}LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO"))),
            transport=TransportType(os.getenv(f"{profile_prefix}TRANSPORT", os.getenv("TRANSPORT", "stdio"))),
            default_output_format=OutputFormat(os.getenv(f"{profile_prefix}OUTPUT_FORMAT", os.getenv("OUTPUT_FORMAT", "csv"))),
            
            # Feature flags
            enable_health_checks=os.getenv(f"{profile_prefix}ENABLE_HEALTH_CHECKS", os.getenv("ENABLE_HEALTH_CHECKS", "true")).lower() == "true",
            enable_streaming=os.getenv(f"{profile_prefix}ENABLE_STREAMING", os.getenv("ENABLE_STREAMING", "true")).lower() == "true",
            enable_caching=os.getenv(f"{profile_prefix}ENABLE_CACHING", os.getenv("ENABLE_CACHING", "true")).lower() == "true",
            enable_rate_limiting=os.getenv(f"{profile_prefix}ENABLE_RATE_LIMITING", os.getenv("ENABLE_RATE_LIMITING", "true")).lower() == "true",
            
            # SSE settings
            sse_host=os.getenv(f"{profile_prefix}SSE_HOST", os.getenv("SSE_HOST", "localhost")),
            sse_port=int(os.getenv(f"{profile_prefix}SSE_PORT", os.getenv("SSE_PORT", "8080"))),
            sse_cors_origins=json.loads(os.getenv(f"{profile_prefix}SSE_CORS_ORIGINS", os.getenv("SSE_CORS_ORIGINS", '["*"]'))),
            
            # Security settings
            allowed_schemas=json.loads(os.getenv(f"{profile_prefix}ALLOWED_SCHEMAS", os.getenv("ALLOWED_SCHEMAS", "[]"))),
            blocked_schemas=json.loads(os.getenv(f"{profile_prefix}BLOCKED_SCHEMAS", os.getenv("BLOCKED_SCHEMAS", '["sys", "information_schema"]'))),
            max_query_length=int(os.getenv(f"{profile_prefix}MAX_QUERY_LENGTH", os.getenv("MAX_QUERY_LENGTH", "10000"))),
            enable_ddl=os.getenv(f"{profile_prefix}ENABLE_DDL", os.getenv("ENABLE_DDL", "false")).lower() == "true",
            enable_dml=os.getenv(f"{profile_prefix}ENABLE_DML", os.getenv("ENABLE_DML", "true")).lower() == "true",
            
            # Performance settings
            query_timeout=int(os.getenv(f"{profile_prefix}QUERY_TIMEOUT", os.getenv("QUERY_TIMEOUT", "30"))),
            max_concurrent_queries=int(os.getenv(f"{profile_prefix}MAX_CONCURRENT_QUERIES", os.getenv("MAX_CONCURRENT_QUERIES", "5")))
        )
        
        # Connection pool configuration
        server_config.connection_pool = ConnectionPoolConfig(
            min_connections=int(os.getenv(f"{profile_prefix}POOL_MIN_CONNECTIONS", os.getenv("POOL_MIN_CONNECTIONS", "1"))),
            max_connections=int(os.getenv(f"{profile_prefix}POOL_MAX_CONNECTIONS", os.getenv("POOL_MAX_CONNECTIONS", "10"))),
            connection_timeout=int(os.getenv(f"{profile_prefix}POOL_CONNECTION_TIMEOUT", os.getenv("POOL_CONNECTION_TIMEOUT", "30"))),
            idle_timeout=int(os.getenv(f"{profile_prefix}POOL_IDLE_TIMEOUT", os.getenv("POOL_IDLE_TIMEOUT", "300"))),
            max_lifetime=int(os.getenv(f"{profile_prefix}POOL_MAX_LIFETIME", os.getenv("POOL_MAX_LIFETIME", "3600"))),
            retry_attempts=int(os.getenv(f"{profile_prefix}POOL_RETRY_ATTEMPTS", os.getenv("POOL_RETRY_ATTEMPTS", "3"))),
            retry_delay=float(os.getenv(f"{profile_prefix}POOL_RETRY_DELAY", os.getenv("POOL_RETRY_DELAY", "1.0")))
        )
        
        # Rate limiting configuration
        server_config.rate_limit = RateLimitConfig(
            enabled=os.getenv(f"{profile_prefix}RATE_LIMIT_ENABLED", os.getenv("RATE_LIMIT_ENABLED", "true")).lower() == "true",
            requests_per_minute=int(os.getenv(f"{profile_prefix}RATE_LIMIT_RPM", os.getenv("RATE_LIMIT_RPM", "60"))),
            burst_limit=int(os.getenv(f"{profile_prefix}RATE_LIMIT_BURST", os.getenv("RATE_LIMIT_BURST", "10"))),
            window_size=int(os.getenv(f"{profile_prefix}RATE_LIMIT_WINDOW", os.getenv("RATE_LIMIT_WINDOW", "60")))
        )
        
        # Cache configuration
        server_config.cache = CacheConfig(
            enabled=os.getenv(f"{profile_prefix}CACHE_ENABLED", os.getenv("CACHE_ENABLED", "true")).lower() == "true",
            max_size=int(os.getenv(f"{profile_prefix}CACHE_MAX_SIZE", os.getenv("CACHE_MAX_SIZE", "1000"))),
            ttl_seconds=int(os.getenv(f"{profile_prefix}CACHE_TTL", os.getenv("CACHE_TTL", "300"))),
            cleanup_interval=int(os.getenv(f"{profile_prefix}CACHE_CLEANUP_INTERVAL", os.getenv("CACHE_CLEANUP_INTERVAL", "60")))
        )
        
        return cls(database=database_config, server=server_config)
    
    @classmethod
    def from_file(cls, config_path: str) -> 'AppConfig':
        """Load configuration from JSON file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        # Parse database config
        db_data = config_data.get('database', {})
        database_config = DatabaseConfig(**db_data)
        
        # Parse server config
        server_data = config_data.get('server', {})
        
        # Handle nested configurations
        connection_pool_data = server_data.pop('connection_pool', {})
        rate_limit_data = server_data.pop('rate_limit', {})
        cache_data = server_data.pop('cache', {})
        
        server_config = ServerConfig(**server_data)
        server_config.connection_pool = ConnectionPoolConfig(**connection_pool_data)
        server_config.rate_limit = RateLimitConfig(**rate_limit_data)
        server_config.cache = CacheConfig(**cache_data)
        
        return cls(database=database_config, server=server_config)
    
    def validate(self) -> None:
        """Validate configuration settings."""
        errors = []
        
        # Database validation
        if not self.database.server:
            errors.append("Database server is required")
        if not self.database.database:
            errors.append("Database name is required")
        if not self.database.username:
            errors.append("Database username is required")
        if not self.database.password:
            errors.append("Database password is required")
        
        # Server validation
        if self.server.max_rows <= 0:
            errors.append("max_rows must be positive")
        if self.server.query_timeout <= 0:
            errors.append("query_timeout must be positive")
        if self.server.max_concurrent_queries <= 0:
            errors.append("max_concurrent_queries must be positive")
        
        # Connection pool validation
        if self.server.connection_pool.min_connections < 0:
            errors.append("min_connections must be non-negative")
        if self.server.connection_pool.max_connections <= 0:
            errors.append("max_connections must be positive")
        if self.server.connection_pool.min_connections > self.server.connection_pool.max_connections:
            errors.append("min_connections cannot exceed max_connections")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")


# Global configuration instance
_config: Optional[AppConfig] = None


def load_config(profile: Optional[str] = None, config_file: Optional[str] = None) -> AppConfig:
    """
    Load application configuration.
    
    Args:
        profile: Configuration profile name (e.g., 'dev', 'prod')
        config_file: Path to configuration file (JSON)
        
    Returns:
        AppConfig: Loaded and validated configuration
    """
    global _config
    
    if _config is not None:
        return _config
    
    try:
        if config_file:
            logger.info(f"Loading configuration from file: {config_file}")
            _config = AppConfig.from_file(config_file)
        else:
            logger.info(f"Loading configuration from environment (profile: {profile or 'default'})")
            _config = AppConfig.from_environment(profile)
        
        _config.validate()
        logger.info("Configuration loaded and validated successfully")
        return _config
        
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise


def get_config() -> AppConfig:
    """Get the current configuration."""
    if _config is None:
        return load_config()
    return _config


def reload_config(profile: Optional[str] = None, config_file: Optional[str] = None) -> AppConfig:
    """Reload configuration."""
    global _config
    _config = None
    return load_config(profile, config_file)


# Legacy compatibility functions
def load_database_config() -> DatabaseConfig:
    """Load database configuration (legacy compatibility)."""
    return get_config().database


def load_server_config() -> ServerConfig:
    """Load server configuration (legacy compatibility)."""
    return get_config().server


def get_connection_params(db_config: DatabaseConfig) -> Dict[str, Any]:
    """Get connection parameters for pymssql (legacy compatibility)."""
    return db_config.get_pymssql_params()
