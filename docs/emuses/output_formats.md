# EMUSES Output Formats Comprehensive Guide

**Complete reference for all EMUSES analysis results, prediction formats, and data export options**

This guide provides structured information about EMUSES outputs across different user experience levels, from quick start references to detailed format specifications for advanced integration.

## 📋 **Quick Reference for New Users**

Essential output information for getting started with EMUSES results.

### **Key Output Files**

| File Type | Purpose | Example Name | When Generated |
|-----------|---------|--------------|----------------|
| **Predictions CSV** | Main prediction results | `validation_predictions_20250824_143022.csv` | All inference runs |
| **Confidence CSV** | Model confidence scores | `validation_confidence_20250824_143022.csv` | When available |
| **Performance JSON** | Model validation metrics | `performance_metrics.json` | Validation mode |
| **Model Files** | Trained pipeline components | `best_pipeline_fold0.joblib` | Training runs |

### **Basic CSV Structure**

**Single Target** (most common):
```csv
sample_id,target_0_ensemble_prediction,target_0_confidence_score
sample_0000,1.234,0.85
sample_0001,2.456,0.92
```

**Multi-Target**:
```csv
sample_id,target_0_ensemble_prediction,target_1_ensemble_prediction,target_0_confidence_score,target_1_confidence_score
sample_0000,1.234,5.678,0.85,0.92
sample_0001,2.456,6.789,0.88,0.91
```

<details markdown="1">
<summary>📊 **Level 2 · Complete Format Specifications**</summary>

## **CSV Prediction Formats**

### **Column Naming Convention**
All prediction outputs follow consistent target-specific naming:

- **Pattern**: `{target}_{metric_type}`
- **Target Names**: `target_0`, `target_1`, etc. (single-target always uses `target_0`)
- **Metric Types**: `ensemble_prediction`, `confidence_score`, `{model_name}`

### **Single-Target Results Structure**
Even single-target results use target_0_ prefixing for consistency:

```csv
sample_id,target_0_ensemble_prediction,target_0_confidence_score,target_0_model_1,target_0_model_2
sample_0000,1.234,0.85,1.123,1.345
sample_0001,2.456,0.92,2.341,2.567
sample_0002,3.789,0.78,3.654,3.890
```

**Column Descriptions**:
- `sample_id`: Sequential sample identifier (sample_0000, sample_0001, ...)
- `target_0_ensemble_prediction`: Averaged prediction across all models for the target
- `target_0_confidence_score`: Model ensemble confidence (0.0-1.0, higher = more confident)
- `target_0_{model_name}`: Individual model predictions for transparency

### **Multi-Target Results Structure**
Multiple targets generate target-specific column groups:

```csv
sample_id,target_0_ensemble_prediction,target_1_ensemble_prediction,target_2_ensemble_prediction,target_0_confidence_score,target_1_confidence_score,target_2_confidence_score,target_0_fold_0,target_1_fold_0,target_2_fold_0
sample_0000,1.234,10.567,0.789,0.85,0.92,0.76,1.123,10.234,0.756
sample_0001,2.456,11.890,0.834,0.88,0.89,0.82,2.341,11.567,0.801
```

**Organization Pattern**:
1. **Ensemble predictions** for all targets first
2. **Confidence scores** for all targets second  
3. **Individual model predictions** grouped by target

### **Confidence CSV Format** (when available)
Separate confidence-only file with simplified structure:

```csv
sample_id,target_0_confidence_score,target_1_confidence_score
sample_0000,0.85,0.92
sample_0001,0.88,0.89
sample_0002,0.78,0.86
```

</details>

<details markdown="1">
<summary>🔌 **Level 3 · API Integration & Advanced Formats**</summary>

## **API Response Structure**

### **InferenceStage Results Format**
The unified multi-target architecture returns consistent structure:

```python
{
    "mode": "validation",
    "status": "completed", 
    "samples_processed": 214,
    "embeddings_shape": [214, 2],
    "target_results": {
        "target_0": {
            "ensemble_predictions": [1.234, 2.456, 3.789],
            "confidence_scores": [0.85, 0.92, 0.78],
            "individual_predictions": {
                "fold_0": [1.123, 2.341, 3.654],
                "fold_1": [1.345, 2.567, 3.890]
            },
            "model_count": 2,
            "model_names": ["fold_0", "fold_1"]
        }
    },
    "target_count": 1,
    "model_count": 2,
    "individual_predictions": {
        "fold_0": [1.123, 2.341, 3.654],
        "fold_1": [1.345, 2.567, 3.890]
    },
    "model_names": ["fold_0", "fold_1"],
    "performance_breakdown": {
        "data_load_ms": 10.0,
        "transform_ms": 50.0,
        "prediction_ms": 100.0,
        "total_ms": 490.0,
        "throughput_samples_per_sec": 440.4
    }
}
```

### **Validation Metrics Structure**
When ground truth is available, validation metrics are included:

```python
"validation_metrics": {
    "target_0": {
        "r2_score": -31.835,
        "mse": 2147.34,
        "mae": 97.547,
        "rmse": 97.547
    },
    "_summary": {  # Multi-target only
        "target_count": 2,
        "mean_r2_score": 0.123,
        "std_r2_score": 0.045
    }
}
```

**Validation Metrics Explanation**:
- **r2_score**: Coefficient of determination (1.0 = perfect, 0.0 = no better than mean, negative = worse than mean)
- **mse**: Mean Squared Error (lower is better)
- **mae**: Mean Absolute Error (lower is better)  
- **rmse**: Root Mean Squared Error (lower is better)

### **Model Metadata Structure** (Enhanced with optimization_time)
Model files now include complete optimization timing:

```python
{
    "model_type": "sklearn_pipeline",
    "version": "1.0.0",
    "created_at": "2025-08-24T15:36:27.758122Z",
    "optuna_study": {
        "study_name": "nested_optuna_cv_target_0_fold_1",
        "direction": "StudyDirection.MAXIMIZE",
        "best_value": 0.2451,
        "n_trials": 50,
        "optimization_time": 7.76,  # ✅ Now correctly populated
        "sampler_name": "TPESampler",
        "best_trial": {
            "trial_number": 23,
            "value": 0.2451,
            "params": {...}
        }
    }
}
```

</details>

<details markdown="1">
<summary>🚧 **Future Enhancements - Statistical Maps Implementation**</summary>

## **Statistical Maps Integration (Planned)**

**Status**: Ready for implementation - placeholders prepared

### **Planned Output Structure**
```
analysis_results/
├── predictions.csv                    # Current implementation ✅
├── confidence.csv                     # Current implementation ✅
├── validation_metrics.json            # Current implementation ✅
└── statistical_maps/                  # 🚧 PLANNED
    ├── stat_map_target_0.nii.gz      # NIfTI format statistical map
    ├── stat_map_target_0.png         # Visualization 
    ├── effect_size_map.nii.gz        # Effect size calculations
    └── thresholded_map.nii.gz        # Statistical significance thresholding
```

### **Implementation Roadmap**

**TODO - Phase 1: Core Statistical Mapping**
- [ ] **Grid Predictions**: Dense spatial prediction grids over brain space
- [ ] **Effect Size Calculations**: Cohen's d, Mann-Whitney U, t-test statistics
- [ ] **Statistical Thresholding**: Multiple correction methods (FDR, Bonferroni)

**TODO - Phase 2: Format Support**  
- [ ] **NIfTI Export**: Neuroimaging-compatible statistical maps
- [ ] **PNG Visualizations**: Interactive and static map visualizations
- [ ] **Grid Metadata**: Spatial coordinate mappings and reference frames

**TODO - Phase 3: API Integration**
- [ ] **REST Endpoints**: `GET /api/v1/analysis/{job_id}/statistical_maps`
- [ ] **CLI Access**: `emuses analysis generate-maps model.pkl data.csv`
- [ ] **Format Options**: Support multiple export formats

### **Integration Points Ready**

**Existing Functions to Leverage**:
- `input_matrix_stat_map()` - Effect size calculations with multiple test types
- `calculate_correlation_grid()` - Correlation analysis for embeddings  
- `plot_clustering_interactive_with_hover()` - Interactive visualization
- `run_kernel_heatmap_analysis()` - Complete statistical analysis pipeline
- `run_heatmap_analysis()` - Alternative statistical analysis approach

**Configuration Structure (Prepared)**:
```python
statistical_maps_config = {
    "enable_statistical_maps": True,      # Feature flag
    "grid_resolution": 64,                # Spatial resolution 
    "effect_size_method": "cohens_d",     # Statistical test type
    "threshold_method": "fdr",            # Multiple comparisons correction
    "output_formats": ["nifti", "png"],   # Export formats
    "visualization_options": {
        "colormap": "viridis",
        "threshold": 0.05
    }
}
```

**Related Documentation**:
- Implementation planning: `dev-docs/analysis-api/plan.md` (Task 0B.1)
- Function specifications: `dev-docs/analysis-api/existing_work_assessment.md`
- Architecture context: `dev-docs/analysis-api/context.md`

</details>

## **Integration Examples**

### **Python API Usage**
```python
from emuses.pipelines.inference_stage import InferenceStage

# Results follow consistent target_results structure
results = inference_stage.run(context)
target_0_predictions = results['target_results']['target_0']['ensemble_predictions']
```

### **CSV Processing**
```python
import pandas as pd

# Load EMUSES predictions - consistent column naming
df = pd.read_csv('validation_predictions_20250824_143022.csv')
ensemble_preds = df['target_0_ensemble_prediction']
confidence = df['target_0_confidence_score']
```

### **Multi-Target Processing**
```python
# Handle both single and multi-target consistently  
for target_name, target_data in results['target_results'].items():
    predictions = target_data['ensemble_predictions']
    confidence = target_data['confidence_scores']
    print(f"{target_name}: {len(predictions)} predictions")
```

---

**Last Updated**: 2025-08-24  
**Version**: Unified Multi-Target Architecture  
**Related**: [InferenceStage Documentation](inference_stage.md), [Model I/O Guide](utils/model_io.md)