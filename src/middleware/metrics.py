"""Metrics collection middleware."""

import time
import asyncio
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a specific operation."""
    count: int = 0
    total_time: float = 0.0
    errors: int = 0
    last_error: Optional[str] = None
    last_execution: Optional[datetime] = None
    
    @property
    def avg_time(self) -> float:
        """Average execution time."""
        return self.total_time / self.count if self.count > 0 else 0.0
    
    @property
    def error_rate(self) -> float:
        """Error rate percentage."""
        return (self.errors / self.count * 100) if self.count > 0 else 0.0


class MetricsCollector:
    """Collect and report metrics."""
    
    def __init__(self):
        self.metrics: Dict[str, OperationMetrics] = defaultdict(OperationMetrics)
        self._lock = asyncio.Lock()
        self.start_time = datetime.utcnow()
    
    async def record_operation(
        self,
        operation: str,
        duration: float,
        success: bool,
        error: Optional[str] = None
    ):
        """Record operation metrics."""
        async with self._lock:
            metric = self.metrics[operation]
            metric.count += 1
            metric.total_time += duration
            metric.last_execution = datetime.utcnow()
            
            if not success:
                metric.errors += 1
                metric.last_error = error
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        async with self._lock:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            
            return {
                "uptime_seconds": round(uptime, 2),
                "operations": {
                    operation: {
                        "count": metric.count,
                        "total_time": round(metric.total_time, 3),
                        "avg_time": round(metric.avg_time, 3),
                        "errors": metric.errors,
                        "error_rate": round(metric.error_rate, 1),
                        "last_error": metric.last_error,
                        "last_execution": metric.last_execution.isoformat() if metric.last_execution else None
                    }
                    for operation, metric in self.metrics.items()
                }
            }
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        async with self._lock:
            total_operations = sum(m.count for m in self.metrics.values())
            total_errors = sum(m.errors for m in self.metrics.values())
            total_time = sum(m.total_time for m in self.metrics.values())
            
            return {
                "total_operations": total_operations,
                "total_errors": total_errors,
                "overall_error_rate": round((total_errors / total_operations * 100) if total_operations > 0 else 0, 1),
                "total_execution_time": round(total_time, 3),
                "avg_execution_time": round(total_time / total_operations, 3) if total_operations > 0 else 0,
                "operations_count": len(self.metrics),
                "uptime_seconds": round((datetime.utcnow() - self.start_time).total_seconds(), 2)
            }
    
    def create_middleware(self):
        """Create middleware decorator."""
        def middleware(func: Callable):
            async def wrapper(*args, **kwargs):
                operation = func.__name__
                start_time = time.time()
                error = None
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    error = str(e)
                    raise
                finally:
                    duration = time.time() - start_time
                    await self.record_operation(
                        operation=operation,
                        duration=duration,
                        success=(error is None),
                        error=error
                    )
            
            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper
        
        return middleware


# Global metrics collector instance
metrics_collector = MetricsCollector()
