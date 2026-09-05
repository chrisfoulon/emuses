#!/usr/bin/env python3
"""
Development test runner for local validation before pushing.

Two modes, and the point of this file is that CI runs the *same* commands, so
"passes locally" and "passes in CI" cannot drift apart:

    python scripts/dev_test_runner.py          # smoke: syntax + parallelism, ~1 s
    python scripts/dev_test_runner.py --core   # the core contract, ~3 min

THE CORE CONTRACT
-----------------
`CORE_SUITES` below is the definition of "the core pipeline still works", and it is
the single place that definition lives -- the workflows call this script rather than
listing directories of their own, because two lists in two YAML files drift.

It must be **green at all times**. It was green when written (2026-09-05), measured
directly. Areas outside it carry known failures (`tests/model_registry` 32,
`tests/cli` 16, `tests/foundation_fastapi_service` 10, `tests/security` 1) which are
real but do not touch the science path; they are swept non-gating by ci.yml so they
stay visible without turning every push red.

Two rules for changing this list, both learned the expensive way:

1. **Only ever add.** Removing a suite to get back to green converts a real failure
   into an invisible one, which is the failure mode this project keeps paying for
   (cf. the regression conftest, which errored in whole-tree runs for months).
   If something here breaks, fix it or state plainly that it is broken.
2. **`tests/regression` stays.** It is the numerical pinning, and it is the only
   thing in the suite that catches a *silent* change in scientific output rather
   than a crash.
"""

import shlex
import subprocess
import sys
import time
from pathlib import Path


# The core contract. See the module docstring before editing -- especially the
# "only ever add" rule. Counts are what each suite measured on 2026-09-05.
CORE_SUITES = [
    ("tests/regression", "Numerical pinning (scores, clusters, embedding geometry)"),
    ("tests/pipelines", "Pipeline stages"),
    ("tests/inference", "Inference path"),
    ("tests/flexible-inference-stage", "Inference stage flexibility"),
    ("tests/tools", "Shared tools"),
    ("tests/unit", "Unit tests"),
    ("tests/test_pytest_option_registration.py", "Pinning stays armed in whole-tree runs"),
    # A branch that adds tests adds them here, in its own commit. Nothing here may
    # name a path that does not exist yet: pytest exits 4 on a missing path, so the
    # whole contract would fail for a bookkeeping reason and teach everyone to
    # ignore it.
]


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}")
    
    start_time = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=False)
    duration = time.time() - start_time
    
    if result.returncode == 0:
        print(f"✅ {description} - PASSED ({duration:.1f}s)")
        return True
    else:
        print(f"❌ {description} - FAILED ({duration:.1f}s)")
        return False


def main():
    """Run development tests locally."""
    core = "--core" in sys.argv

    if core:
        print("🚀 Running the EMUSES CORE CONTRACT")
        print("The suites that must stay green. ~3 minutes.")
    else:
        print("🚀 Running EMUSES Development Tests (smoke)")
        print("Syntax and parallelism only. Use --core before opening a PR.")

    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    import os
    os.chdir(project_root)

    all_passed = True

    # Use the interpreter this script was started with, not whatever "python" and
    # "pytest" happen to be first on PATH. Those were resolving to a different
    # installation entirely (miniforge3 / Python 3.12 / pytest 9), so the pre-push gate
    # was validating an environment the test suite never runs in — and reporting a
    # serene 13/13 while doing it.
    py = shlex.quote(sys.executable)

    # Test 1: Syntax validation (very fast)
    if not run_command(
        f"{py} -m py_compile emuses/cli/main.py emuses/tools/parallelism_utils.py emuses/__init__.py",
        "Syntax and Import Validation"
    ):
        all_passed = False
    
    # Test 2: Fast unit tests
    if not run_command(
        f"{py} -m pytest tests/tools/test_parallelism_utils.py -v --maxfail=2 -x --tb=short",
        "Fast Development Tests"
    ):
        all_passed = False

    failed_suites = []
    if core:
        # One pytest per suite rather than one invocation over all of them: a suite
        # that dies during collection would otherwise take the whole run's result
        # with it and say nothing about the others. `-p no:randomly` because the
        # contract is a pass/fail gate, and a randomised order that fails only
        # sometimes is not a gate.
        for path, description in CORE_SUITES:
            if not run_command(
                f"{py} -m pytest {path} -q -p no:randomly --tb=short",
                f"Core: {description} ({path})",
            ):
                all_passed = False
                failed_suites.append(path)

    # Summary
    print(f"\n{'='*60}")
    if all_passed:
        if core:
            print("🎉 CORE CONTRACT GREEN. Safe to push and open a PR.")
        else:
            print("🎉 Smoke tests PASSED. Run --core before opening a PR.")
    else:
        print("🛑 Some tests FAILED! Fix issues before pushing to save CI credits.")
        if failed_suites:
            print(f"📝 Core suites failing: {', '.join(failed_suites)}")
            print("   Do NOT resolve this by removing a suite from CORE_SUITES;")
            print("   see the 'only ever add' rule in this file's docstring.")
    print(f"{'='*60}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
