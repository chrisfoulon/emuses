# HCP Dataset Analysis Example

Complete workflow using Human Connectome Project data, demonstrating EMUSES capabilities for neuroimaging research with real-world data patterns.

## Overview

This example demonstrates a comprehensive analysis pipeline using the Human Connectome Project (HCP) sample dataset included with EMUSES. The workflow covers connectivity matrix analysis, dimensionality reduction with UMAP, and predictive modeling for behavioral outcomes.

## Dataset Description

**Source**: Human Connectome Project (HCP)  
**Subjects**: 1,068 participants  
**Input Variables**: Selected neuroimaging features from structural and functional MRI  
**Target Variable**: Fluid intelligence scores (continuous prediction task)  

**Files Location**:
- `docs/examples/sample_data/hcp_input_data.csv` - Neuroimaging features (1068 subjects)
- `docs/examples/sample_data/hcp_labels.csv` - Fluid intelligence scores for prediction

## Complete Analysis Workflow

### Step 1: Basic Analysis with CLI

Run the complete EMUSES pipeline with optimal parameters for HCP data:

```bash
python -m emuses.cli full \
  "./results/hcp_analysis" \
  "docs/examples/sample_data/hcp_input_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm robust \
  --scores "docs/examples/sample_data/hcp_labels.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 5 \
  --hdbscan_trials 3 \
  --prediction_model "ridge"
```

### Step 2: Understanding the Pipeline Stages

The HCP analysis runs through multiple stages:

#### **Stage 1: Data Preprocessing**
- Robust normalization of neuroimaging features
- Missing data handling and quality control
- Feature scaling appropriate for neuroimaging data

#### **Stage 2: Dimensionality Reduction (UMAP)**
- **Trials**: 5 different parameter combinations tested
- **Optimization**: Automatic parameter selection for neuroimaging data
- **Output**: Low-dimensional embedding preserving brain network topology

#### **Stage 3: Clustering Analysis (HDBSCAN)**  
- **Trials**: 3 clustering configurations
- **Method**: Density-based clustering suitable for neuroimaging
- **Result**: Identification of distinct brain connectivity patterns

#### **Stage 4: Predictive Modeling**
- **Algorithm**: Ridge regression (optimal for neuroimaging prediction)
- **Target**: Fluid intelligence prediction from brain features
- **Validation**: Cross-validation with neuroimaging-appropriate splits

### Step 3: Results Interpretation

#### **Expected Outputs**
After running the analysis, you'll find in `./results/hcp_analysis/`:

```
hcp_analysis/
├── preprocessing/
│   ├── normalized_features.csv
│   └── preprocessing_report.html
├── umap/
│   ├── embeddings.csv
│   ├── umap_parameters.json
│   └── umap_visualization.html
├── clustering/
│   ├── cluster_assignments.csv
│   ├── cluster_metrics.json
│   └── cluster_visualization.html
└── prediction/
    ├── model_results.json
    ├── predictions.csv
    ├── feature_importance.csv
    └── validation_report.html
```

#### **Key Results to Examine**

1. **UMAP Visualization** (`umap/umap_visualization.html`)
   - 2D representation of brain connectivity patterns
   - Color-coded by fluid intelligence scores
   - Interactive plot for detailed exploration

2. **Clustering Results** (`clustering/cluster_assignments.csv`)
   - Distinct brain connectivity subtypes
   - Statistical validation of cluster quality
   - Relationship to cognitive performance

3. **Prediction Performance** (`prediction/model_results.json`)
   - Fluid intelligence prediction accuracy
   - Cross-validation performance metrics
   - Feature importance for neuroimaging interpretation

### Step 4: Advanced Customization

#### **Parameter Optimization for Your Data**

```bash
# Increase trials for more thorough parameter search
python -m emuses.cli full \
  "./results/hcp_detailed" \
  "docs/examples/sample_data/hcp_input_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm robust \
  --scores "docs/examples/sample_data/hcp_labels.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 10 \
  --hdbscan_trials 8 \
  --prediction_model "ridge" \
  --cross_validation_folds 10
```

#### **Integration with Your HCP Data**

To use your own HCP data:

1. **Prepare your connectivity matrices** in CSV format
2. **Include subject IDs** as the first column
3. **Prepare behavioral scores** in a separate CSV file
4. **Adjust file paths** in the command above

```bash
python -m emuses.cli full \
  "./results/my_hcp_analysis" \
  "/path/to/your/connectivity_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm robust \
  --scores "/path/to/your/behavioral_scores.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 5 \
  --hdbscan_trials 3 \
  --prediction_model "ridge"
```

## Scientific Interpretation

### Neuroimaging Context

This workflow demonstrates typical neuroimaging research patterns:

- **Connectivity Analysis**: Brain network analysis using connectivity matrices
- **Dimensionality Reduction**: Handling high-dimensional neuroimaging data
- **Individual Differences**: Relating brain patterns to cognitive abilities
- **Predictive Modeling**: Brain-behavior relationships

### Research Applications

**Individual Research**:
- Pilot analyses with HCP data
- Method development and validation
- Parameter optimization for your specific research

**Lab Collaboration**:
- Standardized analysis protocols
- Reproducible research workflows
- Shared analysis parameters

**Community Research**:
- Public dataset analysis
- Method comparison and benchmarking
- Reproducible science practices

## Data Attribution

**Source**: Human Connectome Project (HCP)  
**License**: HCP Open Access Data Use Terms  
**Citation**:
```
Van Essen DC, Smith SM, Barch DM, Behrens TE, Yacoub E, Ugurbil K; 
WU-Minn HCP Consortium. The WU-Minn Human Connectome Project: 
an overview. Neuroimage. 2013 Oct 15;80:62-79.
```

## Next Steps

1. **Run the Example**: Start with the basic command above
2. **Explore Results**: Examine the generated visualizations and reports
3. **Customize Parameters**: Adjust the analysis for your research questions
4. **Apply to Your Data**: Adapt the workflow for your own neuroimaging datasets

For more advanced usage patterns, see:
- [Custom Pipeline Example](custom_pipeline.md) - Building custom analysis workflows
- [API Integration Example](api_integration.md) - Programmatic usage
- [Research Workflows](../RESEARCH_WORKFLOWS.md) - Scientific use cases