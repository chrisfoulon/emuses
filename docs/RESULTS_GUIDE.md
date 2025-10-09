# 📊 Understanding Your EMUSES Analysis Results

**A comprehensive guide to interpreting and using EMUSES analysis outputs**

After running EMUSES analysis, you'll get a rich set of outputs designed to provide deep insights into your data. This guide explains what each file means and how to use them effectively for your research.

## 🎯 **Quick Results Overview**

When EMUSES completes analysis, you'll find your results organized into several key categories:

### **Essential Output Categories**
| Category | Purpose | Key Files | When You'll Use It |
|----------|---------|-----------|-------------------|
| **Prediction Models** | Trained models for inference | `*.joblib` files | Applying models to new data |
| **Analysis Visualizations** | Spatial analysis results | `prediction-heatmaps/`, `correlation-heatmaps/` | Understanding data patterns |
| **Effect Size Maps** | Statistical significance findings | `prediction-effects/`, `correlation-effects/` | Scientific interpretation |
| **Interactive Plots** | Exploratory visualizations | `*.html` files | Data exploration |
| **Performance Metrics** | Model validation results | `*.json`, `*.csv` | Assessing model quality |

### **Navigating Your Results Folder**
```
your_analysis_results/
├── 📁 target_0/                    # Primary analysis target
│   ├── 📊 prediction-heatmaps/     # Spatial model predictions  
│   ├── 📊 correlation-heatmaps/    # UMAP correlation analysis
│   ├── 📈 prediction-effects/      # Statistical effect maps from predictions
│   ├── 📈 correlation-effects/     # Statistical effect maps from correlations
│   ├── 🎨 heatmap_visualizations/  # Base heatmap images
│   └── 🔍 interactive_plots/       # Interactive exploration tools
├── 🤖 *.joblib                     # Trained models (UMAP, HDBSCAN, prediction)
├── 📋 validation_*.csv             # Prediction results and confidence scores  
└── 📊 *.html                       # Optimization and clustering reports
```

<details markdown="1">
<summary>📋 **File-by-File Technical Reference**</summary>

## **Spatial Analysis Outputs**

### **prediction-heatmaps/ Directory**
Contains spatial analysis of model predictions across your embedding space:

| File | Data Type | Content | Usage |
|------|-----------|---------|-------|
| `prediction_values.npy` | NumPy array (100×100) | Raw model predictions on spatial grid | Load with `np.load()` for custom analysis |
| `confidence_values.npy` | NumPy array (100×100) | Model confidence scores (0-1 range) | Identify high/low confidence regions |
| `combined_values.npy` | NumPy array (100×100) | Prediction × confidence product | Main heatmap for interpretation |
| `grid_coordinates.npy` | NumPy array (100×100×2) | X,Y coordinates for each grid point | Map grid indices to embedding coordinates |
| `prediction_metadata.json` | JSON | Analysis parameters and model info | Understand analysis settings used |

**Loading Example**:
```python
import numpy as np
import json

# Load prediction heatmap
predictions = np.load('target_0/prediction-heatmaps/combined_values.npy')
coordinates = np.load('target_0/prediction-heatmaps/grid_coordinates.npy')

# Load analysis metadata
with open('target_0/prediction-heatmaps/prediction_metadata.json') as f:
    metadata = json.load(f)
    print(f"Analysis used {metadata['model_count']} models")
```

### **correlation-heatmaps/ Directory**
Contains correlation analysis between UMAP embedding space and your target variables:

| File | Data Type | Content | Usage |
|------|-----------|---------|-------|
| `correlation_values_pearson.npy` | NumPy array (100×100) | Pearson correlation coefficients | Linear relationship analysis |
| `correlation_values_spearman.npy` | NumPy array (100×100) | Spearman correlation coefficients | Monotonic relationship analysis |
| `correlation_values_point_biserial.npy` | NumPy array (100×100) | Point-biserial correlations | Binary target analysis |
| `correlation_metadata.json` | JSON | Sigma values and correlation methods | Analysis parameters used |

**Key Technical Details**:
- **Grid Resolution**: 100×100 points across embedding space
- **Coordinate System**: Normalized UMAP embedding space (0-1 range)
- **Correlation Methods**: Multiple approaches for robust analysis
- **Sigma Calculation**: 25th percentile for sharp, localized patterns

### **Effect Size Maps** (prediction-effects/ & correlation-effects/)

Statistical significance analysis with per-cluster effect size calculations:

| File Pattern | Content | Scientific Meaning |
|--------------|---------|-------------------|
| `effect_size_map_target_0_cluster_{N}_{high\|low}_{N}.csv` | Per-cluster statistical results | Effect sizes for significant spatial regions |
| `*.png.html` | Interactive cluster visualizations | Explore clusters with hover details |
| `high_significance_regions.npy` | Grid indices | Locations of statistically significant regions |
| `low_significance_regions.npy` | Grid indices | Locations of low significance (prediction only) |
| `metadata.json` | Analysis parameters | Clustering and statistical methods used |

**Effect Size Map CSV Structure**:
```csv
feature_name,effect_size,p_value,significant,cluster_info
feature_001,0.845,0.003,True,"High prediction cluster 1"
feature_002,0.234,0.156,False,"High prediction cluster 1"
...
```

## **Model Files & Performance Data**

### **Trained Models**
| File Pattern | Model Type | Usage |
|--------------|------------|--------|
| `best_umap_model_*.joblib` | UMAP dimensionality reduction | Apply to new data for embedding |
| `hdbscan_model_*.joblib` | HDBSCAN clustering | Cluster assignment for new samples |
| `best_pipeline_fold*.joblib` | Prediction models (per CV fold) | Generate predictions for new data |
| `input_scaler.joblib` | Data preprocessing scaler | Normalize new data before analysis |

### **Prediction Results**  
| File | Content | Usage |
|------|---------|-------|
| `validation_predictions_*.csv` | Model predictions with confidence | Main results for scientific interpretation |
| `validation_confidence_*.csv` | Confidence scores only | Assess prediction reliability |
| `validation_metadata_*.json` | Analysis metadata | Understand analysis configuration |

**Prediction CSV Structure**:
```csv
sample_id,target_0_ensemble_prediction,target_0_confidence_score
sample_0000,1.234,0.85
sample_0001,2.456,0.92
```

## **Visualization Files**

### **Static Visualizations**
| File | Content | Usage |
|------|---------|-------|
| `heatmap_visualizations/prediction_heatmap_target_0.png` | Prediction heatmap with UMAP scatter | Publication-ready visualization |
| `heatmap_visualizations/correlation_heatmap_target_0.png` | Correlation heatmap with scatter overlay | Scientific interpretation |

### **Interactive Reports**
| File | Content | Usage |
|------|---------|-------|
| `interactive_plots/interactive_clustering_target_0.html` | Interactive cluster exploration | Data exploration and quality assessment |
| `optimization_history.html` | Hyperparameter optimization results | Understand model selection process |
| `best_clustering.html` | Clustering analysis results | Validate clustering quality |

</details>

<details markdown="1">
<summary>🔬 **Scientific Interpretation & Research Applications**</summary>

## **Understanding Analysis Methodologies**

### **Two-Heatmap Scientific Approach**
EMUSES uses a dual analysis strategy to separate different aspects of your data:

**Prediction Analysis** (`prediction-heatmaps/`, `prediction-effects/`):
- **Purpose**: Shows how trained models behave across embedding space
- **Scientific Meaning**: Reveals regions where your models make consistent predictions
- **Research Application**: Identify areas of high/low predictive power for your research question

**Correlation Analysis** (`correlation-heatmaps/`, `correlation-effects/`):
- **Purpose**: Analyzes UMAP manifold structure correlation with targets
- **Scientific Meaning**: Shows intrinsic data topology relationships
- **Research Application**: Understand underlying data patterns independent of model training

### **Effect Size Map Interpretation**

**Statistical Workflow**:
1. **Significance Detection**: Identifies regions using percentile thresholds (default: 5th/95th percentiles)
2. **Spatial Clustering**: Groups significant regions using HDBSCAN
3. **Effect Size Calculation**: Computes Cohen's d and statistical significance per cluster
4. **Output Generation**: Creates per-cluster effect maps matching your input format

**Key Interpretation Guidelines**:
- **High Significance Regions**: Areas with strong relationships to your research variables
- **Effect Size Magnitude**: 
  - Small effect: 0.2-0.5
  - Medium effect: 0.5-0.8  
  - Large effect: 0.8+
- **Statistical Significance**: P-values adjusted for multiple comparisons
- **Cluster Coherence**: Spatially connected regions of consistent effects

### **Research Workflow Integration**

**For Neuroimaging Research**:
1. **Effect Size Maps** → Identify brain regions with significant relationships
2. **Correlation Heatmaps** → Understand intrinsic network structure
3. **Prediction Models** → Apply findings to new datasets
4. **Interactive Plots** → Explore and validate results

**For Other Scientific Domains**:
- **Genomics**: Identify gene expression patterns and regulatory networks
- **Ecology**: Understand species distribution patterns and environmental relationships  
- **Social Sciences**: Analyze behavioral patterns and demographic relationships
- **Economics**: Identify market patterns and economic indicators

### **Publication Guidelines**

**Reporting Results**:
- **Methods**: Document EMUSES version, parameters, and analysis settings from metadata files
- **Results**: Report effect sizes, confidence intervals, and statistical significance
- **Visualization**: Use heatmap images and interactive plots for figure preparation
- **Reproducibility**: Share model files and configuration for replication

**Statistical Considerations**:
- **Multiple Comparisons**: Effect size maps include appropriate corrections
- **Cross-Validation**: Prediction results based on robust nested CV
- **Confidence Assessment**: Use confidence scores to report prediction reliability
- **Effect Size Interpretation**: Report both statistical and practical significance

## **Troubleshooting & Common Issues**

### **File Loading Problems**
```python
# Common loading patterns
import numpy as np
import pandas as pd
import json

# For NumPy arrays (.npy files)
data = np.load('path/to/file.npy')

# For CSV files with proper encoding
df = pd.read_csv('path/to/file.csv', encoding='utf-8')

# For JSON metadata
with open('path/to/metadata.json', 'r', encoding='utf-8') as f:
    metadata = json.load(f)
```

### **Missing Files**
If expected files are missing:
1. **Check analysis completion**: Look for error logs in analysis output
2. **Verify input data**: Ensure input data was properly formatted
3. **Review parameters**: Some outputs depend on specific analysis settings

### **Interpretation Questions**
- **Low effect sizes**: May indicate subtle relationships or need for different analysis approaches
- **High prediction confidence with low correlations**: Suggests model overfitting or data-specific patterns
- **Missing clusters in effects**: Some regions may not meet significance thresholds

</details>

---

**Next Steps**: 
- 🚀 **New to EMUSES?** → Try our [Quick Start Guide](QUICK_START.md) for your first analysis
- 📖 **Want more details?** → See the [Complete User Guide](USER_GUIDE.md) for advanced workflows  
- 🔧 **Technical specifications?** → Check [Analysis Outputs Reference](emuses/output_formats.md) for detailed formats

**Last Updated**: 2025-08-31  
**Related**: [Output Formats](emuses/output_formats.md) | [User Guide](USER_GUIDE.md) | [Quick Start](QUICK_START.md)