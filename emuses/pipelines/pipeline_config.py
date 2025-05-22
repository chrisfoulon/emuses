# pipelines/pipeline_config.py

import argparse
from dataclasses import dataclass, field
import logging
from pathlib import Path
from datetime import datetime
import sys

from bcblib.tools.general_utils import save_json


@dataclass
class PipelineConfig:
    # Direct parameter fields (replaces args.*)
    output_folder_path: str
    sigma: float = None
    fwhm: float = None
    # Other parameters with defaults as needed

    # Computed fields
    output_folder: Path = field(init=False)
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
            # Convert namespace to kwargs
            namespace_dict = vars(args[0])
            # Initialize with flattened args
            self.__init__(**namespace_dict)
            return

        # Standard dataclass initialization with direct parameters
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Call post_init to set up derived fields
        self.__post_init__()

    def __post_init__(self):
        # ------------------------------------------------------------------
        # Create / resolve output folder
        # ------------------------------------------------------------------
        self.output_folder = Path(self.output_folder).resolve()
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # Configure global logging (only once)
        # ------------------------------------------------------------------
        log_path = self.output_folder / "log"
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
