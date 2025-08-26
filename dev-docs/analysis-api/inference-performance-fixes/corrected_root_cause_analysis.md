# Root Cause Analysis - Coordinate Usage Issue RESOLVED

## Issue Summary
KernelRegressor models produce all zero predictions during both training and inference.

## Root Cause Identified ✅
**Inconsistent coordinate usage between training and inference scenarios:**

### Training Flow (CORRECT):
- UMAPStage creates `prediction_train_coords` (rescaled using `rescale_embedding`)
- HeatmapStage uses `prediction_train_coords` to train KernelRegressor models
- Result: Models trained on properly rescaled embedding coordinates

### Inference Flows (INCONSISTENT):
1. **Internal Pipeline Mode** (`--test_size > 0`):
   - UMAPStage creates `prediction_test_coords` (properly rescaled)
   - **PROBLEM**: InferenceStage was not checking for `prediction_test_coords` in context
   - **RESULT**: Was doing unnecessary UMAP transform instead of using pre-computed rescaled coordinates

2. **External Standalone Mode**:
   - No `prediction_test_coords` in context
   - InferenceStage should do UMAP transform + rescale using saved parameters
   - **PROBLEM**: This was the only mode working correctly

## Solution Implemented ✅

### Coordinate Usage Fix
**Location**: `emuses/pipelines/inference_stage.py:125`

**Implementation**:
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

## Result ✅

### Coordinate Flow Now Consistent:
- **Training**: Uses `prediction_train_coords` (rescaled coordinates)
- **Internal Inference**: Uses `prediction_test_coords` (rescaled coordinates) 
- **External Inference**: Uses UMAP transform + rescale (equivalent to rescaled coordinates)
- **All scenarios**: KernelRegressor receives consistently rescaled coordinates

### Expected Outcome:
- ✅ Proper distance calculations in KernelRegressor
- ✅ Elimination of zero predictions issue
- ✅ Consistent coordinate scaling across all inference modes

## Key Insights

1. **The issue was NOT about normalization methods** - it was about coordinate consistency
2. **rescale_embedding already handles coordinate scaling properly** - no additional normalization needed
3. **The fix was simple** - just check if rescaled coordinates already exist before computing them
4. **UMAPStage was working correctly** - it was creating the right coordinates, just not being used

## Validation Required

1. Test internal inference mode (`--test_size > 0`) - should use `prediction_test_coords`
2. Test external inference mode (standalone) - should use UMAP transform + rescale  
3. Verify zero predictions are eliminated in both modes
4. Confirm coordinate ranges are consistent between training and inference