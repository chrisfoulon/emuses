# Integration Tests and Command Workflows

## Overview
This document tests combinations of EMUSES CLI commands and complete workflows, building on the basic functionality tests and using any trained models created.

## Prerequisites  
- Basic functionality testing completed (`02_basic_functionality_tests.md`)
- At least one working command identified
- Ideally a trained model from the full pipeline

## 1. Model Registry Workflows

### 1.1 Model Lifecycle Testing
```bash
# Assuming we have a trained model from basic testing
MODEL_REGISTRY="/tmp/emuses_cli_test_outputs/model_registry_test"

# List all models
python -m emuses.cli models list --registry "$MODEL_REGISTRY"

# Get detailed info about specific model (adapt based on actual model names)
python -m emuses.cli models info --registry "$MODEL_REGISTRY" --model "best_model" 2>&1

# Export model (if command exists)  
python -m emuses.cli models export --registry "$MODEL_REGISTRY" --model "best_model" --output "/tmp/emuses_cli_test_outputs/exported_model" 2>&1
```

**Test Results:**
| Workflow Step | Status | Notes |
|---------------|--------|-------|
| List models | ⏳ | |  
| Model info | ⏳ | |
| Export model | ⏳ | |

### 1.2 Model Comparison (if supported)
```bash
# Compare multiple models (if command exists)
python -m emuses.cli models compare --registry "$MODEL_REGISTRY" --models "model1,model2" 2>&1

# Model performance metrics (if command exists)
python -m emuses.cli models metrics --registry "$MODEL_REGISTRY" --model "best_model" 2>&1
```

## 2. Analysis Pipeline Workflows  

### 2.1 Incremental Analysis
Test if we can run partial pipelines or continue from checkpoints:

```bash
# Run only UMAP step (if supported)
python -m emuses.cli umap "$MODEL_REGISTRY/input_data.csv" "/tmp/emuses_cli_test_outputs/umap_only" 2>&1

# Run only clustering step (if supported)  
python -m emuses.cli cluster "$MODEL_REGISTRY/umap_results" "/tmp/emuses_cli_test_outputs/cluster_only" 2>&1

# Run only prediction step (if supported)
python -m emuses.cli predict "$MODEL_REGISTRY/cluster_results" "/tmp/emuses_cli_test_outputs/predict_only" 2>&1
```

**Test Results:**
| Pipeline Step | Status | Notes |
|---------------|--------|-------|
| UMAP only | ⏳ | |
| Clustering only | ⏳ | |  
| Prediction only | ⏳ | |

### 2.2 Configuration Workflows
Test different configuration approaches:

```bash
# Using different optimization dictionaries  
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/config_test_1" \
    "$MODEL_REGISTRY/../selected_columns_data.csv" \
    --optim_dict minimal_dict \
    --optuna_trials 2 \
    2>&1 | tee "/tmp/emuses_cli_test_outputs/config_test_1.log"

# Using configuration files (if supported)
python -m emuses.cli full \
    --config "/path/to/config.yaml" \
    "/tmp/emuses_cli_test_outputs/config_test_2" \
    2>&1 | tee "/tmp/emuses_cli_test_outputs/config_test_2.log"
```

## 3. Data Import/Export Workflows

### 3.1 Data Format Testing
```bash
# Test different input formats (if supported)
# CSV with different configurations
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/csv_test" \
    "test_data.csv" \
    --input_header 1 \
    --input_index_column 1 \
    2>&1

# JSON input (if supported)
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/json_test" \
    "test_data.json" \
    2>&1

# HDF5 input (if supported)  
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/hdf5_test" \
    "test_data.h5" \
    2>&1
```

### 3.2 Export Workflows
```bash
# Export results in different formats
python -m emuses.cli export --input "$MODEL_REGISTRY" --output "/tmp/emuses_cli_test_outputs/export_csv" --format csv 2>&1

python -m emuses.cli export --input "$MODEL_REGISTRY" --output "/tmp/emuses_cli_test_outputs/export_json" --format json 2>&1

# Export plots/visualizations
python -m emuses.cli plot --model "$MODEL_REGISTRY" --output "/tmp/emuses_cli_test_outputs/plots" --format png 2>&1
```

## 4. Service Integration Workflows

### 4.1 Multi-User Service Testing (if applicable)
```bash
# Start service (if supported)  
python -m emuses.cli service start --port 8080 --background 2>&1

# Test service status
python -m emuses.cli service status 2>&1

# Submit job to service (if supported)
python -m emuses.cli service submit --config job_config.json 2>&1

# Stop service
python -m emuses.cli service stop 2>&1
```

### 4.2 Workspace Management (if applicable)
```bash
# Create workspace
python -m emuses.cli workspace create --name "test_workspace" --path "/tmp/emuses_cli_test_outputs/workspace" 2>&1

# List workspaces  
python -m emuses.cli workspace list 2>&1

# Switch workspace
python -m emuses.cli workspace use --name "test_workspace" 2>&1

# Clean workspace
python -m emuses.cli workspace clean --name "test_workspace" 2>&1
```

## 5. Error Recovery and Robustness

### 5.1 Interrupted Pipeline Recovery
```bash
# Start a pipeline, then test if it can be resumed (manual interruption needed)
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/interrupt_test" \
    "test_data.csv" \
    --checkpoint \
    2>&1 &

# Wait a bit, then kill the process
sleep 30
kill %1

# Try to resume (if supported)
python -m emuses.cli resume "/tmp/emuses_cli_test_outputs/interrupt_test" 2>&1
```

### 5.2 Resource Constraint Testing  
```bash
# Test with limited resources
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/resource_test" \
    "test_data.csv" \
    --n_jobs 1 \
    --memory_limit 1GB \
    2>&1
```

## 6. Complex Workflow Examples

### 6.1 Research Workflow Simulation
```bash
# Simulate a complete research workflow:

# 1. Explore data
python -m emuses.cli explore "raw_data.csv" --output "/tmp/emuses_cli_test_outputs/exploration" 2>&1

# 2. Preprocess  
python -m emuses.cli preprocess "raw_data.csv" --output "/tmp/emuses_cli_test_outputs/processed_data.csv" --normalize robust 2>&1

# 3. Train model
python -m emuses.cli full \
    "/tmp/emuses_cli_test_outputs/research_model" \
    "/tmp/emuses_cli_test_outputs/processed_data.csv" \
    --scores "scores.csv" \
    2>&1

# 4. Validate model  
python -m emuses.cli validate \
    --model "/tmp/emuses_cli_test_outputs/research_model" \
    --test_data "validation_data.csv" \
    --output "/tmp/emuses_cli_test_outputs/validation_results" \
    2>&1

# 5. Generate report
python -m emuses.cli report \
    --model "/tmp/emuses_cli_test_outputs/research_model" \
    --validation "/tmp/emuses_cli_test_outputs/validation_results" \
    --output "/tmp/emuses_cli_test_outputs/final_report.html" \
    2>&1
```

## 7. Integration Test Results

### ✅ Working Workflows
```
# Document successful command combinations
```

### 🔗 Partial Workflows  
```
# Workflows where some steps work but others fail
```

### ❌ Failed Integrations
```
# Command combinations that don't work together
```

### ⚠️ Data Compatibility Issues
```
# Format or structure incompatibilities between commands
```

## 8. Performance Analysis

### 8.1 Workflow Timing
| Workflow | Duration | Commands | Bottlenecks |
|----------|----------|----------|-------------|
| Basic full pipeline | ? | 1 | ? |
| Model registry ops | ? | 3-4 | ? |  
| Export workflow | ? | 2-3 | ? |
| Service workflow | ? | 4-5 | ? |

### 8.2 Resource Usage  
```bash
# Monitor resource usage during workflows (if tools available)
# Memory, CPU, disk I/O during different command combinations
```

## 9. Generated Integration Artifacts

### Workflow Documentation
- Command sequences that work together
- Data flow between commands  
- Configuration dependencies
- Error patterns in command combinations

### Test Data Sets
- Validated input/output pairs for each workflow
- Minimal test cases for quick validation  
- Edge case data sets

## 10. Next Steps

Based on integration testing results:
1. **Error Handling Tests**: Focus on failure modes discovered  
2. **Performance Tests**: Deep-dive on slow workflows
3. **Output Validation**: Verify data integrity through workflows
4. **User Experience**: Document confusing or problematic interactions

### Priority Areas for Error Testing
1. Workflows with partial success
2. Commands that failed integration  
3. Data format edge cases
4. Resource constraint scenarios

## Notes
- Adapt command names and parameters based on actual CLI discovery
- Document all intermediate files created for later validation
- Note any state dependencies between commands  
- Track data lineage through multi-step workflows
