# pipelines/pipeline_config.py

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import os

from bcblib.tools.general_utils import save_json

@dataclass
class PipelineConfig:
    args: argparse.Namespace
    output_folder: Path = field(init=False)
    umap_params: dict = field(default_factory=dict)
    clustering_params: dict = field(default_factory=dict)
    heatmap_params: dict = field(default_factory=dict)
    prediction_params: dict = field(default_factory=dict)
    # Additional attributes as needed

    def __post_init__(self):
        self.output_folder = Path(self.args.output_folder).resolve()
        self.output_folder.mkdir(parents=True, exist_ok=True)
        if not self.output_folder.is_dir():
            raise ValueError(f"Output folder {self.output_folder} is not a valid path")

        # Initialize UMAP parameters from args
        self.umap_params = {
            # Add UMAP parameters if any
        }

        # Initialize clustering parameters from args
        self.clustering_params = {
            'min_cluster_size': getattr(self.args, 'min_cluster_size', 5),
        }

        # Initialize heatmap parameters from args
        self.heatmap_params = {
            'sigma': getattr(self.args, 'sigma', None),
            'fwhm': getattr(self.args, 'fwhm', None),
        }

        # Initialize prediction parameters from args
        self.prediction_params = {
            # Add prediction-related parameters if needed
        }

        # Save the arguments to a log file
        os.makedirs(self.output_folder / 'log', exist_ok=True)
        dict_args = vars(self.args)
        dict_args['datetime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json(
            self.output_folder / 'log' / f'arguments_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json', dict_args)
