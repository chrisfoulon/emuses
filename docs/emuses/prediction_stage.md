# Prediction Stage

The PredictionStage implements machine learning model training and evaluation for prediction tasks using UMAP embeddings as features. It supports both enhanced pipeline mode with Optuna optimization and a classic pipeline mode. The stage can handle multiple feature engineering approaches including Gaussian Weighted Distance (GWD) features and provides comprehensive model evaluation with test set performance metrics.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function/Class | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `PredictionStage.__init__(config)` | Initialize prediction stage | `config: PipelineConfig` | `PredictionStage` | None |
| `PredictionStage.run(context, progress_queue)` | Execute model training and evaluation | `context: dict, progress_queue: Queue` | `None` | Saves trained models, performance metrics |
| `optuna_model_selection(X, y, n_trials, **kwargs)` | Hyperparameter optimization with Optuna | `X: ndarray, y: ndarray, n_trials: int` | `dict` | Saves optimization plots and models |
| `compute_gwd_summary(embeddings, sigma, mode)` | Compute Gaussian Weighted Distance features | `embeddings: ndarray, sigma: float, mode: str` | `ndarray` | None |
| `train_and_test_model_per_label(train_coords, train_labels, **kwargs)` | Classic pipeline model training | `train_coords: ndarray, train_labels: ndarray` | `List[dict]` | Saves models and predictions |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Stage Initialization and Configuration
The prediction stage handles model training with flexible feature engineering and optimization:

```python
def __init__(self, config):
    """
    Initialize prediction stage with configuration.
    
    Parameters
    ----------
    config : PipelineConfig
        Pipeline configuration containing prediction parameters
        
    Notes
    -----
    Stage supports two modes:
    - Enhanced pipeline: Optuna optimization with multiple feature sets
    - Classic pipeline: Standard kernel ridge regression
    """
    super().__init__(config)
    
    # Configuration will determine:
    # - use_enhanced_pipeline: Enable Optuna optimization
    # - parallel_models: Train feature sets in parallel
    # - model_selection: Which models to try
    # - optuna_trials: Number of optimization trials
```

## Enhanced Pipeline with Feature Engineering
Advanced pipeline mode with multiple feature engineering approaches:

```python
def run(self, context, progress_queue=None):
    """
    Execute prediction model training and evaluation.
    
    Workflow:
    1. Extract UMAP embeddings and labels from context
    2. Compute additional feature sets (GWD, combined features)
    3. Train models on different feature sets (optionally in parallel)
    4. Evaluate on test data and save best models
    5. Generate comprehensive performance reports
    """
    # Get reproducible random seeds
    random_seeds = context.get("random_seeds", {})
    prediction_seed = random_seeds.get("prediction_seed", 42)
    cv_seed = random_seeds.get("cv_seed", 42)
    optuna_seed = random_seeds.get("optuna_seed", 42)
    
    # Extract data using standardized naming
    train_embeddings = context.get("prediction_train_coords")  # UMAP embeddings
    test_embeddings = context.get("prediction_test_coords")
    train_labels = context.get("prediction_train_labels")     # Target variables
    test_labels = context.get("prediction_test_labels")
    
    # Determine pipeline mode
    use_enhanced_pipeline = getattr(self.config, "use_enhanced_pipeline", False)
    
    if use_enhanced_pipeline:
        # Enhanced mode with feature engineering and optimization
        sigma = context.get("prediction_train_sigma")
        if sigma is None:
            sigma = np.sqrt(train_embeddings.shape[1]) * 0.5
            context["prediction_train_sigma"] = sigma
        
        # Compute GWD features
        train_gwd_features = compute_gwd_summary(train_embeddings, sigma, mode="extended")
        if test_embeddings is not None:
            test_gwd_features = compute_gwd_summary_test(
                test_embeddings, train_embeddings, sigma, mode="extended"
            )
```

## Multiple Feature Set Evaluation
The enhanced pipeline evaluates different feature engineering approaches:

```python
# Create multiple feature sets for comparison
feature_sets = {
    "embeddings_only": (train_embeddings, test_embeddings),
    "gwd_only": (train_gwd_features, test_gwd_features), 
    "combined": (
        np.hstack((train_embeddings, train_gwd_features)),
        np.hstack((test_embeddings, test_gwd_features))
    ),
}

# Process each target variable (support for multi-target prediction)
train_labels_array = train_labels.values if hasattr(train_labels, "values") else train_labels
if train_labels_array.ndim == 1:
    train_labels_array = train_labels_array.reshape(-1, 1)

# Get column names for interpretable results
column_names = getattr(train_labels, "columns", 
                      [f"Target_{i}" for i in range(train_labels_array.shape[1])])

for label_idx in range(train_labels_array.shape[1]):
    label_name = column_names[label_idx]
    y_train = train_labels_array[:, label_idx]
    y_test = test_labels_array[:, label_idx] if test_labels_array is not None else None
```

## Parallel Model Training
Optional parallelization across feature sets for efficient computation:

```python
if parallel_models:
    # Parallel training across feature sets
    def train_feature_set(feature_name, features):
        """Train model on specific feature set with Optuna optimization."""
        X_train, X_test = features
        
        # Create output directory for this combination
        label_output_folder = output_folder / label_name / feature_name
        label_output_folder.mkdir(parents=True, exist_ok=True)
        
        # Run Optuna optimization
        results = optuna_model_selection(
            X=X_train, y=y_train,
            n_trials=optuna_trials,
            n_jobs=1,  # Single job since we parallelize at feature level
            output_folder=label_output_folder,
            feature_set_name=feature_name,
            models=model_selection,
            random_state=cv_seed,
            optuna_seed=optuna_seed,
        )
        
        # Evaluate on test data if available
        best_model = results["best_model"]
        if X_test is not None and y_test is not None:
            y_pred = best_model.predict(X_test)
            r2 = r2_score(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)
            
            results.update({
                "test_r2": r2, "test_mse": mse, "test_mae": mae,
                "y_pred": y_pred, "y_test": y_test,
            })
        
        return results
    
    # Execute parallel training
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(n_jobs, len(feature_sets))) as executor:
        future_to_feature = {
            executor.submit(train_feature_set, feature_name, features): feature_name
            for feature_name, features in feature_sets.items()
        }
        
        feature_set_results = {}
        for future in concurrent.futures.as_completed(future_to_feature):
            feature_name = future_to_feature[future]
            try:
                feature_set_results[feature_name] = future.result()
            except Exception as e:
                logger.error(f"Error training models for feature set {feature_name}: {e}")
```

## Model Selection and Evaluation
Comprehensive evaluation and best model selection:

```python
# Find best feature set based on test performance
best_feature_set = max(feature_set_results.items(), key=lambda x: x[1]["test_r2"])
best_feature_name, best_result = best_feature_set

logger.info(f"Best feature set for {label_name}: {best_feature_name} (R2: {best_result['test_r2']:.4f})")

# Collect results for summary
results_list.append({
    "label_name": label_name,
    "best_feature_set": best_feature_name,
    "best_model": best_result["best_model_name"],
    "test_r2": best_result["test_r2"],
    "test_mse": best_result["test_mse"],
    "test_mae": best_result["test_mae"],
    "model_params": best_result["best_params"],
})
```

## Classic Pipeline Mode
Fallback to simple kernel ridge regression for basic use cases:

```python
else:
    # Classic pipeline with simple cross-validation
    logger.info("Using original prediction pipeline")
    
    if test_embeddings is not None and test_labels is not None:
        # Use train_and_test_model_per_label for full evaluation
        results_list = train_and_test_model_per_label(
            train_embeddings=train_embeddings,
            train_labels=train_labels,
            test_embeddings=test_embeddings,
            test_labels=test_labels,
            output_folder=output_folder,
            categorical=getattr(self.config, "classification", False),
            show_plot=getattr(self.config, "show_plots", False),
            n_jobs=n_jobs,
        )
    else:
        # Cross-validation only mode
        for label_idx in range(train_labels_array.shape[1]):
            label_name = column_names[label_idx]
            y_train = train_labels_array[:, label_idx]
            
            # Simple KernelRidge with cross-validation
            model = KernelRidge(alpha=0.1, kernel="rbf")
            cv_scores = cross_val_score(model, train_embeddings, y_train, cv=5, scoring="r2")
            
            # Train final model on all data
            model.fit(train_embeddings, y_train)
            
            # Save model using ModelIOManager
            label_output_folder = output_folder / label_name
            label_output_folder.mkdir(parents=True, exist_ok=True)
            
            model_manager = ModelIOManager(label_output_folder)
            model_manager.save_model(
                model=model,
                model_name="final_model",
                model_type="kernel_ridge",
                description=f"KernelRidge model for {label_name} prediction",
                tags=["prediction", "kernel_ridge", label_name],
                config={"alpha": 0.1, "kernel": "rbf"},
            )
```

## Performance Reporting
Comprehensive performance tracking and export:

```python
# Save results in multiple formats for analysis
performance_df = pd.DataFrame(results_list)
output_folder_perf = Path(self.config.output_folder) / "prediction_performance"
output_folder_perf.mkdir(parents=True, exist_ok=True)

# CSV format for easy analysis
perf_csv_file = output_folder_perf / "prediction_performance.csv"
performance_df.to_csv(perf_csv_file, index=False)
logger.info(f"Saved test performance metrics to {perf_csv_file}")

# JSON format for programmatic access
perf_json_file = output_folder_perf / "prediction_performance.json"
save_json(perf_json_file, results_list)

return context
```

## Feature Engineering Details
The GWD (Gaussian Weighted Distance) features provide spatial relationships:

```python
def compute_gwd_summary(embeddings, sigma, mode="extended"):
    """
    Compute Gaussian Weighted Distance features from embeddings.
    
    Parameters
    ----------
    embeddings : ndarray, shape (n_samples, n_dims)
        Low-dimensional embeddings (typically from UMAP)
    sigma : float
        Bandwidth parameter for Gaussian weighting
    mode : str
        Feature extraction mode ('basic', 'extended')
        
    Returns
    -------
    ndarray
        GWD feature matrix with spatial relationship features
        
    Notes
    -----
    GWD features capture local neighborhood structure:
    - Distance-weighted averages of nearby points
    - Local density estimates
    - Gradient information in embedding space
    """
    # Implementation computes various spatial statistics
    # using Gaussian-weighted neighborhoods in embedding space
```

</details>
