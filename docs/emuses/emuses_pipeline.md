# EMUSES Core Pipeline

The EMUSESPipeline class serves as the central orchestrator for the EMUSES machine learning workflow. It manages data preprocessing, stage execution, random state management, and context sharing between pipeline stages. The pipeline supports both classic mode (single dataset) and label_dataset mode (separate labeled/unlabeled datasets) for flexible experimental designs.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function/Class | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `EMUSESPipeline.__init__(args)` | Initialize pipeline with configuration | `args: argparse.Namespace` | `EMUSESPipeline` | Creates output dirs, sets up logging, manages random seeds |
| `process_dataset(dataset_identifier, is_labelled)` | Load and preprocess datasets into matrices | `dataset_identifier: str/Path, is_labelled: bool` | `(input_matrix: ndarray, dataset_type: str, format_info: tuple, scores: ndarray)` | None |
| `split_dataset()` | Split data into train/test with stratification | `None` | `None` | Updates context with split data and indices |
| `add_stage(stage)` | Add pipeline stage for execution | `stage: PipelineStage` | `None` | Appends to stages list |
| `run(progress_callback, progress_queue)` | Execute all pipeline stages sequentially | `progress_callback: Callable, progress_queue: Queue` | `None` | Executes stages, updates context, logs timing |
| `format_args()` | Process and validate pipeline arguments | `None` | `None` | Loads datasets, processes scores, calls split_dataset |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Pipeline Initialization
The pipeline constructor handles configuration, random state management, and data preprocessing:

```python
def __init__(self, args):
    """
    Initialize EMUSES pipeline with comprehensive setup.
    
    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments containing all pipeline configuration
        
    Notes
    -----
    - Creates deterministic random seeds for all pipeline components
    - Supports both classic mode (single dataset) and label_dataset mode
    - Initializes logging and output directory structure
    - Processes datasets immediately during initialization
    """
    self.config = PipelineConfig(args)
    self.output_folder = self.config.output_folder
    
    # Initialize data containers for different modes
    self.input_matrix = None          # Classic mode main dataset
    self.scores = None               # Associated scores/labels
    self.labelled_input_matrix = None  # Label_dataset mode labeled data
    self.labelled_scores = None      # Label_dataset mode scores
    
    # Pipeline execution state
    self.stages = []
    self.context = {}  # Shared data between stages
    self.results = {}
```

## Random State Management
Implements reproducible randomness across all pipeline components:

```python
# Create root random number generator from master seed
master_seed = getattr(self.config, "random_state", 42)
root_rng = default_rng(master_seed)

# Generate component-specific seeds for full reproducibility  
random_seeds = {
    "master_seed": master_seed,
    "split_seed": root_rng.integers(0, 2**32),
    "umap_seed": root_rng.integers(0, 2**32), 
    "clustering_seed": root_rng.integers(0, 2**32),
    "prediction_seed": root_rng.integers(0, 2**32),
    "cv_seed": root_rng.integers(0, 2**32),
    "optuna_seed": root_rng.integers(0, 2**32),
}

# Persist seeds for reproducibility and debugging
seed_file = self.output_folder / "random_seeds.json"
save_json(seed_file, random_seeds)
```

## Dataset Processing
Supports multiple input formats with automatic type detection:

```python
def process_dataset(self, dataset_identifier, is_labelled=False):
    """
    Load and preprocess datasets with automatic format detection.
    
    Parameters
    ----------
    dataset_identifier : str or Path
        Path to dataset or special identifier (e.g., 'mnist')
    is_labelled : bool
        Whether this is a labeled dataset for prediction
        
    Returns
    -------
    tuple
        (input_matrix, dataset_type, format_info, scores)
        
    Notes
    -----
    Supports formats:
    - Images (jpg, png, etc.)
    - NIfTI files (.nii, .nii.gz)
    - Spreadsheets (csv, xlsx)
    - BIDS datasets
    - Built-in datasets (MNIST, digits)
    """
    # Detect dataset type automatically
    dataset_type = detect_dataset_type(dataset_identifier)
    
    if dataset_type == 'images':
        input_matrix = process_images(dataset_identifier, ...)
    elif dataset_type == 'nifti':
        input_matrix = nifti_dataset_to_matrix(dataset_identifier, ...)
    elif dataset_type == 'spreadsheet':
        input_matrix = spreadsheet_to_input_df(dataset_identifier, ...)
    # ... additional format handlers
```

## Data Splitting Strategy
Implements stratified splitting with support for multiple experimental modes:

```python
def split_dataset(self):
    """
    Split datasets into train/test with mode-specific handling.
    
    Notes
    -----
    Classic mode: Same data used for embedding and prediction
    Label_dataset mode: Separate unlabeled (embedding) and labeled (prediction) data
    
    Updates context with standardized naming:
    - embedding_train_features: Data for UMAP training
    - prediction_train_features: Data for model training  
    - prediction_train_labels: Target variables
    """
    test_size = getattr(self.config, "test_size", 0.2)
    split_seed = self.context["random_seeds"]["split_seed"]
    
    if hasattr(self.config, 'label_dataset') and self.config.label_dataset:
        # Label_dataset mode: separate embedding and prediction data
        self.context.update({
            "embedding_train_features": self.input_matrix,  # Unlabeled for UMAP
            "prediction_train_features": self.labelled_input_matrix,  # Labeled for prediction
            "prediction_train_labels": self.labelled_scores,
        })
    else:
        # Classic mode: split single dataset
        train_features, test_features, train_labels, test_labels = train_test_split(
            self.input_matrix, self.scores,
            test_size=test_size, random_state=split_seed
        )
        self.context.update({
            "embedding_train_features": train_features,
            "prediction_train_features": train_features,  # Same data
            "prediction_train_labels": train_labels,
            # ... test data
        })
```

## Stage Execution
Manages sequential stage execution with timing and progress tracking:

```python
def run(self, progress_callback=None, progress_queue=None):
    """
    Execute all registered pipeline stages in order.
    
    Parameters
    ----------
    progress_callback : callable, optional
        Function called with stage progress updates
    progress_queue : Queue, optional  
        Queue for inter-process communication of progress
        
    Notes
    -----
    - Stages share data through self.context dictionary
    - Runtime metrics collected for performance analysis
    - Pipeline metadata tracked for reproducibility
    """
    total_stages = len(self.stages)
    
    for i, stage in enumerate(self.stages):
        stage_name = stage.__class__.__name__
        stage_start_time = time.time()
        
        # Execute stage with shared context
        stage.run(self.context, progress_queue=progress_queue)
        
        # Track completion and timing
        stage_runtime = time.time() - stage_start_time
        self.context["pipeline_metadata"]["stages_completed"].append(stage_name)
        self.context["pipeline_metadata"]["stages_runtime"][stage_name] = stage_runtime
        
        # Report progress if callback provided
        if progress_callback:
            progress = (i + 1) / total_stages
            progress_callback(stage_name=stage_name, progress=progress)
```

</details>
