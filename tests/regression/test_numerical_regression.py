"""Numerical regression: does the pipeline still produce the same numbers?

What this suite is for
----------------------
To fail when a code change moves a scientific result. Nothing else. Read the
caveats before trusting a pass:

* **``test_data/features.csv`` is 48 samples x 7 features** (40 after the split).
  That is enough to catch a regression and **not** enough to judge scientific
  quality.
* **The prediction baselines on those two datasets pin nothing.** In every fold
  the winning ElasticNet has all coefficients exactly zero, so the model is a
  constant intercept and its score depends only on the fold split -- it is
  mathematically independent of the embedding coordinates. Those eight numbers
  per dataset survive any change to the coordinate system, right or wrong. The
  ``swiss_roll`` dataset was added on 2026-09-06 because of this and is the only
  one here that can see such a change; see
  ``test_some_dataset_pins_the_coordinate_to_prediction_path`` and ADR 2.9d.
  Do not read a green ``test_prediction_scores[regression]`` as evidence that a
  coordinate-space change was inert.
* **These tolerances detect code changes at a fixed seed.** They say nothing
  about scientific stability. At a different master seed the same config
  produces a cluster ARI of 0.0 against this one, and ``Mean_Score`` moves from
  -0.48 to -1.00 (``dev-docs/issues/reproducibility_tolerances_2026_08.md``).
  That is an under-converged search on 40 samples, not a defect, and it is not
  what this suite measures.
* **Local run-to-run variation is exactly zero**, so every float tolerance below
  is a *chosen* cross-machine allowance, not a measured one. They are labelled
  individually. ADR 2.9b puts bitwise-across-platforms out of scope.
* **This is a same-machine instrument.** Every test that compares a recorded
  number is marked ``machine_specific``, and CI deselects those. They gate on
  the machine that owns the baselines -- your pre-push
  ``python scripts/dev_test_runner.py --core`` -- and report, without gating, on
  a runner. Section "Why CI cannot check these numbers" below is the reason;
  read it before promoting anything back.

Every numerical assertion appends ``environment_note``, which says whether this
machine matches the one that produced the baseline. See
``regression_provenance.py``: the answer to "code change or machine change?"
should not require a day of experiments twice.

Why CI cannot check these numbers
---------------------------------
Measured 2026-09-05, after the environment was brought up to the pinned
versions on both sides. Same code, same seed, same library versions; the only
difference is the host CPU. Local reproduced the baseline **exactly**; the
GitHub runner did not.

The mechanism is amplification through an argmax, not float drift:

1. numba compiles UMAP's kernels for the host CPU (``llvm_cpu_name``:
   ``meteorlake`` here, something else on a runner), so the embedding differs
   in the last bits -- pairwise-distance correlation 0.990299, i.e. the same
   shape, slightly perturbed.
2. That perturbation crosses HDBSCAN decision boundaries: cluster count 3 -> 4.
3. Which changes each Optuna trial's score, so **a different trial wins**.
   ``composite_score`` is the winning trial's score, and it moved 0.4914 ->
   0.5297. That is not a 1e-6 drift of the same quantity; it is a different
   quantity. No float tolerance can cover a change of argmax, and inventing one
   loose enough to try would make the assertion pass on anything.

So the choice is not "tight gate versus loose gate". It is "a gate on the
machine that produced the baselines" versus "a gate that fires on the CPU model
and teaches everyone to ignore it". ADR 2.9b already puts bitwise-across-
platforms out of scope; what is new here is that "not bitwise" does not degrade
gracefully into "within tolerance" once a search selects on the result.

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

# CHOSEN. Measured 1.0 across every repeat *on one machine*; 0.95 allows one
# point of 40 to move between clusters. See the machine_specific mark below for
# why a floor this tight is not a cross-machine gate.
MIN_CLUSTER_ARI = 0.95

# CHOSEN. Measured 1.0. Compared as distances, not coordinates, because UMAP is
# defined only up to rotation and reflection.
#
# Keep it tight. This is the assertion with the most discriminating power in the
# suite, measured 2026-09-05 with the same code and the same seed:
#
#     a different master seed  ->  0.043, 0.050, 0.062, 0.176
#     a different CPU          ->  0.990299
#     this machine, repeated   ->  1.000000
#
# Two orders of magnitude between "different draw" and "same draw, perturbed",
# which is exactly the distinction a numerical regression suite needs to make.
# Do not widen it to 0.95 to accommodate a runner: that would still exclude a
# reseed, but it would also stop detecting a real change to the embedding, and
# the runner problem is not solved by tolerance anyway (see the module
# docstring).
MIN_DISTANCE_CORR = 0.999

# MEASURED. Zero variation, and an integer count has no float drift to allow.
CLUSTER_COUNT_EXACT = True


@pytest.fixture(autouse=True)
def _skip_when_regenerating(regenerating):
    if regenerating:
        pytest.skip("regenerating baselines; nothing to assert against yet")


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_pipeline_produces_the_expected_outputs(regression_results, baselines, dataset):
    """The science path runs and emits everything it is supposed to emit.

    Deliberately NOT ``machine_specific``: it compares the *shape* of the output
    against the baseline, never a value, so it means the same thing on any CPU.

    This is what keeps CI honest once the value comparisons are deselected.
    Without it the core contract would deselect its way to running four
    assertions in 0.06 s and never executing the pipeline at all -- green, fast,
    and checking nothing, which is this project's signature failure. It catches a
    stage that stopped writing its output, a metric that disappeared from the
    search, a target that vanished from the summary CSV, and an embedding that
    changed dimensionality: all real regressions, none of them detectable by
    reading a number.
    """
    current = regression_results[dataset]
    expected = baselines[dataset]["metrics"]

    missing = sorted(set(expected) - set(current))
    assert not missing, (
        f"{dataset}: the pipeline no longer produces {missing}. Something stopped "
        "writing an output, or a metric was dropped from the search."
    )

    assert current["embedding_shape"] == expected["embedding_shape"], (
        f"{dataset}: embedding shape {current['embedding_shape']}, "
        f"baseline {expected['embedding_shape']}"
    )
    assert len(current["_cluster_labels"]) == current["embedding_shape"][0], (
        f"{dataset}: {len(current['_cluster_labels'])} cluster labels for "
        f"{current['embedding_shape'][0]} embedded points"
    )
    assert set(current["umap_params"]) == set(expected["umap_params"]), (
        f"{dataset}: UMAP search space changed, "
        f"{sorted(current['umap_params'])} vs {sorted(expected['umap_params'])}"
    )
    assert set(current["hdbscan_params"]) == set(expected["hdbscan_params"]), (
        f"{dataset}: HDBSCAN search space changed, "
        f"{sorted(current['hdbscan_params'])} vs {sorted(expected['hdbscan_params'])}"
    )

    # Finite, not merely present. A NaN composite or score is how an
    # all-noise clustering or a collapsed model reports itself, and it would
    # satisfy every key-presence check above.
    numeric = ["composite_score"] + [k for k in expected if k.startswith("metric_")]
    numeric += [k for k in expected if k.endswith(SCORE_FIELDS)]
    nonfinite = [k for k in numeric if not np.isfinite(current[k])]
    assert not nonfinite, f"{dataset}: non-finite values for {nonfinite}"


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


def test_some_dataset_pins_the_coordinate_to_prediction_path(baselines):
    """The prediction half of the same guard, and it is deliberately not per-dataset.

    ``test_baseline_is_not_degenerate`` above asks whether the *clustering*
    assertions can fail. This asks the same of the *prediction* assertions, and
    the answer used to be no on every dataset in the suite -- which nothing
    detected, because a suite that cannot fail also cannot report that it cannot
    fail.

    On the two 40-sample datasets, in every fold, the winning ElasticNet has all
    coefficients exactly zero. The L1 penalty zeroes them, so the model is a
    constant intercept and its score depends only on the fold split. Found on
    2026-09-06 by switching the pipeline from per-axis to isotropic rescaling and
    watching all 16 tests pass **bit-identically** while the narrow embedding axis
    went from spanning 1.0 to spanning 0.24 (ADR 2.9d).

    Not parametrized, because those two datasets are still degenerate for
    prediction and that is accepted: they earn their place on the raw-derived
    quantities (embedding geometry, cluster structure, composite score), which are
    non-degenerate and discriminating. What must never again be true is that
    **no** dataset can see a coordinate change. ``swiss_roll`` is the one that can:
    the target is the roll's own generative parameter, so the signal is real, and
    4 of its 5 folds are won by a kernel over the embedding.
    """
    live = sorted(
        dataset
        for dataset, payload in baselines.items()
        if payload["metrics"].get("prediction_depends_on_coordinates")
    )
    breakdown = {
        dataset: (
            f"{payload['metrics'].get('n_constant_prediction_models')}"
            f"/{payload['metrics'].get('n_prediction_models')} folds constant"
        )
        for dataset, payload in baselines.items()
    }
    assert live, (
        "no dataset in this suite has a prediction model that reads the embedding "
        f"coordinates: {breakdown}. Every prediction baseline here is the score of "
        "a constant model, so it will survive any change to the coordinate system, "
        "correct or not -- the suite pins a number that cannot move. Do not fix "
        "this by relaxing an assertion; add or repair a dataset with real signal. "
        "See ADR 2.9d."
    )


# --- Below here: the value comparisons -- the actual pinning ------------------
#
# All four carry `machine_specific`, which means "runs everywhere, gates only on
# the machine that owns the baselines". `scripts/dev_test_runner.py --core`
# runs them; `--core --foreign-machine` (what CI passes) deselects them, and the
# non-gating whole-tree sweep still runs and reports them.
#
# The reason is measured and is in the module docstring under "Why CI cannot
# check these numbers". Two things follow from it that are easy to get wrong:
#
#   * Do not fix a red runner by loosening a tolerance here. The runner does not
#     produce a drifted version of the same number; it produces the score of a
#     different Optuna trial.
#   * Do not delete these because CI does not run them. They are the only thing
#     in the project that catches a silent change to a scientific result, and on
#     the machine that owns the baselines they are exact -- repeated runs vary by
#     zero, so a failure there is a code change, full stop.
#
# The route to a genuine cross-machine gate is a config whose search converges
# to the same optimum from either side of a last-bit perturbation, not a wider
# floor. On 40 samples this one does not: at four alternative master seeds the
# cluster ARI against the baseline is -0.004, -0.030, -0.027, 0.059 and the
# count moves 3 <-> 2, so there is no stable structure to pin in the first place.


@pytest.mark.machine_specific
@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_prediction_scores(regression_results, baselines, dataset, environment_note):
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
            err_msg=(
                f"{dataset}: {key} moved beyond the chosen tolerance"
                f"{environment_note[dataset]}"
            ),
        )


@pytest.mark.machine_specific
@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_composite_and_search_metrics(
    regression_results, baselines, dataset, environment_note
):
    """Composite score and the UMAP/HDBSCAN metrics behind it."""
    current = regression_results[dataset]
    expected = baselines[dataset]["metrics"]
    keys = ["composite_score"] + sorted(
        key for key in expected if key.startswith("metric_")
    )

    # Which trial won, reported rather than asserted. `composite_score` is the
    # winning trial's score, so if the search selected a different trial these
    # numbers are not a drifted version of the baseline's -- they belong to a
    # different point in the parameter space, and reading the delta as drift
    # sends you looking for a tolerance that does not exist. Named in the
    # failure so the next occurrence is diagnosed from the log.
    trials = (
        f"\n[search] winning trial: baseline {expected.get('trial_number')}, "
        f"here {current.get('trial_number')}; "
        f"umap params baseline {expected.get('umap_params')}, "
        f"here {current.get('umap_params')}"
    )

    for key in keys:
        assert key in current, f"{key} disappeared from the output"
        np.testing.assert_allclose(
            current[key],
            expected[key],
            rtol=SEARCH_RTOL,
            err_msg=(
                f"{dataset}: {key} moved beyond the chosen tolerance"
                f"{trials}{environment_note[dataset]}"
            ),
        )


@pytest.mark.machine_specific
@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_cluster_count(regression_results, baselines, dataset, environment_note):
    current = regression_results[dataset]["n_clusters"]
    expected = baselines[dataset]["metrics"]["n_clusters"]
    assert current == expected, (
        f"{dataset}: cluster count {current}, baseline {expected}"
        f"{environment_note[dataset]}"
    )


@pytest.mark.machine_specific
@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_cluster_structure(regression_results, baselines, dataset, environment_note):
    """Compared label-invariantly: cluster ids are arbitrary."""
    ari = cluster_ari(
        baselines[dataset]["metrics"]["_cluster_labels"],
        regression_results[dataset]["_cluster_labels"],
    )
    assert ari >= MIN_CLUSTER_ARI, (
        f"{dataset}: cluster structure changed, adjusted Rand index {ari:.4f} "
        f"against a chosen floor of {MIN_CLUSTER_ARI}{environment_note[dataset]}"
    )


@pytest.mark.machine_specific
@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_embedding_geometry(regression_results, baselines, dataset, environment_note):
    """Geometry, not coordinates: UMAP is fixed only up to rotation/reflection.

    The discriminating assertion in this suite -- see MIN_DISTANCE_CORR.
    """
    corr = distance_correlation(
        baselines[dataset]["metrics"]["_embedding_distances"],
        regression_results[dataset]["_embedding_distances"],
    )
    assert corr >= MIN_DISTANCE_CORR, (
        f"{dataset}: embedding geometry changed, pairwise-distance correlation "
        f"{corr:.6f} against a chosen floor of {MIN_DISTANCE_CORR}"
        f"{environment_note[dataset]}"
    )
