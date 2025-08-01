"""Background task integration for multi-user EMUSES service.

This module provides integration components for initializing and managing
the background task system within the FastAPI application lifecycle.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI

from emuses.multi_user_service.background_tasks import BackgroundTaskManager
from emuses.multi_user_service.job_manager import MultiUserJobManager
from emuses.multi_user_service.task_endpoints import set_task_manager

logger = logging.getLogger(__name__)


# Global task manager instance
_global_task_manager: Optional[BackgroundTaskManager] = None


def get_global_task_manager() -> Optional[BackgroundTaskManager]:
    """Get the global task manager instance.
    
    Returns
    -------
    Optional[BackgroundTaskManager]
        Global task manager instance if initialized
    """
    return _global_task_manager


def initialize_task_manager(
    job_manager: MultiUserJobManager,
    max_workers: Optional[int] = None,
    task_timeout: float = 3600.0,
    process_memory_limit_gb: float = 8.0
) -> BackgroundTaskManager:
    """Initialize the background task manager.
    
    Creates and configures the background task manager with the provided
    settings and stores it as the global instance.
    
    Parameters
    ----------
    job_manager : MultiUserJobManager
        Multi-user job manager for workspace isolation
    max_workers : Optional[int]
        Maximum worker processes (defaults to CPU count-based calculation)
    task_timeout : float
        Task execution timeout in seconds
    process_memory_limit_gb : float
        Memory limit per process in GB
        
    Returns
    -------
    BackgroundTaskManager
        Initialized task manager instance
    """
    global _global_task_manager
    
    if _global_task_manager is not None:
        logger.warning("Task manager already initialized, shutting down previous instance")
        _global_task_manager.shutdown(wait=False)
    
    # Create new task manager
    _global_task_manager = BackgroundTaskManager(
        job_manager=job_manager,
        max_workers=max_workers,
        task_timeout=task_timeout,
        process_memory_limit_gb=process_memory_limit_gb
    )
    
    # Configure the process pool
    _global_task_manager.configure_process_pool()
    
    # Set task manager in endpoints module
    set_task_manager(_global_task_manager)
    
    logger.info(
        f"Background task manager initialized with {_global_task_manager.max_workers} workers, "
        f"{task_timeout}s timeout, {process_memory_limit_gb}GB memory limit"
    )
    
    return _global_task_manager


def shutdown_task_manager(timeout: float = 30.0) -> None:
    """Shutdown the background task manager.
    
    Gracefully shuts down the background task manager, waiting for
    running tasks to complete or timing out.
    
    Parameters
    ----------
    timeout : float
        Maximum time to wait for shutdown in seconds
    """
    global _global_task_manager
    
    if _global_task_manager is not None:
        logger.info("Shutting down background task manager")
        _global_task_manager.shutdown(wait=True, timeout=timeout)
        _global_task_manager = None
        logger.info("Background task manager shutdown complete")


@asynccontextmanager
async def task_manager_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager for background task manager.
    
    Initializes the background task manager on startup and shuts it down
    on application shutdown. This should be used as the FastAPI lifespan
    parameter.
    
    Parameters
    ----------
    app : FastAPI
        FastAPI application instance
        
    Yields
    ------
    None
        Context for application lifetime
    """
    # Startup: Initialize task manager
    try:
        # Get configuration from environment or use defaults
        base_directory = os.getenv("EMUSES_JOBS_DIRECTORY", "/tmp/emuses_jobs")
        max_workers = None
        if os.getenv("EMUSES_MAX_WORKERS"):
            try:
                max_workers = int(os.getenv("EMUSES_MAX_WORKERS"))
            except ValueError:
                logger.warning("Invalid EMUSES_MAX_WORKERS value, using default")
        
        task_timeout = float(os.getenv("EMUSES_TASK_TIMEOUT", "3600"))
        memory_limit = float(os.getenv("EMUSES_PROCESS_MEMORY_LIMIT_GB", "8.0"))
        
        # Create job manager
        job_manager = MultiUserJobManager(base_directory)
        
        # Initialize task manager
        task_manager = initialize_task_manager(
            job_manager=job_manager,
            max_workers=max_workers,
            task_timeout=task_timeout,
            process_memory_limit_gb=memory_limit
        )
        
        logger.info("Background task system startup complete")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize background task system: {e}")
        raise
    
    finally:
        # Shutdown: Clean up task manager
        try:
            shutdown_task_manager()
        except Exception as e:
            logger.error(f"Error during task manager shutdown: {e}")


def setup_task_integration(app: FastAPI) -> None:
    """Set up background task integration with FastAPI application.
    
    Configures the FastAPI application to use the task manager lifespan
    and ensures proper initialization and cleanup.
    
    Parameters
    ----------
    app : FastAPI
        FastAPI application instance to configure
    """
    # Store the original lifespan if it exists
    original_lifespan = getattr(app, "router", {}).get("lifespan_context")
    
    if original_lifespan is not None:
        logger.warning("FastAPI app already has a lifespan context manager")
        
        # Create combined lifespan that runs both
        @asynccontextmanager
        async def combined_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            async with original_lifespan(app):
                async with task_manager_lifespan(app):
                    yield
        
        app.router.lifespan_context = combined_lifespan
    else:
        app.router.lifespan_context = task_manager_lifespan
    
    logger.info("Background task integration configured")


def get_task_manager_health() -> dict:
    """Get health status of the background task manager.
    
    Returns health information about the task manager for monitoring
    and diagnostics purposes.
    
    Returns
    -------
    dict
        Health status information
    """
    if _global_task_manager is None:
        return {
            "status": "not_initialized",
            "healthy": False,
            "error": "Task manager not initialized"
        }
    
    try:
        system_status = _global_task_manager.get_system_status()
        
        # Determine health based on executor status and running tasks
        healthy = (
            system_status["executor_active"] and
            system_status["active_workers"] <= system_status["max_workers"]
        )
        
        return {
            "status": "active" if healthy else "degraded",
            "healthy": healthy,
            "max_workers": system_status["max_workers"],
            "active_workers": system_status["active_workers"],
            "total_tasks": system_status["total_tasks"],
            "task_counts": system_status["task_counts"],
            "executor_active": system_status["executor_active"]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "healthy": False,
            "error": str(e)
        }