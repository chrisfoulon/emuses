"""Where pytest command-line options are declared, and why it is not negotiable.

pytest honours ``pytest_addoption`` only from *initial* conftests - the rootdir conftest and the
conftests of directories named on the command line. ``pytest.ini`` sets ``testpaths = tests``, so
a bare ``pytest`` has ``tests`` as its initial path: ``tests/conftest.py`` qualifies and nothing
below it does.

``--regen-baselines`` was declared in ``tests/regression/conftest.py`` until 2026-08-25, which
looked tidy - the flag beside the fixtures that read it. The effect was that every test in
``tests/regression/`` errored at setup with ``ValueError: no option named 'regen_baselines'`` in
any run that did not name the directory. The numerical pinning that guards against silent
scientific drift therefore did not run at all under a bare ``pytest``, and said "error" rather
than "regression detected" inside a suite already carrying ~150 known failures.

The 14 regression tests only complain in whole-tree runs, which is the invocation nobody watches.
These two tests complain in *every* invocation. That is the entire point of them.

See ``dev-docs/issues/regression_conftest_addoption_2026_08.md``.
"""

import ast
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent

# The only conftest pytest treats as initial under `testpaths = tests`.
CANONICAL_CONFTEST = TESTS_ROOT / "conftest.py"


def _declares_addoption(path: Path) -> bool:
    """True if `path` defines pytest_addoption at module level.

    Parsed, not grepped: a comment or docstring mentioning the name must not count. A check that
    matches text rather than structure is how a verification silently passes without verifying
    anything.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "pytest_addoption"
        for node in tree.body
    )


def test_addoption_is_declared_only_in_the_initial_conftest():
    """No conftest below tests/ may declare pytest_addoption."""
    declaring = sorted(
        path
        for path in TESTS_ROOT.rglob("conftest.py")
        if _declares_addoption(path)
    )

    assert declaring == [CANONICAL_CONFTEST], (
        "pytest_addoption must be declared in tests/conftest.py and nowhere else under tests/.\n"
        f"Found it in: {[str(p.relative_to(TESTS_ROOT.parent)) for p in declaring]}\n\n"
        "pytest honours this hook only from initial conftests. With `testpaths = tests`, a hook "
        "in a subdirectory conftest is silently ignored under a bare `pytest`, and every test "
        "that reads the option dies at setup with `no option named ...` - visible only in "
        "whole-tree runs. Moving it back down disables tests/regression/ exactly there.\n"
        "See dev-docs/issues/regression_conftest_addoption_2026_08.md."
    )


def test_the_regen_baselines_option_is_actually_registered(pytestconfig):
    """The static check above says where the hook lives; this says pytest ran it.

    Deliberately separate: the file could be in the right place and the hook still fail to
    register (renamed flag, an exception during collection). Only asking the live config settles
    that, and it settles it for whichever invocation is running right now.
    """
    try:
        pytestconfig.getoption("--regen-baselines")
    except ValueError as exc:  # pragma: no cover - the failure this file exists to prevent
        pytest.fail(
            f"--regen-baselines is not registered in this invocation: {exc}\n"
            "tests/regression/ cannot run at all in this mode; its 14 tests will report "
            "setup errors rather than numerical failures. Check that pytest_addoption is in "
            "tests/conftest.py.",
            pytrace=False,
        )
