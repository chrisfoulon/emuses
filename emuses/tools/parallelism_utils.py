"""
Parallelism utility module for EMUSES.

Chooses a joblib backend and n_jobs based on whether we are running in the main process or
inside a worker, so that nested parallelism does not deadlock or oversubscribe the machine.

Spawning loky worker *processes* from inside an already-forked process is a known source of
hangs and resource exhaustion, so a worker uses the threading backend and a single job.
"""

import logging
import multiprocessing as mp
from contextlib import contextmanager

logger = logging.getLogger(__name__)

VALID_BACKENDS = ("loky", "threading", "multiprocessing")

# Process-wide override. Prefer the `parallelism_backend` context manager over setting this
# through configure_parallelism_backend(): an override that is never restored leaks into
# everything else sharing the interpreter, which is how a pipeline test came to change the
# outcome of an unrelated test that ran after it.
_force_backend = None


def is_subprocess_context():
    """
    Check whether the current process is a multiprocessing worker.

    Returns
    -------
    bool
        True if running in a worker process, False in the main process.
    """
    return mp.current_process().name != "MainProcess"


def get_safe_parallel_backend():
    """
    Get the appropriate joblib backend for the current process context.

    Returns
    -------
    str
        The configured override if one is set, otherwise 'threading' in a worker process and
        'loky' in the main process.

    Notes
    -----
    This used to consult a `get_process_hierarchy_depth()` helper that walked
    `mp.current_process().parent`. `multiprocessing.Process` has no `parent` attribute, so the
    walk never executed and the function always reported depth 0 - meaning this function always
    returned 'loky', including in the worker case it exists to catch. Its tests passed because
    they mocked `current_process()` with a `MagicMock`, which fabricates any attribute asked of
    it, so the mock had the `.parent` the real object lacks.

    The subprocess check below is the one that has always worked, and was already being used by
    `get_safe_n_jobs`.
    """
    if _force_backend is not None:
        logger.debug(f"Using configured backend override: {_force_backend}")
        return _force_backend

    if is_subprocess_context():
        logger.debug("Worker process detected, using threading backend")
        return "threading"

    logger.debug("Main process detected, using loky backend")
    return "loky"


def get_safe_n_jobs(requested_n_jobs):
    """
    Get a safe n_jobs value for the current context.

    Parameters
    ----------
    requested_n_jobs : int
        Requested number of jobs.

    Returns
    -------
    int
        1 in a worker process, otherwise the requested value unchanged.
    """
    if is_subprocess_context() and requested_n_jobs != 1:
        logger.debug(
            f"Worker process detected, limiting n_jobs from {requested_n_jobs} to 1"
        )
        return 1
    return requested_n_jobs


def _validate_backend(backend):
    """Raise ValueError unless `backend` is a supported joblib backend or None."""
    if backend is not None and backend not in VALID_BACKENDS:
        raise ValueError(
            f"Invalid backend '{backend}'. Must be one of: {list(VALID_BACKENDS)}"
        )


def configure_parallelism_backend(force_backend=None):
    """
    Set the process-wide backend override.

    Parameters
    ----------
    force_backend : str or None
        Backend to force ('loky', 'threading', 'multiprocessing'), or None for auto-detection.

    Raises
    ------
    ValueError
        If an unsupported backend is given.

    Notes
    -----
    Prefer `parallelism_backend()` where the override applies to a bounded piece of work. This
    function changes global state that nothing restores.
    """
    global _force_backend

    _validate_backend(force_backend)
    _force_backend = force_backend
    logger.debug(f"Parallelism backend configuration: {force_backend or 'auto-detect'}")


@contextmanager
def parallelism_backend(backend):
    """
    Temporarily force a joblib backend, restoring the previous setting on exit.

    Parameters
    ----------
    backend : str or None
        Backend to force for the duration of the block, or None to force auto-detection.

    Examples
    --------
    >>> with parallelism_backend("threading"):
    ...     run_some_work()
    """
    global _force_backend

    _validate_backend(backend)
    previous = _force_backend
    _force_backend = backend
    try:
        yield
    finally:
        _force_backend = previous


def create_safe_parallel(n_jobs=-1, **kwargs):
    """
    Create a joblib Parallel object with a context-appropriate backend and n_jobs.

    Parameters
    ----------
    n_jobs : int, default=-1
        Number of parallel jobs.
    **kwargs
        Additional arguments for Parallel.

    Returns
    -------
    joblib.Parallel
    """
    from joblib import Parallel

    return Parallel(
        n_jobs=get_safe_n_jobs(n_jobs), backend=get_safe_parallel_backend(), **kwargs
    )
