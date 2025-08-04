"""
EMUSES Observability Module

Provides lightweight monitoring capabilities using Prometheus metrics and structured logging.
Designed for <2% performance overhead while enabling comprehensive system monitoring.
"""

from .context import create_span, track_scientific_operation
from .logging import get_logger, setup_structured_logging
from .metrics import (MetricsRegistry, active_jobs, dataset_size_bytes,
                      get_metrics_registry, http_request_duration_seconds,
                      http_requests_total, memory_usage_bytes,
                      optimization_trials_total, pipeline_duration,
                      pipeline_errors_total, track_http_request,
                      track_optimization_trial)

__all__ = [
    "MetricsRegistry",
    "pipeline_duration",
    "pipeline_errors_total",
    "active_jobs",
    "memory_usage_bytes",
    "dataset_size_bytes",
    "optimization_trials_total",
    "http_requests_total",
    "http_request_duration_seconds",
    "get_metrics_registry",
    "track_optimization_trial",
    "track_http_request",
    "setup_structured_logging",
    "get_logger",
    "create_span",
    "track_scientific_operation",
]
