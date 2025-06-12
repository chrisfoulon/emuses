# Heatmap Stage

The HeatmapStage implements advanced predictive modeling using nested cross-validation with Optuna optimization. It performs conditional feature engineering and model selection to build robust prediction models from UMAP embeddings, with optional autoencoder pretraining for enhanced feature extraction. The stage supports both regression and classification tasks with comprehensive performance evaluation.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Function/Class | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `HeatmapStage.__init__(config, output_format_info)` | Initialize heatmap stage | `config: PipelineConfig, output_format_info: tuple` | `HeatmapStage` | None |
| `HeatmapStage.run(context, progress_queue)` | Execute nested CV and model training | `context: dict, progress_queue: Queue` | `None` | Saves trained models, performance metrics, heatmaps |
| `nested_optuna_cv(X, y, task, optim_dict, **kwargs)` | Nested cross-validation with hyperparameter optimization | `X: ndarray, y: ndarray, task: str, optim_dict: dict` | `(cv_scores: ndarray, best_pipelines: List[Pipeline])` | Saves models per fold |
| `optimize_ae_pretraining(X, n_trials, **kwargs)` | Autoencoder pretraining optimization | `X: ndarray, n_trials: int` | `dict` | Saves pretrained autoencoder models |
| `suggest_parameters_conditional(trial, optim_dict)` | Conditional hyperparameter sampling | `trial: optuna.Trial, optim_dict: dict` | `dict` | None |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## Stage Initialization and Configuration
The heatmap stage handles complex model optimization with conditional feature engineering:

```python
def __init__(self, config, output_format_info):
    """
    Initialize heatmap stage with prediction optimization configuration.
    
    Parameters
    ----------
    config : PipelineConfig
        Pipeline configuration with optimization parameters
    output_format_info : tuple
        Output format information for result generation
        
    Notes
    -----
    - Loads prediction optimization dictionary (optim_dict_predict)
    - Configures task type (regression vs classification)
    - Sets up autoencoder pretraining if enabled
    """
    super().__init__(config)
    self.output_format_info = output_format_info
    
    # Load optimization configuration for prediction models
    self.optim_dict = self._load_prediction_optim_dict()
    
    # Determine task type from configuration
    self.task = "clf" if getattr(config, "classification", False) else "reg"
```

## Prediction Optimization Dictionary Loading
Flexible loading of optimization configurations with fallback mechanisms:

```python
def run(self, context, progress_queue=None):
    """
    Execute prediction model optimization and training.
    
    Workflow:
    1. Load optimization dictionary for prediction models
    2. Optionally run autoencoder pretraining
    3. Execute nested cross-validation with Optuna optimization
    4. Generate performance summaries and save models
    """
    # Load prediction optimization dictionary with fallback
    if "optim_dict_predict" in context and context["optim_dict_predict"]:
        optim_dict_predict_selected = context["optim_dict_predict"]
    elif "cli_args" in context and "prediction_optim_dict" in context["cli_args"]:
        prediction_optim_dict_name = context["cli_args"]["prediction_optim_dict"]
        try:
            optim_dict_predict_selected = load_optim_dict_predict(prediction_optim_dict_name)
            logger.info(f"Loaded prediction optimization dictionary: '{prediction_optim_dict_name}'")
        except Exception as e:
            logger.error(f"Error loading prediction optim_dict '{prediction_optim_dict_name}': {e}")
            optim_dict_predict_selected = optim_dict_predict  # fallback
    else:
        optim_dict_predict_selected = optim_dict_predict
```

## Autoencoder Pretraining
Optional autoencoder pretraining for enhanced feature extraction:

```python
# Check if autoencoder pretraining is needed
use_ae_pretrain = getattr(self.config, "use_ae_pretrain", False)
feat_choices = optim_dict_predict_selected["param"]["features"]["feat_type"]["choices"]
has_ae_choice = "ae" in feat_choices

# Auto-enable AE pretraining if optimization space includes AE features
if not use_ae_pretrain and has_ae_choice:
    use_ae_pretrain = True
    logger.info("Auto-enabling AE pretraining: optim dict contains 'ae' features")

if use_ae_pretrain and has_ae_choice:
    # Try to load existing pretrained model
    ae_results = None
    try:
        saved_ae = load_pretrained_ae(self.config.output_folder)
        if saved_ae:
            # Validate model on current data
            if getattr(self.config, "validate_loaded_ae", True):
                fitted_ae = saved_ae["fitted_ae"]
                recon_error = np.mean(fitted_ae.get_reconstruction_error(ae_input_data))
                max_diff = getattr(self.config, "max_ae_error_diff", 0.2)
                
                if abs(recon_error - saved_ae["best_score"]) <= max_diff:
                    ae_results = saved_ae
                    logger.info(f"Using saved AE model (error: {recon_error:.4f})")
    except Exception as e:
        logger.warning(f"Error loading pretrained AE: {e}")
    
    # Train new autoencoder if none found or validation failed
    if ae_results is None:
        ae_trials = getattr(self.config, "ae_optuna_trials", 20)
        ae_results = optimize_ae_pretraining(
            X=prediction_train_coords,  # Use UMAP embeddings as input
            n_trials=ae_trials,
            output_folder=self.config.output_folder,
            random_state=42,
        )
        logger.info(f"AE pretraining completed. Best error: {ae_results['best_score']:.4f}")
```

## Nested Cross-Validation with Conditional Feature Engineering
The core optimization loop with conditional parameter spaces:

```python
# Extract design matrix and targets
X = prediction_train_coords  # UMAP embeddings (n_samples, 2)
Y = prediction_train_labels  # Target variables (n_samples, p)

if Y.ndim == 1:
    Y = Y[:, None]  # Ensure 2D for uniform processing

# Handle multi-class classification as multiple binary targets
if task == "clf" and Y.shape[1] == 1:
    unique_classes = np.unique(Y[:, 0])
    if len(unique_classes) > 2:
        # Convert to one-vs-rest binary classification
        Y_binary = np.zeros((Y.shape[0], len(unique_classes)))
        for i, cls in enumerate(unique_classes):
            Y_binary[:, i] = (Y[:, 0] == cls).astype(int)
        Y = Y_binary

# Parallel optimization for each target variable
fitted_ae = ae_results.get("fitted_ae") if ae_results else None

results = Parallel(n_jobs=-1, backend="loky")(
    delayed(_optimise_target)(
        col_idx, X, Y, task, self.config, self.config.output_folder,
        logger.name, optim_dict_predict_selected, fitted_ae
    )
    for col_idx in range(Y.shape[1])
)

# Collect results from parallel execution
for tag, scores, pipes in results:
    context.setdefault("prediction_results", {})[tag] = {
        "cv_scores": scores,
        "best_pipelines": pipes,
    }
```

## Conditional Parameter Sampling
The optimization uses conditional parameter spaces based on feature type selection:

```python
def suggest_parameters_conditional(trial, optim_dict):
    """
    Sample hyperparameters with conditional dependencies.
    
    Parameters
    ----------
    trial : optuna.Trial
        Optuna trial object for parameter suggestion
    optim_dict : dict
        Optimization dictionary with conditional parameter space
        
    Returns
    -------
    dict
        Sampled parameters with conditional structure
        
    Notes
    -----
    Parameter sampling flow:
    1. Sample feature type (raw_coords, gwd, pca_gwd, kernel_pca_gwd, ae)
    2. Based on feature type, sample relevant feature parameters
    3. Sample model type and corresponding model parameters
    4. Handle conditional dependencies (e.g., AE requires pretrained model)
    """
    params = {}
    
    # Sample feature engineering approach
    feat_type = trial.suggest_categorical(
        "feat_type", 
        optim_dict["param"]["features"]["feat_type"]["choices"]
    )
    params["features"] = {"feat_type": feat_type}
    
    # Sample feature-specific parameters based on type
    if feat_type == "gwd":
        params["features"]["p_norm"] = trial.suggest_categorical(
            "gwd_p_norm", optim_dict["param"]["features"]["gwd"]["p_norm"]["choices"]
        )
    elif feat_type == "pca_gwd":
        params["features"]["n_components"] = trial.suggest_int(
            "pca_n_components", 
            optim_dict["param"]["features"]["pca_gwd"]["n_components"]["low"],
            optim_dict["param"]["features"]["pca_gwd"]["n_components"]["high"]
        )
    elif feat_type == "ae":
        # AE features require pretrained autoencoder (provided externally)
        pass
    
    # Sample model type
    model_type = trial.suggest_categorical(
        "model_type",
        optim_dict["param"]["model"]["model_type"]["choices"]
    )
    params["model"] = {"model_type": model_type}
    
    # Sample model-specific hyperparameters
    if model_type == "gaussian_process":
        params["model"]["alpha"] = trial.suggest_float(
            "gp_alpha",
            optim_dict["param"]["model"]["gaussian_process"]["alpha"]["low"],
            optim_dict["param"]["model"]["gaussian_process"]["alpha"]["high"],
            log=True
        )
    # ... additional model types
    
    return params
```

## Performance Evaluation and Summary Generation
Comprehensive performance tracking with multiple output formats:

```python
def _generate_performance_csv_files(self, context, task, n_targets, logger):
    """
    Generate comprehensive performance summaries.
    
    Creates:
    - Per-target performance files with fold-wise results
    - Aggregated summary statistics across all targets
    - Excel files for easy analysis
    - JSON files for programmatic access
    """
    prediction_results = context.get("prediction_results", {})
    output_folder = Path(self.config.output_folder)
    
    summary_data = []
    individual_fold_data = []
    
    for target_tag, result_data in prediction_results.items():
        cv_scores = result_data.get("cv_scores", [])
        
        if len(cv_scores) == 0:
            logger.warning(f"No CV scores found for {target_tag}")
            continue
        
        # Target-specific performance summary
        target_summary = {
            "target": target_tag,
            "mean_score": np.mean(cv_scores),
            "std_score": np.std(cv_scores),
            "min_score": np.min(cv_scores),
            "max_score": np.max(cv_scores),
            "n_folds": len(cv_scores),
            "task_type": task,
        }
        summary_data.append(target_summary)
        
        # Fold-wise detailed results
        for fold_idx, score in enumerate(cv_scores):
            fold_result = {
                "target": target_tag,
                "fold": fold_idx,
                "score": score,
                "task_type": task,
            }
            individual_fold_data.append(fold_result)
    
    # Save summary files
    summary_df = pd.DataFrame(summary_data)
    summary_file = output_folder / "performance_summary" / "target_summary.csv"
    summary_df.to_csv(summary_file, index=False)
    
    # Save detailed fold results
    fold_df = pd.DataFrame(individual_fold_data)
    fold_file = output_folder / "performance_summary" / "fold_details.csv"
    fold_df.to_csv(fold_file, index=False)
```

</details>
