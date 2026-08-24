"""Entry point for running the EMUSES service as its own process.

The CLI used to start the local service with ``multiprocessing.Process``. That had two
consequences, both measured on 2026-08-23:

- **``--n_jobs`` was inert.** ``is_subprocess_context()`` asks whether
  ``mp.current_process().name != "MainProcess"``, which is true in a forked child, so
  ``get_safe_n_jobs()`` clamped every request to 1 inside the service. The clamp itself is
  right - spawning loky workers from an already-forked process genuinely hangs, which was
  reproduced - but the service is the *top* of the pipeline's work, not a joblib worker.
  Process identities, measured:

  ==========================  ======================  =============
  context                     ``type().__name__``     clamp?
  ==========================  ======================  =============
  main process                ``_MainProcess``        no
  loky worker                 ``LokyProcess``         yes
  joblib mp worker            ``ForkProcess``         yes
  service (old, forked)       ``Process``             no, but did
  ==========================  ======================  =============

- **A killed CLI orphaned the service.** After a ``timeout`` kill, the child held its port
  for over an hour, ignored SIGTERM and needed SIGKILL; ``atexit`` never runs when the
  parent is terminated.

Run as its own interpreter the service is ``MainProcess``, so the clamp stops firing
without ``get_safe_n_jobs`` being touched at all, and loky is safe because nothing is
nested.

Not reusing ``emuses/foundation_fastapi_service/app.py``'s ``__main__``: it hardcodes port
8000 and binds ``0.0.0.0``, exposing a single-user local service on every interface.
"""

import argparse
import os
import signal
import sys
import threading


def _die_with_parent() -> None:
    """Exit when the parent process goes away.

    The service must not outlive the CLI that started it. ``atexit`` in the parent is not
    enough - it does not run when the parent is killed, which is exactly the case that
    left a listener holding a port for an hour.

    On Linux ``prctl(PR_SET_PDEATHSIG)`` delivers a signal on parent death and needs no
    polling. Elsewhere, fall back to watching the parent pid.
    """
    if sys.platform == "linux":
        try:
            import ctypes

            PR_SET_PDEATHSIG = 1
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            if libc.prctl(PR_SET_PDEATHSIG, signal.SIGTERM, 0, 0, 0) == 0:
                # Guard the race where the parent died between fork and prctl.
                if os.getppid() == 1:
                    os._exit(0)
                return
        except Exception:  # pragma: no cover - fall through to the portable path
            pass

    original_parent = os.getppid()

    def _watch():
        import time

        while True:
            time.sleep(1.0)
            if os.getppid() != original_parent:
                os._exit(0)

    threading.Thread(target=_watch, daemon=True, name="parent-watchdog").start()


def main(argv=None) -> int:
    """Serve the EMUSES API on a loopback port until terminated."""
    parser = argparse.ArgumentParser(prog="emuses-service")
    parser.add_argument("--port", type=int, required=True)
    # Loopback by default and on purpose. This process backs a single-user local CLI; it
    # is not a deployment surface.
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    _die_with_parent()

    def _shutdown(signum, _frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    import uvicorn

    from emuses.api.main import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
