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
| **Heatmap Arrays** | Spatial analysis grids | `prediction_values.npy`, `correlation_values_pearson.npy` | Analysis enabled |
| **Effect Size Maps** | Statistical effect maps | `effect_size_map_target_0_cluster_1_high_1.csv` | Analysis enabled |
| **Heatmap Visualizations** | Base analysis plots | `prediction_heatmap_target_0.png` | Analysis enabled |

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
<summary>📊 **Statistical Analysis Outputs - Advanced Analysis Features**</summary>

## **Statistical Analysis Integration** ✅

**Status**: Implemented and Production Ready

### **Complete Analysis Output Structure**
```
target_0/
├── prediction-heatmaps/               # ✅ Prediction analysis on embedding space
│   ├── prediction_values.npy          # Raw predictions on 100×100 grid
│   ├── confidence_values.npy          # Model confidence scores 
│   ├── combined_values.npy            # Prediction×confidence combined values
│   ├── grid_coordinates.npy           # Spatial grid coordinates
│   └── prediction_metadata.json       # Analysis parameters and settings
├── correlation-heatmaps/              # ✅ UMAP embedding correlation analysis
│   ├── correlation_values_pearson.npy     # Pearson correlation with targets
│   ├── correlation_values_spearman.npy    # Spearman correlation with targets  
│   ├── correlation_values_point_biserial.npy # Point-biserial correlation
│   ├── grid_coordinates.npy           # Shared spatial grid coordinates
│   └── correlation_metadata.json      # Sigma values and correlation methods
├── prediction-effects/                # ✅ Statistical effect size maps from predictions
│   ├── effect_size_map_target_0_cluster_{N}_{high|low}_{N}.csv # Per-cluster effects
│   ├── effect_size_map_target_0_cluster_{N}_{high|low}_{N}.png.html # Interactive visualizations
│   ├── high_significance_regions.npy  # Grid indices of high-significance regions
│   ├── low_significance_regions.npy   # Grid indices of low-significance regions
│   ├── cluster_visualizations/         # Cluster overlay visualizations
│   └── metadata.json                  # Clustering parameters and thresholds
├── correlation-effects/               # ✅ Statistical effect size maps from correlations  
│   ├── effect_size_map_target_0_cluster_{N}_high_{N}.csv # High-correlation clusters only
│   ├── effect_size_map_target_0_cluster_{N}_high_{N}.png.html # Interactive visualizations
│   ├── high_significance_regions.npy  # Grid indices of significant correlations
│   ├── cluster_visualizations/         # Correlation cluster overlays
│   └── metadata.json                  # Analysis parameters and methods
└── heatmap_visualizations/            # ✅ Base heatmap visualizations
    ├── prediction_heatmap_target_0.png # Prediction heatmap with UMAP scatter overlay
    └── correlation_heatmap_target_0.png # Correlation heatmap with UMAP scatter overlay
```

### **Analysis Methodology**

**Two-Heatmap Scientific Approach**:
- **Prediction Analysis**: Uses trained models to analyze predictive patterns across embedding space
- **Correlation Analysis**: Analyzes UMAP manifold structure correlation with target variables
- **Separation Rationale**: Distinguishes intrinsic data topology from learned predictive relationships

**Effect Size Map Generation**:
- **Significance Detection**: Identifies high/low significance regions using percentile thresholds (default: 5th/95th percentiles)
- **Clustering**: HDBSCAN clustering on significant regions for spatial grouping
- **Statistical Analysis**: Per-cluster effect size calculations with Cohen's d and statistical tests
- **Format Matching**: Output format matches input format (CSV→CSV, NIfTI→NIfTI)

### **Implemented Features** ✅

**Grid Analysis**:
- ✅ **Dense Spatial Grids**: 100×100 coordinate grids over UMAP embedding space
- ✅ **Prediction Mapping**: Trained model predictions across entire embedding space  
- ✅ **Correlation Mapping**: Multiple correlation methods (Pearson, Spearman, Point-biserial)

**Statistical Processing**:
- ✅ **Effect Size Calculations**: Cohen's d, statistical significance testing per cluster
- ✅ **Significance Thresholding**: Configurable percentile-based thresholds
- ✅ **Cluster Detection**: HDBSCAN-based spatial clustering of significant regions

**Visualization Integration**:
- ✅ **Base Heatmaps**: Static PNG visualizations with UMAP scatter overlays
- ✅ **Interactive Maps**: HTML visualizations for per-cluster exploration  
- ✅ **Cluster Overlays**: Highlighted cluster regions on heatmap backgrounds

### **Analysis Configuration**

**Default Settings**:
```python
analysis_config = {
    "grid_size": 100,                   # 100×100 spatial resolution
    "effect_percentile_threshold": 5.0, # 5th/95th percentile significance
    "correlation_methods": ["pearson", "spearman", "point_biserial"],
    "sigma_method": "percentile",        # Correlation sigma calculation
    "sigma_percentile": 25.0,           # 25th percentile for sharp patterns
    "significance_sources": {
        "prediction": ["high", "low"],   # Both high and low prediction regions
        "correlation": ["high"]          # Only high correlation regions
    }
}
```

**Customization Options**:
- **Grid Resolution**: Configurable grid size (default 100×100)
- **Significance Thresholds**: Adjustable percentile cutoffs  
- **Correlation Methods**: Selectable correlation approaches
- **Effect Size Methods**: Multiple statistical test options

### **Integration with Analysis API**

**REST Endpoints** (FastAPI):
- `POST /api/v1/analysis/heatmaps` - Generate prediction and correlation heatmaps
- `POST /api/v1/analysis/statistical-maps` - Create statistical effect size maps

**CLI Integration**:
- Analysis runs automatically during standard pipeline execution
- Outputs integrated into model registry system for sharing and reproducibility

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

**Last Updated**: 2025-08-31  
**Version**: Complete Statistical Analysis Integration  
**Related**: [HeatmapStage Documentation](heatmap_stage.md), [InferenceStage Documentation](inference_stage.md), [Model I/O Guide](utils/model_io.md)