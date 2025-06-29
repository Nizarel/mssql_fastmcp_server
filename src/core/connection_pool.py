"""Connection pool management for better performance."""

import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import pymssql
from queue import Queue, Empty
import threading
import time

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Thread-safe connection pool for pymssql."""
    
    def __init__(self, connection_params: Dict[str, Any], 
                 min_size: int = 2, 
                 max_size: int = 10,
                 timeout: float = 30.0):
        """
        Initialize connection pool.
        
        Args:
            connection_params: Parameters for pymssql.connect
            min_size: Minimum number of connections to maintain
            max_size: Maximum number of connections allowed
            timeout: Connection timeout in seconds
        """
        self._params = connection_params
        self._min_size = min_size
        self._max_size = max_size
        self._timeout = timeout
        self._pool = Queue(maxsize=max_size)
        self._size = 0
        self._lock = threading.Lock()
        self._closed = False
        
        # Pre-create minimum connections
        for _ in range(min_size):
            self._create_connection()
    
    def _create_connection(self) -> Optional[pymssql.Connection]:
        """Create a new database connection."""
        try:
            with self._lock:
                if self._size >= self._max_size:
                    return None
                self._size += 1
            
            conn = pymssql.connect(**self._params)
            self._pool.put(conn)
            logger.debug(f"Created new connection. Pool size: {self._size}")
            return conn
        except Exception as e:
            with self._lock:
                self._size -= 1
            logger.error(f"Failed to create connection: {e}")
            raise
    
    def _get_connection_sync(self) -> pymssql.Connection:
        """Get a connection from the pool."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        try:
            # Try to get from pool
            conn = self._pool.get(timeout=0.1)
            
            # Test if connection is alive
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            return conn
        except Empty:
            # Pool is empty, try to create new connection
            if self._size < self._max_size:
                conn = self._create_connection()
                if conn:
                    return self._pool.get()
            
            # Wait for a connection to be available
            return self._pool.get(timeout=self._timeout)
        except Exception:
            # Connection is dead, create a new one
            with self._lock:
                self._size -= 1
            self._create_connection()
            return self.get_connection()
    
    def release_connection(self, conn: pymssql.Connection):
        """Return a connection to the pool."""
        if self._closed:
            conn.close()
            return
        
        try:
            self._pool.put_nowait(conn)
        except:
            # Pool is full, close the connection
            conn.close()
            with self._lock:
                self._size -= 1
    
    def close(self):
        """Close all connections in the pool."""
        self._closed = True
        
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
        
        self._size = 0
        logger.info("Connection pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Async context manager for acquiring connections."""
        conn = None
        try:
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(None, self._get_connection_sync)
            yield conn
        finally:
            if conn:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.release_connection, conn)
    
    def _get_connection_sync(self) -> pymssql.Connection:
        """Synchronous get connection method for internal use."""
        if self._closed:
            raise RuntimeError("Connection pool is closed")
        
        try:
            # Try to get from pool
            conn = self._pool.get(timeout=0.1)
            
            # Test if connection is alive
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            return conn
        except Empty:
            # Pool is empty, try to create new connection
            if self._size < self._max_size:
                conn = self._create_connection()
                if conn:
                    return self._pool.get()
            
            # Wait for a connection to be available
            return self._pool.get(timeout=self._timeout)
        except Exception:
            # Connection is dead, create a new one
            with self._lock:
                self._size -= 1
            self._create_connection()
            return self._get_connection_sync()
    
    async def close(self):
        """Close all connections in the pool asynchronously."""
        self._closed = True
        
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
        
        self._size = 0
        logger.info("Connection pool closed")
