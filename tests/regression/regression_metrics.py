"""The one definition of what an EMUSES run is compared on.

Shared by the regression suite and by ``scripts/measure_reproducibility.py``,
which loads this module by path. Two hand-maintained copies of a metric set is
the Phase 1A bug in a new place: the harness's tolerances would silently stop
describing what the suite pins.

The comparisons are chosen to be invariant to things that are arbitrary:

* **Cluster ids** carry no meaning, so cluster structure is compared by adjusted
  Rand index, not by label equality.
* **UMAP is defined only up to rotation and reflection**, so embeddings are
  compared through their pairwise distances, never through coordinates.

One trap worth knowing when reading the numbers: ``noise_ratio`` in
``best_trial_info.json`` holds ``1 - noise_ratio`` (``clustering_utils.py:53``
defaults to ``normalized=True``), so ``0.0`` there means *every* point is noise.
``noise_fraction`` below is computed from the labels and reads the ordinary way.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np

# Fields pulled from the prediction summary CSVs. The statistics filename carries
# a timestamp, so it has to be globbed rather than named.
SCORE_FIELDS = (
    "Mean_Score",
    "Std_Score",
    "Min_Score",
    "Max_Score",
    "Median_Score",
    "Q1_Score",
    "Q3_Score",
    "Range_Score",
)


def _first(root, name):
    hits = sorted(Path(root).rglob(name))
    return hits[0] if hits else None


def prediction_liveness(out_dir):
    """Do the fitted models actually read the embedding coordinates?

    Returns ``(n_models, n_dead, depends_on_coordinates)``.

    THE MEASUREMENT THIS EXISTS FOR. A regression suite pins a number; it cannot
    tell you whether that number is *capable* of moving. On the two 40-sample
    datasets it was not: in every fold the winning ElasticNet has all coefficients
    exactly zero, so the model is a constant intercept -- the training-fold mean --
    and its score is a function of the fold split alone, mathematically independent
    of the coordinates it was handed. Every prediction baseline on those datasets
    therefore survives *any* change to the coordinate system, which is how the
    isotropic rescale passed 16 tests bit-identically while moving one axis from
    spanning 1.0 to spanning 0.24. ADR 2.9d.

    WHAT IT DETECTS, EXACTLY: a final estimator that exposes ``coef_`` with every
    entry zero. That is the failure that actually occurred. A model with no
    ``coef_`` (``KernelRegressor``) is counted as live, because a kernel over the
    embedding reads coordinates by construction -- but note this cannot detect a
    kernel degenerate in some other way, e.g. a bandwidth so wide every prediction
    is the global mean. Do not read a True here as "the prediction path is sound".
    It means "at least one model is not the specific constant that fooled us".

    Nothing filename-derived is returned: the saved pipelines carry the joblib
    version in their names (``..._joblib1_5_2.joblib``), so a baseline recording
    one would break on a dependency bump for no scientific reason.
    """
    import joblib

    n_models = 0
    n_dead = 0
    for path in sorted(Path(out_dir).rglob("best_pipeline_*.joblib")):
        try:
            estimator = joblib.load(path)
        except Exception as e:
            # Deliberately NOT skipped. Skipping would drop this model from both
            # the numerator and the denominator, so a run where most pipelines
            # failed to load could still report a healthy liveness ratio from the
            # one that did -- a check quietly measuring less than it claims, which
            # is the failure mode this whole exercise exists to remove. A saved
            # pipeline that will not load is anomalous on its own; say so.
            raise RuntimeError(
                f"could not load {path.name} to check whether the prediction "
                f"reads the embedding coordinates: {e}. This is not a numerical "
                f"regression -- the pipeline the run just wrote cannot be read "
                f"back. Fix that before reading anything else in this suite."
            ) from e
        final = estimator.steps[-1][1] if hasattr(estimator, "steps") else estimator
        n_models += 1
        coef = getattr(final, "coef_", None)
        if coef is not None and not np.any(np.asarray(coef)):
            n_dead += 1

    return n_models, n_dead, n_models > 0 and n_dead < n_models


def pairwise_distances(points):
    diff = points[:, None, :] - points[None, :, :]
    return np.sqrt((diff**2).sum(-1))


def confidence_liveness(out_dir):
    """Does the grid confidence map say anything, and does it say the right thing?

    Returns ``(n_maps, n_constant, sparsity_corr)``, where ``sparsity_corr`` is the
    correlation between a grid point's distance to the nearest training sample and its
    confidence, pooled over every map found (``nan`` if none, or if every map is flat).

    WHY THESE TWO, EXACTLY:

    - **Constant.** ``create_statistical_maps`` selects regions by a *percentile*
      threshold on ``predictions * confidence``, and a percentile is invariant to
      multiplication by a positive constant. So a confidence map with zero variance is
      not a weak contribution to region selection, it is arithmetically none: the
      regions come out identical to a run with no confidence at all. That was the state
      of the code until 2026-09-06, when every regression model was assigned a literal
      0.8 and the aggregation took the standard deviation of identical constants.
    - **Sign of the correlation.** A varying map could still vary the wrong way. The
      claim the confidence is making is that the surface is less trustworthy where the
      training data is sparse, so the correlation must be negative. Pinning the sign
      rather than the value keeps this off the machine-specific list -- the value moves
      with the embedding, the sign does not.

    Reads only files the run already wrote, so it costs no pipeline time.
    """
    from scipy.spatial import cKDTree

    out_dir = Path(out_dir)
    scaling_path = _first(out_dir, "embedding_scaling.json")
    emb_path = _first(out_dir, "embeddings.npy")

    n_maps = 0
    n_constant = 0
    distances = []
    confidences = []

    train = None
    if scaling_path and emb_path:
        scaling = json.loads(scaling_path.read_text())
        raw = np.load(emb_path)
        # embeddings.npy is the RAW training embedding (the scaling file says so in
        # `embeddings_npy_space`); the grid lives in the rescaled space, so it has to be
        # put through the same transform or "distance to the nearest training point" is
        # measured in the wrong units. The bounding-box assertion below is what proves
        # the transform was the right one -- the grid was built from exactly these
        # points, so its extent and theirs must agree.
        lo = np.array(scaling["min_embeddings"], dtype=float)
        hi = np.array(scaling["max_embeddings"], dtype=float)
        train = (raw - lo) / float(np.max(hi - lo))

    for conf_path in sorted(out_dir.rglob("confidence_values.npy")):
        conf = np.load(conf_path)
        n_maps += 1
        # Peak-to-peak, not std, and against a tolerance rather than exactly zero.
        # `multi_target_regression`'s target_1 map holds 10000 copies of one value
        # (np.unique gives 1 element, ptp is exactly 0), yet np.std returns 1.97e-31 --
        # rounding in the variance of a tiny constant. An exact `std == 0` test called
        # that map "varying", computed a correlation over what is numerically noise, and
        # produced a confident-looking negative sign that meant nothing. Confidence is
        # defined on [0, 1], so an absolute epsilon is meaningful here.
        if float(np.ptp(conf)) < 1e-9:
            n_constant += 1
            continue
        grid_path = conf_path.parent / "grid_coordinates.npy"
        if train is None or not grid_path.exists():
            continue
        grid = np.load(grid_path)
        if not (np.allclose(grid.min(axis=0), train.min(axis=0), atol=1e-9)
                and np.allclose(grid.max(axis=0), train.max(axis=0), atol=1e-9)):
            # Deliberately NOT skipped quietly. If these disagree the rescale above is
            # not the one the pipeline used, and every distance computed from it is
            # meaningless -- but a correlation would still come back as a plausible
            # number, which is the failure mode this whole suite exists to catch.
            raise RuntimeError(
                f"{conf_path.parent.name}: the grid spans "
                f"{grid.min(axis=0).tolist()}..{grid.max(axis=0).tolist()} but the "
                f"rescaled training embedding spans {train.min(axis=0).tolist()}.."
                f"{train.max(axis=0).tolist()}. The rescale used here is not the one "
                f"the grid was built with, so a confidence-versus-sparsity correlation "
                f"would be measured in the wrong coordinates."
            )
        d, _ = cKDTree(train).query(grid)
        distances.append(d)
        confidences.append(conf)

    if distances:
        corr = float(np.corrcoef(np.concatenate(distances),
                                 np.concatenate(confidences))[0, 1])
    else:
        corr = float("nan")
    return n_maps, n_constant, corr


def extract_metrics(out_dir):
    """Everything we compare, pulled out before the run folder is deleted.

    Keys prefixed with ``_`` are arrays compared by their own rule rather than
    as scalars.
    """
    out_dir = Path(out_dir)
    metrics = {}

    info_path = _first(out_dir, "best_trial_info.json")
    if info_path:
        info = json.loads(info_path.read_text())
        metrics["composite_score"] = info.get("composite_score")
        metrics["trial_number"] = info.get("trial_number")
        metrics["umap_params"] = info.get("param", {}).get("umap")
        metrics["hdbscan_params"] = info.get("param", {}).get("hdbscan")
        for family in ("umap", "hdbscan"):
            for key, value in (info.get("metrics", {}).get(family) or {}).items():
                metrics[f"metric_{family}_{key}"] = value

    labels_path = _first(out_dir, "cluster_labels.npy")
    if labels_path:
        labels = np.load(labels_path)
        metrics["_cluster_labels"] = labels.tolist()
        metrics["n_clusters"] = int(len(set(labels.tolist()) - {-1}))
        metrics["noise_fraction"] = float((labels == -1).mean())

    emb_path = _first(out_dir, "embeddings.npy")
    if emb_path:
        emb = np.load(emb_path)
        # The full matrix, not its upper triangle: the recorded Phase 2 numbers
        # were computed this way and changing it would silently make them
        # incomparable. Note the zero diagonal and the duplicated half inflate a
        # correlation on it, so treat it as an identity check, not a statistic.
        metrics["_embedding_distances"] = pairwise_distances(emb).tolist()
        metrics["embedding_shape"] = list(emb.shape)

    scores = {}
    for csv_path in sorted(out_dir.rglob("performance_summary_statistics_*.csv")):
        rows = [line.split(",") for line in csv_path.read_text().splitlines() if line]
        if len(rows) < 2:
            continue
        header = rows[0]
        for row in rows[1:]:
            record = dict(zip(header, row))
            target = record.get("Target", "?")
            for field in SCORE_FIELDS:
                if field in record:
                    try:
                        scores[f"{target}_{field}"] = float(record[field])
                    except ValueError:
                        pass
    metrics.update(scores)

    n_models, n_dead, live = prediction_liveness(out_dir)
    metrics["n_prediction_models"] = n_models
    metrics["n_constant_prediction_models"] = n_dead
    metrics["prediction_depends_on_coordinates"] = live

    n_maps, n_flat, sparsity_corr = confidence_liveness(out_dir)
    metrics["n_confidence_maps"] = n_maps
    metrics["n_constant_confidence_maps"] = n_flat
    # The sign, not the value: see confidence_liveness. Recorded as a bool so a
    # machine that shifts the embedding cannot fail this on a tolerance.
    metrics["confidence_falls_with_sparsity"] = (
        bool(sparsity_corr < 0) if sparsity_corr == sparsity_corr else None
    )

    return metrics


def cluster_ari(labels_a, labels_b):
    from sklearn.metrics import adjusted_rand_score

    return float(adjusted_rand_score(labels_a, labels_b))


def distance_correlation(distances_a, distances_b):
    a = np.asarray(distances_a).ravel()
    b = np.asarray(distances_b).ravel()
    if a.shape != b.shape:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def compare(runs):
    """Summarise variation across runs. Returns ``{metric: summary}``."""
    summary = {}
    scalar_keys = sorted(
        {
            k
            for run in runs
            for k, v in run.items()
            if not k.startswith("_") and isinstance(v, (int, float))
        }
    )
    for key in scalar_keys:
        values = [run.get(key) for run in runs if run.get(key) is not None]
        if len(values) < 2:
            continue
        spread = max(values) - min(values)
        summary[key] = {
            "values": values,
            "identical": spread == 0.0,
            "abs_spread": spread,
            "rel_spread": (
                spread / abs(statistics.fmean(values))
                if statistics.fmean(values) != 0
                else None
            ),
        }

    label_sets = [run["_cluster_labels"] for run in runs if "_cluster_labels" in run]
    if len(label_sets) >= 2:
        aris = [cluster_ari(label_sets[0], other) for other in label_sets[1:]]
        summary["cluster_ari_vs_first"] = {
            "values": aris,
            "identical": all(a == 1.0 for a in aris),
            "min": min(aris),
        }

    dist_sets = [
        np.asarray(run["_embedding_distances"])
        for run in runs
        if "_embedding_distances" in run
    ]
    if len(dist_sets) >= 2:
        corrs = [distance_correlation(dist_sets[0], other) for other in dist_sets[1:]]
        maxdiff = [float(np.abs(dist_sets[0] - other).max()) for other in dist_sets[1:]]
        summary["embedding_distance_corr_vs_first"] = {
            "values": corrs,
            "identical": all(c == 1.0 for c in corrs),
            "min": min(corrs),
            "max_abs_distance_diff": max(maxdiff),
        }
    return summary
