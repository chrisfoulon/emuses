"""The service must be its own process, not a fork, and must not outlive the CLI.

Two defects, both measured on 2026-08-23, both caused by ``_start_local_service`` launching
the service with ``multiprocessing.Process``:

1. **``--n_jobs`` was inert on the CLI.** ``is_subprocess_context()`` asks
   ``mp.current_process().name != "MainProcess"``, which is true in any forked child, so
   ``get_safe_n_jobs()`` clamped every request to 1 inside the service. The clamp is not
   wrong - spawning loky workers from an already-forked process genuinely hangs, and that
   was reproduced - but the service is the *top* of the pipeline's work, not a joblib
   worker. Fixing the process identity leaves ``get_safe_n_jobs`` untouched.

2. **A killed CLI orphaned the service.** After a ``timeout`` kill the child held its port
   for over an hour, ignored SIGTERM and needed SIGKILL. ``atexit`` in the parent does not
   run when the parent is killed, which is precisely the case that mattered.

The identity tests spawn real processes. A ``MagicMock`` fabricates ``.name`` and would
pass against an object model that does not exist - the trap that hid this same detector
being broken through the whole of Phase 1B1.
"""

import ast
import inspect
import multiprocessing as mp
import os
import signal
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _identity(_=0):
    """Return this process's identity as joblib/multiprocessing see it."""
    from emuses.tools.parallelism_utils import is_subprocess_context

    proc = mp.current_process()
    return proc.name, type(proc).__name__, is_subprocess_context()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_main_process_is_not_a_worker():
    name, kind, is_worker = _identity()
    assert (name, kind) == ("MainProcess", "_MainProcess")
    assert is_worker is False


@pytest.mark.slow
def test_real_joblib_workers_are_detected():
    """Spawn actual workers on both process backends and check both are caught.

    Clamping in a worker is the behaviour that prevents nested loky from hanging, so this
    must keep passing even as the service stops being misidentified.
    """
    from joblib import Parallel, delayed

    for backend, expected_kind in (("loky", "LokyProcess"), ("multiprocessing", "ForkProcess")):
        name, kind, is_worker = Parallel(n_jobs=2, backend=backend)(
            delayed(_identity)(i) for i in range(2)
        )[0]
        assert kind == expected_kind, f"{backend} worker reported as {kind}"
        assert is_worker is True, (
            f"a real {backend} worker is not detected as one, so n_jobs will not be "
            "clamped there and nested parallelism can hang"
        )


@pytest.mark.slow
def test_the_service_is_not_seen_as_a_worker():
    """A fresh interpreter - which is what the service now is - must not be clamped.

    Guards the actual defect: the service used to be a ``multiprocessing.Process``, whose
    type is ``Process`` and whose name is ``Process-N``, so it was clamped like a worker.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import multiprocessing as mp;"
            "from emuses.tools.parallelism_utils import is_subprocess_context;"
            "p=mp.current_process();"
            "from emuses.tools.parallelism_utils import get_safe_n_jobs;"
            "print(p.name, type(p).__name__, is_subprocess_context(), get_safe_n_jobs(4))",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    name, kind, is_worker, safe_n_jobs = result.stdout.split()
    assert (name, kind) == ("MainProcess", "_MainProcess")
    assert is_worker == "False", (
        "a standalone interpreter is being treated as a joblib worker, so --n_jobs would "
        "be clamped in the service again"
    )
    # The property that actually matters, asserted rather than inferred: the requested
    # n_jobs survives. Absence of loky workers during a run is NOT evidence of this -
    # `_run_pipeline_in_process` forces the threading backend for EMUSES' own parallel
    # calls, so no worker processes appear either way.
    assert safe_n_jobs == "4", (
        f"get_safe_n_jobs(4) returned {safe_n_jobs} in a standalone interpreter. --n_jobs "
        "is being clamped in the service, which is the defect this guards."
    )


def test_the_service_entry_point_binds_loopback_only():
    """A single-user local service must not be exposed on every interface.

    ``emuses/foundation_fastapi_service/app.py``'s own ``__main__`` binds 0.0.0.0, which is
    why the CLI does not use it.
    """
    from emuses.cli import service_process

    source = inspect.getsource(service_process.main)
    assert '"127.0.0.1"' in source, "the default host is no longer loopback"
    assert "0.0.0.0" not in source, (
        "the service entry point binds all interfaces; it backs a local CLI and must not"
    )


def test_start_local_service_does_not_fork():
    """The CLI must launch the service as an independent interpreter.

    Fails if ``multiprocessing.Process`` is reintroduced, which would silently re-clamp
    ``--n_jobs`` and bring back the orphan.
    """
    from emuses.cli import main as cli_main

    tree = ast.parse(textwrap.dedent(inspect.getsource(cli_main._start_local_service)))
    called = {
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "Process" not in called, (
        "_start_local_service constructs a multiprocessing.Process again. The service must "
        "be its own interpreter, or is_subprocess_context() misidentifies it and --n_jobs "
        "goes inert."
    )
    assert called & {"Popen", "run"}, (
        "_start_local_service no longer launches a subprocess; how is the service started?"
    )


@pytest.mark.slow
def test_the_service_dies_with_its_parent():
    """A killed CLI must not leave a listener behind.

    Reproduces the observed failure: a service that outlived its parent by an hour, held a
    port, and ignored SIGTERM. The parent is SIGKILLed here so no cleanup handler can run.
    """
    port = _free_port()
    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"import subprocess,sys,time;"
            f"subprocess.Popen([sys.executable,'-m','emuses.cli.service_process',"
            f"'--port','{port}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
            f"time.sleep(300)",
        ],
        cwd=PROJECT_ROOT,
    )
    try:
        deadline = time.time() + 90
        listening = False
        while time.time() < deadline:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    listening = True
                    break
            time.sleep(1)
        assert listening, "the service never started, so this test proves nothing"

        os.kill(parent.pid, signal.SIGKILL)

        deadline = time.time() + 60
        while time.time() < deadline:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) != 0:
                    return
            time.sleep(1)
        pytest.fail(
            f"port {port} is still accepting connections after the parent was killed - "
            "the service is orphaned, exactly the failure this guards"
        )
    finally:
        if parent.poll() is None:
            parent.kill()
        subprocess.run(
            ["pkill", "-9", "-f", f"service_process --port {port}"],
            capture_output=True,
        )
