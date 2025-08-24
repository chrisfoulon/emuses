# Model I/O Management System

The Model I/O Management System provides a comprehensive, versioned approach to model persistence across all EMUSES pipeline stages. It handles model saving and loading with automatic versioning, metadata tracking, backward compatibility, and robust fallback mechanisms. This system ensures reproducible model artifacts with complete provenance tracking including Optuna optimization history, cross-validation results, and dependency management.

<details><summary>🛠️ Level 2 · Key API table</summary>

| Class/Function | Purpose | Inputs | Outputs | Side-effects |
|---|---|---|---|---|
| `ModelIOManager.__init__(base_path, version)` | Initialize model I/O manager | `base_path: Path, version: str` | `ModelIOManager` | Creates directory structure |
| `ModelIOManager.save_model(model, model_name, model_type, **kwargs)` | Save model with metadata | `model: Any, model_name: str, model_type: str, config: dict, optimization_time: float, **kwargs` | `Path` | Saves model + metadata to disk |
| `ModelIOManager.load_model(model_name, model_type, **kwargs)` | Load model with fallback | `model_name: str, model_type: str, **kwargs` | `ModelArtifact` | None |
| `ModelArtifact` | Container for model + metadata | `model: Any, metadata: ModelMetadata, filepath: Path` | `ModelArtifact` | None |
| `ModelMetadata` | Enhanced metadata with Optuna support | `model_type: str, version: str, created_at: str, **kwargs` | `ModelMetadata` | None |

</details>

<details><summary>🔍 Level 3 · Code walk-through</summary>

## ModelIOManager Initialization

The `ModelIOManager` class provides centralized model persistence with versioning and metadata tracking:

```python
class ModelIOManager:
    """
    Centralized model I/O management with versioning and metadata tracking.
    
    This manager handles:
    - Model saving with automatic versioning
    - Model loading with fallback mechanisms  
    - Metadata persistence and validation
    - Backward compatibility checking
    
    Parameters
    ----------
    base_path : Union[str, Path]
        Base directory for model storage
    version : str, default="1.0.0"
        EMUSES version for compatibility tracking
    
    Attributes
    ----------
    base_path : Path
        Resolved base directory path
    version : str
        EMUSES version string
    metadata_path : Path
        Directory for metadata storage
    """
    
    def __init__(self, base_path: Union[str, Path], version: str = "1.0.0"):
        """Initialize the Model I/O Manager."""
        self.base_path = Path(base_path)
        self.version = version
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create metadata directory
        self.metadata_path = self.base_path / ".metadata"
        self.metadata_path.mkdir(exist_ok=True)
```

**Key features:**
- **Automatic directory creation**: Sets up required folder structure
- **Version tracking**: Associates models with EMUSES version for compatibility
- **Metadata isolation**: Separate `.metadata/` directory for artifact tracking
- **Path resolution**: Handles both string and Path inputs consistently

## Enhanced Model Saving with Optuna Integration

The `save_model` method provides comprehensive model saving with rich metadata:

```python
def save_model(
    self,
    model: Any,
    model_name: str,
    model_type: str,
    config: Optional[Dict] = None,
    description: str = "",
    tags: Optional[List[str]] = None,
    prefix: str = "",
    force_version: Optional[str] = None,
    # Optuna-specific parameters
    optuna_study: Optional[Any] = None,
    optuna_trial: Optional[Any] = None,
    processed_params: Optional[Dict] = None,
    # Cross-validation parameters
    cv_score: Optional[float] = None,
    cv_scores: Optional[List[float]] = None,
    cv_folds: Optional[int] = None,
    fold_index: Optional[int] = None,
    # Target-specific parameters
    target_id: Optional[int] = None,
    **kwargs
) -> Path:
    """
    Save a model with comprehensive metadata tracking.
    
    Parameters
    ----------
    model : Any
        The model object to save (UMAP, HDBSCAN, sklearn pipeline, etc.)
    model_name : str
        Unique identifier for the model
    model_type : str
        Type of model ('umap', 'hdbscan', 'sklearn_pipeline', 'autoencoder')
    config : dict, optional
        Model configuration and hyperparameters
    description : str, optional
        Human-readable description of the model
    tags : List[str], optional
        Tags for model categorization and search
    prefix : str, optional
        Filename prefix for organization
    optuna_study : optuna.Study, optional
        Optuna study object for optimization tracking
    optuna_trial : optuna.Trial, optional
        Specific trial information
    cv_score : float, optional
        Cross-validation score
    cv_scores : List[float], optional
        Per-fold CV scores
    fold_index : int, optional
        Fold index for CV models
    target_id : int, optional
        Target variable identifier for multi-target models
    
    Returns
    -------
    Path
        Path to saved model file
    """
    if config is None:
        config = {}
    if tags is None:
        tags = []

    # Generate version-aware filename
    version_str = force_version or self.version
    joblib_version = joblib.__version__
    
    if prefix:
        filename = f"{prefix}_{model_name}_{model_type}_v{version_str}_joblib{joblib_version}.joblib"
    else:
        filename = f"{model_name}_{model_type}_v{version_str}_joblib{joblib_version}.joblib"
    
    filepath = self.base_path / filename
```

**Metadata enhancement:**
The system creates comprehensive metadata including Optuna study information:

```python
# Extract Optuna study information if available
optuna_study_info = None
if optuna_study is not None:
    best_trial_info = None
    if optuna_study.best_trial is not None:
        best_trial_info = OptunaTrial(
            trial_number=optuna_study.best_trial.number,
            value=optuna_study.best_trial.value,
            params=optuna_study.best_trial.params,
            user_attrs=dict(optuna_study.best_trial.user_attrs),
            system_attrs=dict(optuna_study.best_trial.system_attrs),
            state=str(optuna_study.best_trial.state),
            datetime_start=str(optuna_study.best_trial.datetime_start),
            datetime_complete=str(optuna_study.best_trial.datetime_complete),
            duration=(optuna_study.best_trial.duration.total_seconds() 
                     if optuna_study.best_trial.duration else 0.0)
        )
    
    optuna_study_info = OptunaStudy(
        study_name=optuna_study.study_name,
        direction=str(optuna_study.direction),
        best_value=optuna_study.best_value,
        best_trial=best_trial_info,
        n_trials=len(optuna_study.trials),
        sampler_name=type(optuna_study.sampler).__name__,
        pruner_name=type(optuna_study.pruner).__name__
    )

# Create comprehensive metadata
metadata = ModelMetadata(
    model_type=model_type,
    version=version_str,
    created_at=datetime.now().isoformat(),
    emuses_version=self.version,
    joblib_version=joblib_version,
    dependencies=self._get_dependencies(),
    config_hash=self._compute_config_hash(config),
    file_size=0,  # Will be updated after saving
    description=description,
    tags=tags,
    optuna_study=optuna_study_info,
    processed_params=processed_params,
    cv_score=cv_score,
    cv_scores=cv_scores,
    cv_folds=cv_folds,
    fold_index=fold_index,
    target_id=target_id
)
```

## **Optuna Timing Integration (Fixed)**

The Model I/O system now correctly captures optimization timing information, fixing the issue where `optimization_time` was always 0.0 in saved model metadata.

<details markdown="1">
<summary>🔧 **Optuna Timing Parameters**</summary>

**New Parameters for `save_model()`**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `optimization_time` | `Optional[float]` | `None` | Total Optuna optimization duration in seconds |
| `optuna_study` | `Optional[Any]` | `None` | Complete Optuna study object with trial history |
| `optuna_trial` | `Optional[Any]` | `None` | Best trial information and parameters |

**Usage Example**:
```python
# In optuna_cv.py - optimization_time now properly passed
optimization_start = time.time()
study.optimize(objective, n_trials=n_trials)
optimization_time = time.time() - optimization_start

# Save model with correct timing
model_manager.save_model(
    model=best_pipeline,
    model_name="best_pipeline_fold0",
    model_type="sklearn_pipeline",
    optuna_study=study,
    optuna_trial=study.best_trial,
    optimization_time=optimization_time,  # ✅ Now correctly captured
    config=best_params
)
```

**Result in Metadata**:
```json
{
    "optuna_study": {
        "study_name": "nested_optuna_cv_target_0_fold_1",
        "best_value": 0.2451,
        "n_trials": 50,
        "optimization_time": 7.76,
        "sampler_name": "TPESampler"
    }
}
```

**Fix Details**:
- **Problem**: `optimization_time` in saved model metadata was always 0.0
- **Root Cause**: Calculated optimization time was never passed to `save_model()` method  
- **Solution**: Added `optimization_time` parameter and updated `nested_optuna_cv()` to pass the value
- **Impact**: All future model saves will include accurate optimization timing

</details>

## Robust Model Loading with Fallback

The `load_model` method implements intelligent loading with multiple fallback strategies:

```python
def load_model(
    self,
    model_name: str,
    model_type: str,
    version: Optional[str] = None,
    prefix: str = "",
    strict_version: bool = False,
    target_id: Optional[int] = None,
    fold_index: Optional[int] = None,
    **kwargs
) -> Optional[ModelArtifact]:
    """
    Load a model with automatic fallback to compatible versions.
    
    Parameters
    ----------
    model_name : str
        Name of the model to load
    model_type : str
        Expected model type for validation
    version : str, optional
        Specific version to load (latest if None)
    prefix : str, optional
        Filename prefix to match
    strict_version : bool, default=False
        Whether to enforce exact version matching
    target_id : int, optional
        Target identifier for multi-target models
    fold_index : int, optional
        Fold index for CV models
    
    Returns
    -------
    ModelArtifact or None
        Container with model, metadata, and filepath
    """
    # Build candidate filenames with version hierarchy
    candidates = self._build_candidate_paths(
        model_name, model_type, version, prefix, target_id, fold_index
    )
    
    # Try loading candidates in priority order
    for candidate_path in candidates:
        try:
            if candidate_path.exists():
                # Load model using joblib
                model = joblib.load(candidate_path)
                
                # Load metadata
                metadata = self._load_metadata(candidate_path)
                
                # Validate compatibility
                if not self._validate_compatibility(metadata, model_type, strict_version):
                    logger.warning(f"Compatibility check failed for {candidate_path}")
                    continue
                
                logger.info(f"Successfully loaded model from {candidate_path}")
                return ModelArtifact(
                    model=model,
                    metadata=metadata,
                    filepath=candidate_path
                )
                
        except Exception as e:
            logger.warning(f"Failed to load model from {candidate_path}: {e}")
            continue
    
    logger.error(f"No compatible model found for {model_name} (type: {model_type})")
    return None
```

**Fallback strategy:**
1. **Exact match**: Try exact version and parameters
2. **Version compatibility**: Try compatible versions within major version
3. **Legacy compatibility**: Try older versions with compatibility checks
4. **Parameter flexibility**: Try models with different but compatible parameters

## Metadata Structure and Validation

The system uses structured metadata with comprehensive validation:

```python
@dataclass
class ModelMetadata:
    """Enhanced metadata for model artifacts with Optuna support."""
    
    # Core metadata
    model_type: str
    version: str
    created_at: str
    emuses_version: str
    joblib_version: str
    dependencies: Dict[str, str]
    config_hash: str
    file_size: int
    description: str = ""
    tags: List[str] = None

    # Optuna-specific metadata
    optuna_study: OptunaStudy = None
    raw_optuna_params: Dict[str, Any] = None
    processed_params: Dict[str, Any] = None

    # Cross-validation info
    cv_score: float = None
    cv_scores: List[float] = None
    cv_folds: int = None
    fold_index: int = None

    # Target-specific info for prediction models
    target_id: int = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
```

**Validation features:**
- **Type checking**: Validates model type matches expected type
- **Version compatibility**: Checks EMUSES and joblib version compatibility
- **Dependency tracking**: Records package versions for reproducibility
- **Configuration hashing**: Detects parameter changes via hash comparison

## Integration with EMUSES Pipeline

The ModelIOManager integrates seamlessly with all EMUSES pipeline stages:

### UMAP Stage Integration
```python
# In UMAPStage.run()
manager = ModelIOManager(self.config.output_folder)
umap_filepath = manager.save_model(
    model=best_umap_model,
    model_name=f"{prefix}umap_model" if prefix else "umap_model",
    model_type="umap",
    config={"best_params": best_params, "n_trials": n_trials},
    description=f"Best UMAP model from Bayesian search with {n_trials} trials",
    tags=["bayesian_optimization", "final_model"],
    optuna_study=study,
    optuna_trial=study.best_trial
)
```

### Prediction Stage Integration
```python
# In PredictionStage for CV models
for fold_idx, (train_idx, val_idx) in enumerate(cv_splits):
    # Train model for fold
    cv_pipeline.fit(X_train_fold, y_train_fold)
    
    # Save fold-specific model
    manager.save_model(
        model=cv_pipeline,
        model_name=f"{feature_set_name}_fold_{fold_idx}",
        model_type="sklearn_pipeline",
        cv_score=val_score,
        cv_scores=all_fold_scores,
        cv_folds=len(cv_splits),
        fold_index=fold_idx,
        target_id=target_idx,
        config=best_config,
        optuna_study=study
    )
```

### Loading with Fallback
```python
# Loading with automatic fallback
artifact = manager.load_model(
    model_name="umap_model",
    model_type="umap",
    prefix="best"
)

if artifact:
    umap_model = artifact.model
    print(f"Loaded: {artifact.metadata.description}")
    print(f"Optuna score: {artifact.metadata.optuna_study.best_value}")
else:
    logger.error("No compatible UMAP model found")
```

## Error Handling and Logging

The system provides comprehensive error handling and logging:

```python
def _handle_save_error(self, filepath: Path, error: Exception) -> None:
    """Handle model saving errors with detailed logging."""
    logger.error(f"Failed to save model to {filepath}: {error}")
    
    # Check common issues
    if "PermissionError" in str(error):
        logger.error("Permission denied - check file/directory permissions")
    elif "OSError" in str(error) and "No space left" in str(error):
        logger.error("Disk space exhausted - cannot save model")
    elif "MemoryError" in str(error):
        logger.error("Insufficient memory to save model")
    
    # Cleanup partial files
    if filepath.exists():
        try:
            filepath.unlink()
            logger.info(f"Cleaned up partial file: {filepath}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup {filepath}: {cleanup_error}")

def _validate_compatibility(self, metadata: ModelMetadata, expected_type: str, 
                          strict_version: bool) -> bool:
    """Validate model compatibility with current environment."""
    
    # Check model type
    if metadata.model_type != expected_type:
        logger.warning(f"Model type mismatch: expected {expected_type}, got {metadata.model_type}")
        return False
    
    # Check version compatibility
    if strict_version and metadata.emuses_version != self.version:
        logger.warning(f"Version mismatch: expected {self.version}, got {metadata.emuses_version}")
        return False
    
    # Check critical dependencies
    critical_deps = ["numpy", "scikit-learn", "umap-learn", "hdbscan"]
    current_deps = self._get_dependencies()
    
    for dep in critical_deps:
        if dep in metadata.dependencies and dep in current_deps:
            if self._is_incompatible_version(metadata.dependencies[dep], current_deps[dep]):
                logger.warning(f"Incompatible {dep} version: {metadata.dependencies[dep]} vs {current_deps[dep]}")
                return False
    
    return True
```

**Key advantages:**
- **Comprehensive tracking**: Full provenance from raw data to final models
- **Reproducibility**: Exact parameter and dependency recording
- **Fault tolerance**: Multiple fallback strategies for robust loading
- **Pipeline integration**: Seamless integration with all EMUSES stages
- **Optuna integration**: Native support for hyperparameter optimization tracking

</details>
