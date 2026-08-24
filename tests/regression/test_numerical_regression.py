"""Numerical regression: does the pipeline still produce the same numbers?

What this suite is for
----------------------
To fail when a code change moves a scientific result. Nothing else. Read the
caveats before trusting a pass:

* **``test_data/`` is 48 samples x 7 features** (40 after the split). That is
  enough to catch a regression and **not** enough to judge scientific quality.
* **These tolerances detect code changes at a fixed seed.** They say nothing
  about scientific stability. At a different master seed the same config
  produces a cluster ARI of 0.0 against this one, and ``Mean_Score`` moves from
  -0.48 to -1.00 (``dev-docs/issues/reproducibility_tolerances_2026_08.md``).
  That is an under-converged search on 40 samples, not a defect, and it is not
  what this suite measures.
* **Local run-to-run variation is exactly zero**, so every float tolerance below
  is a *chosen* cross-machine allowance, not a measured one. They are labelled
  individually. ADR 2.9b puts bitwise-across-platforms out of scope.

Config in ``regression_config.py``, deliberately not the shared
``emuses_pipeline_results`` fixture -- see that file for why.
"""

import numpy as np
import pytest
from regression_config import DATASETS, REGRESSION_CONFIG
from regression_metrics import SCORE_FIELDS, cluster_ari, distance_correlation

pytestmark = [pytest.mark.slow, pytest.mark.integration]


# --- Tolerances. Source: dev-docs/issues/reproducibility_tolerances_2026_08.md -
# Each is labelled. Do not let a chosen number start reading as a measured one.

# CHOSEN. The summary CSVs are written to 4 decimal places, so 1e-3 is roughly
# the precision actually recorded. Measured local variation: 0.
PREDICTION_RTOL = 1e-3

# CHOSEN. Cross-BLAS allowance for a different machine. Measured variation: 0.
SEARCH_RTOL = 1e-6

# CHOSEN. Measured 1.0 across every repeat; 0.95 allows one point of 40 to move
# between clusters without failing the suite.
MIN_CLUSTER_ARI = 0.95

# CHOSEN. Measured 1.0. Compared as distances, not coordinates, because UMAP is
# defined only up to rotation and reflection.
MIN_DISTANCE_CORR = 0.999

# MEASURED. Zero variation, and an integer count has no float drift to allow.
CLUSTER_COUNT_EXACT = True


@pytest.fixture(autouse=True)
def _skip_when_regenerating(regenerating):
    if regenerating:
        pytest.skip("regenerating baselines; nothing to assert against yet")


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_baseline_describes_this_config(baselines, dataset):
    """A baseline measured on a different config is not a baseline.

    Same 'declare it as data' shape as ``tests/test_cli_option_mapping.py``: the
    config is recorded alongside the numbers, so editing one without the other
    fails here instead of silently comparing unlike runs.
    """
    recorded = baselines[dataset]["config"]
    drift = {
        key: (value, recorded.get(key, "<absent>"))
        for key, value in REGRESSION_CONFIG.items()
        if recorded.get(key, "<absent>") != value
    }
    assert not drift, (
        "the baseline was produced by a different config, so its numbers do not "
        f"apply: {drift}. Regenerate deliberately with "
        "`pytest tests/regression --regen-baselines`."
    )


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_baseline_is_not_degenerate(baselines, dataset):
    """Guard against a suite that cannot fail.

    The shared fixture's config returns zero clusters with all 40 points noise,
    and an adjusted Rand index between two all-noise labellings is 1.0 by
    construction. If this config ever drifts into that state the cluster
    assertions below stop meaning anything, and they would still pass.
    """
    metrics = baselines[dataset]["metrics"]
    assert metrics["n_clusters"] >= 2, (
        "the baseline has fewer than two clusters, so the ARI assertion cannot "
        "fail. Pick a config that clusters."
    )
    assert metrics["noise_fraction"] < 1.0
    assert len(set(metrics["_cluster_labels"])) > 1


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_prediction_scores(regression_results, baselines, dataset):
    """The number that matters: per-target predictive performance."""
    current = regression_results[dataset]
    expected = baselines[dataset]["metrics"]
    score_keys = sorted(
        key for key in expected if key.endswith(SCORE_FIELDS)
    )
    assert score_keys, "no prediction scores in the baseline -- nothing is pinned"

    for key in score_keys:
        assert key in current, f"{key} disappeared from the output"
        np.testing.assert_allclose(
            current[key],
            expected[key],
            rtol=PREDICTION_RTOL,
            err_msg=f"{dataset}: {key} moved beyond the chosen tolerance",
        )


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_composite_and_search_metrics(regression_results, baselines, dataset):
    """Composite score and the UMAP/HDBSCAN metrics behind it."""
    current = regression_results[dataset]
    expected = baselines[dataset]["metrics"]
    keys = ["composite_score"] + sorted(
        key for key in expected if key.startswith("metric_")
    )

    for key in keys:
        assert key in current, f"{key} disappeared from the output"
        np.testing.assert_allclose(
            current[key],
            expected[key],
            rtol=SEARCH_RTOL,
            err_msg=f"{dataset}: {key} moved beyond the chosen tolerance",
        )


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_cluster_count(regression_results, baselines, dataset):
    assert (
        regression_results[dataset]["n_clusters"]
        == baselines[dataset]["metrics"]["n_clusters"]
    )


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_cluster_structure(regression_results, baselines, dataset):
    """Compared label-invariantly: cluster ids are arbitrary."""
    ari = cluster_ari(
        baselines[dataset]["metrics"]["_cluster_labels"],
        regression_results[dataset]["_cluster_labels"],
    )
    assert ari >= MIN_CLUSTER_ARI, (
        f"{dataset}: cluster structure changed, adjusted Rand index {ari:.4f} "
        f"against a chosen floor of {MIN_CLUSTER_ARI}"
    )


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_embedding_geometry(regression_results, baselines, dataset):
    """Geometry, not coordinates: UMAP is fixed only up to rotation/reflection."""
    corr = distance_correlation(
        baselines[dataset]["metrics"]["_embedding_distances"],
        regression_results[dataset]["_embedding_distances"],
    )
    assert corr >= MIN_DISTANCE_CORR, (
        f"{dataset}: embedding geometry changed, pairwise-distance correlation "
        f"{corr:.6f} against a chosen floor of {MIN_DISTANCE_CORR}"
    )
