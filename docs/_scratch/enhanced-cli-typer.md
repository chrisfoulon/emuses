# Enhanced CLI Typer - Argument Mapping Analysis

## Complete Legacy CLI Argument Inventory

Based on analysis of `emuses/scripts/main.py`, here is the complete mapping of all arguments that must be preserved in the new Typer CLI:

### Commands Structure
- `full` - Run the full pipeline
- `umap` - Train the UMAP and get the embeddings  
- `clustering` - Perform clustering on embeddings
- `heatmap` - Create a heatmap
- `prediction` - Train a prediction model

### Positional Arguments
```python
positional_args = {
    'output_folder': {
        'commands': ['full', 'umap', 'clustering', 'heatmap', 'prediction'],
        'type': 'resolve_path',
        'help': 'Output folder',
        'required': True
    },
    'input_dataset': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],  # NOT clustering
        'type': 'resolve_path', 
        'help': 'Input dataset of images (jpg), NIfTI, or MNIST',
        'required': True
    }
}
```

### File Path Arguments (Security Critical)
```python
file_path_args = {
    'scores': {
        'commands': ['full', 'heatmap', 'prediction'],
        'type': 'resolve_path',
        'help': 'Path to scores file associated with the dataset',
        'required': False
    },
    'load_umap': {
        'commands': ['full', 'umap'],
        'type': 'str',
        'help': 'Path to a pre-trained UMAP model',
        'required': False
    },
    'load_embeddings': {
        'commands': ['full', 'clustering', 'heatmap'],
        'type': 'str', 
        'help': 'Path to precomputed embeddings',
        'required': False
    },
    'load_hdbscan': {
        'commands': ['full', 'clustering', 'heatmap'],
        'type': 'str',
        'help': 'Path to a pre-trained HDBSCAN model', 
        'required': False
    },
    'label_dataset': {
        'commands': ['full'],
        'type': 'resolve_path',
        'help': 'Path to a separate labelled dataset (e.g., folder containing NIfTI files)',
        'required': False
    }
}
```

### Boolean Flags
```python
boolean_flags = {
    'recursive_input_file_search': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],
        'action': 'store_true',
        'help': 'Search recursively in the input dataset folder'
    },
    'columns_are_features': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'], 
        'action': 'store_true',
        'help': 'Columns are features in the spreadsheet input dataset'
    },
    'scores_are_rows': {
        'commands': ['full', 'heatmap', 'prediction'],
        'action': 'store_true',
        'help': 'Scores are in the columns of the spreadsheet input dataset'
    },
    'classification': {
        'commands': ['full', 'heatmap', 'prediction'],
        'action': 'store_true',
        'help': 'Scores are integer classes in one column'
    },
    'filter_labelled_by_scores': {
        'commands': ['full', 'heatmap', 'prediction'],
        'action': 'store_true',
        'help': 'If set, filter the labelled dataset to only keep files referenced in the scores file'
    },
    'interactive_plot': {
        'commands': ['full', 'clustering'],
        'action': 'store_true',
        'help': 'Option to create interactive clustering plots'
    },
    'hdbscan_approx_min_span_tree': {
        'commands': ['full', 'clustering'],
        'action': 'store_false',  # NOTE: store_false, default=True
        'default': True,
        'help': 'When set to False, ensures reproducibility but with much longer runtime (10x-100x slower)'
    },
    'inspect_data_state': {
        'commands': ['full', 'heatmap'],
        'action': 'store_true',
        'help': 'Inspect data state before model training (for debugging)'
    },
    'use_enhanced_pipeline': {
        'commands': ['full', 'prediction'],
        'action': 'store_true',
        'help': 'Use the enhanced pipeline with Optuna optimization for model selection'
    },
    'parallel_models': {
        'commands': ['full', 'prediction'], 
        'action': 'store_true',
        'help': 'Train models in parallel across different feature sets'
    },
    'run_old_prediction': {
        'commands': ['full'],
        'action': 'store_true',
        'help': 'Run the old prediction pipeline'
    }
}
```

### Integer Arguments  
```python
integer_args = {
    'input_header': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],
        'type': 'int',
        'default': None,
        'help': 'Header for the spreadsheet input dataset'
    },
    'input_index_column': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],
        'type': 'int', 
        'default': None,
        'help': 'Index column for the spreadsheet input dataset'
    },
    'scores_header': {
        'commands': ['full', 'heatmap', 'prediction'],
        'type': 'int',
        'default': None,
        'help': 'Header for the scores spreadsheet'
    },
    'scores_index_column': {
        'commands': ['full', 'heatmap', 'prediction'],
        'type': 'int',
        'default': None, 
        'help': 'Index column for the scores spreadsheet'
    },
    'test_size': {
        'commands': ['full', 'umap'],
        'type': 'float',  # NOTE: Actually float, not int
        'default': 0.2,
        'help': 'Test size for splitting the dataset'
    },
    'umap_trials': {
        'commands': ['full', 'umap'],
        'type': 'int',
        'default': 50,
        'help': 'Number of outer (UMAP) optimization trials'
    },
    'hdbscan_trials': {
        'commands': ['full', 'umap'],
        'type': 'int',
        'default': 20,
        'help': 'Number of inner (HDBSCAN) optimization trials'
    },
    'min_cluster_size': {
        'commands': ['full', 'clustering'],
        'type': 'int',
        'default': 5,
        'help': 'Minimum cluster size'
    },
    'hdbscan_core_dist_n_jobs': {
        'commands': ['full', 'clustering'],
        'type': 'int',
        'default': -1,
        'help': 'Number of parallel jobs for core distance computation in HDBSCAN (use 1 for reproducibility)'
    },
    'optuna_trials': {
        'commands': ['full', 'prediction'],
        'type': 'int',
        'default': 60,
        'help': 'Number of trials for Optuna optimization per model/feature set'
    },
    'n_jobs': {
        'commands': ['full', 'prediction'],
        'type': 'int',
        'default': -1,
        'help': 'Number of parallel jobs for model training (-1 uses all cores)'
    },
    'random_state': {
        'commands': ['full', 'umap', 'clustering', 'heatmap', 'prediction'],
        'type': 'int',
        'default': 42,
        'help': 'Master random seed for reproducibility (default: 42)'
    },
    'umap_jobs': {
        'commands': ['full'],  # Via common_parallel parser
        'type': 'int',
        'help': 'Number of parallel jobs for outer (UMAP) optimization. If set, inner optimization runs sequentially.',
        'mutually_exclusive_with': 'hdbscan_jobs'
    },
    'hdbscan_jobs': {
        'commands': ['full'],  # Via common_parallel parser
        'type': 'int', 
        'help': 'Number of parallel jobs for inner (HDBSCAN) optimization. If set, outer optimization runs sequentially.',
        'mutually_exclusive_with': 'umap_jobs'
    }
}
```

### Choice Arguments
```python
choice_args = {
    'input_normalization': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],
        'type': 'str',
        'default': 'none',
        'choices': ['none', 'zscore', 'min-max', 'zero-max', 'robust'],
        'help': 'Normalization method for input data.',
        'aliases': ['-inorm']
    },
    'correlation_method': {
        'commands': ['full', 'heatmap', 'prediction'],
        'type': 'str',
        'default': 'pearson',
        'choices': ['pearson', 'spearman', 'pointbiserial'],
        'help': 'Method to use for correlation calculation (default: pearson)'
    },
    'scores_normalization': {
        'commands': ['full', 'heatmap', 'prediction'],
        'type': 'str',
        'default': 'none',
        'choices': ['none', 'zscore', 'min-max', 'zero-max'],
        'help': 'Normalization method for scores data.',
        'aliases': ['-snorm']
    }
}
```

### List Arguments
```python
list_args = {
    'input_file_types': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],
        'type': 'List[str]',
        'nargs': '+',
        'default': None,
        'help': 'File types to search for in the input dataset folder'
    },
    'inputs_columns': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],
        'type': 'List[str]',
        'nargs': '+',
        'help': 'List of columns for inputs in the scores file'
    },
    'bids_filters': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],
        'type': 'List[str]',
        'nargs': '+',
        'default': None,
        'help': 'BIDS filters for the input dataset'
    },
    'scores_column': {
        'commands': ['full', 'heatmap', 'prediction'],
        'type': 'List[str]',
        'nargs': '+',
        'help': 'Column(s) for scores in the scores file'
    },
    'model_selection': {
        'commands': ['full', 'prediction'],
        'type': 'List[str]',
        'nargs': '+',
        'default': None,
        'help': 'List of models to try. Options: gp, rf, gb, kr, xgb, lgb, et, svr'
    }
}
```

### String Arguments  
```python
string_args = {
    'arg_separator': {
        'commands': ['full', 'umap', 'heatmap', 'prediction'],
        'type': 'str',
        'default': ',',
        'help': 'Separator for the input dataset list'
    },
    'prefix': {
        'commands': ['full', 'umap'],
        'type': 'str',
        'default': '',
        'help': 'Prefix for the output path names'
    },
    'optim_dict': {
        'commands': ['full', 'umap'],
        'type': 'str',
        'default': 'optim_dict_default',
        'help': 'Name of an optim_dict in optim_configs.py of Path to the optimization dictionary'
    },
    'prediction_optim_dict': {
        'commands': ['full', 'heatmap', 'prediction'],
        'type': 'str',
        'default': 'optim_dict_predict',
        'help': 'Name of a prediction optim_dict in optim_configs_predict.py (e.g., optim_dict_predict, optim_dict_phase1)'
    },
    'output_format_info': {
        'commands': ['heatmap'],
        'type': 'str',
        'help': 'Output format information needed'
    }
}
```

## Security Requirements

### Path Traversal Protection
All file path arguments must be validated to prevent directory traversal attacks:
- `output_folder`, `input_dataset`, `scores`, `label_dataset` (via `resolve_path`)  
- `load_umap`, `load_embeddings`, `load_hdbscan` (string paths)

### Input Sanitization
- URL decoding (like legacy `resolve_path`)
- Cross-platform path normalization  
- Prevent access to system directories
- Validate file extensions where appropriate

## Typer Implementation Strategy

### Command Structure
```python
import typer
from typing import Optional, List
from pathlib import Path
from enum import Enum

app = typer.Typer()

class InputNormalization(str, Enum):
    none = "none"
    zscore = "zscore" 
    min_max = "min-max"
    zero_max = "zero-max"
    robust = "robust"

@app.command()
def full(
    output_folder: Path = typer.Argument(..., help="Output folder"),
    input_dataset: Path = typer.Argument(..., help="Input dataset of images (jpg), NIfTI, or MNIST"),
    # ... all other arguments with proper types and defaults
):
    pass
```

### Critical Compatibility Points
1. **Exact argument names** - No changes to argument names
2. **Exact default values** - Preserve all defaults  
3. **Exact help text** - Preserve all help messages
4. **Exact validation** - Same validation rules and error messages
5. **Exit codes** - Same exit codes for different error conditions
6. **Path handling** - Same path resolution and security logic
