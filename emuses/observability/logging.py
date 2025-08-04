"""
Structured Logging for EMUSES

Provides structured JSON logging with correlation IDs for debugging
and operational visibility.
"""

import logging
import uuid
import time
import sys
from typing import Dict, Any, Optional
from contextvars import ContextVar
import structlog


# Context variables for request correlation
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
pipeline_stage_var: ContextVar[Optional[str]] = ContextVar('pipeline_stage', default=None)


def add_correlation_info(logger, method_name, event_dict):
    """Add correlation information to log entries"""
    # Add request correlation
    request_id = request_id_var.get()
    if request_id:
        event_dict['request_id'] = request_id
        
    # Add user context
    user_id = user_id_var.get()
    if user_id:
        event_dict['user_id'] = user_id
        
    # Add pipeline context
    stage = pipeline_stage_var.get()
    if stage:
        event_dict['pipeline_stage'] = stage
        
    return event_dict


def add_system_info(logger, method_name, event_dict):
    """Add system information to log entries"""
    event_dict['service'] = 'emuses'
    event_dict['timestamp'] = time.time()
    return event_dict


def setup_structured_logging(level: str = 'INFO', output_file: Optional[str] = None):
    """
    Configure structured logging for EMUSES.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        output_file: Optional file path for log output (defaults to stdout)
    """
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        add_correlation_info,
        add_system_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Add JSON renderer for structured output
    if output_file or level == 'DEBUG':
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Use console renderer for better readability in development
        processors.append(structlog.dev.ConsoleRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging with both console and file output
    handlers = [logging.StreamHandler(sys.stdout)]
    if output_file:
        handlers.append(logging.FileHandler(output_file, mode='a'))
    
    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=getattr(logging, level.upper())
    )


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (defaults to calling module)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def set_request_context(request_id: Optional[str] = None, user_id: Optional[str] = None):
    """
    Set request context for correlation across log entries.
    
    Args:
        request_id: Unique request identifier
        user_id: User identifier for multi-user tracking
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
        
    request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)


def set_pipeline_context(stage_name: str):
    """
    Set pipeline stage context for scientific operation tracking.
    
    Args:
        stage_name: Name of the current pipeline stage
    """
    pipeline_stage_var.set(stage_name)


def clear_context():
    """Clear all context variables"""
    request_id_var.set(None)
    user_id_var.set(None) 
    pipeline_stage_var.set(None)


class RequestLogger:
    """
    Context manager for request-scoped logging.
    
    Automatically sets and clears request context for structured logging.
    """
    
    def __init__(self, request_id: Optional[str] = None, user_id: Optional[str] = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id
        
    def __enter__(self):
        set_request_context(self.request_id, self.user_id)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_context()


class PipelineLogger:
    """
    Context manager for pipeline-scoped logging.
    
    Automatically sets and clears pipeline context for scientific operation tracking.
    """
    
    def __init__(self, stage_name: str, user_id: Optional[str] = None):
        self.stage_name = stage_name
        self.user_id = user_id
        self.request_id = str(uuid.uuid4())
        
    def __enter__(self):
        set_request_context(self.request_id, self.user_id)
        set_pipeline_context(self.stage_name)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_context()


# Default logger instance
logger = get_logger(__name__)