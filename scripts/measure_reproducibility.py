#!/usr/bin/env python
"""Measure EMUSES run-to-run variation, to derive the Phase 3 regression tolerances.

Why this exists
---------------
Phase 3 pins numerical baselines produced by the ``emuses_pipeline_results``
fixture (``tests/conftest.py``). A tolerance is only meaningful for the config it
was measured on, so this harness runs *that* config, not a convenient one.

It deliberately does two things that matter more than they look:

* **Deletes each run folder as soon as its metrics are extracted.** Root is at
  90%. A previous session filled it and produced 40 spurious
  "No space left on device" test failures.
* **Checks its own config against the fixture** by parsing ``conftest.py``. If
  the fixture is edited and this script is not, the numbers silently stop
  applying to what Phase 3 pins. Same "declare it as data" shape as
  ``tests/test_cli_option_mapping.py`` and ``tests/test_seed_wiring.py``.

Comparisons are chosen to be invariant to things that are arbitrary:
cluster ids (adjusted Rand index), and UMAP orientation (pairwise-distance
correlation, since UMAP is defined only up to rotation and reflection).

Usage
-----
    python scripts/measure_reproducibility.py --arm fixture --repeats 3
    python scripts/measure_reproducibility.py --arm njobs
    python scripts/measure_reproducibility.py --arm coredist
    python scripts/measure_reproducibility.py --arm seeds
    python scripts/measure_reproducibility.py --arm midbudget-seeds

Results accumulate in ``--out`` (default: measurements.json in the CWD).
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFTEST = PROJECT_ROOT / "tests" / "conftest.py"

# Free space below which we refuse to start another run, in GB. A full run plus
# inference is ~69 MB on test_data; the margin is for the digits arm.
MIN_FREE_GB = 1.0


# ---------------------------------------------------------------------------
# The config under measurement, and the check that it still matches the fixture
# ---------------------------------------------------------------------------

# Mirrors emuses_pipeline_results (tests/conftest.py). Verified against it at
# runtime by _assert_matches_fixture below -- do not edit one without the other.
FIXTURE_CONFIG = {
    "columns_are_features": True,
    "input_normalization": "robust",
    "umap_trials": 1,
    "hdbscan_trials": 1,
    "optim_dict": "optim_dict_hcp",
    "prediction_optim_dict": "quick_train_dict",
    "optuna_trials": 2,
    "n_jobs": 4,
    "random_state": 42,
    "inference_mode": False,
    "prefix": "",
    "interactive_plot": False,
    "load_embeddings": False,
    "hdbscan_jobs": 4,
    "umap_jobs": 4,
    "test_size": 0.2,
    "outer_folds": 5,
}

DATASETS = {
    "regression": {
        "features": "test_data/features.csv",
        "scores": "test_data/regression_scores.csv",
    },
    "multi_target_regression": {
        "features": "test_data/features.csv",
        "scores": "test_data/regression_scores_multitarget.csv",
    },
}


def _fixture_assignments():
    """Pull the ``args.<name> = <literal>`` assignments out of the fixture."""
    tree = ast.parse(CONFTEST.read_text())
    fixture = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "emuses_pipeline_results"
        ),
        None,
    )
    if fixture is None:
        raise RuntimeError(
            "emuses_pipeline_results not found in conftest.py -- this harness "
            "measures that fixture's config and can no longer confirm it."
        )
    found = {}
    for node in ast.walk(fixture):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "args"
        ):
            try:
                found[target.attr] = ast.literal_eval(node.value)
            except ValueError:
                pass  # a non-literal (config['features']); not a knob we pin
    return found


def _assert_matches_fixture():
    actual = _fixture_assignments()
    drift = {
        key: (value, actual.get(key, "<absent>"))
        for key, value in FIXTURE_CONFIG.items()
        if actual.get(key, "<absent>") != value
    }
    if drift:
        lines = "\n".join(
            f"  {k}: harness={h!r} fixture={f!r}" for k, (h, f) in sorted(drift.items())
        )
        raise SystemExit(
            "This harness no longer matches emuses_pipeline_results, so its "
            "numbers would not apply to what Phase 3 pins:\n" + lines
        )
    print(f"config check: {len(FIXTURE_CONFIG)} settings match the fixture")


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def _free_gb(path):
    return shutil.disk_usage(path).free / 1024**3


def run_once(dataset, out_dir, overrides=None):
    """Run the pipeline once. Returns (output_path, seconds)."""
    from emuses.pipelines.emuses_pipeline import EMUSESPipeline
    from emuses.pipelines.heatmap_stage import HeatmapStage
    from emuses.pipelines.umap_stage import UMAPStage

    spec = DATASETS[dataset]
    args = type("Args", (), {})()
    args.input_dataset = str(PROJECT_ROOT / spec["features"])
    args.scores = str(PROJECT_ROOT / spec["scores"])
    args.output_folder = str(out_dir)
    args.scores_header = None
    args.scores_index_column = None
    args.input_header = None
    args.input_index_column = None
    for key, value in {**FIXTURE_CONFIG, **(overrides or {})}.items():
        setattr(args, key, value)

    start = time.time()
    pipeline = EMUSESPipeline(args)
    pipeline.add_stage(UMAPStage(pipeline.config))
    pipeline.add_stage(
        HeatmapStage(pipeline.config, pipeline.context.get("output_format_info"))
    )
    pipeline.run()
    return Path(out_dir), time.time() - start


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------


def _first(root, name):
    hits = sorted(root.rglob(name))
    return hits[0] if hits else None


def extract_metrics(out_dir):
    """Everything we compare, pulled out before the folder is deleted."""
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
        metrics["_embedding_distances"] = _pairwise_distances(emb).tolist()
        metrics["embedding_shape"] = list(emb.shape)

    # The statistics filename carries a timestamp, so it must be globbed.
    scores = {}
    for csv_path in sorted(out_dir.rglob("performance_summary_statistics_*.csv")):
        rows = [line.split(",") for line in csv_path.read_text().splitlines() if line]
        if len(rows) < 2:
            continue
        header = rows[0]
        for row in rows[1:]:
            record = dict(zip(header, row))
            target = record.get("Target", "?")
            for field in ("Mean_Score", "Std_Score", "Min_Score", "Max_Score",
                          "Median_Score", "Q1_Score", "Q3_Score", "Range_Score"):
                if field in record:
                    try:
                        scores[f"{target}_{field}"] = float(record[field])
                    except ValueError:
                        pass
    metrics.update(scores)
    return metrics


def _pairwise_distances(points):
    diff = points[:, None, :] - points[None, :, :]
    return np.sqrt((diff**2).sum(-1))


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare(runs):
    """Summarise variation across runs. Returns {metric: summary}."""
    from sklearn.metrics import adjusted_rand_score

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
        aris = [
            adjusted_rand_score(label_sets[0], other) for other in label_sets[1:]
        ]
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
        base = dist_sets[0].ravel()
        corrs = [
            float(np.corrcoef(base, other.ravel())[0, 1]) for other in dist_sets[1:]
        ]
        maxdiff = [float(np.abs(dist_sets[0] - other).max()) for other in dist_sets[1:]]
        summary["embedding_distance_corr_vs_first"] = {
            "values": corrs,
            "identical": all(c == 1.0 for c in corrs),
            "min": min(corrs),
            "max_abs_distance_diff": max(maxdiff),
        }
    return summary


# ---------------------------------------------------------------------------
# Arms
# ---------------------------------------------------------------------------


# A larger budget is only larger if there is something to search. optim_dict_hcp
# -- what the fixture uses -- has every UMAP and HDBSCAN parameter FIXED, and
# UMAP_utils.py:430 deliberately collapses to a single trial in that case
# ("All parameters are fixed - running a single trial"). Raising umap_trials
# against optim_dict_hcp therefore changes nothing, and an arm that did so would
# silently measure the prediction budget alone. optim_dict_default has ranges.
MID_BUDGET = {
    "optim_dict": "optim_dict_default",
    "umap_trials": 10,
    "hdbscan_trials": 5,
    "optuna_trials": 15,
}


def arm_specs(arm, repeats):
    """(label, overrides) pairs for one arm."""
    if arm == "fixture":
        return [(f"repeat_{i}", {}) for i in range(repeats)]
    if arm == "njobs":
        return [
            (f"n_jobs={n}_repeat_{i}", {"n_jobs": n, "hdbscan_jobs": n, "umap_jobs": n})
            for n in (1, 4)
            for i in range(repeats)
        ]
    if arm == "coredist":
        return [
            (f"core_dist={c}_repeat_{i}", {"hdbscan_core_dist_n_jobs": c})
            for c in (1, -1)
            for i in range(repeats)
        ]
    if arm == "seeds":
        return [(f"seed={s}", {"random_state": s}) for s in (42, 7, 1234)]
    if arm == "midbudget":
        return [
            (f"mid_repeat_{i}", MID_BUDGET) for i in range(repeats)
        ]
    if arm == "midbudget-serial":
        # Same as midbudget but with the Optuna searches run sequentially.
        # optuna's optimize(n_jobs>1) runs trials concurrently, so TPE's
        # suggestion depends on which trials have finished when each one asks --
        # thread timing, which no seed controls.
        return [
            (
                f"mid_serial_repeat_{i}",
                {**MID_BUDGET, "umap_jobs": 1, "hdbscan_jobs": 1},
            )
            for i in range(repeats)
        ]
    if arm == "midbudget-seeds":
        return [
            (
                f"mid_seed={s}",
                {"random_state": s, **MID_BUDGET},
            )
            for s in (42, 7, 1234)
        ]
    raise SystemExit(f"unknown arm: {arm}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--dataset", default="regression", choices=sorted(DATASETS))
    parser.add_argument("--out", default="measurements.json")
    parser.add_argument(
        "--keep-last",
        action="store_true",
        help="keep the final run folder for inspection (costs disk)",
    )
    opts = parser.parse_args()

    _assert_matches_fixture()

    specs = arm_specs(opts.arm, opts.repeats)
    print(f"arm {opts.arm!r}: {len(specs)} runs on {opts.dataset}")

    runs, labels, timings = [], [], []
    workdir = Path(tempfile.mkdtemp(prefix="emuses_measure_"))
    try:
        for index, (label, overrides) in enumerate(specs):
            free = _free_gb(workdir)
            if free < MIN_FREE_GB:
                print(f"ABORT: only {free:.2f} GB free, need {MIN_FREE_GB} GB")
                break
            out_dir = workdir / f"run_{index}"
            print(f"  [{index + 1}/{len(specs)}] {label} (free {free:.2f} GB) ...",
                  flush=True)
            _, seconds = run_once(opts.dataset, out_dir, overrides)
            runs.append(extract_metrics(out_dir))
            labels.append(label)
            timings.append(seconds)
            print(f"      {seconds:.1f}s", flush=True)
            # Delete immediately: the matrix must never accumulate on disk.
            if not (opts.keep_last and index == len(specs) - 1):
                shutil.rmtree(out_dir, ignore_errors=True)
    finally:
        if not opts.keep_last:
            shutil.rmtree(workdir, ignore_errors=True)

    result = {
        "arm": opts.arm,
        "dataset": opts.dataset,
        "labels": labels,
        "seconds": timings,
        "config": FIXTURE_CONFIG,
        "per_run": [
            {k: v for k, v in run.items() if not k.startswith("_")} for run in runs
        ],
        "summary": compare(runs) if len(runs) >= 2 else {},
    }

    out_path = Path(opts.out)
    existing = json.loads(out_path.read_text()) if out_path.exists() else {}
    existing[opts.arm + "/" + opts.dataset] = result
    out_path.write_text(json.dumps(existing, indent=2, default=str))

    print(f"\n=== {opts.arm} / {opts.dataset} ===")
    varying = {k: v for k, v in result["summary"].items() if not v.get("identical")}
    print(f"metrics compared: {len(result['summary'])}")
    print(f"identical across runs: {len(result['summary']) - len(varying)}")
    for key, info in sorted(varying.items()):
        print(f"  VARIES {key}: {info}")
    print(f"written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
