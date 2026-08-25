"""
Parallelism utility module for EMUSES.

Chooses a joblib backend and n_jobs based on whether we are running in the main process or
inside a worker, so that nested parallelism does not deadlock or oversubscribe the machine.

Spawning loky worker *processes* from inside an already-forked process is a known source of
hangs and resource exhaustion, so a worker uses the threading backend and a single job.
"""

import contextvars
import logging
import multiprocessing as mp
from contextlib import contextmanager

logger = logging.getLogger(__name__)

VALID_BACKENDS = ("loky", "threading", "multiprocessing")

# The backend override, held in a ContextVar rather than a plain module global.
#
# It was a plain global with save/restore until 2026-08-25. That is only correct when blocks
# unwind in strict LIFO order, which holds for one run at a time and stops holding the moment
# two overlap in one interpreter:
#
#     A enters:  previous=None        -> "threading"
#     B enters:  previous="threading" -> "threading"
#     A exits:   restores None                       <- B is still running
#     B's next create_safe_parallel() -> auto-detect -> main process -> loky
#
# B then silently finishes on loky, which for this workload is several times slower (loky
# re-imports the scientific stack per worker; see pipeline_runner.py). Nothing raises and the
# numbers do not change, so the only symptom is a run that took much longer for no reason.
#
# Today nothing overlaps, but only by accident: `_run_pipeline_in_process` blocks the event
# loop, so a second job cannot start. That is a property of a blocking call in async code, not
# a decision, and the obvious tidy-up (move it to run_in_executor) would remove it. A ContextVar
# is correct under both threads and asyncio tasks, so the guarantee no longer depends on it.
#
# Prefer the `parallelism_backend` context manager over configure_parallelism_backend(): an
# override that is never restored leaks into everything else sharing the context, which is how a
# pipeline test came to change the outcome of an unrelated test that ran after it.
#
# Note the deliberate consequence: a *newly spawned thread* starts with a fresh context and so
# sees the default, not its parent's override. Every path from the scope in
# `pipeline_runner.py` to the `create_safe_parallel` call sites is synchronous and stays on one
# thread (verified 2026-08-25), so this does not arise; if a stage ever hands joblib work to its
# own thread, that thread must enter the scope itself.
_FORCED_BACKEND = contextvars.ContextVar("emuses_forced_parallelism_backend", default=None)


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
    forced = _FORCED_BACKEND.get()
    if forced is not None:
        logger.debug(f"Using configured backend override: {forced}")
        return forced

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
    Set the backend override for the current context.

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
    function sets a value that nothing restores; it just does so per-context rather than
    process-wide.
    """
    _validate_backend(force_backend)
    _FORCED_BACKEND.set(force_backend)
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

    Notes
    -----
    Uses `ContextVar.reset(token)` rather than reading the previous value and writing it back.
    Restoring a captured value is what allowed one run to clobber a concurrently running one;
    a token restores exactly the state this block replaced, and refuses if the block is somehow
    exited from a different context instead of corrupting it silently.
    """
    _validate_backend(backend)
    token = _FORCED_BACKEND.set(backend)
    try:
        yield
    finally:
        _FORCED_BACKEND.reset(token)


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
