# UMAP Stage

The UMAPStage performs dimensionality reduction using UMAP (Uniform Manifold Approximation and Projection) with integrated HDBSCAN clustering optimization. It transforms high-dimensional input data into low-dimensional embeddings while preserving local structure, and simultaneously optimizes clustering parameters using nested Bayesian optimization via Optuna.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function/Class | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `UMAPStage.__init__(config)` | Initialize UMAP stage with configuration | `config: PipelineConfig` | `UMAPStage` | None |
| `UMAPStage.run(context, progress_queue)` | Execute UMAP training and clustering | `context: dict, progress_queue: Queue` | `None` | Saves UMAP model, embeddings, cluster models to disk |
| `train_and_save_umap_optim_with_nested_clustering()` | Bayesian optimization for UMAP+HDBSCAN | `input_matrix: ndarray, output_folder: Path, optim_dict: dict, **kwargs` | `(umap_model, embeddings, model_paths...)` | Creates optimized models and artifacts |
| `load_umap_model(model_path)` | Load pre-trained UMAP model | `model_path: Path` | `(umap_model, metadata)` | None |
| `rescale_embedding(embeddings, preset_min, preset_max)` | Rescale embeddings to consistent range | `embeddings: ndarray, preset_min: ndarray, preset_max: ndarray` | `ndarray` | None |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Stage Initialization
The UMAP stage manages model artifacts and clustering results:

```python
def __init__(self, config):
    """
    Initialize UMAP stage with configuration and artifact tracking.
    
    Parameters
    ----------
    config : PipelineConfig
        Pipeline configuration containing UMAP parameters and paths
        
    Attributes
    ----------
    trained_umap : umap.UMAP
        Fitted UMAP model
    embeddings : ndarray
        Low-dimensional embeddings from UMAP
    best_clusterer : hdbscan.HDBSCAN  
        Optimized HDBSCAN clustering model
    cluster_labels : ndarray
        Cluster assignments for embeddings
    """
    super().__init__(config)
    
    # UMAP model and embeddings
    self.trained_umap = None
    self.embeddings = None
    self.test_embeddings = None
    
    # Clustering components
    self.best_clusterer = None
    self.cluster_labels = None
    
    # Scaling information for consistent transforms
    self.min_embeddings = None
    self.max_embeddings = None
```

## Nested Optimization Workflow
Executes UMAP training with integrated clustering optimization:

```python
def run(self, context, progress_queue=None):
    """
    Execute UMAP training with nested HDBSCAN optimization.
    
    Parameters
    ----------
    context : dict
        Shared pipeline context containing input data and random seeds
    progress_queue : Queue, optional
        Queue for progress reporting to parent process
        
    Notes
    -----
    Workflow:
    1. Load existing models if available, otherwise train new ones
    2. Use Bayesian optimization (Optuna) for UMAP hyperparameters
    3. For each UMAP trial, optimize HDBSCAN clustering parameters  
    4. Select best combination based on composite metric
    5. Transform all datasets using optimized UMAP model
    """
    # Get reproducible random seeds from context
    random_seeds = context.get("random_seeds", {})
    umap_seed = random_seeds.get("umap_seed", 42)
    clustering_seed = random_seeds.get("clustering_seed", 42)
    
    # Extract training data using standardized naming
    train_features = context.get("embedding_train_features")
    test_features = context.get("embedding_test_features")
    
    # Load optimization configuration
    optim_dict = self._load_optimization_config(context)
```

## Model Persistence and Loading
Implements robust model loading with fallback mechanisms:

```python
# Check for existing trained models
prefix = self.config.prefix if hasattr(self.config, "prefix") else ""
umap_model_file = self.config.output_folder / f"{prefix}best_umap_model.joblib"
embeddings_file = self.config.output_folder / f"{prefix}embeddings.npy"

if (umap_model_file.exists() and embeddings_file.exists() and 
    cluster_model_file.exists() and cluster_labels_file.exists()):
    
    # Load existing models using ModelIOManager for version tracking
    self.trained_umap, _ = load_umap_model(umap_model_file)
    self.embeddings = np.load(embeddings_file)
    self.best_clusterer, _ = load_hdbscan_model(
        cluster_model_file.parent, model_name="hdbscan_model"
    )
    self.cluster_labels = np.load(cluster_labels_file)
    
else:
    # Train new models with nested optimization
    (self.trained_umap, embeddings, umap_path, embeddings_path,
     best_clusterer, best_labels, cluster_model_path, 
     cluster_labels_path, input_matrix_path) = train_and_save_umap_optim_with_nested_clustering(
        input_matrix=train_features,
        output_folder=self.config.output_folder,
        optim_dict=optim_dict,
        n_trials=getattr(self.config, "umap_trials", 50),
        n_inner_trials=getattr(self.config, "hdbscan_trials", 20),
        random_state=umap_seed,
        clusterer_random_state=clustering_seed,
        # Reproducibility parameters
        approx_min_span_tree=getattr(self.config, "hdbscan_approx_min_span_tree", True),
        core_dist_n_jobs=getattr(self.config, "hdbscan_core_dist_n_jobs", -1),
    )
```

## Multi-Dataset Transformation
Handles embedding generation for different data splits with consistent scaling:

```python
# Process embedding data (unlabeled, used for UMAP training)
self.embeddings = rescale_embedding(
    self.embeddings,
    preset_min=self.min_embeddings,
    preset_max=self.max_embeddings,
)

# Transform test data if available  
if test_features is not None:
    self.test_embeddings = self.trained_umap.transform(test_features)
    self.test_embeddings = rescale_embedding(
        self.test_embeddings,
        preset_min=self.min_embeddings,  # Use same scaling as training
        preset_max=self.max_embeddings,
    )

# Transform prediction data (labeled, for downstream modeling)
prediction_train_features = context.get("prediction_train_features")
if prediction_train_features is not None:
    prediction_train_coords = self.trained_umap.transform(prediction_train_features)
    prediction_train_coords = rescale_embedding(
        prediction_train_coords,
        preset_min=self.min_embeddings,
        preset_max=self.max_embeddings,
    )
    context["prediction_train_coords"] = prediction_train_coords
```

## Context Updates
Updates shared context with standardized naming for downstream stages:

```python
# Update context with results using consistent naming convention
context.update({
    # Embedding data (unlabeled, for UMAP training)
    "embedding_train_coords": self.embeddings,
    "embedding_test_coords": self.test_embeddings,
    "embedding_train_umap_model": self.trained_umap,
    
    # Clustering results
    "embedding_train_clusterer": self.best_clusterer,
    "embedding_train_cluster_labels": self.cluster_labels,
    
    # Scaling information for consistent transformations
    "embedding_train_min_coords": self.min_embeddings,
    "embedding_train_max_coords": self.max_embeddings,
    
    # File paths for artifact tracking
    "cluster_model_path": self.cluster_model_path,
    "cluster_labels_path": self.cluster_labels_path,
})
```

## Bayesian Optimization Details
The nested optimization uses Optuna for efficient hyperparameter search:

```python
def objective(trial):
    """
    Optuna objective function for UMAP hyperparameter optimization.
    
    For each UMAP parameter combination:
    1. Train UMAP model with suggested parameters
    2. Generate embeddings
    3. Run inner optimization for HDBSCAN clustering
    4. Calculate composite score from UMAP and clustering metrics
    5. Return score for Optuna to optimize
    """
    # Sample UMAP parameters from optimization dictionary
    umap_params = suggest_parameters(trial, optim_dict["param"]["umap"])
    
    # Train UMAP with reproducible random state
    umap_model = umap.UMAP(**umap_params, random_state=umap_seed)
    embeddings = umap_model.fit_transform(input_matrix)
    
    # Evaluate UMAP quality metrics
    umap_metrics = evaluate_embedding_statistics(embeddings, optim_dict["metrics"]["umap"])
    
    # Inner optimization: find best HDBSCAN parameters for these embeddings
    best_hdbscan_params, best_hdbscan_score, best_clusterer, best_labels = inner_optimize_hdbscan(
        embeddings, optim_dict, n_inner_trials=n_inner_trials,
        random_state=clustering_seed
    )
    
    # Combine UMAP and clustering metrics into composite score
    composite_score = compute_composite_score(umap_metrics, best_hdbscan_score, weights)
    
    return composite_score
```

</details>
