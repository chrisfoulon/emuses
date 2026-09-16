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
    # Added 2026-09-06 because the two above pin NOTHING about the path from
    # embedding coordinates to a prediction. On both of them, in every fold, the
    # winning ElasticNet has all coefficients exactly zero -- the L1 penalty
    # zeroes them on 40 samples with no signal -- so the prediction is a constant
    # intercept and `target_0_*_Score` is a function of the fold split alone.
    # That was found by switching the whole pipeline from per-axis to isotropic
    # rescaling and watching all 16 tests pass bit-identically while the narrow
    # axis went from spanning 1.0 to 0.24. See ADR 2.9d.
    #
    # Swiss roll instead, because the answer is known: `make_swiss_roll` returns
    # each sample's position `t` along the roll, which is continuous by
    # construction and certainly recoverable from the 3 coordinates. Here the
    # prediction stage genuinely reads the embedding -- Mean_Score 0.9962, and 4
    # of 5 folds are won by `KernelRegressor`, the family Step 4 of the boundary-
    # bias plan replaces. So this dataset can see a coordinate-space change, and
    # the other two cannot.
    #
    # The CSVs are committed rather than generated at collection time. Regenerating
    # from `make_swiss_roll` on a different sklearn is not guaranteed to reproduce
    # them, and a fixture that quietly changes underneath a baseline is the failure
    # this suite exists to catch. The recipe is in test_data/README.md; the file is
    # authoritative, not the recipe.
    #
    # Cost: 49 s, measured, against 25-34 s for each of the others.
    "swiss_roll": {
        "features": "test_data/swiss_roll_features.csv",
        "scores": "test_data/swiss_roll_scores.csv",
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
