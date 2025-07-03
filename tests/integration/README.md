# EMUSES Integration Testing Guide

This directory contains comprehensive integration tests for the EMUSES pipeline across all interfaces and LAD framework sessions.

## Overview

The integration tests validate that the EMUSES pipeline produces consistent results across different interfaces (CLI, FastAPI, Streamlit) and maintains compatibility throughout the LAD development process.

## Test Structure

### `test_real_world_pipeline.py`

The main integration test module that provides:

- **`RealWorldIntegrationTest`**: Core test suite class with synthetic data generation
- **`TestCLIIntegration`**: CLI-specific integration tests  
- **`TestFastAPIIntegration`**: FastAPI service integration tests (LAD Session 1)
- **`TestStreamlitIntegration`**: Streamlit GUI integration tests (LAD Session 4)

## Running the Tests

### Command Line

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific test class
pytest tests/integration/test_real_world_pipeline.py::TestCLIIntegration -v

# Run with coverage
pytest tests/integration/ --cov=emuses --cov-report=html

# Run in CI mode (reduced parameters for speed)
CI=true pytest tests/integration/ -v
```

### Standalone Execution

```bash
# Run the integration test directly
python tests/integration/test_real_world_pipeline.py
```

## Test Parameters

The integration tests support two parameter sets:

### Default Parameters (Full Testing)
```python
DEFAULT_PARAMS = {
    'n_trials': 10,
    'hdbscan_trials': 5,
    'outer_folds': 3,
    'optim_trials': 10,
    'umap_jobs': 10,
    'hdbscan_jobs': 10,
    'prefix': 'Integration_Test',
    'run_stages': 'umap heatmap prediction'
}
```

### CI Parameters (Fast Testing)
```python
CI_PARAMS = {
    'n_trials': 3,
    'hdbscan_trials': 2,
    'outer_folds': 2,
    'optim_trials': 3,
    'umap_jobs': 2,
    'hdbscan_jobs': 2,
    'prefix': 'CI_Test',
    'run_stages': 'umap heatmap prediction'
}
```

## Real-World Command Reference

The integration tests are based on this real-world CLI command:

```bash
python main.py \
  --embedding /user/lsf/Users/FOULON/NeuroMarkers/Outputs/EMUSES_Revision_Cohort_Test_RRM_RealData/features_train.csv \
  --test_embedding /user/lsf/Users/FOULON/NeuroMarkers/Outputs/EMUSES_Revision_Cohort_Test_RRM_RealData/features_test.csv \
  --labels /user/lsf/Users/FOULON/NeuroMarkers/Outputs/EMUSES_Revision_Cohort_Test_RRM_RealData/labels_train.csv \
  --test_labels /user/lsf/Users/FOULON/NeuroMarkers/Outputs/EMUSES_Revision_Cohort_Test_RRM_RealData/labels_test.csv \
  --output_folder /user/lsf/Users/FOULON/NeuroMarkers/Outputs/EMUSES_Revision_Cohort_Test_RRM_RealData/Output_test \
  --n_trials 10 \
  --hdbscan_trials 5 \
  --outer_folds 3 \
  --optim_trials 10 \
  --umap_jobs 10 \
  --hdbscan_jobs 10 \
  --prefix "Test_RRM_RealData_10_5_3_10" \
  --run_stages umap heatmap prediction
```

## LAD Session Integration

### Session 1: Foundation FastAPI Service
- Tests will validate that FastAPI endpoints produce identical results to CLI
- Focuses on service layer compatibility and background task processing
- Tests will be enabled once `emuses/api/app.py` exists

### Session 2: Enhanced CLI with Typer
- Tests will validate new Typer CLI maintains exact functional parity
- Checks that all existing workflows continue working
- Validates rich progress bars and interactive features

### Session 3: FastAPI Web Layer  
- Tests will validate complete REST API functionality
- File upload/download compatibility with CSV formats
- Background task processing for optimization workloads

### Session 4: Streamlit GUI
- Tests will validate web interface file processing
- Parameter configuration through GUI
- Results visualization and download functionality

### Session 5: Production Readiness
- Tests will validate production service under load
- Authentication and authorization compatibility
- Database storage and retrieval functionality

## Expected Output Structure

The integration tests validate that the following files are created:

```
output_directory/
├── umap_model.pkl              # Trained UMAP model
├── hdbscan_model.pkl           # Trained HDBSCAN clusterer
├── embedding_train_coords.csv  # Training embeddings 
├── embedding_test_coords.csv   # Test embeddings
├── cluster_labels.csv          # Cluster assignments
├── prediction_results.json     # Prediction performance metrics
├── cv_scores.csv              # Cross-validation scores
└── optimization_history.json  # Optuna optimization results
```

## Performance Benchmarks

The integration tests establish baseline performance metrics:

- **UMAP Optimization**: n_trials × hdbscan_trials total evaluations
- **Heatmap Optimization**: outer_folds × optim_trials CV runs  
- **Prediction Inference**: Full test set evaluation
- **Resource Usage**: Memory, CPU, and disk I/O profiles
- **Processing Time**: End-to-end pipeline duration

## Troubleshooting

### Common Issues

1. **Test Timeouts**: Reduce parameters by setting `CI=true`
2. **Memory Issues**: Reduce `n_samples` in synthetic data generation
3. **File Permission Issues**: Ensure temporary directory write permissions
4. **Missing Dependencies**: Install test requirements with `pip install -e .[test]`

### Debugging

```bash
# Run with verbose output
pytest tests/integration/ -v -s

# Run with debugging
pytest tests/integration/ --pdb

# Run with coverage and detailed output
pytest tests/integration/ --cov=emuses --cov-report=term-missing -v
```

## Contributing

When adding new LAD sessions or features:

1. Add corresponding test methods to the appropriate test class
2. Update the `@pytest.mark.skipif` conditions when files are implemented
3. Ensure new tests validate both functionality and compatibility
4. Update this documentation with new test patterns

## Integration with CI/CD

The integration tests are designed to work in CI/CD environments:

- Automatic detection of CI environment via `CI` environment variable
- Reduced parameters for faster execution in CI
- Deterministic random seeds for reproducible results
- Clear failure messages for debugging

Example CI configuration:

```yaml
- name: Run Integration Tests
  run: |
    export CI=true
    pytest tests/integration/ -v --tb=short
```
