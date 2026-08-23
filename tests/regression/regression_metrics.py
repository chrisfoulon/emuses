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


def pairwise_distances(points):
    diff = points[:, None, :] - points[None, :, :]
    return np.sqrt((diff**2).sum(-1))


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
