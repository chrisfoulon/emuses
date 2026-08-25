"""Tests for the parallelism context detection.

These tests deliberately use a **real** `multiprocessing.Process` rather than mocking
`multiprocessing.current_process`. The previous version of this suite mocked it with a
`MagicMock`, which fabricates whatever attribute is asked of it - so the mock had a `.parent`
attribute that the real `multiprocessing.Process` does not. The production code walked that
non-existent attribute, always concluded it was in the main process, and the tests passed
anyway because they were asserting against an object model that does not exist.

A worker process is cheap to start. Use one.
"""

import asyncio
import multiprocessing as mp
import threading

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


class TestConcurrentIsolation:
    """Two overlapping runs must not clobber each other's backend.

    The override was a module global with save/restore until 2026-08-25. That is only correct
    under strict LIFO unwinding. When two runs overlap, the first to *exit* restores the value
    it captured before either had started, and the run still in progress silently falls back to
    auto-detection - loky in the main process, which for this workload is several times slower.

    Nothing raises and no number changes, so the only symptom is a run that took much longer for
    no visible reason. Both tests below fail against the module-global implementation.

    Today nothing overlaps in production, because `_run_pipeline_in_process` blocks the event
    loop. These tests exist so that stops being what the guarantee rests on.
    """

    TIMEOUT = 30

    def test_overlapping_asyncio_tasks_keep_their_own_backend(self):
        """A exits while B is still inside; B must still see its own override."""
        observed = {}

        async def scenario():
            a_entered = asyncio.Event()
            b_entered = asyncio.Event()
            a_exited = asyncio.Event()

            async def job_a():
                with parallelism_backend("threading"):
                    a_entered.set()
                    await b_entered.wait()
                a_exited.set()

            async def job_b():
                await a_entered.wait()
                with parallelism_backend("threading"):
                    b_entered.set()
                    await a_exited.wait()
                    # A has now unwound its scope while this one is still open.
                    observed["b"] = get_safe_parallel_backend()

            await asyncio.wait_for(
                asyncio.gather(job_a(), job_b()), timeout=self.TIMEOUT
            )

        asyncio.run(scenario())

        assert observed["b"] == "threading", (
            f"an overlapping task restored the override out from under this one, which fell "
            f"back to {observed['b']!r}"
        )

    def test_overlapping_threads_keep_their_own_backend(self):
        """Same interleaving across threads rather than tasks."""
        a_entered = threading.Event()
        b_entered = threading.Event()
        a_exited = threading.Event()
        observed = {}

        def job_a():
            with parallelism_backend("threading"):
                a_entered.set()
                b_entered.wait(timeout=self.TIMEOUT)
            a_exited.set()

        def job_b():
            a_entered.wait(timeout=self.TIMEOUT)
            with parallelism_backend("threading"):
                b_entered.set()
                a_exited.wait(timeout=self.TIMEOUT)
                observed["b"] = get_safe_parallel_backend()

        threads = [threading.Thread(target=job_a), threading.Thread(target=job_b)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=self.TIMEOUT)
            assert not thread.is_alive(), "the interleaving deadlocked"

        assert observed.get("b") == "threading", (
            f"an overlapping thread restored the override out from under this one, which fell "
            f"back to {observed.get('b')!r}"
        )

    def test_a_new_thread_does_not_inherit_the_override(self):
        """Documents the boundary of the guarantee, so it is a decision and not a surprise.

        A thread starts with a fresh context, so it sees the default rather than its parent's
        override. Every path from the scope in `pipeline_runner.py` to the `create_safe_parallel`
        call sites is synchronous and stays on one thread, so this does not arise today. If a
        stage ever hands joblib work to a thread of its own, that thread has to enter the scope
        itself - and this test is what should make that obvious rather than mysterious.
        """
        seen = {}

        def probe():
            seen["backend"] = get_safe_parallel_backend()

        with parallelism_backend("threading"):
            thread = threading.Thread(target=probe)
            thread.start()
            thread.join(timeout=self.TIMEOUT)

        assert not thread.is_alive()
        assert seen["backend"] == "loky", (
            "a spawned thread inherited the parent's override; the module comment and this "
            "test both say it does not, so one of them now needs correcting"
        )


class TestCreateSafeParallel:
    def test_uses_context_appropriate_settings(self):
        parallel = create_safe_parallel(n_jobs=2)
        assert parallel.n_jobs == 2

    def test_actually_computes(self):
        from joblib import delayed

        parallel = create_safe_parallel(n_jobs=2)
        assert parallel(delayed(abs)(x) for x in (-3, -1, 4)) == [3, 1, 4]

    def test_the_override_actually_reaches_joblib(self):
        """Positive control: our getter returning "threading" is not the same as joblib using it.

        Without this, every assertion in this module could pass while `Parallel` still span up
        loky workers - the same class of gap as a feature that never engaged.
        """
        with parallelism_backend("threading"):
            parallel = create_safe_parallel(n_jobs=2)
        assert type(parallel._backend).__name__ == "ThreadingBackend", (
            f"joblib was handed {type(parallel._backend).__name__}, not the threading backend "
            f"the override asked for"
        )
