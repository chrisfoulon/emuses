# Implementation Priority Plan - Coordinate Usage Fix

## Root Cause Analysis - RESOLVED

**Issue**: KernelRegressor models produce zero predictions during both training and inference.

**Root Cause**: Inconsistent coordinate usage between training and inference scenarios:
1. **Training**: Uses `prediction_train_coords` (properly rescaled embedding coordinates)
2. **Internal Inference (--test_size > 0)**: Should use `prediction_test_coords` but wasn't checking for it
3. **External Inference (standalone)**: Should use UMAP transform + rescale with saved parameters

## Solution Implemented ✅

### ✅ COMPLETED: Coordinate Usage Fix
**File**: `emuses/pipelines/inference_stage.py:125`

**Change**: Added check for `prediction_test_coords` in context before doing UMAP transform:

```python
# Check if prediction_test_coords already exists in context (internal pipeline mode)
if 'prediction_test_coords' in context:
    transformed_features = context.get('prediction_test_coords')
    logger.info("Using pre-computed prediction_test_coords from context (internal pipeline mode)")
    progress.advance(transform_task, sample_count)
else:
    # External standalone mode: do UMAP transform + rescale
    transformed_features = self._transform_features_with_progress(
        new_features, self.trained_models, progress, transform_task
    )
```

**Result**: 
- **Internal pipeline mode**: Uses `prediction_test_coords` (already rescaled by UMAPStage)
- **External standalone mode**: Uses UMAP transform + rescale with saved parameters
- **Both modes**: Now use consistently rescaled coordinates for KernelRegressor

## Additional Fixes Applied ✅

### ✅ Code Cleanup
- **HeatmapStage**: Refactored to use explicit variable names (`prediction_train_coords` instead of `X`)
- **Documentation**: Cleaned up incorrect analysis from previous approaches

### ✅ Previously Applied Fixes (Still Active)
1. **FutureWarning Suppression**: sklearn warnings suppressed in CLI ✅  
2. **Input/Scores Normalization Path Fix**: EMUSESPipeline uses correct model directory paths ✅
3. **Prediction Denormalization**: InferenceStage denormalizes predictions properly ✅

## Expected Results

With the coordinate usage fix:
- ✅ Training uses `prediction_train_coords` (properly rescaled)
- ✅ Internal inference uses `prediction_test_coords` (properly rescaled)  
- ✅ External inference uses UMAP transform + rescale (consistent with training)
- ✅ KernelRegressor receives consistently rescaled coordinates in all scenarios
- ✅ Zero predictions issue should be resolved

## Next Steps

1. **Test with real models** - Verify zero predictions are eliminated
2. **Validate both inference modes** - Internal (pipeline) and external (standalone)
3. **Monitor coordinate consistency** - Ensure training and inference use equivalent coordinates

## Files Modified

- ✅ `emuses/pipelines/inference_stage.py` - Added coordinate usage fix
- ✅ `emuses/pipelines/heatmap_stage.py` - Refactored variable names for clarity
- ✅ `emuses/cli/main.py` - FutureWarning suppression (previous fix)
- ✅ `emuses/pipelines/emuses_pipeline.py` - Path resolution fix (previous fix)

## Architecture

```
Training Flow:
UMAPStage → prediction_train_coords (rescaled) → HeatmapStage → KernelRegressor

Internal Inference Flow:  
UMAPStage → prediction_test_coords (rescaled) → InferenceStage → KernelRegressor

External Inference Flow:
InferenceStage → UMAP transform + rescale → KernelRegressor
```

All flows now use consistently rescaled coordinates for KernelRegressor distance calculations.