"""
Prometheus Metrics for EMUSES

Lightweight metrics collection focusing on scientific pipeline performance
and system health monitoring.
"""

import time
from contextlib import contextmanager
from typing import Optional

from prometheus_client import (CONTENT_TYPE_LATEST, CollectorRegistry, Counter,
                               Gauge, Histogram, generate_latest)


class MetricsRegistry:
    """
    Centralized metrics registry for EMUSES observability.

    Provides lightweight Prometheus metrics collection with focus on:
    - Scientific pipeline performance
    - System resource utilization
    - API request tracking
    - Error monitoring
    """

    def __init__(self):
        self.registry = CollectorRegistry()
        self._setup_metrics()

    def _setup_metrics(self):
        """Initialize all EMUSES metrics"""

        # Scientific Pipeline Metrics
        self.pipeline_duration = Histogram(
            "emuses_pipeline_duration_seconds",
            "Duration of pipeline operations by stage",
            ["stage", "user_id", "status"],
            registry=self.registry,
            buckets=(
                0.1,
                0.5,
                1.0,
                5.0,
                10.0,
                30.0,
                60.0,
                300.0,
                600.0,
                1800.0,
                3600.0,
                float("inf"),
            ),
        )

        self.pipeline_errors_total = Counter(
            "emuses_pipeline_errors_total",
            "Total number of pipeline errors by stage and type",
            ["stage", "error_type"],
            registry=self.registry,
        )

        self.optimization_trials_total = Counter(
            "emuses_optimization_trials_total",
            "Total number of optimization trials",
            ["stage", "trial_type"],
            registry=self.registry,
        )

        # System Resource Metrics
        self.memory_usage_bytes = Gauge(
            "emuses_memory_usage_bytes",
            "Current memory usage in bytes",
            ["stage", "process_type"],
            registry=self.registry,
        )

        self.active_jobs = Gauge(
            "emuses_active_jobs",
            "Number of currently active jobs",
            ["job_type", "user_id"],
            registry=self.registry,
        )

        self.dataset_size_bytes = Histogram(
            "emuses_dataset_size_bytes",
            "Size of datasets processed in bytes",
            ["dataset_type"],
            registry=self.registry,
            buckets=(1e6, 10e6, 100e6, 1e9, 10e9, 100e9, float("inf")),  # 1MB to 100GB
        )

        # HTTP API Metrics
        self.http_requests_total = Counter(
            "emuses_http_requests_total",
            "Total HTTP requests by method, endpoint, and status",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )

        self.http_request_duration_seconds = Histogram(
            "emuses_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            registry=self.registry,
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
        )

        # Model Registry Metrics
        self.model_downloads_total = Counter(
            "emuses_model_downloads_total",
            "Total number of model downloads",
            ["model_id", "model_type", "user_id", "download_method"],
            registry=self.registry,
        )

        self.model_registry_size = Gauge(
            "emuses_model_registry_size",
            "Total number of models in registry",
            ["registry_type", "visibility"],
            registry=self.registry,
        )

        self.model_analytics_operations_total = Counter(
            "emuses_model_analytics_operations_total",
            "Total number of analytics operations",
            ["operation_type", "status"],
            registry=self.registry,
        )

        self.model_recommendation_requests_total = Counter(
            "emuses_model_recommendation_requests_total",
            "Total number of recommendation requests",
            ["recommendation_type"],
            registry=self.registry,
        )

        self.model_storage_bytes = Histogram(
            "emuses_model_storage_bytes",
            "Model storage size in bytes",
            ["model_type"],
            registry=self.registry,
            buckets=(1e6, 10e6, 100e6, 1e9, 10e9, 100e9, float("inf")),  # 1MB to 100GB
        )

    def get_metrics(self) -> bytes:
        """Generate Prometheus metrics output"""
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """Get Prometheus metrics content type"""
        return CONTENT_TYPE_LATEST


# Global metrics registry instance
_metrics_registry = MetricsRegistry()

# Export individual metrics for convenience
pipeline_duration = _metrics_registry.pipeline_duration
pipeline_errors_total = _metrics_registry.pipeline_errors_total
optimization_trials_total = _metrics_registry.optimization_trials_total
memory_usage_bytes = _metrics_registry.memory_usage_bytes
active_jobs = _metrics_registry.active_jobs
dataset_size_bytes = _metrics_registry.dataset_size_bytes
http_requests_total = _metrics_registry.http_requests_total
http_request_duration_seconds = _metrics_registry.http_request_duration_seconds

# Model Registry metrics
model_downloads_total = _metrics_registry.model_downloads_total
model_registry_size = _metrics_registry.model_registry_size
model_analytics_operations_total = _metrics_registry.model_analytics_operations_total
model_recommendation_requests_total = _metrics_registry.model_recommendation_requests_total
model_storage_bytes = _metrics_registry.model_storage_bytes


def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry instance"""
    return _metrics_registry


@contextmanager
def track_pipeline_stage_minimal(stage_name: str, user_id: Optional[str] = None):
    """
    Ultra-lightweight context manager for high-frequency pipeline operations.

    Only tracks essential metrics with minimal overhead:
    - Execution duration
    - Success/error status
    - Error counts

    Args:
        stage_name: Name of the pipeline stage (e.g., 'umap_optimization')
        user_id: Optional user ID for multi-user tracking

    Example:
        with track_pipeline_stage_minimal('umap_optimization', user_id='user123'):
            # Your pipeline code here
            result = run_umap_optimization()
    """
    start_time = time.perf_counter()  # More precise timing
    user_label = user_id or "unknown"

    try:
        yield

        # Success case - minimal metric update
        duration = time.perf_counter() - start_time
        pipeline_duration.labels(
            stage=stage_name, user_id=user_label, status="success"
        ).observe(duration)

    except Exception as e:
        # Error case - track error and duration
        duration = time.perf_counter() - start_time
        pipeline_duration.labels(
            stage=stage_name, user_id=user_label, status="error"
        ).observe(duration)

        pipeline_errors_total.labels(
            stage=stage_name, error_type=e.__class__.__name__
        ).inc()

        raise


@contextmanager
def track_pipeline_stage(
    stage_name: str, user_id: Optional[str] = None, track_memory: bool = False
):
    """
    Standard context manager for pipeline stage tracking.

    Tracks essential metrics with optional memory tracking:
    - Execution duration
    - Success/error status
    - Error counts
    - Active job tracking
    - Optional memory usage (when track_memory=True)

    Args:
        stage_name: Name of the pipeline stage (e.g., 'umap_optimization')
        user_id: Optional user ID for multi-user tracking
        track_memory: Enable memory tracking (adds overhead)

    Example:
        with track_pipeline_stage('umap_optimization', user_id='user123'):
            # Your pipeline code here
            result = run_umap_optimization()
    """
    start_time = time.perf_counter()  # More precise timing
    user_label = user_id or "unknown"

    try:
        # Track active job (lightweight counter)
        active_jobs.labels(job_type=stage_name, user_id=user_label).inc()

        yield

        # Success case
        duration = time.perf_counter() - start_time
        pipeline_duration.labels(
            stage=stage_name, user_id=user_label, status="success"
        ).observe(duration)

        # Optional memory tracking
        if track_memory:
            track_memory_usage(stage_name)

    except Exception as e:
        # Error case
        duration = time.perf_counter() - start_time
        pipeline_duration.labels(
            stage=stage_name, user_id=user_label, status="error"
        ).observe(duration)

        pipeline_errors_total.labels(
            stage=stage_name, error_type=e.__class__.__name__
        ).inc()

        raise

    finally:
        # Remove from active jobs
        active_jobs.labels(job_type=stage_name, user_id=user_label).dec()


def track_memory_usage(stage_name: str, process_type: str = "pipeline"):
    """Track memory usage for specific stages when needed (not in hot path)"""
    try:
        import psutil

        current_memory = psutil.Process().memory_info().rss
        memory_usage_bytes.labels(stage=stage_name, process_type=process_type).set(
            current_memory
        )
    except ImportError:
        # psutil not available - skip memory tracking
        pass


def track_dataset_size(size_bytes: int, dataset_type: str = "unknown"):
    """Track dataset size for processing analytics"""
    dataset_size_bytes.labels(dataset_type=dataset_type).observe(size_bytes)


def track_optimization_trial(stage_name: str, trial_type: str = "main"):
    """Track individual optimization trials"""
    optimization_trials_total.labels(stage=stage_name, trial_type=trial_type).inc()


@contextmanager
def track_http_request(method: str, endpoint: str):
    """
    Context manager for tracking HTTP request metrics.

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path

    Example:
        with track_http_request('POST', '/api/v1/pipeline'):
            response = await handler()
            return response
    """
    start_time = time.time()
    status_code = "200"  # Default success

    try:
        yield

    except Exception as e:
        # Determine status code from exception type
        if hasattr(e, "status_code"):
            status_code = str(e.status_code)
        else:
            status_code = "500"
        raise

    finally:
        duration = time.time() - start_time

        # Track request count
        http_requests_total.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).inc()

        # Track request duration
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
            duration
        )
