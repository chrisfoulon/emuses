# Remaining Normalization Issues

## Coordinate Usage Fix - COMPLETED ✅
The main coordinate usage issue has been resolved with the fix to use `prediction_test_coords` from context.

## Outstanding Issues

### 1. Input Normalization Issue
**Problem**: Input data normalization inconsistency between training and inference
- **Training**: Input normalization applied and scaler saved
- **Inference**: Input normalization may not be consistently applied using the same scaler

**Status**: Partially addressed in previous fixes but needs validation
**Files**: `emuses/pipelines/emuses_pipeline.py` - path resolution fixes applied

### 2. Inference Output Denormalization Issue  
**Problem**: Prediction outputs not properly denormalized during inference
- **Training**: Scores/targets may be normalized for training
- **Inference**: Predictions need to be denormalized to original scale for meaningful results

**Status**: Denormalization logic exists in InferenceStage but needs validation
**Files**: `emuses/pipelines/inference_stage.py` - denormalization code present

## Next Steps

1. **Validate Input Normalization**:
   - Verify scaler loading from correct paths
   - Ensure consistent normalization between training and inference
   - Test with Object/Timedelta column handling

2. **Validate Output Denormalization**:
   - Confirm predictions are denormalized when scores_scaler exists
   - Test denormalization with different normalization methods
   - Verify denormalized predictions are on correct scale

3. **Integration Testing**:
   - Test complete pipeline with normalization + coordinate fixes
   - Validate against known test cases
   - Monitor for Object/Timedelta column persistence

## Current Status
- ✅ **Coordinate usage**: Fixed (main zero predictions issue)
- 🔧 **Input normalization**: Implemented but needs validation  
- 🔧 **Output denormalization**: Implemented but needs validation
- ⏳ **Integration testing**: Required to validate complete fix