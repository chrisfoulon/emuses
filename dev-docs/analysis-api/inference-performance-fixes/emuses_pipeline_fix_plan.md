# EMUSESPipeline Inference Normalization Fix

## Current Issue
```python
# Line 321 in EMUSESPipeline - WRONG LOGIC  
if args.input_normalization and args.input_normalization.lower() != "none" and not getattr(args, 'inference_mode', False):
    # Normalization only happens during training, SKIPPED during inference!
```

## Problem
- **Training**: ✅ Normalization applied, scaler saved  
- **Inference**: ❌ **Normalization completely skipped** → Object/Timedelta columns remain → UMAP fails

## Solution
**Inference mode should load and apply saved scaler parameters**, not skip normalization entirely.

## Correct Logic
```python
if args.input_normalization and args.input_normalization.lower() != "none":
    if not getattr(args, 'inference_mode', False):
        # TRAINING MODE: Compute new scaling factors  
        inputs_df, scaling_factors = normalize_dataframe(inputs_df, method=args.input_normalization)
        # Save scaler...
    else:
        # INFERENCE MODE: Load saved scaler and apply it
        scaler_path = Path(args.output_folder) / "input_scaler.joblib"
        if scaler_path.exists():
            import joblib
            scaling_factors = joblib.load(scaler_path) 
            inputs_df, _ = normalize_dataframe(inputs_df, method=args.input_normalization, scaling_factors=scaling_factors)
```

This ensures:
- ✅ Training: Computes and saves scaler parameters
- ✅ Inference: Loads and applies training scaler parameters 
- ✅ Consistent normalization between training and inference
- ✅ Timedelta columns get properly converted to numeric