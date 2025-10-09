# InferenceStage - Unified Multi-Target Prediction

**Unified prediction processing system that handles both single-target and multi-target scenarios through a consistent architecture**

The InferenceStage implements a streamlined approach where single-target prediction is treated as multi-target with n=1 targets, eliminating dual workflows and improving maintainability.

## **Essential Overview**

**Key Architecture Principles**:
- **Single Workflow**: One prediction pipeline handles all cases (single-target = multi-target with n=1)
- **Consistent Results**: All outputs use `target_results` structure with target-specific keys
- **Automatic Assignment**: Models without explicit target field are assigned to 'target_0'
- **Unified CSV Format**: Target-prefixed columns for all scenarios (target_0_ensemble_prediction, etc.)

<details markdown="1">
<summary>🛠️ **Level 2 · Key API Reference**</summary>

| Method | Purpose | Inputs | Outputs | Side Effects |
|--------|---------|--------|---------|--------------|
| `InferenceStage.__init__(config)` | Initialize inference stage | `config: PipelineConfig` | `InferenceStage` | None |
| `InferenceStage.run(context, progress_queue)` | Execute complete inference pipeline | `context: dict, progress_queue: Optional[Queue]` | `dict` | Loads models, generates predictions, saves results |
| `InferenceStage._predict(embeddings, models)` | Core prediction processing | `embeddings: ndarray, models: dict` | `dict` | None |
| `InferenceStage._save_results(results, output_format)` | Save predictions in specified format | `results: dict, output_format: str` | `dict` | Creates CSV files |

## **Result Structure Format**

All inference results follow consistent `target_results` structure:

```python
{
    "target_results": {
        "target_0": {
            "ensemble_predictions": np.array([1.234, 2.456, 3.789]),
            "confidence_scores": np.array([0.85, 0.92, 0.78]),
            "individual_predictions": {
                "model_1": np.array([1.123, 2.341, 3.654]),
                "model_2": np.array([1.345, 2.567, 3.890])
            },
            "model_count": 2,
            "model_names": ["model_1", "model_2"]
        }
        # Additional targets for multi-target scenarios
    },
    "target_count": 1,
    "model_count": 2,
    "individual_predictions": {...},  # Aggregated across targets
    "model_names": [...]              # Aggregated model list
}
```

</details>

<details markdown="1">
<summary>🔍 **Level 3 · Architecture & Implementation Details**</summary>

## **Unified Multi-Target Processing**

### **Single Workflow Architecture**
The InferenceStage eliminates the complexity of dual prediction workflows:

```python
def _predict(self, embeddings, models):
    """
    Unified prediction using multi-target processing.
    Single-target is handled as multi-target with n=1.
    """
    prediction_models = models.get('prediction_models', [])
    
    # Group models by target (assigns 'target_0' if no target specified)
    models_by_target = self._group_models_by_target(prediction_models)
    n_targets = len(models_by_target)
    
    # Process predictions with target-specific ensembles
    target_results = self._predict_multi_target(embeddings, models_by_target)
    
    # Format results in consistent target_results structure
    return self._format_multi_target_results(target_results)
```

### **Model Target Assignment**
Models without explicit `target` field are automatically assigned:

```python
def _group_models_by_target(self, prediction_models):
    """Group models by target, assigning 'target_0' for legacy models."""
    models_by_target = {}
    
    for model_info in prediction_models:
        target = model_info.get('target', 'target_0')  # Default assignment
        if target not in models_by_target:
            models_by_target[target] = []
        models_by_target[target].append(model_info)
    
    return models_by_target
```

### **CSV Output Generation**
Unified CSV method handles both single and multi-target:

```python
def _save_predictions_csv(self, results, output_file):
    """Save predictions with target-specific columns."""
    target_results = results['target_results']
    
    # Add ensemble predictions per target
    for target in sorted(target_results.keys()):
        target_result = target_results[target]
        data[f'{target}_ensemble_prediction'] = target_result['ensemble_predictions']
        data[f'{target}_confidence_score'] = target_result.get('confidence_scores', [0.0] * n_samples)
```

### **Legacy Model Compatibility**
Models from older EMUSES versions work seamlessly:

```python
# Legacy model format (no target field)
legacy_model = {
    'model': trained_sklearn_pipeline,
    'fold_info': 'fold_0'
    # No 'target' field - automatically assigned to 'target_0'
}

# Modern multi-target format
modern_model = {
    'model': trained_sklearn_pipeline,
    'target': 'cognitive_performance',
    'fold_info': 'fold_0'
}
```

## **Validation Metrics Processing**

### **Multi-Target Validation**
Validation metrics are calculated per target:

```python
def _calculate_multi_target_validation_metrics(self, target_results, ground_truth_labels):
    """Calculate validation metrics for each target."""
    validation_metrics = {}
    
    for target_idx, target in enumerate(sorted(target_results.keys())):
        target_predictions = target_results[target]['ensemble_predictions']
        target_ground_truth = ground_truth_labels[:, target_idx]
        
        metrics = self._calculate_validation_metrics(target_predictions, target_ground_truth)
        validation_metrics[target] = metrics
        
        logger.info(f"Validation metrics calculated for {target}: R² = {metrics.get('r2_score', 'N/A'):.3f}")
    
    return validation_metrics
```

### **Single-Target Validation**
Single-target validation uses the same multi-target infrastructure:

```python
# Single-target ground truth automatically becomes multi-target format
single_ground_truth = np.array([1.0, 2.0, 3.0])           # Shape: (3,)
multi_format = single_ground_truth.reshape(-1, 1)         # Shape: (3, 1)

# Processed identically through multi-target validation
validation_metrics = stage._calculate_multi_target_validation_metrics(
    prediction_results['target_results'], 
    multi_format
)
```

</details>

<details markdown="1">
<summary>⚙️ **Advanced Configuration & Usage**</summary>

## **Pipeline Integration**

### **Context Requirements**
InferenceStage expects specific context structure:

```python
context = {
    'trained_models': {
        'prediction_models': [
            {
                'model': sklearn_pipeline,
                'target': 'target_name',      # Optional - defaults to 'target_0'
                'fold_info': 'fold_0',
                'feature_type': 'raw_only'    # Optional metadata
            }
        ],
        'umap_model': umap_model,            # For feature transformation
        'scaling_params': {...}              # Feature scaling information
    },
    'features': feature_matrix,              # Input features for prediction
    'labels': labels_matrix,                 # Ground truth for validation (optional)
    'output_folder': Path('/path/to/output') # Results directory
}
```

### **Performance Monitoring**
InferenceStage tracks detailed performance metrics:

```python
performance_data = {
    'data_load_duration_ms': 10.0,
    'transform_duration_ms': 50.0,
    'prediction_duration_ms': 100.0,
    'total_duration_ms': 490.0,
    'throughput_samples_per_sec': 440.4
}
```

### **Error Handling**
Robust error handling for various failure modes:

```python
try:
    results = stage.run(context, progress_queue)
except KeyError as e:
    logger.error(f"Missing required context key: {e}")
    raise
except Exception as e:
    logger.error(f"Inference pipeline execution failed: {e}")
    raise
```

## **Output File Management**

### **Automatic File Generation**
InferenceStage creates timestamped output files:

```python
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_files = {
    'predictions_csv': f'{mode}_predictions_{timestamp}.csv',
    'confidence_csv': f'{mode}_confidence_{timestamp}.csv',
    'performance_json': f'{mode}_performance_{timestamp}.json'
}
```

### **Output Format Options**
Multiple output formats supported:

- **CSV**: Human-readable predictions and confidence scores
- **NPY**: NumPy arrays for programmatic access
- **JSON**: Structured metadata and performance metrics

</details>

## **Usage Examples**

### **Basic Inference**
```python
from emuses.pipelines.inference_stage import InferenceStage

# Initialize stage
config = PipelineConfig(...)
stage = InferenceStage(config)

# Run inference
results = stage.run(context)

# Access predictions
target_0_predictions = results['target_results']['target_0']['ensemble_predictions']
confidence_scores = results['target_results']['target_0']['confidence_scores']
```

### **Multi-Target Processing**
```python
# Process all targets
for target_name, target_data in results['target_results'].items():
    predictions = target_data['ensemble_predictions']
    model_count = target_data['model_count']
    print(f"{target_name}: {len(predictions)} predictions from {model_count} models")
```

### **Validation Mode**
```python
# With ground truth labels
context['labels'] = ground_truth_matrix
results = stage.run(context)

# Access validation metrics
for target, metrics in results['validation_metrics'].items():
    r2_score = metrics['r2_score']
    print(f"{target} R²: {r2_score:.3f}")
```

---

**Related Documentation**: [Output Formats Guide](output_formats.md), [Model I/O System](utils/model_io.md)
**Architecture Notes**: Unified design eliminates ~90 lines of duplicate code while maintaining full functionality