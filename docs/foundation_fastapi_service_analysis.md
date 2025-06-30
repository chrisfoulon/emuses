# foundation_fastapi_service_analysis

The EMUSES pipeline is a sophisticated machine learning framework that performs joint UMAP embedding and HDBSCAN clustering optimization followed by multi-target prediction modeling. The system uses a context-passing pattern where each pipeline stage (`UMAPStage`, `HeatmapStage`, `PredictionStage`) receives and updates a shared context dictionary containing data transformations, model artifacts, and metadata. The pipeline supports both classic mode (single fully-labeled dataset) and label_dataset mode (separate unlabeled data for embedding and labeled data for prediction), with comprehensive random seed management, flexible optimization configurations via nested Optuna trials, and extensive file-based persistence for research traceability.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function/Class | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `EMUSESPipeline.__init__()` | Initialize pipeline with dataset processing and context setup | `args` (config object) | Pipeline instance with populated context | Creates output folder, saves random seeds JSON, processes datasets |
| `EMUSESPipeline.run()` | Execute all pipeline stages with progress tracking | `progress_callback`, `progress_queue` | Updated context with all stage results | Runs stages sequentially, updates metadata, saves timing info |
| `UMAPStage.run()` | Joint UMAP+HDBSCAN optimization using nested Optuna trials | `context` (features, config), `progress_queue` | Context updated with embeddings, clusters, models | Saves UMAP/HDBSCAN models, embeddings, cluster labels to disk |
| `HeatmapStage.run()` | Multi-target prediction model optimization with AE pretraining | `context` (coords, labels, optim_dict), `progress_queue` | Context with CV scores, best models per target | Parallel Optuna optimization, saves models per target, generates performance CSVs |
| `PredictionStage.run()` | Final model evaluation on test data with multiple feature sets | `context` (embeddings, labels), `progress_queue` | Context with test performance metrics | Evaluates best models, saves predictions and performance metrics |
| `train_and_save_umap_optim_with_nested_clustering()` | Core joint optimization function using nested Optuna studies | `input_matrix`, `optim_dict`, `n_trials`, `n_inner_trials` | Trained models, embeddings, cluster labels | Saves optimized UMAP and HDBSCAN models with study results |
| `PipelineConfig.__init__()` | Configuration object wrapping command-line arguments | Raw args object | Validated config with defaults | Processes paths, validates parameters, sets up output structure |
| `suggest_parameters_conditional()` | Optuna parameter suggestion with conditional dependencies | `trial`, `optim_dict` section | Dictionary of suggested parameters | Handles conditional parameter spaces based on model/feature choices |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Pipeline Context Pattern

The EMUSES architecture centers around a shared context dictionary that flows between stages:

```python
# Core context structure populated during initialization
self.context = {
    "pipeline_metadata": {
        "start_time": time.time(),
        "stages_completed": [],
        "stages_runtime": {},
        "dataset_name": "dataset_identifier"
    },
    "random_seeds": {
        "master_seed": 42,
        "umap_seed": generated_seed,
        "clustering_seed": generated_seed,
        "prediction_seed": generated_seed,
        # ... component-specific seeds for reproducibility
    },
    "output_folder": Path("/path/to/output"),
    "dataset_type": "nifti|image|spreadsheet|mnist",
    # Data matrices using standardized naming convention:
    "embedding_train_features": input_matrix,      # Unlabeled data for UMAP
    "prediction_train_features": labeled_matrix,   # Labeled data for prediction
    "prediction_train_labels": labels_array,       # Target values
    # ... test splits and indices when available
}
```

## Stage Execution Flow

Each stage follows the pattern: `stage.run(context, progress_queue)` → context updates:

```python
# UMAPStage: Joint UMAP+HDBSCAN optimization
def run(self, context, progress_queue=None):
    # Extract data using standardized naming
    train_features = context.get("embedding_train_features")
    test_features = context.get("embedding_test_features")
    
    # Load or use default optimization configuration
    optim_dict = context.get("optim_dict", optim_dict_default)
    
    # Nested Optuna optimization: UMAP trials × HDBSCAN trials
    (umap_model, embeddings, best_clusterer, cluster_labels, 
     model_paths...) = train_and_save_umap_optim_with_nested_clustering(
        input_matrix=train_features,
        optim_dict=optim_dict,
        n_trials=50,           # UMAP optimization trials
        n_inner_trials=20,     # HDBSCAN trials per UMAP trial
        random_state=umap_seed
    )
    
    # Update context with standardized outputs
    context.update({
        "embedding_train_coords": embeddings,           # Rescaled embeddings
        "embedding_train_cluster_labels": cluster_labels,
        "embedding_train_umap_model": umap_model,
        "embedding_train_min_coords": min_coords,       # For transform scaling
        "embedding_train_max_coords": max_coords,
        # Transform prediction data if available
        "prediction_train_coords": umap_model.transform(prediction_features),
        # File paths for model persistence
        "cluster_model_path": "/path/to/hdbscan_model.joblib"
    })
```

## Configuration-Driven Optimization

EMUSES uses nested dictionaries for parameter optimization, not individual parameters:

```python
# Example from optim_configs.py - joint UMAP+HDBSCAN configuration
optim_dict_default = {
    'param': {
        'umap': {
            'min_dist': {'name': 'min_dist', 'low': 0.0, 'high': 0.5},
            'n_neighbors': {'name': 'n_neighbors', 'low': 5, 'high': 45, 'step': 10},
            'n_components': {'value': 2},  # Fixed value
            'metric': {'name': 'metric', 'choices': ['euclidean']}
        },
        'hdbscan': {
            'min_cluster_size': {'name': 'min_cluster_size', 'low': 5, 'high': 50},
            'min_samples': {'name': 'min_samples', 'low': 1, 'high': 10}
        }
    },
    'metrics': {
        'umap': {
            'eigen_spread': {'weight': 2.0},
            'density_variability': {'weight': 1.0, 'target': 0.4, 'epsilon': 0.2},
            'entropy': {'weight': 3.0, 'target': 0.6, 'epsilon': 0.25}
        },
        'hdbscan': {
            'cluster_persistence': {'weight': 2},
            'noise_ratio': {'weight': 1.0, 'target': 0.9, 'epsilon': 0.05},
            'dbcv': {'weight': 1.0, 'target': 1, 'epsilon': 0.5}
        }
    }
}

# Prediction optimization with conditional parameters
optim_dict_predict = {
    "param": {
        "model": {
            "model_type": {"choices": ["kernel", "rf", "elastic"]},
            "kernel": {"sigma": {"low": 0.01, "high": 0.3, "log": True}},
            # ... conditional sub-spaces per model type
        },
        "features": {
            "feat_type": {"choices": ["raw_only", "gwd", "pca_gwd", "kpca_gwd"]},
            "sigma_gwd": {
                "low": 0.05, "high": 0.2, "log": True,
                "conditional_on": {"feat_type": ["gwd", "pca_gwd", "kpca_gwd"]}
            }
            # ... conditional feature engineering parameters
        }
    }
}
```

## Multi-Target Parallel Optimization

The HeatmapStage performs parallel optimization across targets:

```python
# HeatmapStage: Multi-target prediction optimization
def run(self, context, progress_queue=None):
    # Extract prediction coordinates and labels
    X = context.get("prediction_train_coords")  # UMAP embeddings
    Y = context.get("prediction_train_labels")  # Multi-target array
    
    # Optional autoencoder pretraining for feature extraction
    if use_ae_pretrain and "ae" in feature_choices:
        ae_results = optimize_ae_pretraining(
            X=X, n_trials=20, output_folder=output_folder
        )
        fitted_ae = ae_results.get("fitted_ae")
    
    # Parallel optimization across targets using joblib
    results = Parallel(n_jobs=-1, backend="loky")(
        delayed(_optimise_target)(
            col_idx, X, Y, task="reg|clf", 
            config, output_folder, logger_name,
            optim_dict_predict,  # Pass optimization configuration
            fitted_ae            # Pre-fitted autoencoder if available
        ) for col_idx in range(Y.shape[1])  # One job per target
    )
    
    # Collect results: each target gets independent nested CV + Optuna
    for target_tag, cv_scores, best_pipeline in results:
        context.setdefault("prediction_results", {})[target_tag] = {
            "cv_scores": cv_scores,              # Cross-validation scores
            "best_pipelines": best_pipeline,     # Optimized model pipeline
            "model_path": f"/path/to/{target_tag}_model.joblib"
        }
```

## Dataset Processing Modes

EMUSES supports two distinct processing modes:

```python
def format_args(self):
    """Process dataset based on mode and update context."""
    if getattr(self.config, "label_dataset", None):
        # Label dataset mode: separate unlabeled and labeled data
        self.input_matrix, _, _, _ = self.process_dataset(
            self.config.input_dataset, is_labelled=False)     # For UMAP
        self.labelled_input_matrix, _, _, _ = self.process_dataset(
            self.config.label_dataset, is_labelled=True)      # For prediction
        self.load_and_process_scores(expected_length=self.labelled_input_matrix.shape[0])
    else:
        # Classic mode: single fully-labeled dataset
        self.input_matrix, _, _, scores = self.process_dataset(
            self.config.input_dataset, is_labelled=False)
        if scores is not None:
            self.scores = scores  # Embedded labels (e.g., MNIST)
        else:
            self.load_and_process_scores(expected_length=self.input_matrix.shape[0])
    
    self.split_dataset()  # Create train/test splits and update context
```

## Model Persistence and I/O

The system extensively uses file-based persistence for research traceability:

```python
# Model saving in UMAPStage
umap_model_path = output_folder / "best_umap_model.joblib"
embeddings_path = output_folder / "embeddings.npy" 
cluster_model_path = output_folder / "hdbscan_model.joblib"
cluster_labels_path = output_folder / "cluster_labels.npy"

# Save with joblib for models, numpy for arrays
joblib.dump(umap_model, umap_model_path)
np.save(embeddings_path, embeddings_array)

# Model loading with existence checks
if all(path.exists() for path in [umap_model_path, embeddings_path, ...]):
    logger.info("Found existing output files. Loading...")
    umap_model, _ = load_umap_model(umap_model_path)
    embeddings = np.load(embeddings_path)
    # Skip re-optimization and use cached results
```

## Random State Management

Comprehensive seed management ensures reproducibility across components:

```python
# Master seed generation in EMUSESPipeline.__init__()
master_seed = getattr(self.config, "random_state", 42)
root_rng = default_rng(master_seed)

# Component-specific seeds for independent reproducibility
random_seeds = {
    "master_seed": master_seed,
    "split_seed": root_rng.integers(0, 2**32),      # Dataset splitting
    "umap_seed": root_rng.integers(0, 2**32),       # UMAP optimization
    "clustering_seed": root_rng.integers(0, 2**32), # HDBSCAN optimization  
    "prediction_seed": root_rng.integers(0, 2**32), # Model training
    "cv_seed": root_rng.integers(0, 2**32),         # Cross-validation
    "optuna_seed": root_rng.integers(0, 2**32),     # Optuna studies
}

# Persistence for audit trail
seed_file = output_folder / "random_seeds.json"
save_json(seed_file, random_seeds)

# Usage in stages
def run(self, context, progress_queue=None):
    random_seeds = context.get("random_seeds", {})
    umap_seed = random_seeds.get("umap_seed", 42)
    # Use component-specific seed for this stage's operations
```

</details>
