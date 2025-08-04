"""
Parallelism utility module for EMUSES.

Provides safe parallelism handling that detects multiprocessing context
and adjusts backend/n_jobs accordingly to avoid conflicts.
"""

import logging
import multiprocessing as mp

logger = logging.getLogger(__name__)

# Global configuration for backend override
_force_backend = None


def get_process_hierarchy_depth():
    """
    Get the depth of the current process in the process hierarchy.

    Returns
    -------
    int
        Process hierarchy depth (0 for main process, 1+ for subprocesses)
    """
    current = mp.current_process()
    depth = 0

    # Traverse up the process hierarchy
    while hasattr(current, "parent") and current.parent is not None:
        depth += 1
        current = current.parent
        # Safety check to prevent infinite loops
        if depth > 10:
            logger.warning(
                "Process hierarchy depth exceeded 10 levels, stopping traversal"
            )
            break

    return depth


def is_subprocess_context():
    """
    Check if current process is running in a subprocess context.

    Returns
    -------
    bool
        True if in subprocess, False if main process
    """
    return mp.current_process().name != "MainProcess"


def configure_parallelism_backend(force_backend=None):
    """
    Configure parallelism backend behavior.

    Parameters
    ----------
    force_backend : str or None
        Force specific backend ('loky', 'threading', 'multiprocessing')
        or None for auto-detection

    Raises
    ------
    ValueError
        If invalid backend specified
    """
    global _force_backend

    if force_backend is not None:
        valid_backends = ["loky", "threading", "multiprocessing"]
        if force_backend not in valid_backends:
            raise ValueError(
                f"Invalid backend '{force_backend}'. Must be one of: {valid_backends}"
            )

    _force_backend = force_backend
    logger.debug(f"Parallelism backend configuration: {force_backend or 'auto-detect'}")


def get_safe_parallel_backend():
    """
    Get appropriate Joblib backend based on process context.

    Uses enhanced process hierarchy detection and configuration options.

    Returns
    -------
    str
        'loky' for main process, 'threading' for subprocess, or configured override
    """
    # Use configured override if set
    if _force_backend is not None:
        logger.debug(f"Using configured backend override: {_force_backend}")
        return _force_backend

    # Enhanced context detection
    hierarchy_depth = get_process_hierarchy_depth()
    logger.debug(f"Process hierarchy depth: {hierarchy_depth}")

    if hierarchy_depth > 0:
        logger.debug(
            f"Subprocess detected (depth {hierarchy_depth}), using threading backend"
        )
        backend = "threading"
    else:
        logger.debug("Main process detected, using loky backend")
        backend = "loky"

    logger.debug(f"Selected backend: {backend}")
    return backend


def get_safe_n_jobs(requested_n_jobs):
    """
    Get safe n_jobs value based on context.

    Parameters
    ----------
    requested_n_jobs : int
        Requested number of jobs

    Returns
    -------
    int
        Safe n_jobs value for current context
    """
    if is_subprocess_context() and requested_n_jobs != 1:
        hierarchy_depth = get_process_hierarchy_depth()
        logger.debug(
            f"Subprocess detected (depth {hierarchy_depth}), limiting n_jobs from {requested_n_jobs} to 1"
        )
        return 1
    return requested_n_jobs


def create_safe_parallel(n_jobs=-1, **kwargs):
    """
    Create Parallel object with safe backend selection.

    Parameters
    ----------
    n_jobs : int, default=-1
        Number of parallel jobs
    **kwargs
        Additional arguments for Parallel

    Returns
    -------
    joblib.Parallel
        Configured Parallel object with safe backend and n_jobs
    """
    from joblib import Parallel

    safe_n_jobs = get_safe_n_jobs(n_jobs)
    safe_backend = get_safe_parallel_backend()

    return Parallel(n_jobs=safe_n_jobs, backend=safe_backend, **kwargs)
