"""
Context Management for EMUSES Observability

Provides lightweight context tracking for metrics and logging correlation
without the overhead of full distributed tracing.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from .logging import get_logger, set_pipeline_context
from .metrics import (pipeline_duration, pipeline_errors_total,
                      track_pipeline_stage, track_pipeline_stage_minimal)

logger = get_logger(__name__)

# Performance optimization: Pre-generate span IDs for minimal overhead
_span_counter = 0
_sample_counter = 0
SAMPLE_RATE = 100  # Only track every 100th operation for ultra-high frequency scenarios


def _get_span_id() -> str:
    """Generate efficient span ID without UUID overhead"""
    global _span_counter
    _span_counter = (_span_counter + 1) % 100000
    return f"sp{_span_counter:05d}"


def _should_sample() -> bool:
    """Determine if this operation should be sampled for metrics"""
    global _sample_counter
    _sample_counter = (_sample_counter + 1) % SAMPLE_RATE
    return _sample_counter == 0


@contextmanager
def create_span(operation_name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Create a lightweight 'span' for operation tracking.

    Optimized for minimal overhead in high-frequency operations.
    Logging is significantly reduced for performance.

    Args:
        operation_name: Name of the operation being tracked
        attributes: Optional key-value attributes for context

    Example:
        with create_span('umap_optimization', {'n_neighbors': 15}) as span:
            span.set_attribute('trials_completed', 25)
            result = run_optimization()
            span.set_attribute('final_score', result.score)
    """
    span_id = _get_span_id()  # Efficient span ID generation
    start_time = time.perf_counter()  # More precise timing

    # Minimal context setup - no pipeline context for performance
    user_attributes = attributes or {}

    class SpanContext:
        """Lightweight span context for attribute tracking"""

        def __init__(self, span_id: str, operation: str):
            self.span_id = span_id
            self.operation = operation
            self.attributes = user_attributes.copy()
            self.error = None

        def set_attribute(self, key: str, value: Any):
            """Add an attribute to this span context"""
            self.attributes[key] = value

        def record_exception(self, exception: Exception):
            """Record an exception in this span context"""
            self.error = exception
            self.attributes["error"] = True
            self.attributes["error_type"] = exception.__class__.__name__
            self.attributes["error_message"] = str(exception)

            # Only log errors - critical for debugging
            logger.error(
                "Operation failed",
                span_id=self.span_id,
                operation=self.operation,
                error_type=exception.__class__.__name__,
                error_message=str(exception),
            )

    span_context = SpanContext(span_id, operation_name)

    try:
        yield span_context

        # Minimal completion tracking - no logging for success
        duration = time.perf_counter() - start_time
        span_context.set_attribute("duration_seconds", duration)
        span_context.set_attribute("status", "success")

    except Exception as e:
        # Track error completion
        duration = time.perf_counter() - start_time
        span_context.record_exception(e)
        span_context.set_attribute("duration_seconds", duration)
        span_context.set_attribute("status", "error")

        raise


@contextmanager
def track_scientific_operation(
    stage_name: str,
    user_id: Optional[str] = None,
    additional_attributes: Optional[Dict[str, Any]] = None,
    performance_mode: str = "ultra_fast",
):
    """
    Optimized context manager for high-frequency scientific operations.

    Performance modes:
    - 'ultra_fast': <2% overhead, sampling-based metrics (default for high-freq ops)
    - 'minimal': Low overhead, essential metrics only
    - 'benchmark': No metrics, minimal overhead for performance testing
    - 'full': Complete observability with higher overhead

    Args:
        stage_name: Pipeline stage name (e.g., 'umap_optimization')
        user_id: Optional user ID for multi-user tracking
        additional_attributes: Additional context attributes
        performance_mode: Performance/observability trade-off

    Example:
        with track_scientific_operation('umap_optimization', user_id='user123') as ctx:
            ctx.set_attribute('n_trials', 50)
            result = run_umap_optimization()
            ctx.set_attribute('best_score', result.best_score)
    """

    if performance_mode == "ultra_fast":
        # Ultra-fast mode - sampling-based metrics for <2% overhead
        start_time = time.perf_counter()
        should_track = _should_sample()  # Only sample 1% of operations

        class UltraFastSpanContext:
            def __init__(self):
                self.attributes = additional_attributes or {}
                self.tracked = should_track

            def set_attribute(self, key: str, value: Any):
                """Store attribute (no overhead)"""
                if self.tracked:
                    self.attributes[key] = value

            def record_exception(self, exception: Exception):
                """Record exception (always track errors)"""
                pass

        try:
            yield UltraFastSpanContext()

            # Sample-based metric tracking
            if should_track:
                duration = time.perf_counter() - start_time
                pipeline_duration.labels(
                    stage=stage_name, user_id=user_id or "unknown", status="success"
                ).observe(duration)

        except Exception as e:
            # Always track errors (critical for debugging)
            duration = time.perf_counter() - start_time
            pipeline_duration.labels(
                stage=stage_name, user_id=user_id or "unknown", status="error"
            ).observe(duration)

            pipeline_errors_total.labels(
                stage=stage_name, error_type=e.__class__.__name__
            ).inc()

            raise

    elif performance_mode == "benchmark":
        # Benchmark mode - no metrics, absolute minimal overhead
        class BenchmarkSpanContext:
            def __init__(self):
                self.attributes = additional_attributes or {}

            def set_attribute(self, key: str, value: Any):
                """Store attribute (no-op for benchmarking)"""
                pass

            def record_exception(self, exception: Exception):
                """Record exception (no-op for benchmarking)"""
                pass

        yield BenchmarkSpanContext()

    elif performance_mode == "minimal":
        # Minimal mode - essential metrics only, no sampling
        start_time = time.perf_counter()

        class MinimalSpanContext:
            def __init__(self):
                self.attributes = additional_attributes or {}

            def set_attribute(self, key: str, value: Any):
                """Store attribute (minimal overhead)"""
                self.attributes[key] = value

            def record_exception(self, exception: Exception):
                """Record exception (minimal overhead)"""
                pass

        try:
            yield MinimalSpanContext()

            # Essential metric tracking
            duration = time.perf_counter() - start_time
            pipeline_duration.labels(
                stage=stage_name, user_id=user_id or "unknown", status="success"
            ).observe(duration)

        except Exception as e:
            # Error tracking
            duration = time.perf_counter() - start_time
            pipeline_duration.labels(
                stage=stage_name, user_id=user_id or "unknown", status="error"
            ).observe(duration)

            pipeline_errors_total.labels(
                stage=stage_name, error_type=e.__class__.__name__
            ).inc()

            raise
    else:
        # Full observability mode - complete tracing with higher overhead
        attributes = additional_attributes or {}
        if user_id:
            attributes["user_id"] = user_id

        with track_pipeline_stage(stage_name, user_id):
            with create_span(f"pipeline.{stage_name}", attributes) as span:
                yield span
