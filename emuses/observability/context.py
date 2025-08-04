"""
Context Management for EMUSES Observability

Provides lightweight context tracking for metrics and logging correlation
without the overhead of full distributed tracing.
"""

import time
import uuid
from contextlib import contextmanager
from typing import Dict, Any, Optional
from .logging import set_pipeline_context, get_logger
from .metrics import track_pipeline_stage


logger = get_logger(__name__)


@contextmanager
def create_span(operation_name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Create a lightweight 'span' for operation tracking.
    
    This provides similar functionality to distributed tracing spans but uses
    only structured logging and metrics collection for minimal overhead.
    
    Args:
        operation_name: Name of the operation being tracked
        attributes: Optional key-value attributes for context
        
    Example:
        with create_span('umap_optimization', {'n_neighbors': 15}) as span:
            span.set_attribute('trials_completed', 25)
            result = run_optimization()
            span.set_attribute('final_score', result.score)
    """
    span_id = str(uuid.uuid4())[:8]  # Short span ID
    start_time = time.time()
    
    # Set pipeline context for logging
    set_pipeline_context(operation_name)
    
    # Initialize span attributes
    user_attributes = attributes or {}
    span_attributes = {
        'span_id': span_id,
        'operation': operation_name,
        'start_time': start_time,
        **user_attributes
    }
    
    # Log span start
    logger.info(
        "Operation started",
        span_id=span_id,
        operation=operation_name,
        **user_attributes
    )
    
    class SpanContext:
        """Lightweight span context for attribute tracking"""
        
        def __init__(self, span_id: str, operation: str, attributes: Dict[str, Any]):
            self.span_id = span_id
            self.operation = operation
            self.attributes = attributes
            
        def set_attribute(self, key: str, value: Any):
            """Add an attribute to this span context"""
            self.attributes[key] = value
            
        def record_exception(self, exception: Exception):
            """Record an exception in this span context"""
            self.attributes['error'] = True
            self.attributes['error_type'] = exception.__class__.__name__
            self.attributes['error_message'] = str(exception)
            
            logger.error(
                "Operation failed",
                span_id=self.span_id,
                operation=self.operation,
                error_type=exception.__class__.__name__,
                error_message=str(exception)
            )
    
    span_context = SpanContext(span_id, operation_name, span_attributes)
    
    try:
        yield span_context
        
        # Log successful completion
        duration = time.time() - start_time
        span_context.set_attribute('duration_seconds', duration)
        span_context.set_attribute('status', 'success')
        
        logger.info(
            "Operation completed",
            span_id=span_id,
            operation=operation_name,
            duration_seconds=duration,
            status='success'
        )
        
    except Exception as e:
        # Log error completion
        duration = time.time() - start_time
        span_context.record_exception(e)
        span_context.set_attribute('duration_seconds', duration)
        span_context.set_attribute('status', 'error')
        
        raise
        
    finally:
        # Always log span completion for metrics
        duration = time.time() - start_time
        logger.debug(
            "Operation span closed",
            span_id=span_id,
            operation=operation_name,
            total_duration=duration
        )


@contextmanager
def track_scientific_operation(
    stage_name: str, 
    user_id: Optional[str] = None,
    additional_attributes: Optional[Dict[str, Any]] = None
):
    """
    Combined context manager for scientific operations.
    
    Integrates metrics tracking, structured logging, and lightweight span context
    for comprehensive observability of scientific pipeline operations.
    
    Args:
        stage_name: Pipeline stage name (e.g., 'umap_optimization')
        user_id: Optional user ID for multi-user tracking
        additional_attributes: Additional context attributes
        
    Example:
        with track_scientific_operation('umap_optimization', user_id='user123', 
                                      additional_attributes={'dataset': 'hcp_motor'}) as ctx:
            ctx.set_attribute('n_trials', 50)
            result = run_umap_optimization()
            ctx.set_attribute('best_score', result.best_score)
    """
    
    attributes = additional_attributes or {}
    if user_id:
        attributes['user_id'] = user_id
        
    # Use both metrics tracking and span context
    with track_pipeline_stage(stage_name, user_id):
        with create_span(f'pipeline.{stage_name}', attributes) as span:
            yield span