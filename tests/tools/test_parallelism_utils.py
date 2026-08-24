"""Tests for the parallelism context detection.

These tests deliberately use a **real** `multiprocessing.Process` rather than mocking
`multiprocessing.current_process`. The previous version of this suite mocked it with a
`MagicMock`, which fabricates whatever attribute is asked of it - so the mock had a `.parent`
attribute that the real `multiprocessing.Process` does not. The production code walked that
non-existent attribute, always concluded it was in the main process, and the tests passed
anyway because they were asserting against an object model that does not exist.

A worker process is cheap to start. Use one.
"""

import multiprocessing as mp

import pytest

from emuses.tools.parallelism_utils import (
    configure_parallelism_backend,
    create_safe_parallel,
    get_safe_n_jobs,
    get_safe_parallel_backend,
    is_subprocess_context,
    parallelism_backend,
)


def _probe(queue):
    """Report the parallelism decisions from inside a real worker process."""
    queue.put(
        {
            "process_name": mp.current_process().name,
            "is_subprocess": is_subprocess_context(),
            "backend": get_safe_parallel_backend(),
            "n_jobs_for_minus_one": get_safe_n_jobs(-1),
            "n_jobs_for_four": get_safe_n_jobs(4),
        }
    )


@pytest.fixture(scope="module")
def worker_context():
    """Run the probe in a real child process and return what it observed."""
    queue = mp.Queue()
    process = mp.Process(target=_probe, args=(queue,))
    process.start()
    result = queue.get(timeout=60)
    process.join(timeout=30)
    assert not process.is_alive(), "probe process did not exit"
    return result


class TestContextDetection:
    """Detection must work against the real multiprocessing API."""

    def test_main_process_is_not_a_subprocess(self):
        assert mp.current_process().name == "MainProcess"
        assert is_subprocess_context() is False

    def test_worker_process_is_detected(self, worker_context):
        assert worker_context["process_name"] != "MainProcess"
        assert worker_context["is_subprocess"] is True


class TestBackendSelection:
    """The whole point of the module: workers must not spawn loky processes."""

    def test_main_process_uses_loky(self):
        assert get_safe_parallel_backend() == "loky"

    def test_worker_process_uses_threading(self, worker_context):
        # This is the assertion the old suite could not make. It failed against the previous
        # implementation, which returned "loky" here.
        assert worker_context["backend"] == "threading", (
            "a worker process selected the loky backend, which is what this module exists to "
            "prevent - nesting loky inside a forked process risks hangs and oversubscription"
        )


class TestNJobsClamping:
    def test_main_process_keeps_requested_n_jobs(self):
        assert get_safe_n_jobs(-1) == -1
        assert get_safe_n_jobs(4) == 4

    def test_worker_process_is_clamped_to_one(self, worker_context):
        assert worker_context["n_jobs_for_minus_one"] == 1
        assert worker_context["n_jobs_for_four"] == 1

    def test_explicit_single_job_is_untouched(self):
        assert get_safe_n_jobs(1) == 1


class TestBackendOverride:
    def test_override_wins_over_detection(self):
        with parallelism_backend("threading"):
            assert get_safe_parallel_backend() == "threading"

    def test_context_manager_restores_previous_value(self):
        before = get_safe_parallel_backend()
        with parallelism_backend("multiprocessing"):
            assert get_safe_parallel_backend() == "multiprocessing"
        assert get_safe_parallel_backend() == before

    def test_context_manager_restores_on_exception(self):
        before = get_safe_parallel_backend()
        with pytest.raises(RuntimeError):
            with parallelism_backend("threading"):
                raise RuntimeError("boom")
        assert get_safe_parallel_backend() == before, (
            "an override that survives an exception leaks into unrelated later work"
        )

    def test_nested_overrides_unwind_in_order(self):
        with parallelism_backend("threading"):
            with parallelism_backend("multiprocessing"):
                assert get_safe_parallel_backend() == "multiprocessing"
            assert get_safe_parallel_backend() == "threading"

    def test_none_restores_auto_detection(self):
        with parallelism_backend("threading"):
            with parallelism_backend(None):
                assert get_safe_parallel_backend() == "loky"

    @pytest.mark.parametrize("bad", ["invalid_backend", "dask", ""])
    def test_invalid_backend_rejected(self, bad):
        with pytest.raises(ValueError, match="Invalid backend"):
            configure_parallelism_backend(force_backend=bad)
        with pytest.raises(ValueError, match="Invalid backend"):
            with parallelism_backend(bad):
                pass


class TestCreateSafeParallel:
    def test_uses_context_appropriate_settings(self):
        parallel = create_safe_parallel(n_jobs=2)
        assert parallel.n_jobs == 2

    def test_actually_computes(self):
        from joblib import delayed

        parallel = create_safe_parallel(n_jobs=2)
        assert parallel(delayed(abs)(x) for x in (-3, -1, 4)) == [3, 1, 4]
