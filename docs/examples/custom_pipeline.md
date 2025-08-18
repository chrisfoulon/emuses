# Custom Pipeline Example

Building custom analysis pipelines with EMUSES: stage-by-stage pipeline construction, parameter optimization, custom preprocessing workflows, and integration with existing neuroimaging tools.

## Overview

This example demonstrates how to build custom analysis pipelines tailored to your specific research needs. Learn how to customize individual stages, optimize parameters, and integrate EMUSES with your existing neuroimaging workflow.

## Understanding EMUSES Pipeline Architecture

EMUSES pipelines consist of modular stages that can be customized independently:

```
Input Data → Preprocessing → UMAP → Clustering → Prediction → Results
     ↓           ↓           ↓         ↓           ↓         ↓
   Raw CSV   Normalized   Embedding  Clusters   ML Model  Outputs
```

Each stage can be:
- **Configured** with custom parameters
- **Replaced** with alternative algorithms
- **Extended** with additional processing steps
- **Skipped** if not needed for your analysis

## Basic Custom Pipeline

### Step 1: Custom Configuration

```python
from emuses.config.pipeline_config import PipelineConfig
from emuses.core.pipeline import EMUSESPipeline
import pandas as pd

# Load your data
features = pd.read_csv("docs/examples/sample_data/hcp_input_data.csv", index_col=0)
labels = pd.read_csv("docs/examples/sample_data/hcp_labels.csv", index_col=0)

# Create custom configuration
custom_config = PipelineConfig(
    # Preprocessing customization
    normalization="zscore",          # Alternative: "robust", "minmax", "quantile"
    missing_data_strategy="median",  # How to handle missing values
    feature_selection=True,          # Enable feature selection
    n_features_select=500,           # Number of features to keep
    
    # UMAP customization
    umap_n_neighbors=30,             # Larger neighborhood = more global structure
    umap_min_dist=0.0,               # Tighter clustering = more detailed structure
    umap_n_components=3,             # 3D embedding instead of 2D
    umap_metric="cosine",            # Alternative: "euclidean", "manhattan"
    umap_trials=10,                  # More thorough parameter search
    
    # Clustering customization
    hdbscan_min_cluster_size=50,     # Minimum cluster size
    hdbscan_min_samples=20,          # Minimum samples per cluster
    hdbscan_cluster_selection_epsilon=0.1,  # Cluster selection threshold
    hdbscan_trials=8,                # Multiple clustering attempts
    
    # Prediction customization
    prediction_model="random_forest", # Alternative: "ridge", "svm", "xgboost"
    cross_validation_folds=10,       # More robust validation
    feature_importance=True,         # Enable feature importance analysis
    
    # Output customization
    interactive_plots=True,          # Generate interactive visualizations
    generate_report=True,            # Comprehensive HTML report
    save_intermediate=True           # Save intermediate results
)

# Run custom pipeline
pipeline = EMUSESPipeline(custom_config)
results = pipeline.run(
    features=features,
    labels=labels,
    output_dir="./custom_pipeline_results"
)
```

### Step 2: Stage-by-Stage Construction

```python
from emuses.stages import PreprocessingStage, UMAPStage, ClusteringStage, PredictionStage

# Build pipeline stage by stage
preprocessing = PreprocessingStage({
    "normalization": "robust",
    "outlier_detection": True,
    "outlier_threshold": 3.0,
    "feature_scaling": "standard"
})

umap_stage = UMAPStage({
    "n_neighbors": [15, 30, 50],     # Test multiple values
    "min_dist": [0.0, 0.1, 0.5],    # Test multiple values
    "n_components": 2,
    "metric": "euclidean",
    "random_state": 42
})

clustering_stage = ClusteringStage({
    "algorithm": "hdbscan",          # Alternative: "kmeans", "gaussian_mixture"
    "min_cluster_size": [20, 50, 100],
    "optimization_metric": "silhouette"
})

prediction_stage = PredictionStage({
    "models": ["ridge", "random_forest", "gradient_boosting"],
    "hyperparameter_tuning": True,
    "cv_strategy": "stratified_kfold",
    "scoring_metric": "r2"
})

# Combine stages into custom pipeline
custom_pipeline = EMUSESPipeline([
    preprocessing,
    umap_stage, 
    clustering_stage,
    prediction_stage
])

results = custom_pipeline.run(features, labels)
```

## Advanced Customization Patterns

### Custom Preprocessing Workflow

```python
from emuses.preprocessing import CustomPreprocessor
import numpy as np
from sklearn.feature_selection import SelectKBest, f_regression

class NeuroPreprocessor(CustomPreprocessor):
    """Custom preprocessing for neuroimaging data"""
    
    def __init__(self, config):
        super().__init__(config)
        self.brain_atlas = config.get("brain_atlas", "aal")
        self.connectivity_threshold = config.get("conn_threshold", 0.1)
    
    def preprocess_connectivity_matrix(self, data):
        """Custom connectivity matrix preprocessing"""
        # Apply Fisher z-transform for connectivity data
        data_transformed = np.arctanh(np.clip(data, -0.99, 0.99))
        
        # Threshold weak connections
        data_transformed[np.abs(data_transformed) < self.connectivity_threshold] = 0
        
        return data_transformed
    
    def select_roi_features(self, data, n_features=200):
        """Select most informative brain regions"""
        selector = SelectKBest(score_func=f_regression, k=n_features)
        selected_data = selector.fit_transform(data, self.labels)
        
        # Store selected feature indices for interpretation
        self.selected_features = selector.get_support(indices=True)
        return selected_data
    
    def run(self, data, labels=None):
        """Complete custom preprocessing pipeline"""
        self.labels = labels
        
        # Standard normalization
        data = self.normalize_data(data, method="robust")
        
        # Neuroimaging-specific processing
        data = self.preprocess_connectivity_matrix(data)
        data = self.select_roi_features(data)
        
        return data

# Use custom preprocessor
neuro_config = {
    "brain_atlas": "aal",
    "conn_threshold": 0.15,
    "normalization": "robust"
}

custom_preprocessor = NeuroPreprocessor(neuro_config)
preprocessed_data = custom_preprocessor.run(features, labels)
```

### Parameter Optimization Framework

```python
from emuses.optimization import ParameterOptimizer
from sklearn.model_selection import ParameterGrid

# Define parameter space for optimization
param_space = {
    "umap": {
        "n_neighbors": [10, 15, 30, 50, 100],
        "min_dist": [0.0, 0.1, 0.3, 0.5],
        "metric": ["euclidean", "cosine", "manhattan"]
    },
    "clustering": {
        "min_cluster_size": [20, 50, 100, 200],
        "min_samples": [10, 20, 50],
        "cluster_selection_epsilon": [0.0, 0.1, 0.2]
    },
    "prediction": {
        "model": ["ridge", "random_forest", "gradient_boosting"],
        "alpha": [0.1, 1.0, 10.0],  # For ridge regression
        "n_estimators": [100, 200, 500]  # For tree-based models
    }
}

# Setup optimization
optimizer = ParameterOptimizer(
    param_space=param_space,
    optimization_metric="adjusted_rand_index",
    cv_folds=5,
    n_jobs=4  # Parallel processing
)

# Run optimization
best_params = optimizer.optimize(
    features=features,
    labels=labels,
    max_evaluations=50  # Budget for parameter search
)

print("Best parameters found:")
for stage, params in best_params.items():
    print(f"  {stage}: {params}")

# Use optimized parameters
optimized_config = PipelineConfig(**best_params)
optimized_pipeline = EMUSESPipeline(optimized_config)
results = optimized_pipeline.run(features, labels)
```

### Integration with External Tools

#### **FSL Integration**

```python
from emuses.external import FSLIntegration
import subprocess

class FSLEMUSESPipeline:
    """Integration with FSL neuroimaging tools"""
    
    def __init__(self, fsl_dir="/usr/local/fsl"):
        self.fsl_dir = fsl_dir
        self.setup_fsl_environment()
    
    def setup_fsl_environment(self):
        """Configure FSL environment"""
        import os
        os.environ["FSLDIR"] = self.fsl_dir
        os.environ["PATH"] = f"{self.fsl_dir}/bin:" + os.environ["PATH"]
    
    def extract_connectivity_matrix(self, subject_dir, atlas="aal"):
        """Extract connectivity matrix using FSL tools"""
        cmd = [
            "probtrackx2",
            "--dir", subject_dir,
            "--samples", f"{subject_dir}/merged",
            "--mask", f"{subject_dir}/nodif_brain_mask",
            "--seed", f"{atlas}_seeds.txt",
            "--target", f"{atlas}_targets.txt"
        ]
        subprocess.run(cmd, check=True)
        
        # Load resulting connectivity matrix
        conn_matrix = np.loadtxt(f"{subject_dir}/fdt_matrix2.dot")
        return conn_matrix
    
    def run_full_pipeline(self, subject_dirs, behavioral_data):
        """Complete FSL + EMUSES pipeline"""
        # Step 1: Extract connectivity matrices using FSL
        connectivity_matrices = []
        for subject_dir in subject_dirs:
            conn_matrix = self.extract_connectivity_matrix(subject_dir)
            connectivity_matrices.append(conn_matrix.flatten())
        
        # Step 2: Create DataFrame for EMUSES
        features = pd.DataFrame(connectivity_matrices)
        
        # Step 3: Run EMUSES analysis
        config = PipelineConfig(
            normalization="robust",
            umap_trials=5,
            prediction_model="ridge"
        )
        
        pipeline = EMUSESPipeline(config)
        results = pipeline.run(
            features=features,
            labels=behavioral_data,
            output_dir="./fsl_emuses_results"
        )
        
        return results

# Usage
fsl_pipeline = FSLEMUSESPipeline()
results = fsl_pipeline.run_full_pipeline(
    subject_dirs=["/data/subject_001", "/data/subject_002"],
    behavioral_data=behavioral_scores
)
```

#### **BIDS Integration**

```python
from emuses.bids import BIDSProcessor
import bids

class BIDSEMUSESIntegration:
    """EMUSES integration with BIDS datasets"""
    
    def __init__(self, bids_root):
        self.bids_root = bids_root
        self.layout = bids.BIDSLayout(bids_root)
    
    def extract_features_from_bids(self, task=None, space="MNI152NLin2009cAsym"):
        """Extract features from BIDS dataset"""
        # Get functional connectivity files
        conn_files = self.layout.get(
            suffix="timeseries",
            extension=".tsv",
            task=task,
            space=space
        )
        
        features_data = []
        subject_ids = []
        
        for conn_file in conn_files:
            # Load timeseries data
            timeseries = pd.read_csv(conn_file.path, sep='\t')
            
            # Compute correlation matrix
            corr_matrix = np.corrcoef(timeseries.T)
            
            # Extract upper triangle (connectivity features)
            features = corr_matrix[np.triu_indices_from(corr_matrix, k=1)]
            features_data.append(features)
            
            # Store subject ID
            subject_ids.append(conn_file.entities['subject'])
        
        # Create features DataFrame
        features_df = pd.DataFrame(features_data, index=subject_ids)
        return features_df
    
    def get_behavioral_data(self, phenotype="participants.tsv"):
        """Extract behavioral data from BIDS"""
        phenotype_file = self.layout.get(suffix="participants")[0]
        behavioral_data = pd.read_csv(phenotype_file.path, sep='\t', index_col='participant_id')
        return behavioral_data
    
    def run_bids_analysis(self, target_variable, task=None):
        """Complete BIDS + EMUSES analysis"""
        # Extract features and behavioral data
        features = self.extract_features_from_bids(task=task)
        behavioral_data = self.get_behavioral_data()
        
        # Align data
        common_subjects = features.index.intersection(behavioral_data.index)
        features_aligned = features.loc[common_subjects]
        labels_aligned = behavioral_data.loc[common_subjects, target_variable]
        
        # Run EMUSES analysis
        config = PipelineConfig(
            normalization="robust",
            umap_trials=5,
            hdbscan_trials=3,
            prediction_model="ridge"
        )
        
        pipeline = EMUSESPipeline(config)
        results = pipeline.run(
            features=features_aligned,
            labels=labels_aligned,
            output_dir=f"./bids_analysis_{task or 'rest'}"
        )
        
        return results

# Usage
bids_processor = BIDSEMUSESIntegration("/data/bids_dataset")
results = bids_processor.run_bids_analysis(
    target_variable="age",
    task="rest"
)
```

## Performance Optimization

### Memory-Efficient Processing

```python
from emuses.optimization import ChunkedProcessor

# For large datasets, process in chunks
chunked_processor = ChunkedProcessor(
    chunk_size=500,        # Process 500 subjects at a time
    memory_limit_gb=8,     # Memory constraint
    n_parallel_chunks=2    # Parallel processing
)

results = chunked_processor.run_pipeline(
    features=large_features_dataset,
    labels=large_labels_dataset,
    pipeline_config=custom_config
)
```

### GPU Acceleration

```python
# Enable GPU processing where available
gpu_config = PipelineConfig(
    use_gpu=True,
    gpu_memory_limit=4096,  # MB
    umap_trials=20,         # More trials with GPU speed
    hdbscan_trials=15
)

gpu_pipeline = EMUSESPipeline(gpu_config)
results = gpu_pipeline.run(features, labels)
```

## Validation and Testing

### Custom Validation Strategies

```python
from sklearn.model_selection import GroupKFold, StratifiedKFold
from emuses.validation import CustomValidator

# For neuroimaging data, account for site effects
class NeuroValidator(CustomValidator):
    def __init__(self, site_info):
        self.site_info = site_info
    
    def get_cv_splits(self, X, y):
        """Site-aware cross-validation"""
        group_kfold = GroupKFold(n_splits=5)
        return group_kfold.split(X, y, groups=self.site_info)

validator = NeuroValidator(site_info=site_labels)
config.validation_strategy = validator
```

## Next Steps

1. **Start with Basic Customization**: Modify parameters in PipelineConfig
2. **Add Custom Preprocessing**: Implement domain-specific preprocessing
3. **Optimize Parameters**: Use systematic parameter optimization
4. **Integrate External Tools**: Connect with your existing workflow
5. **Scale for Production**: Implement memory and GPU optimizations

For more examples:
- [HCP Dataset Analysis](hcp_analysis.md) - Real-world application
- [API Integration](api_integration.md) - Programmatic usage patterns  
- [Research Workflows](../RESEARCH_WORKFLOWS.md) - Scientific applications