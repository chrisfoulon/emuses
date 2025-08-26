# Implementation Guide - Inference Performance Fixes

## Quick Start for Fresh Claude Sessions

### Problem Summary
- **Issue**: KernelRegressor models return zero predictions during inference
- **Root Cause**: Input data and scores not normalized consistently between training and inference
- **Solution**: Save normalization scalers during training, load and apply during inference
- **Status**: Embeddings rescaling already correctly implemented in UMAPStage

### Key Findings - DO NOT RE-RESEARCH
1. ✅ **UMAPStage embeddings rescaling**: Already correct, no changes needed
2. ❌ **Scores normalization**: Not saved for inference reuse  
3. ⚠️ **Input normalization**: Partially implemented, needs extension to model files
4. ✅ **Manifest system**: Perfect infrastructure already exists in ModelIOManager

## Implementation Roadmap

### Phase 1: Normalization Parameter Storage (HIGH PRIORITY)
**Files to modify**:
1. `emuses/pipelines/emuses_pipeline.py:load_and_process_scores()` (~line 388)
2. `emuses/pipelines/emuses_pipeline.py:process_dataset()` (~line 250)
3. `emuses/tools/model_io.py:_generate_manifest_from_directory()`

**Actions**:
- Modify `normalize_dataframe()` calls to return and save scaler objects
- Save scalers as `{model_dir}/scores_scaler.joblib` and `{model_dir}/input_scaler.joblib`
- Update manifest generation to detect and reference scaler files

### Phase 2: Inference Loading and Application (HIGH PRIORITY)  
**Files to modify**:
1. `emuses/pipelines/inference_stage.py:_load_trained_models_with_context()` (~line 85)
2. `emuses/pipelines/inference_stage.py:_transform_features_with_umap()`

**Actions**:
- Load scalers from manifest during model loading
- Apply input normalization before UMAP transform
- Apply scores normalization for validation comparisons

### Phase 3: Logging Cleanup (MEDIUM PRIORITY)
**Files to modify**:
1. `emuses/pipelines/inference_stage.py:run()`
2. `emuses/pipelines/emuses_pipeline.py` (JSON logging)
3. `emuses/cli/main.py:_execute_inference_locally()` (CLI status)

**Actions**:
- Coordinate logging between EMUSESPipeline, InferenceStage, and CLI
- Eliminate duplicate "Starting inference pipeline execution" messages
- Consolidate Rich console outputs

## Technical Implementation Details

### Normalization Methods Investigation Needed
**IMPORTANT**: Must investigate `bcblib.tools.dataframe_filtering.normalize_dataframe()`:
- Does it support returning scaler objects?
- Is it reversible with inverse operations?
- May need migration to sklearn StandardScaler/MinMaxScaler/RobustScaler

### Manifest Integration (ALREADY PLANNED)
```json
{
  "normalization": {
    "scores_scaler": "scores_scaler.joblib",
    "input_scaler": "input_scaler.joblib", 
    "scores_method": "standardscaler",
    "input_method": "minmaxscaler"
  }
}
```

### InferenceStage Integration Pattern
```python
# In _load_trained_models_with_context():
models = {...}  # existing models
if 'input_scaler' in manifest_normalization:
    models['input_scaler'] = joblib.load(model_dir / "input_scaler.joblib")
if 'scores_scaler' in manifest_normalization:
    models['scores_scaler'] = joblib.load(model_dir / "scores_scaler.joblib")
return models
```

## Testing Strategy

### Development Testing
- **Pre-push**: `python scripts/dev_test_runner.py`
- **Module specific**: `pytest tests/inference/ -xvs`
- **Full validation**: `pytest -q --tb=short`

### Validation Requirements
1. KernelRegressor models produce non-zero predictions
2. ElasticNet models continue working (regression test)
3. Embedding ranges: training [0,1] vs inference [0,1] 
4. Backward compatibility: models without scalers work
5. Scaler integrity: SHA256 validation works

## Error Handling Requirements
- **Missing scalers**: Log warning, continue inference
- **Corrupt scalers**: Log error, continue without normalization
- **Version mismatches**: Graceful degradation
- **bcblib migration**: Fallback to sklearn if needed

## User Experience Goals
- **Transparent**: Clear logging when scalers detected and applied
- **Automatic**: No user intervention required
- **Reliable**: Consistent predictions between training and inference
- **Compatible**: Existing models continue working unchanged

## Files Summary for Implementation

### Core Files to Modify
1. **emuses/pipelines/emuses_pipeline.py** - Save scalers during training
2. **emuses/pipelines/inference_stage.py** - Load and apply scalers during inference  
3. **emuses/tools/model_io.py** - Extend manifest generation for scaler detection

### Test Files to Create
1. **tests/inference/test_normalization_storage.py** - Test scaler saving
2. **tests/inference/test_inference_normalization.py** - Test scaler loading/application
3. **tests/inference/test_normalization_validation.py** - End-to-end validation

### Documentation Files
1. **manifest_integration_spec.md** - Complete technical specification
2. **implementation_guide.md** - This file (session handover guide)
3. **Updated plan.md and context.md** - Detailed implementation plan

## Quick Commands for Implementation
```bash
# Find normalization code
grep -r "normalize_dataframe" emuses/pipelines/

# Find manifest generation
grep -r "_generate_manifest" emuses/tools/

# Find inference model loading
grep -r "_load_trained_models" emuses/pipelines/

# Test normalization changes
pytest tests/inference/ -k normalization -xvs
```

This guide provides everything needed for a fresh Claude session to continue implementation without re-researching the codebase or requirements.