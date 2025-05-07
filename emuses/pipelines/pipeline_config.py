# pipelines/pipeline_config.py

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import os

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
        self.output_folder = Path(self.output_folder).resolve()
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # Set up parameter dictionaries
        self.heatmap_params = {
            'sigma': self.sigma,
            'fwhm': self.fwhm,
        }

        # Save the arguments to a log file
        os.makedirs(self.output_folder / 'log', exist_ok=True)
        dict_args = vars(self)
        dict_args['datetime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json(
            self.output_folder / 'log' / f'arguments_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json', dict_args)
