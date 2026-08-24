"""The config the numerical regression baselines are pinned on.

Deliberately **not** ``emuses_pipeline_results`` (``tests/conftest.py``). That
fixture uses ``optim_dict_hcp``, in which every UMAP and HDBSCAN parameter is
fixed, so ``UMAP_utils`` collapses the search to a single trial and HDBSCAN
returns zero clusters with all 40 points labelled noise. An adjusted Rand index
between two all-noise labellings is 1.0 by construction: a cluster-structure
assertion on that config could never fail. Leaving it untouched also means no
existing test changes behaviour.

This is the ``midbudget-serial`` arm of ``scripts/measure_reproducibility.py``,
chosen because it is the only measured config that is both reproducible and
non-degenerate: 20 of 20 metrics identical across three repeats at seed 42, and
3 clusters at ``noise_fraction`` 0.1
(``dev-docs/issues/reproducibility_tolerances_2026_08.md``). Serial search is
what makes the first half true -- ``optuna.study.optimize(n_jobs>1)`` schedules
trials concurrently and no seed fixes that.

Measured cost: 25-34 s per dataset.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REGRESSION_CONFIG = {
    "columns_are_features": True,
    "input_normalization": "robust",
    # A budget with something to search: optim_dict_default has ranges, unlike
    # optim_dict_hcp and optim_dict_test, which are fully fixed.
    "optim_dict": "optim_dict_default",
    "umap_trials": 10,
    "hdbscan_trials": 5,
    "optuna_trials": 15,
    "prediction_optim_dict": "quick_train_dict",
    # Serial search: the reproducibility of every baseline below depends on it.
    "umap_jobs": 1,
    "hdbscan_jobs": 1,
    # Model training parallelism, measured to change nothing (1 vs 4, 20/20).
    "n_jobs": 4,
    "random_state": 42,
    "inference_mode": False,
    # Empty on purpose: a prefix renames the files the registry looks for.
    "prefix": "",
    "interactive_plot": False,
    "load_embeddings": False,
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


def build_args(dataset, output_folder, overrides=None):
    """Build the plain args object ``EMUSESPipeline`` consumes."""
    spec = DATASETS[dataset]
    args = type("Args", (), {})()
    args.input_dataset = str(PROJECT_ROOT / spec["features"])
    # `scores`, not `scores_dataset`: the latter is the service-layer name and
    # PipelineConfig copies unknown attributes verbatim, so the wrong one fails
    # silently with no scores loaded at all.
    args.scores = str(PROJECT_ROOT / spec["scores"])
    args.output_folder = str(output_folder)
    args.scores_header = None
    args.scores_index_column = None
    args.input_header = None
    args.input_index_column = None
    for key, value in {**REGRESSION_CONFIG, **(overrides or {})}.items():
        setattr(args, key, value)
    return args


def run_pipeline(dataset, output_folder, overrides=None):
    """Run one pipeline through the Python API. Returns the output folder."""
    from emuses.pipelines.emuses_pipeline import EMUSESPipeline
    from emuses.pipelines.heatmap_stage import HeatmapStage
    from emuses.pipelines.umap_stage import UMAPStage

    args = build_args(dataset, output_folder, overrides)
    pipeline = EMUSESPipeline(args)
    # Stages are the caller's responsibility: run() iterates self.stages, which
    # only add_stage() populates.
    pipeline.add_stage(UMAPStage(pipeline.config))
    pipeline.add_stage(
        HeatmapStage(pipeline.config, pipeline.context.get("output_format_info"))
    )
    pipeline.run()
    return Path(output_folder)
