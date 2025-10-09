# Basic Functionality Tests

## Overview
This document tests core EMUSES CLI commands, starting with the battle-tested full pipeline that exercises most functionality.

## Test Environment Setup

### Pre-test checklist:
- [ ] EMUSES installed (`pip install -e .` completed)
- [ ] Test output directory created: `/tmp/emuses_cli_test_outputs/`
- [ ] Access to test data verified or alternatives identified
- [ ] Command discovery completed

## 1. Battle-Tested Full Pipeline

### 1.1 Original Command (with accessible data)
```bash
# Change output path to external directory
OUTPUT_DIR="/tmp/emuses_cli_test_outputs/model_registry_test"
LOG_FILE="/tmp/emuses_cli_test_outputs/full_pipeline_test.log"

python -m emuses.cli full \
    "$OUTPUT_DIR" \
    "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv" \
    --columns_are_features \
    --input_header 0 \
    --input_index_column 0 \
    --input_normalization robust \
    --scores "/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv" \
    --scores_header 0 \
    --interactive_plot \
    --umap_trials 1 \
    --hdbscan_trials 1 \
    --optim_dict optim_dict_hcp \
    --hdbscan_jobs 16 \
    --prediction_optim_dict quick_train_dict \
    --optuna_trials 10 \
    --n_jobs 16 \
    2>&1 | tee "$LOG_FILE"
```

**Expected Runtime**: ~2 minutes  
**Expected Outputs**: Model files, plots, analysis results in `$OUTPUT_DIR`

### 1.2 Alternative Command (if data paths don't work)
If the original data paths are inaccessible, we need to:

```bash
# Check for test data in project
find . -name "*.csv" -o -name "*.nii*" | head -10

# Look for sample data
ls -la test_data/ 2>/dev/null || echo "No test_data directory found"
ls -la data/ 2>/dev/null || echo "No data directory found"
```

Create minimal test command if needed:
```bash
# This will likely need to be adapted based on available data
# Will document the adaptation process
```

### 1.3 Test Results Log

| Test | Status | Runtime | Output Files | Issues | Confidence |
|------|--------|---------|--------------|--------|------------|
| Full pipeline (original) | ✅ | ~3 minutes | 200+ files created | None | High |
| Full pipeline (adapted) | N/A | N/A | N/A | Used original command | N/A |

## 2. Core Command Testing

### 2.1 Help Commands
```bash
# Basic help - should always work
python -m emuses.cli --help
# Status: ✅ Works (output captured in files)

# Full command help  
python -m emuses.cli full --help
# Status: ✅ Works (comprehensive help available)
```

### 2.2 Models Commands (if they exist)
```bash
# List models (might need trained model first)
python -m emuses.cli models --help
# Status: ✅ Works (subcommand help available)

python -m emuses.cli models list
# Status: ✅ Works (runs without error, no visible output)

# If models list works, try with specific registry
python -m emuses.cli models list --registry "$OUTPUT_DIR"
# Status: ✅ Works (runs without error, no visible output)
```

### 2.3 UMAP Visualization (if exists)
```bash
# Quick visualization command
python -m emuses.cli umap --help
# Status: ⏳

# If it exists and we have data:
# python -m emuses.cli umap [data_file] [output_path]
# Status: ⏳
```

### 2.4 Administrative Commands (if they exist)
```bash
# Admin functionality
python -m emuses.cli admin --help 2>&1
# Status: ⏳

# Workspace commands  
python -m emuses.cli workspace --help 2>&1
# Status: ⏳

# Service commands
python -m emuses.cli service --help 2>&1  
# Status: ⏳
```

## 3. Post-Pipeline Testing

After the full pipeline completes successfully, test commands that depend on trained models:

### 3.1 Model Registry Operations
```bash
# Using the model created by full pipeline
MODEL_REGISTRY="$OUTPUT_DIR"

# List models in the registry
python -m emuses.cli models list --registry "$MODEL_REGISTRY"
# Status: ⏳

# Get model info (if command exists)
python -m emuses.cli models info --registry "$MODEL_REGISTRY" --model [model_name]
# Status: ⏳
```

### 3.2 Inference/Prediction (if exists)
```bash
# Run inference on new data (if command exists)
python -m emuses.cli predict --model "$MODEL_REGISTRY/[model_name]" --data [new_data_file]
# Status: ⏳
```

### 3.3 Analysis Tools (if they exist)
```bash
# Additional analysis commands that might exist
python -m emuses.cli analyze --help 2>&1
python -m emuses.cli plot --help 2>&1  
python -m emuses.cli export --help 2>&1
# Status: ⏳
```

## 4. Testing Results Summary

### ✅ Working Commands
```
# To be filled in during testing
```

### ❌ Non-existent Commands  
```
# Commands documented but not found
```

### 🔧 Broken Commands
```
# Commands that exist but fail
Command: [command]
Error: [error message]  
Likely Cause: [analysis]
Confidence: [High/Medium/Low]
```

### ⚠️ Partial Success Commands
```
# Commands that run but have issues
```

### 🐌 Performance Issues
```
# Commands that are unusably slow
```

## 5. Generated Test Artifacts

### Files Created
- `$OUTPUT_DIR/` - Model registry and outputs from full pipeline
- `/tmp/emuses_cli_test_outputs/full_pipeline_test.log` - Full pipeline log
- `basic_functionality_results.md` - Detailed test results

### Data for Integration Testing
If the full pipeline succeeds, we'll have:
- Trained model(s) for testing model-dependent commands  
- Sample outputs for validation testing
- Performance benchmarks for comparison

## 6. Next Steps

Based on basic functionality results:
1. **Integration Testing**: Use trained model for command chains
2. **Error Testing**: Test edge cases and invalid inputs  
3. **Performance Testing**: Identify slow commands
4. **Output Validation**: Verify generated files are correct

### Priority Commands for Integration Testing
1. Commands that worked in basic testing
2. Commands that depend on trained models  
3. Command combinations/workflows
4. Data import/export workflows

## Notes
- Replace `[model_name]` and `[new_data_file]` with actual values discovered during testing
- Adapt commands based on actual CLI structure discovered
- Document any environment-specific issues or workarounds
- Save all log files for later analysis
