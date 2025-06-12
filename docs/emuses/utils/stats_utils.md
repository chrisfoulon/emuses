# Statistics and Modeling Utilities

The Statistics and Modeling Utilities provide comprehensive functions for predictive modeling, statistical analysis, and model evaluation within the EMUSES pipeline. These utilities handle the enhanced prediction pipeline with nested cross-validation, Optuna hyperparameter optimization, feature engineering integration, and statistical testing for cluster analysis and correlation mapping.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `new_pipeline_test(embeddings, combined_input_matrix, scores_vectors_dict, output_folder, **kwargs)` | Enhanced prediction pipeline with nested CV | `embeddings: ndarray, combined_input_matrix: ndarray, scores_vectors_dict: dict, output_folder: Path, **kwargs` | `dict` | Saves models and results |
| `train_model(train_coords, train_scores, test_coords, test_scores, score_name, output_folder, **kwargs)` | Train single predictive model | `train_coords: ndarray, train_scores: ndarray, test_coords: ndarray, test_scores: ndarray, score_name: str, output_folder: Path, **kwargs` | `dict` | Saves model and plots |
| `create_cluster_representative_maps(array, discrete_embeddings, input_matrix, original_shape, test_name)` | Statistical cluster analysis | `array: ndarray, discrete_embeddings: ndarray, input_matrix: ndarray, original_shape: tuple, test_name: str` | `(stat_maps, pval_maps, effect_size_maps, centroids)` | None |
| `filter_nan_rows(coords, scores)` | Clean data by removing NaN values | `coords: ndarray, scores: ndarray` | `(coords_clean, scores_clean, mask)` | None |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Enhanced Prediction Pipeline

The `new_pipeline_test` function implements the core prediction pipeline with advanced feature engineering and optimization:

```python
def new_pipeline_test(
    embeddings,
    combined_input_matrix,
    scores_vectors_dict,
    output_folder,
    grid_size=100,
    dataset_type="image",
    cluster_labels=None,
    full_embeddings=None,
    test_embeddings=None,
    test_labels=None,
    sparse_threshold=500,
    run_parallel=True,
    n_jobs=-1,
    optuna_trials=50,
    model_selection=None,
    random_state=42,
    optuna_seed=None,
):
    """
    Enhanced prediction pipeline with nested cross-validation and feature engineering.
    
    This function implements the core EMUSES prediction workflow:
    1. Prepares multiple feature representations (Raw, GWD, PCA+GWD, KernelPCA+GWD)
    2. Uses Optuna to find optimal σ (sigma) parameter for GWD calculation
    3. Generates correlation heatmaps on discrete grid
    4. Trains multiple model types with hyperparameter optimization
    5. Evaluates models using nested cross-validation
    6. Compares performance across feature sets and models
    7. Provides comprehensive results summary
    
    Parameters
    ----------
    embeddings : ndarray, shape (n_samples, n_dims)
        UMAP embeddings for the labelled (training) data
    combined_input_matrix : ndarray, shape (n_samples, n_features)
        The original high-dimensional input data
    scores_vectors_dict : dict
        Dictionary mapping VOI (Variable of Interest) score tags to target vectors
        Format: {"score_name": array_of_values, ...}
    output_folder : str or Path
        Directory to save outputs (models, plots, results)
    grid_size : int, default=100
        Grid resolution for heatmap generation
    dataset_type : str, default="image"
        Type of input data ('image', 'tabular', etc.)
    cluster_labels : ndarray, optional
        Cluster labels from HDBSCAN clustering
    full_embeddings : ndarray, optional
        Full UMAP embeddings (if available)
    test_embeddings : ndarray, optional
        Test set UMAP embeddings for evaluation
    test_labels : ndarray, optional
        Test set labels (possibly multi-dimensional)
    sparse_threshold : int, default=500
        Threshold to switch to sparse GP model version
    run_parallel : bool, default=True
        Whether to train models in parallel
    n_jobs : int, default=-1
        Number of processes for parallel execution (-1 for all cores)
    optuna_trials : int, default=50
        Number of Optuna optimization trials per model
    model_selection : list, optional
        List of model types to train (default: all available)
    random_state : int, default=42
        Random seed for reproducibility
    optuna_seed : int, optional
        Random seed for Optuna optimization
    
    Returns
    -------
    dict
        Comprehensive results dictionary containing:
        - Feature sets and their statistics
        - Model performance metrics
        - Best performing model and feature set
        - Correlation heatmaps and grid coordinates
        - Sigma optimization results
    """
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting enhanced prediction pipeline in {output_folder}")
    print(f"Input shapes - Embeddings: {embeddings.shape}, Input matrix: {combined_input_matrix.shape}")
    
    # STEP 1: Handle multiple VOI vectors
    if len(scores_vectors_dict) > 1:
        print(f"Multiple VOI vectors found: {list(scores_vectors_dict.keys())}")
        # Use first VOI for demonstration (could be extended to handle multiple)
        key = sorted(scores_vectors_dict.keys())[0]
        VOI_vector = np.array(scores_vectors_dict[key])
    else:
        key = next(iter(scores_vectors_dict))
        VOI_vector = np.array(scores_vectors_dict[key])
    print(f"Using VOI_vector from key: {key}")

    # For normalization
    global_range = np.max(VOI_vector) - np.min(VOI_vector)

    # STEP 2: Optuna optimization for optimal sigma
    print("Starting Optuna optimization to find robust sigma for GWD calculation...")
    
    def objective(trial):
        """Optuna objective for sigma optimization with nested CV."""
        sigma = trial.suggest_float("sigma", 0.01, 2.0, log=True)
        
        # Create GWD transformer with suggested sigma
        gwd_transformer = GWD(sigma=sigma)
        gwd_features = gwd_transformer.fit_transform(embeddings)
        
        # Apply correlation filtering
        corr_filter = CorrFilter(thr=0.1)  # Low threshold for initial filtering
        filtered_features = corr_filter.fit_transform(gwd_features, VOI_vector)
        
        # Quick cross-validation score using simple model
        cv_scores = []
        kf = KFold(n_splits=3, shuffle=True, random_state=random_state)
        
        for train_idx, val_idx in kf.split(filtered_features):
            X_train, X_val = filtered_features[train_idx], filtered_features[val_idx]
            y_train, y_val = VOI_vector[train_idx], VOI_vector[val_idx]
            
            # Clean training data
            X_train_clean, y_train_clean, _ = filter_nan_rows(X_train, y_train)
            X_val_clean, y_val_clean, _ = filter_nan_rows(X_val, y_val)
            
            if len(y_train_clean) < 5 or len(y_val_clean) < 2:
                continue
            
            # Simple regression model for quick evaluation
            model = LinearRegression()
            model.fit(X_train_clean, y_train_clean)
            
            y_pred = model.predict(X_val_clean)
            score = r2_score(y_val_clean, y_pred)
            cv_scores.append(score)
        
        return np.mean(cv_scores) if cv_scores else -1.0

    # Run sigma optimization
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=optuna_seed or random_state)
    )
    study.optimize(objective, n_trials=20)  # Quick optimization for sigma
    
    best_sigma = study.best_params["sigma"]
    print(f"Optimal sigma found: {best_sigma:.4f} (score: {study.best_value:.4f})")
```

## Feature Set Generation and Optimization

The pipeline creates multiple sophisticated feature representations:

```python
# STEP 3: Generate comprehensive feature sets with optimal sigma
print("Generating comprehensive feature sets...")

# Raw coordinates (baseline)
features_1 = embeddings.copy()

# Gaussian-weighted distances with optimal sigma
gwd_transformer = GWD(sigma=best_sigma)
gwd_features = gwd_transformer.fit_transform(embeddings)
print(f"GWD features shape: {gwd_features.shape}")

# Compute GWD summary statistics
gwd_summaries = {
    "mean_distances": np.mean(gwd_features, axis=1),
    "max_distances": np.max(gwd_features, axis=1),
    "std_distances": np.std(gwd_features, axis=1),
    "median_distances": np.median(gwd_features, axis=1)
}

# PCA compression of GWD features
print("Computing PCA compression of GWD features...")
pca = PCA(n_components=min(50, gwd_features.shape[1]))
pca_gwd_features = pca.fit_transform(gwd_features)
print(f"PCA-GWD features shape: {pca_gwd_features.shape}")
print(f"PCA explained variance ratio: {pca.explained_variance_ratio_.sum():.3f}")

# Combined feature set (Raw + PCA-GWD)
features_4 = np.hstack([features_1, pca_gwd_features])

# Organize feature sets for model training
feature_sets = {
    "raw_coords": (
        features_1, 
        "Raw UMAP coordinates (baseline features)"
    ),
    "gwd_summaries": (
        np.column_stack(list(gwd_summaries.values())), 
        f"GWD summary statistics (σ={best_sigma:.3f})"
    ),
    "pca_gwd": (
        pca_gwd_features, 
        f"PCA-compressed GWD features (σ={best_sigma:.3f}, {pca_gwd_features.shape[1]} components)"
    ),
    "combined_features": (
        features_4, 
        f"Combined Raw + PCA-GWD features ({features_4.shape[1]} total features)"
    )
}

print(f"Generated {len(feature_sets)} feature sets:")
for name, (data, desc) in feature_sets.items():
    print(f"  {name}: {data.shape} - {desc}")
```

## Correlation Heatmap Generation

The system generates high-resolution correlation heatmaps on discrete grids:

```python
# STEP 4: Generate correlation heatmap on discrete grid
print(f"Generating correlation heatmap with grid size {grid_size}x{grid_size}...")

# Create regular grid over embedding space
x_min, x_max = embeddings[:, 0].min(), embeddings[:, 0].max()
y_min, y_max = embeddings[:, 1].min(), embeddings[:, 1].max()

# Add small margin to ensure all points are included
margin = 0.05
x_range = x_max - x_min
y_range = y_max - y_min
x_min -= margin * x_range
x_max += margin * x_range
y_min -= margin * y_range
y_max += margin * y_range

corr_grid_x = np.linspace(x_min, x_max, grid_size)
corr_grid_y = np.linspace(y_min, y_max, grid_size)
grid_points = np.array(np.meshgrid(corr_grid_x, corr_grid_y)).T.reshape(-1, 2)

# Compute GWD from grid points to data points
print("Computing GWD from grid to data points...")
grid_gwd = GWD(sigma=best_sigma)
grid_gwd.fit(embeddings)  # Fit on actual data points
grid_features = grid_gwd.transform(grid_points)  # Transform grid points

# Apply correlation filtering to grid features
print("Computing correlations for heatmap...")
grid_correlations = []
for i in range(grid_features.shape[0]):
    corr, _ = pearsonr(grid_features[i], VOI_vector)
    grid_correlations.append(corr if not np.isnan(corr) else 0.0)

correlation_heatmap = np.array(grid_correlations).reshape(grid_size, grid_size)

# Save correlation heatmap
heatmap_path = output_folder / "correlation_heatmap.npy"
np.save(heatmap_path, correlation_heatmap)
print(f"Correlation heatmap saved to {heatmap_path}")

# Generate heatmap visualization
plt.figure(figsize=(10, 8))
plt.imshow(correlation_heatmap, extent=[x_min, x_max, y_min, y_max], 
           aspect='auto', cmap='RdBu_r', vmin=-1, vmax=1)
plt.colorbar(label='Pearson Correlation')
plt.scatter(embeddings[:, 0], embeddings[:, 1], c=VOI_vector, 
           s=20, alpha=0.6, cmap='viridis')
plt.title(f'Correlation Heatmap for {key}')
plt.xlabel('UMAP Dimension 1')
plt.ylabel('UMAP Dimension 2')
plt.tight_layout()
plt.savefig(output_folder / "correlation_heatmap.png", dpi=300, bbox_inches='tight')
plt.close()
```

## Model Training with Nested Cross-Validation

The pipeline implements sophisticated model training with hyperparameter optimization:

```python
# STEP 5: Model training with nested cross-validation and Optuna
print("Starting model training with nested CV and hyperparameter optimization...")

def optimize_train_model(feature_set_name, X_train, y_train, X_test=None, y_test=None):
    """
    Optimize and train a single model on a feature set.
    
    Uses nested cross-validation:
    - Outer loop: Performance estimation
    - Inner loop: Hyperparameter optimization with Optuna
    """
    print(f"Processing feature set: {feature_set_name}")
    
    # Clean training data
    X_train_clean, y_train_clean, train_mask = filter_nan_rows(X_train, y_train)
    
    if len(y_train_clean) < 10:
        print(f"Insufficient training data for {feature_set_name}: {len(y_train_clean)} samples")
        return None
    
    # Determine task type
    unique_values = len(np.unique(y_train_clean))
    is_categorical = unique_values < 10 and unique_values / len(y_train_clean) < 0.3
    task_type = "classification" if is_categorical else "regression"
    
    print(f"Task type: {task_type} ({unique_values} unique values)")
    
    # Set up nested cross-validation
    outer_cv = KFold(n_splits=5, shuffle=True, random_state=random_state)
    cv_scores = []
    cv_models = []
    
    for fold_idx, (train_idx, val_idx) in enumerate(outer_cv.split(X_train_clean)):
        print(f"  Processing fold {fold_idx + 1}/5...")
        
        X_fold_train, X_fold_val = X_train_clean[train_idx], X_train_clean[val_idx]
        y_fold_train, y_fold_val = y_train_clean[train_idx], y_train_clean[val_idx]
        
        # Inner optimization with Optuna
        def optuna_objective(trial):
            # Suggest model type
            model_type = trial.suggest_categorical(
                "model_type", 
                ["random_forest", "gradient_boosting", "elastic_net", "kernel_regression"]
            )
            
            # Build model with suggested hyperparameters
            if model_type == "random_forest":
                model = RandomForestRegressor(
                    n_estimators=trial.suggest_int("n_estimators", 50, 200),
                    max_depth=trial.suggest_int("max_depth", 3, 15),
                    min_samples_split=trial.suggest_int("min_samples_split", 2, 10),
                    min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 5),
                    random_state=random_state
                ) if task_type == "regression" else RandomForestClassifier(
                    n_estimators=trial.suggest_int("n_estimators", 50, 200),
                    max_depth=trial.suggest_int("max_depth", 3, 15),
                    min_samples_split=trial.suggest_int("min_samples_split", 2, 10),
                    min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 5),
                    random_state=random_state
                )
            
            elif model_type == "gradient_boosting":
                model = GradientBoostingRegressor(
                    n_estimators=trial.suggest_int("n_estimators", 50, 200),
                    learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3),
                    max_depth=trial.suggest_int("max_depth", 3, 8),
                    random_state=random_state
                )
            
            elif model_type == "elastic_net":
                model = ElasticNet(
                    alpha=trial.suggest_float("alpha", 0.01, 10.0, log=True),
                    l1_ratio=trial.suggest_float("l1_ratio", 0.1, 0.9),
                    random_state=random_state
                )
            
            elif model_type == "kernel_regression":
                from emuses.tools.kernel_regression_utils import KernelRegressor
                model = KernelRegressor(
                    kernel=trial.suggest_categorical("kernel", ["rbf", "polynomial"]),
                    gamma=trial.suggest_float("gamma", 1e-4, 1e-1, log=True),
                    alpha=trial.suggest_float("alpha", 1e-6, 1e-2, log=True)
                )
            
            # Cross-validation within the fold
            inner_cv = KFold(n_splits=3, shuffle=True, random_state=random_state)
            inner_scores = []
            
            for inner_train_idx, inner_val_idx in inner_cv.split(X_fold_train):
                X_inner_train, X_inner_val = X_fold_train[inner_train_idx], X_fold_train[inner_val_idx]
                y_inner_train, y_inner_val = y_fold_train[inner_train_idx], y_fold_train[inner_val_idx]
                
                try:
                    model.fit(X_inner_train, y_inner_train)
                    y_pred = model.predict(X_inner_val)
                    
                    if task_type == "regression":
                        score = r2_score(y_inner_val, y_pred)
                    else:
                        score = accuracy_score(y_inner_val, y_pred)
                    
                    inner_scores.append(score)
                except Exception as e:
                    print(f"    Model fitting failed: {e}")
                    return -1.0
            
            return np.mean(inner_scores) if inner_scores else -1.0
        
        # Run Optuna optimization for this fold
        fold_study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=optuna_seed or random_state)
        )
        fold_study.optimize(optuna_objective, n_trials=optuna_trials)
        
        # Train final model with best parameters
        best_params = fold_study.best_params
        model_type = best_params.pop("model_type")
        
        # Build and train final model (implementation depends on model_type)
        # ... (model building code as above)
        
        final_model.fit(X_fold_train, y_fold_train)
        
        # Evaluate on validation fold
        y_val_pred = final_model.predict(X_fold_val)
        if task_type == "regression":
            fold_score = r2_score(y_fold_val, y_val_pred)
        else:
            fold_score = accuracy_score(y_fold_val, y_val_pred)
        
        cv_scores.append(fold_score)
        cv_models.append(final_model)
        
        print(f"    Fold {fold_idx + 1} score: {fold_score:.4f}")
    
    # Aggregate results
    mean_cv_score = np.mean(cv_scores)
    std_cv_score = np.std(cv_scores)
    
    print(f"  {feature_set_name} CV score: {mean_cv_score:.4f} ± {std_cv_score:.4f}")
    
    return {
        "feature_set": feature_set_name,
        "task_type": task_type,
        "cv_scores": cv_scores,
        "mean_cv_score": mean_cv_score,
        "std_cv_score": std_cv_score,
        "models": cv_models,
        "n_samples": len(y_train_clean),
        "n_features": X_train_clean.shape[1]
    }
```

## Results Aggregation and Analysis

The pipeline provides comprehensive results analysis and model comparison:

```python
# STEP 6: Execute parallel model training
if run_parallel and n_jobs != 1:
    print(f"Running parallel model training with {n_jobs} processes...")
    with Pool(processes=n_jobs if n_jobs > 0 else cpu_count()) as pool:
        results = pool.starmap(optimize_train_model, parallel_tasks)
else:
    print("Running sequential model training...")
    results = []
    for task in parallel_tasks:
        result = optimize_train_model(*task)
        results.append(result)

# Filter successful results
successful_results = [r for r in results if r is not None]

# STEP 7: Results analysis and comparison
print(f"\nResults Summary ({len(successful_results)} successful models):")
print("=" * 70)

# Sort by performance
successful_results.sort(key=lambda x: x["mean_cv_score"], reverse=True)

best_result = successful_results[0] if successful_results else None
best_fs = best_result["feature_set"] if best_result else "none"

# Print performance table
print("Feature Set Performance:")
print("-" * 70)
print(f"{'Feature Set':<25} {'CV Score':<12} {'Std':<8} {'Samples':<8} {'Features':<8}")
print("-" * 70)

for result in successful_results:
    print(f"{result['feature_set']:<25} "
          f"{result['mean_cv_score']:<12.4f} "
          f"{result['std_cv_score']:<8.4f} "
          f"{result['n_samples']:<8} "
          f"{result['n_features']:<8}")

# STEP 8: Comprehensive results dictionary
final_results = {
    "embeddings_shape": embeddings.shape,
    "input_matrix_shape": combined_input_matrix.shape,
    "voi_key": key,
    "voi_stats": {
        "mean": float(np.mean(VOI_vector)),
        "std": float(np.std(VOI_vector)),
        "min": float(np.min(VOI_vector)),
        "max": float(np.max(VOI_vector)),
        "range": float(global_range)
    },
    "optimal_sigma": best_sigma,
    "gwd_summaries": gwd_summaries,
    "combined_features": features_4,
    "feature_sets": {name: data for name, (data, _) in feature_sets.items()},
    "pca_components": pca.n_components_,
    "pca_explained_variance": pca.explained_variance_ratio_.sum(),
    "correlation_heatmap": {
        "heatmap": correlation_heatmap,
        "grid_x": corr_grid_x,
        "grid_y": corr_grid_y,
    },
    "final_sigma": best_sigma,
    "model_results": successful_results,
    "best_feature_set": best_fs,
    "best_cv_score": best_result["mean_cv_score"] if best_result else 0.0,
    "processing_time": time.time() - start_time,
    "parameters": {
        "grid_size": grid_size,
        "dataset_type": dataset_type,
        "optuna_trials": optuna_trials,
        "random_state": random_state,
        "n_jobs": n_jobs
    }
}

# Save comprehensive results
results_path = output_folder / "comprehensive_results.json"
save_json(results_path, final_results)
print(f"\nComprehensive results saved to: {results_path}")

return final_results
```

## Statistical Cluster Analysis

The utilities provide sophisticated statistical analysis for cluster characterization:

```python
def create_cluster_representative_maps(
    array, discrete_embeddings, input_matrix, original_shape, test_name="mann-whitney"
):
    """
    Create statistical maps comparing clusters to the rest of the data.
    
    For each cluster, performs statistical tests to identify which input features
    (voxels, pixels, or other measurements) are significantly different between
    cluster members and the rest of the dataset.
    
    Parameters
    ----------
    array : ndarray, shape (n_samples,)
        Cluster labels (-1 for noise points)
    discrete_embeddings : ndarray, shape (n_samples, n_dims)
        Discrete embedding coordinates
    input_matrix : ndarray, shape (n_samples, n_features)
        Original high-dimensional input data
    original_shape : tuple
        Shape to reshape statistical maps (for imaging data)
    test_name : str, default="mann-whitney"
        Statistical test to use ("mann-whitney", "t-test")
    
    Returns
    -------
    tuple
        (stat_maps, pval_maps, effect_size_maps, centroids)
        Statistical maps, p-value maps, effect size maps, and cluster centroids
    """
    # Separate clusters and extract coordinates
    clusters_coords = separate_clusters_and_extract_coords(array, discrete_embeddings)
    
    stat_maps = []
    pval_maps = []
    effect_size_maps = []
    centroids = []
    
    for cluster_label, cluster_coords in clusters_coords.items():
        if cluster_label == -1:  # Skip noise points
            continue
            
        print(f"Processing cluster {cluster_label} ({len(cluster_coords)} points)")
        
        # Get indices of points in this cluster
        cluster_mask = (array == cluster_label)
        cluster_data = input_matrix[cluster_mask]
        other_data = input_matrix[~cluster_mask]
        
        # Initialize maps
        stat_map = np.zeros(input_matrix.shape[1])
        pval_map = np.zeros(input_matrix.shape[1])
        effect_size_map = np.zeros(input_matrix.shape[1])
        
        # Perform statistical test for each feature
        for feature_idx in range(input_matrix.shape[1]):
            cluster_values = cluster_data[:, feature_idx]
            other_values = other_data[:, feature_idx]
            
            # Remove NaN values
            cluster_values = cluster_values[~np.isnan(cluster_values)]
            other_values = other_values[~np.isnan(other_values)]
            
            if len(cluster_values) < 3 or len(other_values) < 3:
                continue
            
            # Perform statistical test
            if test_name == "mann-whitney":
                try:
                    statistic, p_value = mannwhitneyu(
                        cluster_values, other_values, alternative='two-sided'
                    )
                    stat_map[feature_idx] = statistic
                    pval_map[feature_idx] = p_value
                except ValueError:
                    # Handle cases where test cannot be performed
                    stat_map[feature_idx] = 0
                    pval_map[feature_idx] = 1.0
                    
            elif test_name == "t-test":
                try:
                    statistic, p_value = ttest_ind(
                        cluster_values, other_values, equal_var=False
                    )
                    stat_map[feature_idx] = statistic
                    pval_map[feature_idx] = p_value
                except (ValueError, ZeroDivisionError):
                    stat_map[feature_idx] = 0
                    pval_map[feature_idx] = 1.0
            
            # Compute effect size (Cohen's d)
            if len(cluster_values) > 0 and len(other_values) > 0:
                pooled_std = np.sqrt(
                    ((len(cluster_values) - 1) * np.var(cluster_values, ddof=1) +
                     (len(other_values) - 1) * np.var(other_values, ddof=1)) /
                    (len(cluster_values) + len(other_values) - 2)
                )
                if pooled_std > 0:
                    cohens_d = (np.mean(cluster_values) - np.mean(other_values)) / pooled_std
                    effect_size_map[feature_idx] = cohens_d
        
        # Reshape maps to original shape if provided
        if original_shape is not None:
            stat_map = stat_map.reshape(original_shape)
            pval_map = pval_map.reshape(original_shape)
            effect_size_map = effect_size_map.reshape(original_shape)
        
        stat_maps.append(stat_map)
        pval_maps.append(pval_map)
        effect_size_maps.append(effect_size_map)
        
        # Find cluster centroid
        centroid = find_centroid_and_check(cluster_coords)
        centroids.append(centroid)
    
    return stat_maps, pval_maps, effect_size_maps, centroids

def filter_nan_rows(coords: np.ndarray, scores: np.ndarray):
    """
    Remove rows where scores contain NaN values.
    
    Parameters
    ----------
    coords : ndarray, shape (n_samples, n_features)
        Coordinate/feature data
    scores : ndarray, shape (n_samples,)
        Target scores/labels
    
    Returns
    -------
    tuple
        (coords_clean, scores_clean, mask) where mask indicates valid rows
    """
    mask = ~np.isnan(scores)
    return coords[mask], scores[mask], mask
```

**Key advantages:**
- **Comprehensive pipeline**: End-to-end prediction workflow with feature engineering
- **Advanced optimization**: Nested CV with Optuna hyperparameter search
- **Multiple feature types**: Raw coordinates, GWD, PCA-GWD, and combined features
- **Statistical rigor**: Proper cross-validation and statistical testing
- **Visualization**: Correlation heatmaps and model performance plots
- **Parallel processing**: Efficient parallel model training
- **Robust evaluation**: Multiple metrics and comprehensive results tracking

</details>
