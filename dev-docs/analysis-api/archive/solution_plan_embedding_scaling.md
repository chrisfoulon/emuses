# Solution Plan: Fix Inference Embedding Scaling Issue

**Date**: 2025-08-27  
**Issue**: UMAP embeddings not scaled during inference, causing all predictions to be zero  
**Priority**: CRITICAL  
**Root Cause**: Scale mismatch between training (scaled embeddings) and inference (raw embeddings)

## Root Cause Analysis

### The Problem
- **Training embeddings**: Range [0.0003, 1.000] (properly scaled)
- **Inference embeddings**: Range [1.744, 13.594] (raw UMAP output) 
- **Kernel sigma**: 0.069 (designed for scaled distances)
- **Result**: Minimum distance 7.248 → `exp(-0.5 * (7.248/0.069)²) ≈ exp(-5540) ≈ 0`

### Why This Happens
During **training**, UMAP embeddings are scaled before being used to train kernel models. During **inference**, this scaling step is missing, causing all kernel weights to be zero.

## Evidence From Logs

```
UMAP_DEBUG: Output from UMAP transform: shape=(1067, 2), mean=8.398523, std=2.501345, range=[1.743872, 13.593728]
UMAP_DEBUG: Scaling parameters not available - using raw embeddings
KERNEL_ZERO_ISSUE target_0_best_pipeline_fold0_v1_0_0_joblib1_3_1: ALL PREDICTIONS ARE ZERO!
```

The warning "Scaling parameters not available" is the smoking gun.

## Solution Implementation

### Phase 1: Understand Current Training Pipeline

**Files to investigate:**
- `emuses/pipelines/heatmap_stage.py` - How are embeddings scaled during training?
- `emuses/tools/model_io.py` - Are scaling parameters saved with models?

**Key questions:**
1. Where in training are embeddings scaled?
2. What scaling method is used (StandardScaler, MinMaxScaler, etc.)?
3. Are the scaler parameters saved to disk?
4. Why doesn't inference load these parameters?

### Phase 2: Fix Inference Pipeline

**File**: `emuses/pipelines/inference_stage.py`

**Current problematic code (around line 61):**
```python
UMAP_DEBUG: Scaling parameters not available - using raw embeddings
```

**Required changes:**
1. **Load embedding scaler parameters** during model loading
2. **Apply same scaling** to inference embeddings as was used in training
3. **Validate** that scaled embeddings have similar statistics to training

### Phase 3: Implementation Steps

#### Step 1: Locate Embedding Scaling in Training
```bash
# Find where embeddings are scaled during training
grep -r "scaler" emuses/pipelines/heatmap_stage.py
grep -r "fit_transform" emuses/pipelines/heatmap_stage.py  
grep -r "StandardScaler\|MinMaxScaler" emuses/pipelines/heatmap_stage.py
```

#### Step 2: Save Scaling Parameters
Ensure training saves embedding scaling parameters:
```python
# In training pipeline
embedding_scaler = StandardScaler()  # or whatever scaler is used
scaled_embeddings = embedding_scaler.fit_transform(embeddings)

# Save scaler with model
joblib.dump(embedding_scaler, output_dir / "embedding_scaler.joblib")
```

#### Step 3: Load and Apply During Inference
In `inference_stage.py`:
```python
# Load embedding scaler
embedding_scaler_path = model_path / "embedding_scaler.joblib"
if embedding_scaler_path.exists():
    embedding_scaler = joblib.load(embedding_scaler_path)
    scaled_embeddings = embedding_scaler.transform(raw_embeddings)
    logger.info(f"Applied embedding scaling: {scaled_embeddings.min():.3f} to {scaled_embeddings.max():.3f}")
else:
    logger.warning("No embedding scaler found - using raw embeddings")
    scaled_embeddings = raw_embeddings
```

#### Step 4: Add Validation
```python
# Validate scaled embeddings match training distribution
if hasattr(model, 'X_train'):
    training_stats = f"mean={model.X_train.mean():.3f}, std={model.X_train.std():.3f}"
    inference_stats = f"mean={scaled_embeddings.mean():.3f}, std={scaled_embeddings.std():.3f}"
    logger.info(f"Embedding stats - Training: {training_stats}, Inference: {inference_stats}")
    
    # Warning if distributions are very different
    if abs(scaled_embeddings.mean() - model.X_train.mean()) > 0.5:
        logger.warning("Inference embedding distribution differs significantly from training")
```

### Phase 4: Testing Plan

#### Test 1: Verify Training Saves Scaler
```bash
# Run training and check if embedding_scaler.joblib is created
python -m emuses.cli full test_model/ data.csv --scores scores.csv
ls test_model/embedding_scaler.joblib  # Should exist
```

#### Test 2: Test Inference with Fixed Scaling
```bash
# Run inference and verify predictions are no longer identical
python -m emuses.cli inference results/ data.csv --model test_model/
# Check that predictions vary across samples
```

#### Test 3: Validate Prediction Quality
```bash
# Run inference in validation mode and check R²
python -m emuses.cli inference results/ data.csv --model test_model/ --validate
# R² should be > 0.1 and similar to training performance
```

### Phase 5: Additional Safeguards

#### Add Zero-Prediction Detection
In `kernel_regression_utils.py`, enhance the predict method:
```python
def predict(self, X):
    predictions = []
    for x in X:
        # ... existing code ...
        if weight_sum == 0:
            logger.warning(f"Zero kernel weights for sample - possible scale mismatch")
            prediction = 0  # or np.mean(self.y_train)
        # ... existing code ...
    
    # Check for all-identical predictions (should never happen)
    unique_predictions = len(set(predictions))
    if unique_predictions == 1 and len(predictions) > 1:
        logger.error(f"ALL {len(predictions)} PREDICTIONS ARE IDENTICAL: {predictions[0]}")
        
    return np.array(predictions)
```

#### Add Model Validation
In model saving, validate that loaded models work:
```python
# After training, test model on a few training samples
test_predictions = model.predict(X_train[:5])
if len(set(test_predictions)) == 1:
    raise ValueError("Model produces identical predictions - training failed")
```

## Expected Outcomes

### Before Fix
- All predictions identical: ✅ (BAD)
- R² ≈ -0.01: ✅ (BAD) 
- Kernel weights all zero: ✅ (BAD)

### After Fix
- Predictions vary by sample: ✅ (GOOD)
- R² > 0.1: ✅ (GOOD)
- Kernel weights > 0: ✅ (GOOD)
- Similar performance to training: ✅ (GOOD)

## Timeline
- **Phase 1 (Investigation)**: 2 hours
- **Phase 2 (Implementation)**: 4 hours
- **Phase 3 (Testing)**: 2 hours
- **Phase 4 (Validation)**: 2 hours
- **Total**: 10 hours

This fix should completely resolve the inference failure and restore proper model functionality.