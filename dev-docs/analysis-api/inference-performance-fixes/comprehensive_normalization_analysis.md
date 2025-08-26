# Comprehensive Normalization Analysis - Complete Solution Plan

## Executive Summary 🎯

**ROOT CAUSE**: The inference pipeline has **multiple normalization issues** that create a cascade of failures:

1. **Input normalization skipped** in EMUSESPipeline during inference mode
2. **Scores normalization also skipped** in EMUSESPipeline during inference mode
3. **No prediction denormalization** - outputs aren't converted back to original score scale
4. **Data type conversion failure** - Timedelta/Object columns not converted to numeric

**RESULT**: KernelRegressor gets wrong input ranges and produces zero predictions

## Detailed Analysis

### 1. BCBlib Analysis ✅

**normalize_dataframe() capabilities**:
- ✅ **Handles Timedelta columns**: Converts `dt.total_seconds()` (line 176)
- ✅ **Handles datetime columns**: Converts to int64/1e9 (line 173) 
- ✅ **Supports scaling_factors parameter**: Uses precomputed factors when provided
- ✅ **Returns scaling_factors**: Can be saved and reused for inference
- ✅ **Has inverse function**: `inverse_normalize_dataframe()` for denormalization

**Robust method (used in our case)**:
- Uses sklearn RobustScaler objects stored in scaling_factors
- Fully reversible with `scaler.transform()` and `scaler.inverse_transform()`

### 2. Input Normalization Issues ❌

**Current broken logic in EMUSESPipeline.process_dataset()** (line 321):
```python
if args.input_normalization and args.input_normalization.lower() != "none" and not getattr(args, 'inference_mode', False):
    # TRAINING: Normalization applied ✅
    # INFERENCE: Normalization SKIPPED ❌
```

**Problem**: During inference mode, normalization is completely skipped, leaving:
- Object columns (114 columns): `dtype('O'): 114` 
- Timedelta columns (2 columns): `dtype('<m8[ns]'): 2`
- UMAP fails with: `'float' and 'Timedelta'` error

**Solution needed**:
```python
if args.input_normalization and args.input_normalization.lower() != "none":
    if not getattr(args, 'inference_mode', False):
        # TRAINING: Compute new scaling factors
        inputs_df, scaling_factors = normalize_dataframe(inputs_df, method=args.input_normalization)
        # Save scaling factors...
    else:
        # INFERENCE: Load and apply saved scaling factors  
        scaler_path = self.output_folder / "input_scaler.joblib"
        if scaler_path.exists():
            import joblib
            scaling_factors = joblib.load(scaler_path)
            inputs_df, _ = normalize_dataframe(inputs_df, method=args.input_normalization, scaling_factors=scaling_factors)
```

### 3. Scores Normalization Issues ❌

**Same problem in load_and_process_scores()** (line 397):
```python
if (args.scores_normalization and args.scores_normalization.lower() != "none" and not getattr(args, 'inference_mode', False)):
    # TRAINING: Scores normalization applied ✅ 
    # INFERENCE: Scores normalization SKIPPED ❌
```

**Impact**: Scores never get normalized during inference, but models expect normalized score ranges.

### 4. Missing Prediction Denormalization ❌

**Critical missing step**: After inference, predictions need to be denormalized using scores_scaler to be comparable to original raw scores.

**Current flow**:
```
Training: Raw scores → normalize_dataframe() → Normalized scores → Model training
Inference: Model predictions → ??? → Should be denormalized to raw score scale
```

**Missing step**: `inverse_normalize_dataframe(predictions, scores_scaling_factors, method='robust')`

### 5. Data Flow Analysis

**Training Data Flow (WORKING)**:
```
CSV → spreadsheet_to_input_df() → Time → Timedelta → normalize_dataframe() → Numeric → Save scalers → UMAP/Models
Raw scores → normalize_dataframe() → Normalized scores → Model training
```

**Current Inference Flow (BROKEN)**:
```
CSV → spreadsheet_to_input_df() → Time → Timedelta → SKIP normalization → Object/Timedelta → UMAP fails
No scores normalization → No denormalization of predictions
```

**Target Inference Flow (NEEDED)**:
```
CSV → spreadsheet_to_input_df() → Time → Timedelta → normalize_dataframe(saved factors) → Numeric → UMAP success
Model predictions → inverse_normalize_dataframe(scores factors) → Raw score scale predictions
```

## Complete Solution Plan

### Phase 1: Fix Input Normalization in EMUSESPipeline ⚠️

**File**: `emuses/pipelines/emuses_pipeline.py` lines 321-350

**Change**: Modify logic to apply saved scaling factors during inference:
```python
if args.input_normalization and args.input_normalization.lower() != "none":
    if not getattr(args, 'inference_mode', False):
        # TRAINING MODE: Compute and save scaling factors
        # (existing logic)
    else:
        # INFERENCE MODE: Load and apply saved scaling factors
        scaler_path = self.output_folder / "input_scaler.joblib" 
        if scaler_path.exists():
            import joblib
            scaling_factors = joblib.load(scaler_path)
            inputs_df, _ = normalize_dataframe(inputs_df, method=args.input_normalization, scaling_factors=scaling_factors)
            self.logger.info(f"Applied saved input normalization ({args.input_normalization}) during inference")
        else:
            self.logger.warning("Input scaler not found, skipping normalization")
```

### Phase 2: Fix Scores Normalization in EMUSESPipeline ⚠️

**File**: `emuses/pipelines/emuses_pipeline.py` lines 397-425

**Change**: Similar logic for scores normalization during inference.

### Phase 3: Remove Duplicate Normalization from InferenceStage ✅

**Status**: Already completed - removed duplicate normalization code.

### Phase 4: Add Prediction Denormalization to InferenceStage ⚠️

**File**: `emuses/pipelines/inference_stage.py` - after model predictions

**Add**: Denormalization step using scores scaler:
```python
# After ensemble predictions are computed
if 'scores_scaler' in models and models['scores_scaler'] is not None:
    scores_scaler = models['scores_scaler'] 
    scores_method = models.get('metadata', {}).get('scores_normalization_method', 'min-max')
    
    # Convert predictions to DataFrame for denormalization
    pred_df = pd.DataFrame(ensemble_predictions, columns=['prediction'])
    denorm_df = inverse_normalize_dataframe(pred_df, scores_scaler, method=scores_method)
    ensemble_predictions = denorm_df['prediction'].values
    
    logger.info(f"Applied prediction denormalization ({scores_method}) to restore original score scale")
```

## Implementation Priority

1. **HIGHEST**: Phase 1 (Input normalization) - Fixes immediate UMAP failure
2. **HIGH**: Phase 2 (Scores normalization) - Ensures model consistency  
3. **HIGH**: Phase 4 (Prediction denormalization) - Makes outputs meaningful
4. **DONE**: Phase 3 (Remove duplicate normalization) - Already completed

## Expected Results

After all fixes:
- ✅ EMUSESPipeline converts Timedelta → Numeric during inference
- ✅ UMAP receives proper numeric input ranges
- ✅ KernelRegressor gets correct [0,1] embedding coordinates  
- ✅ Model predictions are denormalized to original score scale
- ✅ Zero predictions issue resolved
- ✅ Inference outputs comparable to training scores

## Risk Assessment

**Low risk**: BCBlib functions are well-tested and reversible
**Medium risk**: Must ensure scaler loading works correctly during inference
**High impact**: Fixes the core zero predictions issue completely