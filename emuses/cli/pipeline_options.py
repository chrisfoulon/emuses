"""One declaration of the pipeline CLI options, shared by ``full``, ``umap`` and ``heatmap``.

``full``, ``umap`` and ``heatmap`` run the same pipeline and differ only in which stages are
enabled, so they must accept the same options. Before 2026-08-23 only ``full`` declared any:
``umap`` and ``heatmap`` took ``output_folder`` and ``input_dataset`` and nothing else, which
is one of the three reasons neither command could run.

The obvious fix - copy ``full``'s option block twice - is the one to avoid. It would recreate
the Phase 1A bug (four options silently not reaching the pipeline) three times over, because
nothing would relate the copies to each other and drift would be invisible.

Typer builds its CLI from ``inspect.signature()``, so the options cannot be shared as a plain
dict. They can, however, be shared as a *signature*: Typer honours a programmatically assigned
``__signature__`` (verified against typer 0.19.2). So the canonical declaration below is
ordinary readable Python, and :func:`with_pipeline_options` stamps it onto each command.

The declaration function is never called. It exists to carry its signature.
"""

import inspect
from enum import Enum
from pathlib import Path
from typing import Annotated, List, Optional

import typer

class InputNormalization(str, Enum):
    """Input normalization options."""

    none = "none"
    zscore = "zscore"
    min_max = "min-max"
    zero_max = "zero-max"
    robust = "robust"


class CorrelationMethod(str, Enum):
    """Correlation calculation methods."""

    pearson = "pearson"
    spearman = "spearman"
    pointbiserial = "pointbiserial"


class ScoresNormalization(str, Enum):
    """Scores normalization options."""

    none = "none"
    zscore = "zscore"
    min_max = "min-max"
    zero_max = "zero-max"
    robust = "robust"


def _shared_pipeline_options(
    output_folder: Annotated[Path, typer.Argument(help="Output folder")],
    input_dataset: Annotated[
        Path, typer.Argument(help="Input dataset of images (jpg), NIfTI, or MNIST")
    ],
    # Optional arguments start here
    input_file_list: Annotated[
        bool,
        typer.Option(
            "--input_file_list",
            help="Treat input_dataset as a file (CSV/Excel/TXT) containing paths to data files"
        ),
    ] = False,
    scores: Annotated[
        Optional[Path],
        typer.Option(help="Path to scores file associated with the dataset"),
    ] = None,
    label_dataset: Annotated[
        Optional[Path], typer.Option("--label_dataset", help="Path to a separate labelled dataset")
    ] = None,
    recursive_search: Annotated[
        bool,
        typer.Option(
            "--recursive-input-file-search",
            help="Search recursively in the input dataset folder",
        ),
    ] = False,
    input_file_types: Annotated[
        Optional[List[str]],
        typer.Option(
            "--input_file_types",
            help="File types to search for in the input dataset folder",
        ),
    ] = None,
    arg_separator: Annotated[
        str,
        typer.Option("--arg_separator", help="Separator for the input dataset list"),
    ] = ",",
    input_header: Annotated[
        Optional[int],
        typer.Option("--input_header", help="Header for the spreadsheet input dataset"),
    ] = None,
    inputs_columns: Annotated[
        Optional[List[str]],
        typer.Option(
            "--inputs_columns", help="List of columns for inputs in the scores file"
        ),
    ] = None,
    input_index_column: Annotated[
        Optional[int],
        typer.Option(
            "--input_index_column",
            help="Index column for the spreadsheet input dataset",
        ),
    ] = None,
    columns_are_features: Annotated[
        bool,
        typer.Option(
            "--columns_are_features",
            help="Columns are features in the spreadsheet input dataset",
        ),
    ] = False,
    bids_filters: Annotated[
        Optional[List[str]], typer.Option(help="BIDS filters for the input dataset")
    ] = None,
    input_normalization: Annotated[
        InputNormalization,
        typer.Option(
            "-inorm",
            "--input_normalization",
            help="Normalization method for input data",
        ),
    ] = InputNormalization.none,
    scores_header: Annotated[
        Optional[int],
        typer.Option("--scores_header", help="Header for the scores spreadsheet"),
    ] = None,
    scores_index_column: Annotated[
        Optional[int],
        typer.Option(
            "--scores_index_column", help="Index column for the scores spreadsheet"
        ),
    ] = None,
    scores_are_rows: Annotated[
        bool,
        typer.Option(
            "--scores_are_rows",
            help="Scores are in the columns of the spreadsheet input dataset",
        ),
    ] = False,
    scores_column: Annotated[
        Optional[List[str]],
        typer.Option("--scores_column", help="Column(s) for scores in the scores file"),
    ] = None,
    classification: Annotated[
        bool, typer.Option(help="Scores are integer classes in one column")
    ] = False,
    correlation_method: Annotated[
        CorrelationMethod,
        typer.Option(
            "--correlation_method", help="Method to use for correlation calculation"
        ),
    ] = CorrelationMethod.pearson,
    scores_normalization: Annotated[
        ScoresNormalization,
        typer.Option(
            "-snorm",
            "--scores_normalization",
            help="Normalization method for scores data",
        ),
    ] = ScoresNormalization.none,
    filter_labelled_by_scores: Annotated[
        bool,
        typer.Option(
            "--filter_labelled_by_scores",
            help="Filter the labelled dataset to only keep files referenced in the scores file",
        ),
    ] = False,
    load_umap: Annotated[
        Optional[str], typer.Option(help="Path to a pre-trained UMAP model")
    ] = None,
    load_embeddings: Annotated[
        Optional[str], typer.Option(help="Path to precomputed embeddings")
    ] = None,
    test_size: Annotated[
        float, typer.Option("--test_size", help="Test size for splitting the dataset")
    ] = 0.2,
    prefix: Annotated[str, typer.Option(help="Prefix for the output path names")] = "",
    optim_dict: Annotated[
        str,
        typer.Option("--optim_dict", help="Name of an optim_dict in optim_configs.py"),
    ] = "optim_dict_default",
    umap_n_components: Annotated[
        Optional[int],
        typer.Option(
            "--umap_n_components",
            help=(
                "Embedding dimensionality, overriding n_components in the optim_dict. "
                "Only `emuses umap` can use anything other than 2: the heatmap builds a "
                "2-D grid over the morphospace and has no N-D form yet. Note the default "
                "optim_dicts score trials partly on `entropy`, which is a histogram over "
                "n_bins^d cells and stops being meaningful above 2-D - use optim_dict_nd, "
                "which omits it."
            ),
        ),
    ] = None,
    umap_trials: Annotated[
        int,
        typer.Option(
            "--umap_trials", help="Number of outer (UMAP) optimization trials"
        ),
    ] = 50,
    hdbscan_trials: Annotated[
        int,
        typer.Option(
            "--hdbscan_trials", help="Number of inner (HDBSCAN) optimization trials"
        ),
    ] = 20,
    load_hdbscan: Annotated[
        Optional[str], typer.Option(help="Path to a pre-trained HDBSCAN model")
    ] = None,
    min_cluster_size: Annotated[
        int, typer.Option("--min_cluster_size", help="Minimum cluster size")
    ] = 5,
    interactive_plot: Annotated[
        bool,
        typer.Option(
            "--interactive_plot", help="Option to create interactive clustering plots"
        ),
    ] = False,
    hdbscan_approx_min_span_tree: Annotated[
        bool,
        typer.Option(
            "--hdbscan_approx_min_span_tree",
            help="When set to False, ensures reproducibility but with much longer runtime",
        ),
    ] = True,
    hdbscan_core_dist_n_jobs: Annotated[
        int,
        typer.Option(
            "--hdbscan_core_dist_n_jobs",
            help="Number of parallel jobs for core distance computation in HDBSCAN",
        ),
    ] = -1,
    inspect_data_state: Annotated[
        bool,
        typer.Option(
            "--inspect_data_state",
            help="Inspect data state before model training (for debugging)",
        ),
    ] = False,
    use_enhanced_pipeline: Annotated[
        bool,
        typer.Option(
            "--use_enhanced_pipeline",
            help="Use the enhanced pipeline with Optuna optimization for model selection",
        ),
    ] = False,
    optuna_trials: Annotated[
        int,
        typer.Option(
            "--optuna_trials",
            help="Number of trials for Optuna optimization per model/feature set",
        ),
    ] = 60,
    parallel_models: Annotated[
        bool,
        typer.Option(
            "--parallel_models",
            help="Train models in parallel across different feature sets",
        ),
    ] = False,
    n_jobs: Annotated[
        int,
        typer.Option(
            "--n_jobs",
            help="Number of parallel jobs for model training (-1 uses all cores)",
        ),
    ] = -1,
    service_timeout: Annotated[
        float,
        typer.Option(
            "--service-timeout",
            help="Service request timeout in seconds (0 for unlimited)",
        ),
    ] = 0.0,
    umap_timeout: Annotated[
        float,
        typer.Option(
            "--umap-timeout", help="UMAP stage timeout in seconds (0 for unlimited)"
        ),
    ] = 0.0,
    heatmap_timeout: Annotated[
        float,
        typer.Option(
            "--heatmap-timeout",
            help="Heatmap stage timeout in seconds (0 for unlimited)",
        ),
    ] = 0.0,
    prediction_timeout: Annotated[
        float,
        typer.Option(
            "--prediction-timeout",
            help="Prediction stage timeout in seconds (0 for unlimited)",
        ),
    ] = 0.0,
    model_selection: Annotated[
        Optional[List[str]],
        typer.Option(
            "--model_selection",
            help="List of models to try. Options: gp, rf, gb, kr, xgb, lgb, et, svr",
        ),
    ] = None,
    prediction_optim_dict: Annotated[
        str,
        typer.Option(
            "--prediction_optim_dict",
            help="Name of a prediction optim_dict in optim_configs_predict.py",
        ),
    ] = "optim_dict_predict",
    random_state: Annotated[
        Optional[int],
        typer.Option(
            "--random_state",
            help=(
                "Master random seed. All component seeds derive from it. It does "
                "not change --umap_jobs: a parallel search is nondeterministic "
                "whatever the seed."
            ),
        ),
    ] = None,
    umap_jobs: Annotated[
        Optional[int],
        typer.Option(
            "--umap_jobs",
            help=(
                "Parallel jobs for the UMAP/HDBSCAN search. Default 1. Anything "
                "above 1 makes the run NON-REPRODUCIBLE: optuna schedules trials "
                "concurrently, so the search depends on thread timing."
            ),
        ),
    ] = None,
    hdbscan_jobs: Annotated[
        Optional[int],
        typer.Option(
            "--hdbscan_jobs",
            help=(
                "Parallel jobs for the inner (HDBSCAN) search. Currently has no "
                "effect: that search always runs serially."
            ),
        ),
    ] = None,
    interactive: Annotated[
        bool, typer.Option("--interactive", help="Run in interactive mode")
    ] = False,
    use_service: Annotated[
        bool, typer.Option("--service", help="Use remote service for execution")
    ] = False,
    service_url: Annotated[
        Optional[str],
        typer.Option(
            "--service-url",
            help="URL of the remote service (auto-detected in multi-user mode)",
        ),
    ] = None,
    token: Annotated[
        Optional[str],
        typer.Option("--token", help="Authentication token for multi-user mode"),
    ] = None,
) -> None:
    """Canonical declaration of the options every pipeline command accepts.

    Never called. :data:`SHARED_PIPELINE_SIGNATURE` is taken from this function's signature
    and stamped onto the real commands, so this parameter list is the single place where a
    pipeline option is added, removed or re-helped.
    """
    raise NotImplementedError(
        "_shared_pipeline_options carries a signature and is not meant to be called"
    )


SHARED_PIPELINE_SIGNATURE = inspect.signature(_shared_pipeline_options)


def with_pipeline_options(func):
    """Give ``func`` the shared pipeline option signature.

    The decorated function must accept ``**kwargs``: Typer parses against the stamped
    signature and calls ``func`` with those names as keyword arguments.
    """
    func.__signature__ = SHARED_PIPELINE_SIGNATURE
    return func


def shared_option_names() -> set:
    """Names of the options every pipeline command accepts.

    Used by the guard test to relate the three commands to one declaration rather than
    trusting each of them separately.
    """
    return set(SHARED_PIPELINE_SIGNATURE.parameters)
