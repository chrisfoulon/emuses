"""
EMUSES Observability Module

Provides lightweight monitoring capabilities using Prometheus metrics and structured logging.
Designed for <2% performance overhead while enabling comprehensive system monitoring.
"""

from .metrics import (
    MetricsRegistry,
    pipeline_duration,
    pipeline_errors_total,
    active_jobs,
    memory_usage_bytes,
    dataset_size_bytes,
    optimization_trials_total,
    http_requests_total,
    http_request_duration_seconds,
    get_metrics_registry
)

from .logging import setup_structured_logging, get_logger
from .context import create_span

__all__ = [
    'MetricsRegistry',
    'pipeline_duration', 
    'pipeline_errors_total',
    'active_jobs',
    'memory_usage_bytes',
    'dataset_size_bytes',
    'optimization_trials_total',
    'http_requests_total',
    'http_request_duration_seconds',
    'get_metrics_registry',
    'setup_structured_logging',
    'get_logger',
    'create_span'
]