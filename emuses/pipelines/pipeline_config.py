# pipelines/pipeline_config.py

import argparse
import atexit
from dataclasses import dataclass, field
import logging
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from datetime import datetime
import sys
import sys, multiprocessing as mp

from bcblib.tools.general_utils import save_json
import optuna

# create ONE queue at module load, so children can see it
LOG_QUEUE = mp.Queue(-1)


@dataclass
class PipelineConfig:
    # Direct parameter fields (replaces args.*)
    output_folder: str
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
    umap_jobs: int = None  # Number of parallel jobs for UMAP optimization
    hdbscan_jobs: int = None  # Number of parallel jobs for HDBSCAN optimization
    umap_trials: int = 50  # Number of UMAP optimization trials
    hdbscan_trials: int = 20  # Number of HDBSCAN optimization trials

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
        """
        if len(args) == 1 and isinstance(args[0], argparse.Namespace):
            # Convert namespace to kwargs and merge with any existing kwargs
            namespace_dict = vars(args[0])
            kwargs.update(namespace_dict)

        # Set all the attributes directly (respecting dataclass defaults)
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Call post_init only once
        self.__post_init__()

    def __post_init__(self):
        # ------------------------------------------------------------------
        # Create / resolve output folder
        # ------------------------------------------------------------------
        self.output_path = Path(self.output_folder).resolve()
        self.output_path.mkdir(parents=True, exist_ok=True)
        # Update output_folder to be the Path object for stage compatibility
        self.output_folder = self.output_path
        self._configure_logging()

        # ------------------------------------------------------------------
        # Configure global logging (only once)
        # ------------------------------------------------------------------
        log_path = self.output_path / "log"
        log_path.mkdir(exist_ok=True)

        log_file = log_path / "pipeline.log"

        # Avoid duplicate handlers in interactive sessions
        if not any(
            isinstance(h, logging.FileHandler) and h.baseFilename == str(log_file)
            for h in logging.getLogger().handlers
        ):
            logging.basicConfig(
                level=logging.INFO,  # default level
                format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
                handlers=[
                    logging.StreamHandler(sys.stdout),  # console
                    logging.FileHandler(log_file, mode="w"),  # file
                ],
            )
            # Quiet down very chatty libs if you like:
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
        dict_args = vars(self).copy()
        dict_args["datetime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json(
            log_path / f"arguments_{dict_args['datetime'].replace(':','-')}.json",
            dict_args,
        )

    def _configure_logging(self):
        log_dir = self.output_path / "log"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "pipeline.log"

        root = logging.getLogger()
        root.setLevel(logging.INFO)

        # ➋ CHILD processes: just attach QueueHandler once and return
        if mp.current_process().name != "MainProcess":
            if not any(isinstance(h, QueueHandler) for h in root.handlers):
                root.addHandler(QueueHandler(LOG_QUEUE))
            return

        # ➌ MAIN process: create listener & real handlers
        stream = logging.StreamHandler(sys.stdout)
        file = logging.FileHandler(log_file, mode="a", encoding="utf-8")

        listener = QueueListener(LOG_QUEUE, file, stream, respect_handler_level=True)
        listener.start()

        # remove any default handlers added by basicConfig
        root.handlers.clear()
        root.addHandler(QueueHandler(LOG_QUEUE))

        # make sure everything is flushed on shutdown
        atexit.register(listener.stop)

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
