"""Fixtures for the numerical regression suite.

The suite runs the pipeline once per dataset, extracts the metrics, and
**deletes the run folder immediately**. Root sits at ~90% and a previous session
filled it, producing 40 spurious "No space left on device" failures.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from regression_config import DATASETS, REGRESSION_CONFIG, run_pipeline
from regression_metrics import extract_metrics

BASELINE_DIR = Path(__file__).resolve().parent / "baselines"

REGEN_HELP = (
    "Regenerate the numerical baselines instead of asserting against them. "
    "Deliberate act: the commit message must say what moved the numbers and why."
)


def pytest_addoption(parser):
    parser.addoption("--regen-baselines", action="store_true", help=REGEN_HELP)


@pytest.fixture(scope="session")
def regenerating(pytestconfig):
    return pytestconfig.getoption("--regen-baselines")


@pytest.fixture(scope="session")
def regression_results(regenerating):
    """Run each dataset once, keep only the metrics.

    Session-scoped because a run costs 25-34 s and every assertion in the suite
    reads from the same one.
    """
    workdir = Path(tempfile.mkdtemp(prefix="emuses_regression_"))
    results = {}
    try:
        for dataset in DATASETS:
            out_dir = workdir / dataset
            run_pipeline(dataset, out_dir)
            results[dataset] = extract_metrics(out_dir)
            shutil.rmtree(out_dir, ignore_errors=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if regenerating:
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        for dataset, metrics in results.items():
            payload = {
                "config": REGRESSION_CONFIG,
                "metrics": metrics,
            }
            path = BASELINE_DIR / f"{dataset}.json"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True))
            print(f"\nregenerated baseline: {path}")

    return results


@pytest.fixture(scope="session")
def baselines(regenerating):
    """Load the pinned baselines. A missing one fails; it is never created silently.

    Creating a baseline on demand would let the suite ratchet to whatever the
    code currently does, which is the failure mode a regression suite exists to
    prevent.

    Returns nothing while regenerating: this is session-scoped, so it is set up
    at the first test, before ``regression_results`` has written anything.
    """
    if regenerating:
        return {}

    loaded = {}
    for dataset in DATASETS:
        path = BASELINE_DIR / f"{dataset}.json"
        if not path.exists():
            pytest.fail(
                f"No baseline at {path}. Regenerate deliberately with:\n"
                f"    pytest tests/regression --regen-baselines\n"
                "and say in the commit message what moved the numbers and why."
            )
        loaded[dataset] = json.loads(path.read_text())
    return loaded
