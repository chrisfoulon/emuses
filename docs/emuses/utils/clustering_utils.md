# Clustering Utilities

The Clustering Utilities provide comprehensive functions for HDBSCAN clustering optimization, evaluation metrics, and integration with UMAP embeddings. These utilities handle clustering quality assessment, hyperparameter optimization via Optuna, model persistence, and provide both simple and advanced clustering workflows with robust metric evaluation for the EMUSES pipeline.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `inner_optimize_hdbscan(embeddings, optim_dict, n_inner_trials, **kwargs)` | HDBSCAN hyperparameter optimization | `embeddings: ndarray, optim_dict: dict, n_inner_trials: int, **kwargs` | `(best_params, best_score, best_clusterer, best_labels, best_metrics)` | None |
| `evaluate_clustering_metrics(clusterer, embeddings, metrics_config)` | Evaluate clustering quality | `clusterer: HDBSCAN, embeddings: ndarray, metrics_config: dict` | `dict` | None |
| `compute_cluster_persistence(clusterer, normalized, max_value)` | Compute cluster persistence metric | `clusterer: HDBSCAN, normalized: bool, max_value: float` | `float` | None |
| `compute_noise_ratio(labels, normalized)` | Compute noise ratio metric | `labels: ndarray, normalized: bool` | `float` | None |
| `compute_dbcv(embeddings, labels, normalized)` | Compute DBCV clustering validity index | `embeddings: ndarray, labels: ndarray, normalized: bool` | `float` | None |
| `load_hdbscan_model(base_path, model_name)` | Load HDBSCAN model with fallback | `base_path: Path, model_name: str` | `(hdbscan_model, filepath)` | None |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## HDBSCAN Hyperparameter Optimization

The `inner_optimize_hdbscan` function provides comprehensive hyperparameter optimization for HDBSCAN clustering:

```python
def inner_optimize_hdbscan(
    embeddings,
    optim_dict,
    n_inner_trials=20,
    n_jobs=1,
    random_state=42,
    approx_min_span_tree=True,
    core_dist_n_jobs=-1,
):
    """
    Optimize HDBSCAN hyperparameters using Optuna with comprehensive metrics.
    
    Performs Bayesian optimization to find optimal HDBSCAN parameters by evaluating
    multiple clustering quality metrics including cluster persistence, noise ratio,
    and DBCV (Density-Based Cluster Validation) index.
    
    Parameters
    ----------
    embeddings : ndarray, shape (n_samples, n_dims)
        UMAP embeddings to cluster
    optim_dict : dict
        Optimization dictionary with parameter ranges and metric configurations:
        {
            "param": {
                "hdbscan": {
                    "min_cluster_size": {"low": 5, "high": 50},
                    "min_samples": {"low": 1, "high": 10},
                    "cluster_selection_epsilon": {"low": 0.0, "high": 1.0},
                    "max_cluster_size": {"low": 100, "high": 1000},
                    "cluster_selection_method": {"choices": ["eom", "leaf"]},
                    "metric": {"choices": ["euclidean", "manhattan", "cosine"]}
                }
            },
            "metrics": {
                "hdbscan": {
                    "cluster_persistence": {"weight": 2.0},
                    "noise_ratio": {"weight": 1.0, "target": 0.1, "epsilon": 0.05},
                    "dbcv": {"weight": 1.5}
                }
            }
        }
    n_inner_trials : int, default=20
        Number of optimization trials to run
    n_jobs : int, default=1
        Number of parallel jobs for Optuna optimization
    random_state : int, default=42
        Random seed for reproducible clustering
    approx_min_span_tree : bool, default=True
        Use approximate minimum spanning tree (faster but less reproducible)
    core_dist_n_jobs : int, default=-1
        Number of parallel jobs for core distance computation
    
    Returns
    -------
    tuple
        (best_params, best_score, best_clusterer, best_labels, best_metrics)
        Best hyperparameters, composite score, fitted clusterer, cluster labels,
        and detailed metrics dictionary
    """
    print(f"Starting HDBSCAN optimization with {n_inner_trials} trials...")
    
    # Extract HDBSCAN parameter configuration
    hdbscan_param_dict = optim_dict["param"]["hdbscan"]
    hdbscan_metrics_config = optim_dict["metrics"]["hdbscan"]
    
    # Initialize tracking variables
    best_score = -float("inf")
    best_params = None
    best_clusterer = None
    best_labels = None
    best_metrics = None
    
    def objective(trial):
        """Optuna objective function for HDBSCAN optimization."""
        nonlocal best_score, best_params, best_clusterer, best_labels, best_metrics
        
        # Suggest parameters based on configuration
        params = {}
        for param_name, param_config in hdbscan_param_dict.items():
            if "low" in param_config and "high" in param_config:
                if isinstance(param_config["low"], int):
                    params[param_name] = trial.suggest_int(
                        param_name, param_config["low"], param_config["high"]
                    )
                else:
                    params[param_name] = trial.suggest_float(
                        param_name, param_config["low"], param_config["high"]
                    )
            elif "choices" in param_config:
                params[param_name] = trial.suggest_categorical(
                    param_name, param_config["choices"]
                )
            elif "value" in param_config:
                params[param_name] = param_config["value"]
        
        print(f"  Trial {trial.number}: Testing HDBSCAN params: {params}")
        
        try:
            # Create and fit HDBSCAN clusterer
            clusterer = hdbscan.HDBSCAN(
                **params,
                # Reproducibility parameters
                cluster_selection_method=params.get("cluster_selection_method", "eom"),
                algorithm='best',  # Use best available algorithm
                core_dist_n_jobs=core_dist_n_jobs,
                # Set approximation for reproducibility vs. speed trade-off
                approx_min_span_tree=approx_min_span_tree,
                # Ensure consistent results
                random_state=random_state if random_state is not None else 42
            )
            
            # Fit the clusterer
            clusterer.fit(embeddings)
            labels = clusterer.labels_
            
            # Evaluate clustering metrics
            metrics = evaluate_clustering_metrics(
                clusterer, embeddings, hdbscan_metrics_config
            )
            
            # Compute composite score
            from emuses.tools.optim_utils import calculate_composite_score
            composite_score = calculate_composite_score(
                {"hdbscan": metrics}, {"hdbscan": hdbscan_metrics_config}
            )
            
            print(f"  Trial {trial.number}: Metrics: {metrics}")
            print(f"  Trial {trial.number}: Composite score: {composite_score:.4f}")
            
            # Update best results if improved
            if composite_score > best_score:
                best_score = composite_score
                best_params = params.copy()
                best_clusterer = clusterer
                best_labels = labels.copy()
                best_metrics = metrics.copy()
                
                print(f"  Trial {trial.number}: New best score: {best_score:.4f}")
            
            return composite_score
            
        except Exception as e:
            print(f"  Trial {trial.number}: Clustering failed: {e}")
            return -1.0
    
    # Create and run Optuna study
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=random_state)
    )
    
    if n_jobs > 1:
        study.optimize(objective, n_trials=n_inner_trials, n_jobs=n_jobs)
    else:
        study.optimize(objective, n_trials=n_inner_trials)
    
    print(f"HDBSCAN optimization completed. Best score: {best_score:.4f}")
    print(f"Best parameters: {best_params}")
    
    return best_params, best_score, best_clusterer, best_labels, best_metrics
```

## Clustering Quality Metrics

The system provides comprehensive clustering quality assessment with multiple metrics:

```python
def evaluate_clustering_metrics(clusterer, embeddings, metrics_config=None):
    """
    Evaluate clustering quality using multiple metrics.
    
    Computes various clustering quality metrics including cluster persistence,
    noise ratio, DBCV index, and silhouette score. Metrics are normalized
    and can be weighted according to the provided configuration.
    
    Parameters
    ----------
    clusterer : hdbscan.HDBSCAN
        Fitted HDBSCAN clusterer object
    embeddings : ndarray, shape (n_samples, n_dims)
        Data used for clustering
    metrics_config : dict, optional
        Configuration specifying which metrics to compute:
        {
            "cluster_persistence": {"weight": 2.0},
            "noise_ratio": {"weight": 1.0, "target": 0.1, "epsilon": 0.05},
            "dbcv": {"weight": 1.5},
            "silhouette": {"weight": 1.0}
        }
    
    Returns
    -------
    dict
        Dictionary containing computed clustering metrics
    """
    if metrics_config is None:
        # Default configuration evaluates all available metrics
        metrics_config = {
            "cluster_persistence": {"weight": 1.0},
            "noise_ratio": {"weight": 1.0},
            "dbcv": {"weight": 1.0},
            "silhouette": {"weight": 1.0}
        }
    
    metrics = {}
    labels = clusterer.labels_
    
    # Cluster persistence - measures stability of cluster hierarchy
    if "cluster_persistence" in metrics_config:
        persistence = compute_cluster_persistence(clusterer, normalized=True)
        metrics["cluster_persistence"] = persistence
        print(f"    Cluster persistence: {persistence:.4f}")
    
    # Noise ratio - fraction of points labeled as noise
    if "noise_ratio" in metrics_config:
        noise_ratio = compute_noise_ratio(labels, normalized=True)
        metrics["noise_ratio"] = noise_ratio
        print(f"    Noise ratio (normalized): {noise_ratio:.4f}")
    
    # DBCV - Density-Based Cluster Validation index
    if "dbcv" in metrics_config:
        dbcv_score = compute_dbcv(embeddings, labels, normalized=True)
        metrics["dbcv"] = dbcv_score
        print(f"    DBCV score (normalized): {dbcv_score:.4f}")
    
    # Silhouette score - only if we have valid clusters
    if "silhouette" in metrics_config:
        unique_labels = np.unique(labels)
        valid_clusters = unique_labels[unique_labels != -1]
        
        if len(valid_clusters) >= 2:
            try:
                # Filter out noise points for silhouette calculation
                mask = labels != -1
                if np.sum(mask) > 1:
                    silhouette = silhouette_score(embeddings[mask], labels[mask])
                    # Normalize silhouette score from [-1, 1] to [0, 1]
                    silhouette_normalized = (silhouette + 1) / 2
                    metrics["silhouette"] = silhouette_normalized
                    print(f"    Silhouette score (normalized): {silhouette_normalized:.4f}")
                else:
                    metrics["silhouette"] = 0.0
            except Exception as e:
                print(f"    Silhouette computation failed: {e}")
                metrics["silhouette"] = 0.0
        else:
            metrics["silhouette"] = 0.0
            print(f"    Silhouette score: 0.0 (insufficient clusters)")
    
    # Cluster count and size statistics
    unique_labels = np.unique(labels)
    n_clusters = len(unique_labels[unique_labels != -1])
    n_noise = np.sum(labels == -1)
    
    metrics["n_clusters"] = n_clusters
    metrics["n_noise"] = n_noise
    metrics["cluster_sizes"] = [np.sum(labels == label) for label in unique_labels if label != -1]
    
    print(f"    Number of clusters: {n_clusters}")
    print(f"    Number of noise points: {n_noise}")
    
    return metrics

def compute_cluster_persistence(clusterer, normalized=True, max_value=1.0):
    """
    Compute the mean persistence of clusters from an HDBSCAN clusterer.
    
    Cluster persistence measures the stability of clusters in the hierarchy.
    Higher persistence indicates more stable, well-separated clusters.
    
    Parameters
    ----------
    clusterer : hdbscan.HDBSCAN
        Fitted HDBSCAN clusterer object
    normalized : bool, default=True
        Whether to normalize the persistence value to [0, 1]
    max_value : float, default=1.0
        Maximum expected persistence value for normalization
    
    Returns
    -------
    float
        Cluster persistence metric (0 if all points are noise)
    """
    # Check if labels are available and all points are noise
    if hasattr(clusterer, "labels_") and np.all(clusterer.labels_ == -1):
        return 0.0
    
    # Compute the raw persistence
    if (hasattr(clusterer, "cluster_persistence_") and 
        len(clusterer.cluster_persistence_) > 0):
        persistence = np.mean(clusterer.cluster_persistence_)
    else:
        persistence = 0.0
    
    if not normalized:
        return persistence
    
    # Normalize to [0, 1] range
    return min(1.0, persistence / max_value)

def compute_noise_ratio(labels, normalized=True):
    """
    Compute the noise ratio of the clustering.
    
    The noise ratio is the fraction of points labeled as noise (-1).
    Lower noise ratios generally indicate better clustering quality.
    
    Parameters
    ----------
    labels : ndarray, shape (n_samples,)
        Cluster labels (-1 indicates noise)
    normalized : bool, default=True
        If True, returns 1 - noise_ratio (so higher is better)
    
    Returns
    -------
    float
        Noise ratio or normalized noise score
    """
    noise_points = np.sum(labels == -1)
    total_points = len(labels)
    raw_ratio = noise_points / total_points if total_points > 0 else 0.0
    
    if not normalized:
        return raw_ratio
    
    # Return inverted ratio so higher values are better
    return 1 - raw_ratio

def compute_dbcv(embeddings, labels, normalized=True):
    """
    Compute the DBCV (Density-Based Cluster Validation) index.
    
    DBCV is a clustering validation metric designed specifically for
    density-based clustering algorithms like HDBSCAN. It measures
    the relative density within clusters vs. between clusters.
    
    Parameters
    ----------
    embeddings : ndarray, shape (n_samples, n_features)
        The data used for clustering
    labels : ndarray, shape (n_samples,)
        Cluster labels obtained from HDBSCAN
    normalized : bool, default=True
        If True, transforms score from [-1,1] to [0,1] range
    
    Returns
    -------
    float
        DBCV index (normalized if requested)
    """
    try:
        embeddings = np.asarray(embeddings, dtype=np.float64)
        dbcv_score = validity.validity_index(embeddings, labels)
        
        if normalized:
            # Transform from [-1, 1] to [0, 1] range
            return (dbcv_score + 1) / 2
        
        return dbcv_score
        
    except Exception as e:
        print(f"DBCV computation failed: {e}")
        return 0.0 if normalized else -1.0
```

## Advanced Clustering Analysis

The utilities provide sophisticated clustering analysis capabilities:

```python
def analyze_cluster_hierarchy(clusterer, embeddings, output_folder=None):
    """
    Analyze the cluster hierarchy and generate detailed statistics.
    
    Provides comprehensive analysis of the HDBSCAN cluster hierarchy
    including cluster birth/death times, stability, and condensed tree
    information.
    
    Parameters
    ----------
    clusterer : hdbscan.HDBSCAN
        Fitted HDBSCAN clusterer object
    embeddings : ndarray, shape (n_samples, n_features)
        Data used for clustering
    output_folder : Path, optional
        Directory to save analysis plots and results
    
    Returns
    -------
    dict
        Comprehensive hierarchy analysis results
    """
    analysis = {}
    
    # Basic cluster statistics
    labels = clusterer.labels_
    unique_labels = np.unique(labels)
    valid_clusters = unique_labels[unique_labels != -1]
    
    analysis["n_clusters"] = len(valid_clusters)
    analysis["n_noise"] = np.sum(labels == -1)
    analysis["noise_fraction"] = analysis["n_noise"] / len(labels)
    
    # Cluster size statistics
    cluster_sizes = []
    for cluster_id in valid_clusters:
        size = np.sum(labels == cluster_id)
        cluster_sizes.append(size)
    
    if cluster_sizes:
        analysis["cluster_sizes"] = {
            "sizes": cluster_sizes,
            "mean": np.mean(cluster_sizes),
            "std": np.std(cluster_sizes),
            "min": np.min(cluster_sizes),
            "max": np.max(cluster_sizes),
            "median": np.median(cluster_sizes)
        }
    
    # Cluster persistence and stability
    if hasattr(clusterer, "cluster_persistence_"):
        analysis["cluster_persistence"] = {
            "values": list(clusterer.cluster_persistence_),
            "mean": np.mean(clusterer.cluster_persistence_),
            "std": np.std(clusterer.cluster_persistence_),
            "min": np.min(clusterer.cluster_persistence_),
            "max": np.max(clusterer.cluster_persistence_)
        }
    
    # Outlier scores
    if hasattr(clusterer, "outlier_scores_"):
        outlier_stats = {
            "mean": np.mean(clusterer.outlier_scores_),
            "std": np.std(clusterer.outlier_scores_),
            "min": np.min(clusterer.outlier_scores_),
            "max": np.max(clusterer.outlier_scores_),
            "median": np.median(clusterer.outlier_scores_)
        }
        analysis["outlier_scores"] = outlier_stats
    
    # Condensed tree statistics
    if hasattr(clusterer, "condensed_tree_"):
        tree = clusterer.condensed_tree_
        analysis["condensed_tree"] = {
            "n_nodes": len(tree),
            "max_lambda": np.max(tree['lambda_val']) if len(tree) > 0 else 0,
            "min_lambda": np.min(tree['lambda_val']) if len(tree) > 0 else 0
        }
    
    # Generate visualizations if output folder provided
    if output_folder is not None:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
        
        # Plot cluster hierarchy
        try:
            import matplotlib.pyplot as plt
            from emuses.tools.visualisation import plot_clustering_with_hierarchy
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            
            # Scatter plot of clusters
            scatter = axes[0, 0].scatter(
                embeddings[:, 0], embeddings[:, 1], 
                c=labels, cmap='viridis', s=20, alpha=0.6
            )
            axes[0, 0].set_title('Cluster Assignment')
            plt.colorbar(scatter, ax=axes[0, 0])
            
            # Outlier scores if available
            if hasattr(clusterer, "outlier_scores_"):
                scatter = axes[0, 1].scatter(
                    embeddings[:, 0], embeddings[:, 1],
                    c=clusterer.outlier_scores_, cmap='plasma', s=20, alpha=0.6
                )
                axes[0, 1].set_title('Outlier Scores')
                plt.colorbar(scatter, ax=axes[0, 1])
            
            # Cluster size histogram
            if cluster_sizes:
                axes[1, 0].hist(cluster_sizes, bins=20, alpha=0.7, edgecolor='black')
                axes[1, 0].set_title('Cluster Size Distribution')
                axes[1, 0].set_xlabel('Cluster Size')
                axes[1, 0].set_ylabel('Frequency')
            
            # Persistence histogram if available
            if hasattr(clusterer, "cluster_persistence_"):
                axes[1, 1].hist(clusterer.cluster_persistence_, bins=20, 
                              alpha=0.7, edgecolor='black')
                axes[1, 1].set_title('Cluster Persistence Distribution')
                axes[1, 1].set_xlabel('Persistence')
                axes[1, 1].set_ylabel('Frequency')
            
            plt.tight_layout()
            plt.savefig(output_folder / "cluster_analysis.png", dpi=300, bbox_inches='tight')
            plt.close()
            
        except Exception as e:
            print(f"Failed to generate cluster analysis plots: {e}")
    
    return analysis

def compare_clustering_parameters(embeddings, param_grid, output_folder=None):
    """
    Compare clustering results across different parameter combinations.
    
    Performs systematic comparison of HDBSCAN parameters to understand
    the stability and sensitivity of clustering results.
    
    Parameters
    ----------
    embeddings : ndarray, shape (n_samples, n_features)
        Data to cluster
    param_grid : dict
        Parameter grid for comparison:
        {
            "min_cluster_size": [5, 10, 20, 50],
            "min_samples": [1, 3, 5],
            "cluster_selection_epsilon": [0.0, 0.1, 0.2]
        }
    output_folder : Path, optional
        Directory to save comparison results
    
    Returns
    -------
    pd.DataFrame
        Comparison results with metrics for each parameter combination
    """
    import pandas as pd
    from itertools import product
    
    # Generate all parameter combinations
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    param_combinations = list(product(*param_values))
    
    results = []
    
    print(f"Comparing {len(param_combinations)} parameter combinations...")
    
    for i, params in enumerate(param_combinations):
        param_dict = dict(zip(param_names, params))
        print(f"  Testing combination {i+1}/{len(param_combinations)}: {param_dict}")
        
        try:
            # Create and fit clusterer
            clusterer = hdbscan.HDBSCAN(**param_dict, random_state=42)
            clusterer.fit(embeddings)
            
            # Evaluate metrics
            metrics = evaluate_clustering_metrics(clusterer, embeddings)
            
            # Combine parameters and metrics
            result = {**param_dict, **metrics}
            results.append(result)
            
        except Exception as e:
            print(f"    Failed: {e}")
            result = {**param_dict, "error": str(e)}
            results.append(result)
    
    # Convert to DataFrame for analysis
    df_results = pd.DataFrame(results)
    
    # Save results if output folder provided
    if output_folder is not None:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
        df_results.to_csv(output_folder / "parameter_comparison.csv", index=False)
        
        # Generate comparison plots
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            # Heatmap of key metrics
            numeric_cols = df_results.select_dtypes(include=[np.number]).columns
            metric_cols = [col for col in numeric_cols if col not in param_names]
            
            if len(metric_cols) > 0:
                fig, axes = plt.subplots(2, 2, figsize=(15, 12))
                axes = axes.ravel()
                
                for i, metric in enumerate(metric_cols[:4]):
                    if i < len(axes):
                        pivot_data = df_results.pivot_table(
                            values=metric, 
                            index=param_names[0] if len(param_names) > 0 else 'min_cluster_size',
                            columns=param_names[1] if len(param_names) > 1 else 'min_samples',
                            aggfunc='mean'
                        )
                        
                        sns.heatmap(pivot_data, annot=True, fmt='.3f', 
                                  cmap='viridis', ax=axes[i])
                        axes[i].set_title(f'{metric.replace("_", " ").title()}')
                
                plt.tight_layout()
                plt.savefig(output_folder / "parameter_heatmaps.png", 
                          dpi=300, bbox_inches='tight')
                plt.close()
                
        except Exception as e:
            print(f"Failed to generate comparison plots: {e}")
    
    return df_results
```

## Model Loading and Persistence

The clustering utilities provide robust model loading with fallback mechanisms:

```python
def load_hdbscan_model(base_path, model_name="hdbscan_model", prefix=""):
    """
    Load HDBSCAN model with automatic fallback to compatible versions.
    
    Attempts to load HDBSCAN models using multiple strategies:
    1. New ModelIOManager system
    2. Legacy joblib files with version matching
    3. Fallback to any compatible joblib file
    
    Parameters
    ----------
    base_path : str or Path
        Directory containing HDBSCAN model files
    model_name : str, default="hdbscan_model"
        Base name for the model file
    prefix : str, optional
        File prefix for model identification
    
    Returns
    -------
    tuple or (None, None)
        (loaded_hdbscan_model, filepath) if successful, (None, None) if failed
    """
    base_path = Path(base_path)
    
    # Try new ModelIOManager system first
    try:
        manager = ModelIOManager(base_path)
        full_model_name = f"{prefix}_{model_name}" if prefix else model_name
        
        artifact = manager.load_model(model_name=full_model_name, model_type="hdbscan")
        
        if artifact:
            print(f"Successfully loaded HDBSCAN model using ModelIOManager: {artifact.filepath}")
            return artifact.model, artifact.filepath
        else:
            print(f"No HDBSCAN model found with name: {full_model_name}")
            
    except Exception as e:
        print(f"Failed to load HDBSCAN model using new I/O system: {e}")

    # Fallback to legacy loading methods
    candidates = []
    
    if prefix:
        candidates.extend([
            f"{prefix}_{model_name}.joblib",
            f"{prefix}_hdbscan_model.joblib",
            f"{prefix}best_hdbscan_model.joblib"
        ])
    else:
        candidates.extend([
            f"{model_name}.joblib",
            "hdbscan_model.joblib",
            "best_hdbscan_model.joblib"
        ])
    
    # Try each candidate
    for filename in candidates:
        filepath = base_path / filename
        
        if filepath.exists():
            try:
                loaded_clusterer = joblib.load(filepath)
                print(f"Successfully loaded HDBSCAN model from: {filepath}")
                return loaded_clusterer, filepath
            except Exception as e:
                print(f"Failed to load HDBSCAN model from: {filepath}, due to: {e}")

    print(f"No compatible HDBSCAN model found in {base_path}")
    return None, None
```

**Key advantages:**
- **Comprehensive optimization**: Bayesian hyperparameter search with multiple metrics
- **Robust evaluation**: Multiple clustering quality metrics including DBCV and persistence
- **Hierarchy analysis**: Detailed analysis of cluster hierarchy and stability
- **Parameter comparison**: Systematic parameter sensitivity analysis
- **Flexible integration**: Seamless integration with UMAP optimization pipeline
- **Reproducible results**: Consistent random seeding and deterministic algorithms
- **Performance monitoring**: Detailed logging and metric tracking

</details>
