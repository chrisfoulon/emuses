"""Marks everything under tests/extras/ as testing a parked feature.

These suites cover features that are kept in the tree but are not part of the
core EMUSES workflow: the model marketplace (search, analytics, ranking,
benchmarking, community), the cloud and database registry backends, and the
multi-tenant service layer. See tests/test_architecture_boundary.py for the
boundary itself and why it exists.

They are excluded from the default run by `-m "not extras"` in pytest.ini, and
run on demand with:

    pytest -m extras

Nothing here is skipped or deleted - it is deselected, which pytest reports, so
the coverage remains visible rather than silently disappearing.
"""

import pytest


def pytest_collection_modifyitems(config, items):
    """Apply the `extras` marker to every test collected from this directory."""
    for item in items:
        if "tests/extras/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.extras)
