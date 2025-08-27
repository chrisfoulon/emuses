# Simple Solution: Save UMAP Embedding Min/Max Parameters

**Date**: 2025-08-27  
**Issue**: UMAP embeddings not scaled during inference, causing all predictions to be zero  
**Simple Solution**: Save `min_embeddings` and `max_embeddings` from UMAPStage and load them during inference

## Root Cause (Confirmed)

**UMAPStage** already calculates scaling parameters during training:
```python
# Lines 195-196 in umap_stage.py
self.min_embeddings = self.embeddings.min(axis=0) 
self.max_embeddings = self.embeddings.max(axis=0)
```

**During training**: These are passed via context to HeatmapStage, so embeddings get properly scaled  
**During inference**: These parameters are lost, so raw embeddings are used → kernel weights = 0

## Simple Solution

### Step 1: Save Min/Max Parameters in UMAPStage

**File**: `emuses/pipelines/umap_stage.py`
**Location**: After line 196 where min/max are calculated

```python
# Rescale embeddings
self.min_embeddings = self.embeddings.min(axis=0)
self.max_embeddings = self.embeddings.max(axis=0)

# NEW: Save embedding scaling parameters
embedding_scaling = {
    'min_embeddings': self.min_embeddings.tolist(),
    'max_embeddings': self.max_embeddings.tolist() 
}
import json
scaling_file = self.output_folder / "embedding_scaling.json"
with open(scaling_file, 'w') as f:
    json.dump(embedding_scaling, f)
self.logger.info(f"Saved embedding scaling parameters to {scaling_file}")
```

### Step 2: Load Min/Max Parameters in InferenceStage

**File**: `emuses/pipelines/inference_stage.py`  
**Location**: Where the warning "Scaling parameters not available" appears

```python
# Try to load embedding scaling parameters
embedding_scaling_file = self.model_path / "embedding_scaling.json"
if embedding_scaling_file.exists():
    with open(embedding_scaling_file, 'r') as f:
        scaling_params = json.load(f)
    min_embeddings = np.array(scaling_params['min_embeddings'])
    max_embeddings = np.array(scaling_params['max_embeddings'])
    
    # Apply the same scaling as during training  
    scaled_embeddings = (embeddings - min_embeddings) / (max_embeddings - min_embeddings)
    logger.info(f"Applied embedding scaling: range [{scaled_embeddings.min():.3f}, {scaled_embeddings.max():.3f}]")
    embeddings = scaled_embeddings
else:
    logger.warning("No embedding scaling parameters found - using raw embeddings")
```

### Step 3: Test the Fix

**Before fix**:
- Training embeddings: [0.0003, 1.000]  
- Inference embeddings: [1.744, 13.594] ← WRONG SCALE
- All predictions identical: 103.969

**After fix**:
- Training embeddings: [0.0003, 1.000]
- Inference embeddings: [0.0, 1.0] ← CORRECT SCALE  
- Predictions vary by sample

## Implementation Details

### File Format: JSON (Simple and Human-Readable)
```json
{
  "min_embeddings": [1.7438721, 0.8234567],
  "max_embeddings": [13.593728, 7.1234567]
}
```

### Error Handling
```python
# In case min == max (degenerate case)
if np.any(max_embeddings - min_embeddings == 0):
    logger.warning("Degenerate embedding range detected - using raw embeddings")
    return embeddings

# Apply scaling
scaled_embeddings = (embeddings - min_embeddings) / (max_embeddings - min_embeddings)
```

### Validation
```python
# Log statistics for debugging
logger.info(f"Embedding scaling applied:")
logger.info(f"  Training range: [{min_embeddings}] to [{max_embeddings}]")
logger.info(f"  Scaled range: [{scaled_embeddings.min():.3f}, {scaled_embeddings.max():.3f}]")
```

## Expected Result

This simple 2-step fix should completely resolve the issue:

1. **Save**: 2 lines in UMAPStage to save min/max to JSON
2. **Load**: 5 lines in InferenceStage to load and apply scaling  

**Total effort**: ~30 minutes to implement + 30 minutes to test = 1 hour

This will restore proper inference functionality without any complex changes to the codebase.