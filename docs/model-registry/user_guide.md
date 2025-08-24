# EMUSES Model Registry User Guide

## Overview

EMUSES provides a model registry system for managing complete EMUSES training folder units. The registry acts as a lookup service, mapping model IDs to EMUSES folder paths containing all training outputs (UMAP, HDBSCAN, prediction models, and optional feature models).

**Key Principle**: EMUSES models are complete folder units from training runs. The registry provides convenient access without altering the folder structure or separating components.

## 🚀 Quick Start

### Installation and Setup

EMUSES automatically detects your environment and provides model registry support:

```bash
# Check your current registry status
python -m emuses.cli models status

# List registered EMUSES folders
python -m emuses.cli models list

# Get help for registry commands
python -m emuses.cli models --help
```

### Model Registry Operations

**Core Operations** - Working with complete EMUSES folders:

```bash
# Install an EMUSES training folder into the registry
python -m emuses.cli models install /path/to/emuses/folder --name "my_research_model"

# Get detailed information about a registered model
python -m emuses.cli models info <model_id>

# Search for models by name or description
python -m emuses.cli models search "HCP"

# Run inference using registry model ID (no file paths needed!)
python -m emuses.cli inference --model-id <model_id> --data /path/to/data.csv

# Alternative: traditional file path approach still works
python -m emuses.cli inference --model /path/to/emuses/folder --data /path/to/data.csv
```

## Model Registry Concepts

### EMUSES Folder Structure

The registry works with complete EMUSES training folders containing:

```
emuses_training_output/
├── model_manifest.json                    # Training metadata
├── best_umap_model_v1_0_0.joblib          # UMAP model
├── hdbscan_model_v1_0_0.joblib            # HDBSCAN model
├── target_0/                              # Prediction models
│   ├── best_pipeline_fold0_v1_0_0.joblib
│   ├── best_pipeline_fold1_v1_0_0.joblib
│   └── ...
├── embeddings.npy                         # Training embeddings
├── input_matrix.npy                       # Input data
└── [optional] feature models              # PCA/kPCA/Autoencoder
    ├── pca_model_v1_0_0.joblib
    ├── kpca_model_v1_0_0.joblib
    └── autoencoder_model_v1_0_0.joblib
```

### Registry Model IDs

When you install a folder, the registry generates a unique model ID:
- Format: `{name}_{timestamp}_{hash}`
- Example: `hcp_model_20250823_a1b2c3d4`
- Use this ID for inference and model operations

### Feature Augmentation Models

The registry automatically detects optional feature models for preprocessing:
- **PCA models**: Principal component analysis for dimensionality reduction
- **kPCA models**: Kernel PCA for non-linear feature transformation  
- **Autoencoder models**: Neural network-based feature extraction

These models are tracked in registry metadata but remain optional components.

## Usage Examples

### Basic Workflow

```bash
# 1. Install your EMUSES training folder
python -m emuses.cli models install ~/my_emuses_output --name "experiment_001"
# Returns: Model ID for future reference

# 2. List your registered models
python -m emuses.cli models list
# Shows: Model ID, name, installation date, folder path

# 3. Get model information
python -m emuses.cli models info experiment_001_20250823_a1b2c3d4
# Shows: Folder path, model components, feature models (if any)

# 4. Run inference with registry
python -m emuses.cli inference \
  --model-id experiment_001_20250823_a1b2c3d4 \
  --data /path/to/new_data.csv
```

### Advanced Operations

```bash
# Search models by pattern
python -m emuses.cli models search "experiment"

# Check registry status and statistics
python -m emuses.cli models status

# Install with description and tags
python -m emuses.cli models install /path/to/folder \
  --name "hcp_analysis" \
  --description "HCP dataset analysis with optimized parameters"
```

### API Usage

The model registry also provides REST API endpoints:

```python
import requests

# List models via API
response = requests.get("http://localhost:8000/api/v1/models")
models = response.json()

# Run inference via API
inference_request = {
    "model_id": "experiment_001_20250823_a1b2c3d4",  # Use registry ID
    "data_path": "/path/to/data.csv",
    "output_format": "csv"
}
response = requests.post("http://localhost:8000/api/v1/inference", json=inference_request)
```

## Troubleshooting

### Common Issues

**Model Installation Fails**:
```bash
# Check if folder contains required EMUSES files
ls /path/to/folder  # Should have .joblib files, .npy files, manifest.json

# Check detailed error message
python -m emuses.cli models install /path/to/folder --verbose
```

**Registry Lookup Fails**:
```bash
# Verify model ID exists
python -m emuses.cli models list | grep <model_id>

# Check registry status
python -m emuses.cli models status
```

**Inference with --model-id Fails**:
```bash
# Verify model ID is correct
python -m emuses.cli models info <model_id>

# Fall back to direct path if needed
python -m emuses.cli inference --model /path/to/folder --data /path/to/data.csv
```

## Migration from Direct Paths

If you currently use direct folder paths, the registry provides convenient shortcuts:

**Before** (still works):
```bash
python -m emuses.cli inference --model /long/path/to/emuses/folder --data data.csv
```

**After** (more convenient):
```bash
# One-time setup
python -m emuses.cli models install /long/path/to/emuses/folder --name "my_model"

# Then use short ID
python -m emuses.cli inference --model-id my_model_20250823_a1b2c3d4 --data data.csv
```

## Best Practices

1. **Use descriptive names**: `--name "hcp_optimized_v2"` not `--name "model1"`
2. **Keep folders intact**: Don't modify EMUSES training output folders after registration
3. **Use model IDs**: Prefer `--model-id` over `--model` for cleaner commands
4. **Regular status checks**: Use `models status` to monitor registry health
5. **Backup important models**: Registry provides convenience, not storage - keep original folders safe

## See Also

- [API Reference](api_reference.md) - Complete REST API documentation
- [Developer Guide](developer_guide.md) - Registry integration for developers
- [CLI Reference](../CLI_REFERENCE.md) - Complete CLI command documentation