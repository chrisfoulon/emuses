"""
Parallelism utility module for EMUSES.

Provides safe parallelism handling that detects multiprocessing context
and adjusts backend/n_jobs accordingly to avoid conflicts.
"""
import multiprocessing as mp
import logging

logger = logging.getLogger(__name__)


def get_safe_parallel_backend():
    """Get appropriate Joblib backend based on process context.
    
    Returns:
        str: 'loky' for main process, 'threading' for subprocess
    """
    if mp.current_process().name != "MainProcess":
        logger.debug("Subprocess detected, using threading backend")
        return "threading"
    return "loky"


def get_safe_n_jobs(requested_n_jobs):
    """Get safe n_jobs value based on context.
    
    Args:
        requested_n_jobs: Requested number of jobs
        
    Returns:
        int: Safe n_jobs value for current context
    """
    if mp.current_process().name != "MainProcess" and requested_n_jobs != 1:
        logger.debug(f"Subprocess detected, limiting n_jobs from {requested_n_jobs} to 1")
        return 1
    return requested_n_jobs


def create_safe_parallel(n_jobs=-1, **kwargs):
    """Create Parallel object with safe backend selection.
    
    Args:
        n_jobs: Number of parallel jobs
        **kwargs: Additional arguments for Parallel
        
    Returns:
        Parallel: Configured Parallel object
    """
    from joblib import Parallel
    
    safe_n_jobs = get_safe_n_jobs(n_jobs)
    safe_backend = get_safe_parallel_backend()
    
    return Parallel(n_jobs=safe_n_jobs, backend=safe_backend, **kwargs)