# EMUSES Core Pipeline Overview

<details><summary>👶 Level 1 · High-level overview</summary>

The EMUSES (Emerging-properties Mapping via UMAP Spatial Exploration) pipeline is a comprehensive machine learning framework that transforms high-dimensional neuroimaging data into interpretable, low-dimensional representations through a multi-stage workflow. Starting from diverse input datasets (NIfTI files, images, or CSV data), the pipeline performs dimensionality reduction using UMAP with nested clustering optimization, generates predictive models through advanced hyperparameter optimization, and creates interpretable heatmaps showing spatial relationships between neural patterns and behavioral scores. The framework emphasizes reproducibility through deterministic random seed management, supports both regression and classification tasks, and provides extensive model selection capabilities using Optuna-based Bayesian optimization across multiple feature extraction methods and machine learning algorithms.

</details>

<details><summary>🛠️ Level 2 · API & I/O table</summary>

| Function/Method | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `main()` | Entry point and command-line interface orchestrator | `sys.argv: List[str]` | `None` | Creates output directories, runs pipeline stages |
| `EMUSESPipeline.__init__(args)` | Initialize pipeline with configuration and random seed management | `args: argparse.Namespace` | `EMUSESPipeline` | Sets up random seeds, validates arguments |
| `EMUSESPipeline.run()` | Execute all configured pipeline stages sequentially | `None` | `None` | Processes data through stages, updates context |
| `EMUSESPipeline.process_dataset(dataset_identifier, is_labelled)` | Load and preprocess input datasets into matrices | `dataset_identifier: str/Path, is_labelled: bool` | `(input_matrix: ndarray, dataset_type: str, format_info: tuple, scores: ndarray)` | None |
| `EMUSESPipeline.split_dataset()` | Split data into train/test sets with stratification | `None` | `None` | Updates context with split indices and data |
| `UMAPStage.run(context, progress_queue)` | Train UMAP model with nested clustering optimization | `context: dict, progress_queue: Optional[Queue]` | `None` | Saves UMAP model, embeddings, cluster models |
| `train_and_save_umap_optim_with_nested_clustering()` | Bayesian optimization for UMAP+HDBSCAN parameters | `input_matrix: ndarray, output_folder: Path, optim_dict: dict, **kwargs` | `(umap_model, embeddings, model_paths...)` | Creates optimized models and saves artifacts |
| `HeatmapStage.run(context, progress_queue)` | Generate predictive models and correlation heatmaps | `context: dict, progress_queue: Optional[Queue]` | `None` | Trains prediction models, saves results |
| `nested_optuna_cv()` | Nested cross-validation with Optuna hyperparameter optimization | `X: ndarray, y: ndarray, task: str, **kwargs` | `(scores: ndarray, pipelines: List[Pipeline])` | Saves optimized models per fold |
| `_optimise_target()` | Optimize prediction model for single target variable | `col_idx: int, X: ndarray, Y: ndarray, task: str, cfg: object, **kwargs` | `(tag: str, scores: ndarray, pipelines: List)` | Parallel execution for multiple targets |
| `resolve_path(path_str)` | Robust path resolution handling various formats | `path_str: str` | `Union[Path, str]` | None |
| `check_for_existing_optuna_databases(output_folder)` | Prevent conflicts from multiple pipeline runs | `output_folder: Path` | `None` | Exits with error if conflicts detected |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

### Core Pipeline Architecture

The EMUSES pipeline follows a modular stage-based architecture where each stage processes data and updates a shared context:

```python
# Pipeline initialization with reproducible random seed management
class EMUSESPipeline:
    def __init__(self, args):
        self.config = PipelineConfig(args)
        # Initialize master random seed for reproducibility
        master_seed = getattr(self.config, "random_state", 42)
        root_rng = default_rng(master_seed)
        
        # Generate component-specific seeds
        random_seeds = {
            "master_seed": master_seed,
            "umap_seed": root_rng.integers(0, 2**32),
            "clustering_seed": root_rng.integers(0, 2**32),
            "prediction_seed": root_rng.integers(0, 2**32),
            # ... additional seeds for different components
        }
        self.config.random_seeds = random_seeds
```

### Dataset Processing and Splitting

The pipeline supports multiple dataset types with intelligent format detection:

```python
def process_dataset(self, dataset_identifier, is_labelled=False):
    """
    Process datasets into input matrices supporting:
    - NIfTI neuroimaging files 
    - Image datasets (JPG, PNG)
    - MNIST/digits datasets
    - Spreadsheet data (CSV, Excel)
    - BIDS-formatted datasets
    """
    if str(dataset_identifier).lower() == "mnist":
        features, labels = load_and_preprocess_digits_dataset()
        input_matrix = features
        scores = labels if not is_labelled else None
        return input_matrix, "mnist", features[0].shape, scores
    
    # Handle other dataset types with format-specific processing
    # ...
```

### UMAP Stage with Nested Optimization

The UMAP stage performs sophisticated Bayesian optimization combining dimensionality reduction and clustering:

```python
def train_and_save_umap_optim_with_nested_clustering(
    input_matrix, output_folder, optim_dict, 
    n_trials=50, n_inner_trials=20, **kwargs
):
    """
    Nested optimization structure:
    - Outer loop: UMAP parameter optimization
    - Inner loop: HDBSCAN clustering optimization per UMAP embedding
    - Composite scoring: Combines UMAP and clustering metrics
    """
    def outer_objective(trial):
        # Sample UMAP parameters from optimization space
        umap_params = suggest_parameters(trial, optim_dict["param"]["umap"])
        umap_model = umap.UMAP(**umap_params, random_state=random_state)
        embeddings = umap_model.fit_transform(input_matrix)
        
        # Inner optimization for clustering on this embedding
        best_hdbscan_params, best_score, clusterer, labels = inner_optimize_hdbscan(
            embeddings, optim_dict, n_inner_trials=n_inner_trials
        )
        
        # Compute composite score from both UMAP and clustering metrics
        composite_score = calculate_composite_score(
            {"umap": umap_metrics, "hdbscan": clustering_metrics}, 
            optim_dict["metrics"]
        )
        return composite_score
```

### Prediction and Heatmap Generation

The heatmap stage implements advanced model selection with conditional feature engineering:

```python
def nested_optuna_cv(X, y, task="reg", n_trials=50, optim_dict=None, **kwargs):
    """
    Nested cross-validation with conditional hyperparameter optimization:
    - Feature engineering: Raw coordinates, PCA, kernel PCA, autoencoders
    - Model selection: Gaussian processes, random forests, elastic nets
    - Conditional parameters: Features determine available model parameters
    """
    def objective_factory(X_train, y_train, task, inner_cv, optim_dict):
        def objective(trial):
            # Sample from conditional parameter space
            params = suggest_parameters_conditional(trial, optim_dict)
            
            # Build feature extraction pipeline
            feature_union = build_feature_union(
                params["features"], pretrained_ae=pretrained_ae
            )
            
            # Build estimator with task-specific configuration  
            estimator = build_estimator(params["model"], task)
            
            # Create and evaluate pipeline
            pipeline = Pipeline([("feat", feature_union), ("est", estimator)])
            cv_scores = cross_val_score(pipeline, X_train, y_train, cv=inner_cv)
            return cv_scores.mean()
        
        return objective
```

### Advanced Feature Engineering

The pipeline supports multiple feature extraction methods with automatic selection:

```python
def build_feature_union(feature_params, pretrained_ae=None):
    """
    Conditional feature engineering based on optimization parameters:
    
    Parameters
    ----------
    feature_params : dict
        Feature configuration from Optuna trial
    pretrained_ae : object, optional
        Pretrained autoencoder for feature extraction
        
    Returns
    -------
    FeatureUnion
        Configured feature extraction pipeline
    """
    feature_type = feature_params["feat_type"]
    
    if feature_type == "raw":
        # Use raw UMAP coordinates
        return FeatureUnion([("raw", StandardScaler())])
    
    elif feature_type == "pca_gwd":
        # PCA on Gaussian weighted distances
        return FeatureUnion([
            ("pca_gwd", Pipeline([
                ("gwd", GaussianWeightedDistance(
                    sigma=feature_params["gwd_sigma"],
                    correlation_threshold=feature_params["corr_thr"]
                )),
                ("pca", PCA(n_components=feature_params["n_comp"]))
            ]))
        ])
    
    elif feature_type == "ae" and pretrained_ae is not None:
        # Autoencoder-based feature extraction
        return FeatureUnion([("ae", pretrained_ae)])
```

### Model I/O and Persistence

The framework uses a sophisticated model management system for reproducibility:

```python
class ModelIOManager:
    """
    Enhanced model persistence with metadata tracking:
    - Automatic versioning and tagging
    - Optuna study preservation  
    - Cross-validation score tracking
    - Configuration serialization
    """
    def save_model(self, model, model_name, model_type, **metadata):
        model_path = self.base_path / f"{model_name}.joblib"
        
        # Save model with joblib
        joblib.dump(model, model_path)
        
        # Save comprehensive metadata
        metadata_path = model_path.with_suffix('.json')
        full_metadata = {
            "model_name": model_name,
            "model_type": model_type,
            "timestamp": datetime.now().isoformat(),
            "optuna_study": metadata.get("optuna_study"),
            "cv_scores": metadata.get("cv_scores"),
            "config": metadata.get("config"),
            **metadata
        }
        save_json(metadata_path, full_metadata)
        
        return model_path
```

### Error Handling and Validation

The pipeline includes comprehensive error handling and database conflict prevention:

```python
def check_for_existing_optuna_databases(output_folder):
    """
    Prevent pipeline conflicts by detecting existing Optuna databases.
    This ensures clean runs and prevents study name collisions.
    """
    db_pattern = str(output_folder / "optuna_target_*.db")
    existing_dbs = glob.glob(db_pattern)
    
    if existing_dbs:
        print("ERROR: EXISTING OPTUNA DATABASE FILES DETECTED")
        print("This indicates previous pipeline runs in this directory.")
        print("Choose: different output directory, delete files, or backup.")
        sys.exit(1)
```

</details>
