# pipelines/pipeline_config.py

import argparse
import logging
import multiprocessing as mp
from multiprocessing import util as mp_util
import sys
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from typing import Optional, Union

import optuna
from bcblib.tools.general_utils import save_json

from emuses.observability.logging import setup_structured_logging

# create ONE queue at module load, so children can see it
LOG_QUEUE = mp.Queue(-1)

# The single QueueListener draining LOG_QUEUE in the main process.
#
# There must be exactly one. _configure_logging() runs from PipelineConfig.__post_init__,
# so it fires on every PipelineConfig instantiation; creating a listener there unguarded
# started a new thread each time. Two consequences, and the second is the worse one:
#
#   1. The threads were never joined. Each also registered its own atexit handler, and at
#      interpreter shutdown they raced for the stderr lock, aborting the process with
#      "Fatal Python error: _enter_buffered_busy" (exit 134) *after* tests had already
#      passed. Five listeners accumulated over a single four-test file.
#   2. Multiple listeners consuming one queue compete for records. Each log record goes to
#      whichever listener dequeues it first, so output was being split arbitrarily between
#      them rather than duplicated — quietly losing lines from any given handler.
_LOG_LISTENER = None


def _stop_log_listener():
    """
    Stop the shared QueueListener, if one is running.

    Idempotent: QueueListener.stop() joins self._thread and then sets it to None, so a
    second call would raise AttributeError. The global is cleared before stopping so a
    repeat call is a no-op.
    """
    global _LOG_LISTENER

    listener, _LOG_LISTENER = _LOG_LISTENER, None
    if listener is not None:
        listener.stop()


@dataclass
class PipelineConfig:
    # Direct parameter fields (replaces args.*)
    output_folder: Union[str, Path] = field()  # REQUIRED - no default, will be converted to Path in __post_init__
    sigma: float = None
    fwhm: float = None
    # Other parameters with defaults as needed
    # TODO: NEW hyper-parameter search controls to add to the interface at some point
    outer_folds: int = 5  # number of outer CV splits
    optuna_trials: int = 60  # trials per outer split

    # Model versioning for standardized I/O
    model_version: str = "1.0.0"  # Version for model artifacts and metadata tracking

    # UMAP/HDBSCAN optimization parameters
    prefix: str = ""  # Prefix for output file names
    # Serial by default, deliberately. optuna's optimize(n_jobs>1) runs trials
    # concurrently, so TPE's suggestion depends on which trials have finished when
    # each one asks -- thread timing, which no seed controls. Measured 2026-08-23:
    # 10 of 20 metrics identical at jobs=4, 20 of 20 at jobs=1
    # (dev-docs/issues/reproducibility_tolerances_2026_08.md, ADR 2.9c). Parallel
    # search stays available as an opt-in, and asking for it warns.
    umap_jobs: int = 1  # Parallel jobs for the outer (UMAP) Optuna search
    # Currently inert. train_and_save_umap_optim_with_nested_clustering takes
    # parallel_mode="umap" and no caller overrides it, so inner_n_jobs is only read
    # in the parallel_mode == "hdbscan" branch and the inner search always runs at
    # inner_optimize_hdbscan's own n_jobs=1. Declared rather than removed, and
    # guarded by tests/test_search_jobs_default.py so it cannot drift into looking
    # wired.
    hdbscan_jobs: int = 1  # Parallel jobs for the inner (HDBSCAN) Optuna search
    umap_trials: int = 50  # Number of UMAP optimization trials
    hdbscan_trials: int = 20  # Number of HDBSCAN optimization trials
    # Overrides n_components in the optim_dict. None means "use the dict".
    # Only a UMAP-only run may use anything but 2; see
    # emuses/tools/embedding_dimensionality.py for why, and for the check that
    # enforces it before any training happens.
    umap_n_components: int = None
    # Opt in to training predictions in an N-D morphospace, accepting that the
    # grid section is skipped and recorded in heatmaps_skipped.json rather than
    # the run being refused. Prediction training is dimension-agnostic; only the
    # heatmap needs two axes.
    allow_nd_without_heatmaps: bool = False
    # Store subject identifiers in cohort.json. Off by default because that file
    # ships inside the shared model folder; see emuses/tools/cohort_identity.py
    # for why hashing the ids would not make storing them safe.
    record_cohort_ids: bool = False

    # Dataset processing parameters
    input_header: int = None  # Header row for spreadsheet data
    input_index_column: int = None  # Index column for spreadsheet data
    inputs_columns: list = None  # Columns to use from input data
    columns_are_features: bool = False  # Whether columns represent features
    input_normalization: str = None  # Input normalization method
    recursive_input_file_search: bool = False  # Recursive file search
    input_file_types: list = None  # Allowed input file types
    arg_separator: str = ","  # Argument separator
    bids_filters: dict = None  # BIDS dataset filters
    filter_labelled_by_scores: bool = False  # Filter labeled data by scores
    scores_column: str = None  # Column name for scores
    scores_header: int = None  # Header row for scores data
    scores_index_column: int = None  # Index column for scores data
    scores_are_rows: bool = False  # Whether scores are organized as rows
    scores_normalization: str = None  # Normalization method for scores
    scores_columns: list = None  # Columns to use from scores data
    correlation_method: str = "pearson"  # Method for correlation analysis
    classification: bool = False  # Whether to use classification mode

    # Additional CLI parameters that may be missing
    scores: str = None  # Path to scores file
    label_dataset: str = None  # Path to separate labelled dataset
    recursive_search: bool = False  # Search recursively in input dataset folder
    load_umap: str = None  # Path to pre-trained UMAP model
    load_embeddings: str = None  # Path to precomputed embeddings
    test_size: float = 0.2  # Test size for splitting dataset
    optim_dict: str = "optim_dict_default"  # Name of optim_dict
    load_hdbscan: str = None  # Path to pre-trained HDBSCAN model
    min_cluster_size: int = 5  # Minimum cluster size
    interactive_plot: bool = False  # Create interactive clustering plots
    hdbscan_approx_min_span_tree: bool = True  # HDBSCAN approximation setting
    hdbscan_core_dist_n_jobs: int = -1  # Number of parallel jobs for HDBSCAN
    inspect_data_state: bool = False  # Inspect data state before training
    use_enhanced_pipeline: bool = False  # Use enhanced pipeline with Optuna
    parallel_models: bool = False  # Train models in parallel
    n_jobs: int = -1  # Number of parallel jobs for model training
    model_selection: list = None  # List of models to try
    prediction_optim_dict: str = "optim_dict_predict"  # Prediction optim_dict name
    # Master random seed; every component seed derives from it (emuses_pipeline.py).
    # Setting it does NOT change umap_jobs: a parallel Optuna search is
    # nondeterministic whatever the seed. The old comment here claimed otherwise.
    random_state: Optional[int] = None

    # Additional required fields
    input_dataset: str = None  # Input dataset path

    # Pipeline mode control
    inference_mode: bool = False  # Whether this is an inference-only pipeline

    # Computed fields
    output_path: Path = field(init=False)
    umap_params: dict = field(default_factory=dict)
    heatmap_params: dict = field(default_factory=dict)
    prediction_params: dict = field(default_factory=dict)

    def __init__(self, *args, **kwargs):
        """
        Flexible constructor that handles:
        1. Argparse.Namespace objects (flattens them)
        2. Direct parameters as kwargs
        3. Other objects with attributes (flattens them)
        """
        if len(args) == 1:
            if isinstance(args[0], argparse.Namespace):
                # Convert namespace to kwargs and merge with any existing kwargs
                namespace_dict = vars(args[0])
                kwargs.update(namespace_dict)
            else:
                # Handle any object with attributes (like MinimalArgs)
                if hasattr(args[0], "__dict__"):
                    obj_dict = vars(args[0])
                    kwargs.update(obj_dict)

        # Set all the attributes directly (respecting dataclass defaults)
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Call post_init only once
        self.__post_init__()

    def __post_init__(self):
        # ------------------------------------------------------------------
        # Validate and create output folder (REQUIRED)
        # ------------------------------------------------------------------
        if not self.output_folder:
            raise ValueError(
                "output_folder is required. Please provide an explicit output directory path. "
                "Example: PipelineConfig(output_folder='/path/to/your/output')"
            )
        
        self.output_path = Path(self.output_folder).resolve()
        self.output_path.mkdir(parents=True, exist_ok=True)
        # Update output_folder to be the Path object for stage compatibility
        self.output_folder = self.output_path
        self._configure_logging()

        # ------------------------------------------------------------------
        # Quiet down very chatty libs
        # ------------------------------------------------------------------
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)

        # ------------------------------------------------------------------
        # Store heat-map / clustering params
        # ------------------------------------------------------------------
        self.heatmap_params = {"sigma": self.sigma, "fwhm": self.fwhm}
        self.clustering_params = {
            "hdbscan_approx_min_span_tree": getattr(
                self, "hdbscan_approx_min_span_tree", True
            ),
            "hdbscan_core_dist_n_jobs": getattr(self, "hdbscan_core_dist_n_jobs", -1),
        }

        # ------------------------------------------------------------------
        # Persist the full config snapshot
        # ------------------------------------------------------------------
        log_path = self.output_path / "log"
        dict_args = vars(self).copy()
        dict_args["datetime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convert Path objects to strings for JSON serialization
        for key, value in dict_args.items():
            if isinstance(value, Path):
                dict_args[key] = str(value)
        
        save_json(
            log_path / f"arguments_{dict_args['datetime'].replace(':','-')}.json",
            dict_args,
        )

    def _configure_logging(self):
        log_dir = self.output_path / "log"
        log_dir.mkdir(exist_ok=True)
        
        # Use timestamped log filename (same pattern as arguments files)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(':', '-')
        log_file = log_dir / f"pipeline_{timestamp}.log"

        # Setup observability structured logging with file output
        setup_structured_logging(level="INFO", output_file=str(log_file))

        # Ensure file logging works by adding a dedicated FileHandler
        root = logging.getLogger()

        # Check if we already have a file handler for this specific file
        file_handler_exists = any(
            isinstance(h, logging.FileHandler) and h.baseFilename == str(log_file)
            for h in root.handlers
        )

        if not file_handler_exists:
            # Add a dedicated file handler to ensure logs go to timestamped pipeline log
            file_handler = logging.FileHandler(log_file, mode="a")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)8s] %(name)s: %(message)s")
            )
            root.addHandler(file_handler)

        # Log successful configuration
        config_logger = logging.getLogger("emuses.pipeline_config")
        config_logger.info("Pipeline logging configured successfully")

        root = logging.getLogger()
        root.setLevel(logging.INFO)

        # ➋ CHILD processes: just attach QueueHandler once and return
        if mp.current_process().name != "MainProcess":
            if not any(isinstance(h, QueueHandler) for h in root.handlers):
                root.addHandler(QueueHandler(LOG_QUEUE))
            return

        # ➌ MAIN process: create listener & real handlers
        # Use only console handler for QueueListener since file logging is handled by observability
        global _LOG_LISTENER
        if _LOG_LISTENER is None:
            stream = logging.StreamHandler(sys.stdout)

            _LOG_LISTENER = QueueListener(
                LOG_QUEUE, stream, respect_handler_level=True
            )
            _LOG_LISTENER.start()

            # Make sure everything is flushed on shutdown. Registered once, with the
            # listener, so repeated PipelineConfig construction does not stack handlers.
            #
            # Registered as a multiprocessing finalizer rather than with atexit.register,
            # for two reasons:
            #
            #   1. Ordering. LOG_QUEUE registers its own close as a Finalize with
            #      exitpriority=10 (multiprocessing/queues.py), and finalizers run in
            #      descending priority. At 20 the listener is stopped before the queue's
            #      pipe is closed under it. The other way round, the monitor thread is
            #      still blocked in Queue.get() when the pipe goes away and raises
            #      EOFError at interpreter shutdown.
            #   2. It survives the test suite. tests/conftest.py patches atexit.register
            #      with an autouse fixture, so a registration made during any test is
            #      swallowed and the listener is never stopped at all.
            mp_util.Finalize(None, _stop_log_listener, exitpriority=20)

        # Don't clear handlers - let observability logging coexist
        # Only add QueueHandler if not already present
        if not any(isinstance(h, QueueHandler) for h in root.handlers):
            root.addHandler(QueueHandler(LOG_QUEUE))

        opt_file = logging.FileHandler(
            log_dir / "optuna.log", mode="a", encoding="utf-8"
        )
        opt_file.setLevel(logging.INFO)
        logging.getLogger("optuna").addHandler(opt_file)

        optuna.logging.disable_default_handler()
        optuna.logging.enable_propagation()

    def get_model_io_manager(self):
        """
        Get a ModelIOManager instance for standardized model persistence.

        Returns:
            ModelIOManager: Configured manager for this pipeline's models
        """
        from ..tools.model_io import ModelIOManager

        return ModelIOManager(
            base_path=self.output_path / "models", version=self.model_version
        )
