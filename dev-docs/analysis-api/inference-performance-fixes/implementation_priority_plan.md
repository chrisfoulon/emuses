# Implementation Priority Plan - Normalization Pipeline Fix

## Executive Summary

**Current Status**: Phase 1 was incorrectly marked complete. KernelRegressor models still produce zero predictions due to EMUSESPipeline completely skipping normalization during inference mode.

**Root Cause**: EMUSESPipeline has logic `and not getattr(args, 'inference_mode', False)` that skips ALL normalization during inference, leaving Object/Timedelta columns that UMAP cannot process.

## Implementation Priority (High → Low)

### 🔴 CRITICAL: Task 1.1 - Fix EMUSESPipeline Input Normalization Logic

**File**: `emuses/pipelines/emuses_pipeline.py` line ~321  
**Current broken logic**:
```python
if args.input_normalization and args.input_normalization.lower() != "none" and not getattr(args, 'inference_mode', False):
    # PROBLEM: Normalization only during training, SKIPPED during inference
```

**Fix needed**:
```python
if args.input_normalization and args.input_normalization.lower() != "none":
    if not getattr(args, 'inference_mode', False):
        # TRAINING MODE: Compute new scaling factors
        inputs_df, scaling_factors = normalize_dataframe(inputs_df, method=args.input_normalization)
        # Save scaler to joblib file
        scaler_path = Path(self.output_folder) / "input_scaler.joblib"
        import joblib
        joblib.dump(scaling_factors, scaler_path)
        self.logger.info(f"Saved input scaler ({args.input_normalization}) to {scaler_path}")
    else:
        # INFERENCE MODE: Load and apply saved scaler
        scaler_path = Path(self.output_folder) / "input_scaler.joblib" 
        if scaler_path.exists():
            import joblib
            scaling_factors = joblib.load(scaler_path)
            inputs_df, _ = normalize_dataframe(inputs_df, method=args.input_normalization, scaling_factors=scaling_factors)
            self.logger.info(f"Applied saved input normalization ({args.input_normalization}) during inference")
        else:
            self.logger.warning("Input scaler not found, skipping normalization - this may cause inference failures")
```

### 🔴 CRITICAL: Task 1.2 - Fix EMUSESPipeline Scores Normalization Logic

**File**: `emuses/pipelines/emuses_pipeline.py` line ~397  
**Same issue**: Scores normalization also skipped during inference mode.

**Fix needed**: Similar logic change as input normalization, but save/load `scores_scaler.joblib`

### 🟡 HIGH: Task 1.3 - Add Prediction Denormalization to InferenceStage

**File**: `emuses/pipelines/inference_stage.py` - after ensemble predictions computed  
**Purpose**: Convert predictions back to original score scale for user interpretation

**Implementation**:
```python
# After ensemble predictions computed
scores_scaler_path = model_base_path / "scores_scaler.joblib"
if scores_scaler_path.exists():
    import joblib
    from bcblib.tools.dataframe_filtering import inverse_normalize_dataframe
    
    scores_scaler = joblib.load(scores_scaler_path)
    scores_method = 'robust'  # or detect from metadata
    
    # Convert predictions to DataFrame for denormalization
    pred_df = pd.DataFrame(ensemble_predictions, columns=['prediction'])
    denorm_df = inverse_normalize_dataframe(pred_df, scores_scaler, method=scores_method)
    ensemble_predictions = denorm_df['prediction'].values
    
    logger.info(f"Applied prediction denormalization ({scores_method}) to restore original score scale")
```

### 🟢 MEDIUM: Task 1.4 - End-to-End Validation

Test with real KernelRegressor models to verify:
- No more zero predictions  
- Input ranges correct for UMAP
- Predictions in meaningful score ranges
- No regression in ElasticNet models

## Expected Results After Implementation

- ✅ EMUSESPipeline converts Timedelta → Numeric during inference
- ✅ UMAP receives proper numeric input ranges
- ✅ KernelRegressor gets correct embeddings and produces non-zero predictions
- ✅ Predictions denormalized to original score scale
- ✅ Zero predictions issue completely resolved

## Implementation Notes

- **BCBlib ready**: `normalize_dataframe()` and `inverse_normalize_dataframe()` functions fully support the needed operations
- **Scaler persistence**: Use joblib.dump/load for sklearn RobustScaler objects 
- **Backward compatibility**: Check for scaler file existence, graceful degradation if missing
- **Logging**: Informative messages for debugging and user feedback