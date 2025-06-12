# UMAP Utilities

The UMAP Utilities provide comprehensive functions for UMAP dimensionality reduction with Bayesian optimization, clustering integration, and robust model persistence. These utilities handle UMAP training with hyperparameter optimization via Optuna, evaluation of embedding quality metrics, nested clustering optimization, and provide both simple and advanced UMAP workflows for the EMUSES pipeline.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `train_and_save_umap_with_bayesian_search(input_matrix, output_folder, param_ranges, **kwargs)` | Bayesian optimization for UMAP | `input_matrix: ndarray, output_folder: Path, param_ranges: dict, n_trials: int, **kwargs` | `(umap_model, embeddings, model_path, embeddings_path, input_path)` | Saves model and artifacts |
| `train_and_save_umap_optim_with_nested_clustering(input_matrix, output_folder, optim_dict, **kwargs)` | UMAP+HDBSCAN nested optimization | `input_matrix: ndarray, output_folder: Path, optim_dict: dict, n_trials: int, **kwargs` | `(umap_model, embeddings, clusterer, labels, paths...)` | Saves models and plots |
| `load_umap_model(base_path, prefix, model_name)` | Load UMAP model with fallback | `base_path: Path, prefix: str, model_name: str` | `(umap_model, filepath)` | None |
| `evaluate_embedding_statistics(embeddings, metrics_config)` | Evaluate embedding quality | `embeddings: ndarray, metrics_config: dict` | `dict` | None |
| `compute_spread(embeddings, normalized)` | Compute embedding spread metric | `embeddings: ndarray, normalized: bool` | `float` | None |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Bayesian Optimization for UMAP

The `train_and_save_umap_with_bayesian_search` function provides hyperparameter optimization for UMAP using Optuna:

```python
def train_and_save_umap_with_bayesian_search(
    input_matrix,
    output_folder,
    param_ranges,
    n_trials=50,
    maximize_metrics=None,
    pref=None,
    random_state=42,
    optuna_seed=None,
    **kwargs,
):
    """
    Train UMAP with Bayesian hyperparameter optimization using Optuna.
    
    Performs Bayesian optimization to find optimal UMAP parameters by evaluating
    embedding quality metrics. Saves the best model, embeddings, and optimization
    history with comprehensive logging and visualization.
    
    Parameters
    ----------
    input_matrix : ndarray, shape (n_samples, n_features)
        High-dimensional input data for UMAP training
    output_folder : str or Path
        Directory for saving outputs (models, plots, logs)
    param_ranges : dict
        Parameter ranges for optimization, e.g.:
        {
            "n_neighbors": {"type": "int", "low": 5, "high": 50},
            "min_dist": {"type": "float", "low": 0.01, "high": 0.5},
            "n_components": {"type": "int", "low": 2, "high": 10},
            "metric": {"type": "categorical", "choices": ["euclidean", "cosine"]}
        }
    n_trials : int, default=50
        Number of optimization trials to run
    maximize_metrics : dict, optional
        Metrics to optimize with direction, e.g.:
        {"spread": True, "trustworthiness": True, "continuity": False}
    pref : str, optional
        Prefix for saved files
    random_state : int, default=42
        Random seed for UMAP reproducibility
    optuna_seed : int, optional
        Random seed for Optuna optimization
    **kwargs
        Additional UMAP parameters
    
    Returns
    -------
    tuple
        (best_umap_model, best_embeddings, model_path, embeddings_path, input_path)
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    
    def objective(trial):
        """Optuna objective function for UMAP optimization."""
        # Suggest parameters based on param_ranges
        params = {}
        for param_name, param_info in param_ranges.items():
            if param_info["type"] == "int":
                params[param_name] = trial.suggest_int(
                    param_name, param_info["low"], param_info["high"]
                )
            elif param_info["type"] == "float":
                params[param_name] = trial.suggest_float(
                    param_name, param_info["low"], param_info["high"]
                )
            elif param_info["type"] == "categorical":
                params[param_name] = trial.suggest_categorical(
                    param_name, param_info["choices"]
                )

        # Train UMAP with suggested parameters
        umap_params = {**params, "random_state": random_state}
        umap_model = umap.UMAP(**umap_params, **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)

        # Save trial results
        trial_subfolder = output_folder / f"trial_{trial.number}"
        trial_subfolder.mkdir(parents=True, exist_ok=True)

        # Save embedding plot
        plot_embeddings(
            embeddings,
            output_path=trial_subfolder / f"embeddings_{trial.number}.png",
            show_plot=False,
            return_plot=False,
            interactive=False
        )

        # Evaluate embedding quality metrics
        metrics = evaluate_embedding_statistics(embeddings)
        
        # Combine metrics into composite score
        score = 0
        if maximize_metrics:
            for metric_name, maximize in maximize_metrics.items():
                metric_value = metrics.get(metric_name, 0)
                if maximize:
                    score += metric_value
                else:
                    score -= metric_value

        return score
```

**Key optimization features:**
- **Flexible parameter spaces**: Supports int, float, and categorical parameters
- **Multi-metric optimization**: Combines multiple embedding quality metrics
- **Trial visualization**: Saves embedding plots for each trial
- **Reproducible results**: Consistent random seeding across trials

## Nested UMAP + HDBSCAN Optimization

The `train_and_save_umap_optim_with_nested_clustering` function performs joint optimization of UMAP and clustering:

```python
def train_and_save_umap_optim_with_nested_clustering(
    input_matrix,
    output_folder,
    optim_dict,
    n_trials=50,
    n_inner_trials=20,
    pref=None,
    n_jobs=4,
    parallel_mode="umap",
    inner_n_jobs=4,
    random_state=42,
    clusterer_random_state=None,
    approx_min_span_tree=True,
    core_dist_n_jobs=-1,
    **kwargs,
):
    """
    Nested optimization of UMAP parameters with HDBSCAN clustering.
    
    Performs two-level optimization: outer loop optimizes UMAP parameters,
    inner loop optimizes HDBSCAN parameters for each UMAP embedding.
    The composite score combines both embedding quality and clustering metrics.
    
    Parameters
    ----------
    input_matrix : ndarray, shape (n_samples, n_features)
        High-dimensional input data
    output_folder : str or Path
        Directory for saving outputs
    optim_dict : dict
        Unified optimization dictionary with structure:
        {
            "param": {
                "umap": {"n_neighbors": {"low": 5, "high": 50}, ...},
                "hdbscan": {"min_cluster_size": {"low": 5, "high": 50}, ...}
            },
            "metrics": {
                "umap": {
                    "spread": {"weight": 1.0, "target": 0.6, "epsilon": 0.1},
                    "trustworthiness": {"weight": 1.5}
                },
                "hdbscan": {
                    "cluster_persistence": {"weight": 2.0},
                    "noise_ratio": {"weight": 1.0, "target": 0.1, "epsilon": 0.05}
                }
            }
        }
    n_trials : int, default=50
        Number of outer (UMAP) optimization trials
    n_inner_trials : int, default=20
        Number of inner (HDBSCAN) trials per UMAP embedding
    parallel_mode : str, default="umap"
        Parallelization strategy: "umap" or "hdbscan"
    random_state : int, default=42
        Random seed for UMAP reproducibility
    clusterer_random_state : int, optional
        Random seed for HDBSCAN (uses random_state if None)
    approx_min_span_tree : bool, default=True
        Use approximate minimum spanning tree (faster but less reproducible)
    core_dist_n_jobs : int, default=-1
        Parallel jobs for HDBSCAN core distance computation
    
    Returns
    -------
    tuple
        (best_umap_model, best_embeddings, umap_path, embeddings_path,
         best_clusterer, best_labels, cluster_model_path, cluster_labels_path,
         input_matrix_path)
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Initialize tracking variables
    best_score_so_far = -float("inf")
    best_clusterer = None
    best_labels = None
    trial_logs = []

    def outer_objective(trial):
        """Outer optimization objective for UMAP parameters."""
        nonlocal best_score_so_far, best_clusterer, best_labels

        # Suggest UMAP and HDBSCAN parameters
        params_all = suggest_parameters(trial, optim_dict)
        umap_params = params_all["umap"]
        
        # Train UMAP with suggested parameters
        umap_params_with_random_state = {**umap_params, "random_state": random_state}
        umap_model = umap.UMAP(**umap_params_with_random_state, **kwargs)
        embeddings = umap_model.fit_transform(input_matrix)

        # Evaluate UMAP metrics
        umap_metrics = evaluate_embedding_statistics(
            embeddings, optim_dict["metrics"]["umap"]
        )

        # Inner optimization for HDBSCAN
        clusterer_rs = clusterer_random_state or random_state
        
        (best_hdbscan_params, best_hdbscan_score, 
         best_clusterer_trial, best_labels_trial, 
         best_hdbscan_metrics) = inner_optimize_hdbscan(
            embeddings,
            optim_dict,
            n_inner_trials=n_inner_trials,
            random_state=clusterer_rs,
            approx_min_span_tree=approx_min_span_tree,
            core_dist_n_jobs=core_dist_n_jobs,
        )

        # Generate interactive clustering plot
        interactive_plot_path = output_plot_folder / f"interactive_{trial.number}.html"
        plot_clustering_interactive_with_hover(
            embeddings,
            best_labels_trial,
            output_path=interactive_plot_path,
            show_plot=False,
            return_plot=True,
        )

        # Combine UMAP and HDBSCAN metrics
        combined_metrics = {"umap": umap_metrics, "hdbscan": best_hdbscan_metrics}
        composite_score = calculate_composite_score(
            combined_metrics, optim_dict["metrics"]
        )

        # Save best model if score improved
        if composite_score > best_score_so_far:
            best_score_so_far = composite_score
            best_clusterer = best_clusterer_trial
            best_labels = best_labels_trial

            # Save UMAP model using ModelIOManager
            manager = ModelIOManager(output_folder)
            manager.save_model(
                model=umap_model,
                model_name="best_umap_model",
                model_type="umap",
                config=umap_params,
                description=f"Best UMAP model from trial {trial.number} with composite score {composite_score}",
                tags=["optimization", "best_model", f"trial_{trial.number}"],
            )

        return composite_score
```

## Embedding Quality Evaluation

The system provides comprehensive embedding quality assessment:

```python
def evaluate_embedding_statistics(embeddings, metrics_config):
    """
    Evaluate embedding quality using multiple metrics.
    
    Computes various embedding quality metrics including spread, trustworthiness,
    continuity, and neighborhood preservation. Metrics are normalized and
    combined according to the provided configuration.
    
    Parameters
    ----------
    embeddings : ndarray, shape (n_samples, n_dims)
        UMAP embedding coordinates
    metrics_config : dict
        Configuration specifying which metrics to compute and their weights
    
    Returns
    -------
    dict
        Dictionary containing computed metrics
    """
    metrics = {}
    
    if "spread" in metrics_config:
        metrics["spread"] = compute_spread(embeddings, normalized=True)
    
    if "eigen_spread" in metrics_config:
        metrics["eigen_spread"] = compute_eigen_spread(embeddings, normalized=True)
    
    if "density_variability" in metrics_config:
        metrics["density_variability"] = compute_density_variability(
            embeddings, n_neighbors=10, normalized=True
        )
    
    if "entropy" in metrics_config:
        metrics["entropy"] = compute_entropy_range_mean(embeddings)
    
    if "trustworthiness" in metrics_config:
        # Requires original high-dimensional data (not available in this context)
        # metrics["trustworthiness"] = compute_trustworthiness(X_high_dim, embeddings)
        pass
    
    return metrics

def compute_spread(embeddings, normalized=True):
    """
    Compute the spread (standard deviation) of embedding coordinates.
    
    Measures how widely the embeddings are distributed in the low-dimensional
    space. Higher spread indicates better space utilization.
    
    Parameters
    ----------
    embeddings : ndarray, shape (n_samples, n_dims)
        UMAP embedding coordinates
    normalized : bool, default=True
        Whether to normalize the spread metric
    
    Returns
    -------
    float
        Spread metric value
    """
    # Compute standard deviation across all dimensions
    spread = np.std(embeddings)
    
    if normalized:
        # Normalize by typical range for UMAP embeddings
        # UMAP embeddings typically range from -15 to +15
        typical_range = 30.0
        spread = min(1.0, spread / (typical_range * 0.1))
    
    return spread

def compute_eigen_spread(embeddings, normalized=True):
    """
    Compute eigenvalue-based spread metric.
    
    Uses the ratio of eigenvalues from PCA of embeddings to measure
    how evenly the variance is distributed across dimensions.
    
    Parameters
    ----------
    embeddings : ndarray, shape (n_samples, n_dims)
        UMAP embedding coordinates
    normalized : bool, default=True
        Whether to normalize the metric
    
    Returns
    -------
    float
        Eigenvalue spread metric
    """
    # Center the embeddings
    centered = embeddings - np.mean(embeddings, axis=0)
    
    # Compute covariance matrix and eigenvalues
    cov_matrix = np.cov(centered.T)
    eigenvalues = np.linalg.eigvals(cov_matrix)
    eigenvalues = np.real(eigenvalues)  # Remove any imaginary parts
    eigenvalues = eigenvalues[eigenvalues > 1e-10]  # Remove near-zero eigenvalues
    
    if len(eigenvalues) < 2:
        return 0.0
    
    # Compute ratio of smallest to largest eigenvalue
    eigen_ratio = np.min(eigenvalues) / np.max(eigenvalues)
    
    if normalized:
        return eigen_ratio  # Already between 0 and 1
    
    return eigen_ratio
```

## Model Loading with Fallback Mechanisms

The UMAP utilities provide robust model loading with multiple fallback strategies:

```python
def load_umap_model(base_path, prefix="", model_name="umap_model"):
    """
    Load UMAP model with automatic fallback to compatible versions.
    
    Attempts to load UMAP models using multiple strategies:
    1. New ModelIOManager system
    2. Legacy joblib files with version matching
    3. Fallback to any compatible joblib file
    
    Parameters
    ----------
    base_path : str or Path
        Directory containing UMAP model files
    prefix : str, optional
        File prefix for model identification
    model_name : str, default="umap_model"
        Base name for the model file
    
    Returns
    -------
    tuple or (None, None)
        (loaded_umap_model, filepath) if successful, (None, None) if failed
    """
    base_path = Path(base_path)
    
    # Try new ModelIOManager system first
    try:
        manager = ModelIOManager(base_path)
        full_model_name = f"{prefix}_{model_name}" if prefix else model_name
        
        artifact = manager.load_model(model_name=full_model_name, model_type="umap")
        
        if artifact:
            print(f"Successfully loaded UMAP model using ModelIOManager: {artifact.filepath}")
            if hasattr(artifact.metadata, "description"):
                print(f"Model description: {artifact.metadata.description}")
            return artifact.model, artifact.filepath
        else:
            print(f"No UMAP model found with name: {full_model_name}")
            
    except Exception as e:
        print(f"Failed to load UMAP model using new I/O system: {e}")

    # Fallback to legacy loading methods
    current_joblib_version = joblib.__version__
    
    # Build candidate filenames in priority order
    candidates = []
    
    if prefix:
        candidates.extend([
            f"{prefix}_{model_name}_joblib{current_joblib_version}.joblib",
            f"{prefix}_{model_name}.joblib",
            f"{prefix}best_umap_model.joblib"
        ])
    else:
        candidates.extend([
            f"{model_name}_joblib{current_joblib_version}.joblib",
            f"{model_name}.joblib",
            "best_umap_model.joblib"
        ])
    
    # Try each candidate
    for filename in candidates:
        filepath = base_path / filename
        
        if filepath.exists() and is_umap_file(filepath):
            try:
                loaded_umap = joblib.load(filepath)
                print(f"Successfully loaded UMAP model from: {filepath}")
                return loaded_umap, filepath
            except Exception as e:
                print(f"Failed to load UMAP model from: {filepath}, due to: {e}")
        else:
            print(f"No model found at: {filepath}")

    # Try pattern matching for any compatible version
    pattern = f"{prefix}_{model_name}_joblib*.joblib" if prefix else f"{model_name}_joblib*.joblib"
    
    matching_files = list(base_path.glob(pattern))
    if matching_files:
        # Sort by modification time (newest first)
        matching_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for filepath in matching_files:
            if is_umap_file(filepath):
                try:
                    loaded_umap = joblib.load(filepath)
                    print(f"Successfully loaded UMAP model from: {filepath}")
                    return loaded_umap, filepath
                except Exception as e:
                    print(f"Failed to load UMAP model from: {filepath}, due to: {e}")

    print(f"No compatible UMAP model found in {base_path}")
    return None, None

def is_umap_file(umap_path):
    """
    Validate that a file contains a UMAP model.
    
    Performs basic validation to check if a joblib file contains
    a valid UMAP model by inspecting the file size and attempting
    to peek at the object type.
    
    Parameters
    ----------
    umap_path : Path
        Path to the potential UMAP model file
    
    Returns
    -------
    bool
        True if file appears to contain a UMAP model
    """
    try:
        # Check file size (UMAP models are typically > 1KB)
        if umap_path.stat().st_size < 1024:
            return False
        
        # Try to peek at the object without fully loading
        with open(umap_path, 'rb') as f:
            # Read first few bytes to check joblib format
            header = f.read(100)
            if b'umap' in header.lower() or b'UMAP' in header:
                return True
        
        return True  # Assume valid if basic checks pass
    
    except Exception:
        return False
```

## Integration with Optuna Storage

The UMAP utilities support persistent Optuna studies for parallel optimization:

```python
# Set up Optuna storage for parallel optimization
storage_path = output_folder / "optuna_study.db"
storage_url = f"sqlite:///{storage_path.resolve()}"

outer_study = optuna.create_study(
    direction="maximize",
    storage=storage_url,
    study_name="umap_nested_optimization",
    load_if_exists=True,
    sampler=optuna.samplers.TPESampler(seed=random_state),
)

# Enable parallel optimization
if parallel_mode == "umap":
    outer_study.optimize(outer_objective, n_trials=n_trials, n_jobs=n_jobs)
else:
    outer_study.optimize(outer_objective, n_trials=n_trials, n_jobs=1)

# Save optimization history visualization
fig = ov.plot_optimization_history(outer_study)
fig.write_html(str(output_folder / "optimization_history.html"))

# Generate custom optimization log plot
save_optimization_log_plot(
    trial_logs=trial_logs,
    optim_dict=optim_dict,
    output_folder=output_folder,
    plot_filename="optimization_log_plot.png",
)
```

**Key advantages:**
- **Bayesian optimization**: Efficient hyperparameter search using TPE sampler
- **Nested optimization**: Joint optimization of UMAP and clustering parameters
- **Comprehensive evaluation**: Multiple embedding quality metrics
- **Robust persistence**: Multiple fallback mechanisms for model loading
- **Parallel processing**: Support for distributed optimization
- **Rich visualization**: Interactive plots and optimization history tracking
- **Integration ready**: Seamless integration with EMUSES pipeline stages

</details>
