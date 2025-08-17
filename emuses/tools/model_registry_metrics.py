"""Model registry metrics integration.

This module provides metrics collection for model registry operations,
integrating with the existing Prometheus observability infrastructure.
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional, Union
from uuid import UUID

from emuses.observability.metrics import (
    get_metrics_registry,
    model_downloads_total,
    model_registry_size,
    model_storage_bytes,
    http_request_duration_seconds,
    pipeline_errors_total
)

logger = logging.getLogger(__name__)


class ModelRegistryMetrics:
    """Metrics collector for model registry operations.
    
    Provides centralized metrics collection for all registry modes with
    minimal performance overhead and consistent labeling.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern to prevent duplicate metrics registration."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize registry metrics collector."""
        if ModelRegistryMetrics._initialized:
            return
            
        self._metrics_registry = get_metrics_registry()
        
        # Add model registry specific metrics
        from prometheus_client import Counter, Histogram, Gauge
        
        # Registry operation metrics
        self.registry_operations_total = Counter(
            "emuses_registry_operations_total",
            "Total number of registry operations by type and mode",
            ["operation", "registry_mode", "status"],
            registry=self._metrics_registry.registry
        )
        
        self.registry_operation_duration = Histogram(
            "emuses_registry_operation_duration_seconds", 
            "Duration of registry operations",
            ["operation", "registry_mode"],
            registry=self._metrics_registry.registry,
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, float("inf"))
        )
        
        # Model operation metrics
        self.model_operations_total = Counter(
            "emuses_model_operations_total",
            "Total model operations by type and result",
            ["operation", "model_type", "status", "registry_mode"],
            registry=self._metrics_registry.registry
        )
        
        # Cache performance metrics
        self.cache_operations_total = Counter(
            "emuses_registry_cache_operations_total",
            "Total cache operations with hit/miss tracking",
            ["operation", "result"],
            registry=self._metrics_registry.registry
        )
        
        # User activity metrics
        self.user_registry_activity = Counter(
            "emuses_user_registry_activity_total",
            "User registry activity by operation type",
            ["user_id", "operation", "registry_mode"],
            registry=self._metrics_registry.registry
        )
        
        ModelRegistryMetrics._initialized = True
        
    @contextmanager
    def track_operation(self, operation: str, registry_mode: str, 
                       user_id: Optional[str] = None, 
                       model_type: Optional[str] = None):
        """Track registry operation with metrics.
        
        Parameters
        ----------
        operation : str
            Operation name (e.g., 'list_models', 'install_model')
        registry_mode : str
            Registry mode (LOCAL, DATABASE, CLOUD)
        user_id : Optional[str]
            User ID for activity tracking
        model_type : Optional[str]
            Model type for model-specific operations
        """
        start_time = time.perf_counter()
        status = "success"
        
        try:
            yield
            
        except Exception as e:
            status = "error"
            
            # Track error details
            pipeline_errors_total.labels(
                stage=f"registry_{operation}",
                error_type=e.__class__.__name__
            ).inc()
            
            raise
            
        finally:
            duration = time.perf_counter() - start_time
            
            # Track operation metrics
            self.registry_operations_total.labels(
                operation=operation,
                registry_mode=registry_mode,
                status=status
            ).inc()
            
            self.registry_operation_duration.labels(
                operation=operation,
                registry_mode=registry_mode
            ).observe(duration)
            
            # Track user activity if user_id provided
            if user_id:
                self.user_registry_activity.labels(
                    user_id=user_id,
                    operation=operation, 
                    registry_mode=registry_mode
                ).inc()
                
            # Track model operations if applicable
            if model_type:
                self.model_operations_total.labels(
                    operation=operation,
                    model_type=model_type,
                    status=status,
                    registry_mode=registry_mode
                ).inc()
    
    def track_model_download(self, model_id: str, model_type: str, 
                           user_id: str, download_method: str = "registry"):
        """Track model download event.
        
        Parameters
        ----------
        model_id : str
            Model identifier
        model_type : str
            Type/category of model
        user_id : str
            User performing download
        download_method : str
            Download method (registry, direct, migration)
        """
        model_downloads_total.labels(
            model_id=model_id,
            model_type=model_type,
            user_id=user_id,
            download_method=download_method
        ).inc()
    
    def update_registry_size(self, registry_mode: str, visibility: str, count: int):
        """Update registry size gauge.
        
        Parameters
        ----------
        registry_mode : str
            Registry mode (LOCAL, DATABASE, CLOUD)
        visibility : str
            Model visibility (public, private, workspace)
        count : int
            Number of models
        """
        model_registry_size.labels(
            registry_type=registry_mode,
            visibility=visibility
        ).set(count)
        
    def track_model_storage(self, size_bytes: int, model_type: str = "unknown"):
        """Track model storage size.
        
        Parameters
        ----------
        size_bytes : int
            Model size in bytes
        model_type : str
            Type/category of model
        """
        model_storage_bytes.labels(model_type=model_type).observe(size_bytes)
        
    def track_cache_operation(self, operation: str, result: str):
        """Track cache operation (hit/miss/invalidate).
        
        Parameters
        ----------
        operation : str
            Cache operation (get, set, invalidate)
        result : str
            Operation result (hit, miss, success, error)
        """
        self.cache_operations_total.labels(
            operation=operation,
            result=result
        ).inc()


# Global metrics collector instance
_registry_metrics = ModelRegistryMetrics()


def get_registry_metrics() -> ModelRegistryMetrics:
    """Get the global registry metrics collector."""
    return _registry_metrics


# Convenience functions for common operations
def track_list_models(registry_mode: str, user_id: Optional[str] = None):
    """Context manager for tracking list_models operations."""
    return _registry_metrics.track_operation("list_models", registry_mode, user_id)


def track_install_model(registry_mode: str, model_type: str, 
                       user_id: Optional[str] = None):
    """Context manager for tracking install_model operations.""" 
    return _registry_metrics.track_operation(
        "install_model", registry_mode, user_id, model_type
    )


def track_search_models(registry_mode: str, user_id: Optional[str] = None):
    """Context manager for tracking search_models operations."""
    return _registry_metrics.track_operation("search_models", registry_mode, user_id)


def track_get_model_info(registry_mode: str, user_id: Optional[str] = None):
    """Context manager for tracking get_model_info operations."""
    return _registry_metrics.track_operation("get_model_info", registry_mode, user_id)


def track_remove_model(registry_mode: str, model_type: str,
                      user_id: Optional[str] = None):
    """Context manager for tracking remove_model operations."""
    return _registry_metrics.track_operation(
        "remove_model", registry_mode, user_id, model_type
    )


def track_model_download(model_id: str, model_type: str, user_id: str, 
                        download_method: str = "registry"):
    """Track model download event."""
    _registry_metrics.track_model_download(model_id, model_type, user_id, download_method)


def update_registry_size(registry_mode: str, visibility: str, count: int):
    """Update registry size gauge."""
    _registry_metrics.update_registry_size(registry_mode, visibility, count)


def track_model_storage(size_bytes: int, model_type: str = "unknown"):
    """Track model storage size."""
    _registry_metrics.track_model_storage(size_bytes, model_type)


def track_cache_hit():
    """Track cache hit."""
    _registry_metrics.track_cache_operation("get", "hit")


def track_cache_miss():
    """Track cache miss."""
    _registry_metrics.track_cache_operation("get", "miss")


def track_cache_set():
    """Track cache set operation."""
    _registry_metrics.track_cache_operation("set", "success")


def track_cache_invalidate():
    """Track cache invalidation."""
    _registry_metrics.track_cache_operation("invalidate", "success")