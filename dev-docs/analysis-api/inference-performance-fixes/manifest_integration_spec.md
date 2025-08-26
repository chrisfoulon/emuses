# Manifest Integration Specification for Normalization Scalers

## Overview
This document specifies how normalization scalers will integrate with EMUSES' existing ModelIOManager and manifest system for automatic detection and loading during inference.

## Current Manifest Infrastructure

### Existing ModelIOManager Features
- **File**: `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/emuses/tools/model_io.py`
- **Manifest locations**: `manifest.json` or `model_manifest.json` in model directory root
- **Auto-generation**: `_load_or_generate_manifest()` creates manifests from directory structure
- **Integrity verification**: SHA256 hashes for all model files
- **Version management**: Automatic version incrementing with `major.minor.patch` format
- **Integration**: InferenceStage uses `ModelIOManager(base_path=model_dir)` for loading

### Current Manifest Schema
```json
{
  "model_info": {
    "version": "1.0.0",
    "model_type": "complete_emuses_model"
  },
  "file_integrity": {
    "best_umap_model.joblib": {"sha256": "hash_value"},
    "hdbscan_model.joblib": {"sha256": "hash_value"},
    "target_*/best_pipeline_fold*_*.joblib": {"sha256": "hash_value"}
  }
}
```

## Proposed Manifest Extension

### Enhanced Schema with Normalization Support
```json
{
  "model_info": {
    "version": "1.0.0",
    "model_type": "complete_emuses_model"
  },
  "components": {
    "umap_model": "best_umap_model.joblib",
    "cluster_model": "hdbscan_model.joblib",
    "prediction_models": ["target_*/best_pipeline_fold*_*.joblib"]
  },
  "normalization": {
    "scores_scaler": "scores_scaler.joblib",
    "input_scaler": "input_scaler.joblib",
    "scores_method": "standardscaler",
    "input_method": "minmaxscaler",
    "embeddings_rescaling": true
  },
  "file_integrity": {
    "best_umap_model.joblib": {"sha256": "hash_value"},
    "hdbscan_model.joblib": {"sha256": "hash_value"},
    "scores_scaler.joblib": {"sha256": "hash_value"},
    "input_scaler.joblib": {"sha256": "hash_value"}
  }
}
```

### New Fields Specification

#### `normalization` Section
- **Purpose**: Define which normalization methods were used during training
- **Optional**: Only present if normalization was applied during training
- **Fields**:
  - `scores_scaler`: Path to joblib file containing fitted scaler for scores normalization
  - `input_scaler`: Path to joblib file containing fitted scaler for input data normalization  
  - `scores_method`: String identifying normalization method used for scores ("standardscaler", "minmaxscaler", "robustscaler")
  - `input_method`: String identifying normalization method used for input data
  - `embeddings_rescaling`: Boolean indicating if UMAP embeddings use rescaling (always true for EMUSES)

## Implementation Integration Points

### 1. Training Phase - EMUSESPipeline Modifications

#### File: `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/emuses/pipelines/emuses_pipeline.py`

**Scores Normalization** (Line ~388):
```python
# Current code:
scores_df = normalize_dataframe(scores_df, method=args.scores_normalization)

# Enhanced code:
if args.scores_normalization and args.scores_normalization.lower() != "none":
    scores_df, scores_scaler = normalize_dataframe(
        scores_df, method=args.scores_normalization, return_scaler=True
    )
    # Save scaler to model directory
    scores_scaler_path = self.output_folder / "scores_scaler.joblib"
    joblib.dump(scores_scaler, scores_scaler_path)
    # Update context for manifest generation
    self.context["scores_scaler_info"] = {
        "path": "scores_scaler.joblib",
        "method": args.scores_normalization
    }
```

**Input Normalization** (Line ~250):
```python
# Current code (already partially implemented):
if not is_labelled:
    inputs_df, scaling_factors = normalize_dataframe(
        inputs_df, method=args.input_normalization
    )
    self.context["input_scaling_factors"] = scaling_factors

# Enhanced code:
if not is_labelled:
    inputs_df, input_scaler = normalize_dataframe(
        inputs_df, method=args.input_normalization, return_scaler=True
    )
    # Save scaler to model directory
    input_scaler_path = self.output_folder / "input_scaler.joblib"
    joblib.dump(input_scaler, input_scaler_path)
    # Update context for manifest generation
    self.context["input_scaler_info"] = {
        "path": "input_scaler.joblib", 
        "method": args.input_normalization
    }
```

### 2. Manifest Generation - ModelIOManager Enhancement

#### Method: `_generate_manifest_from_directory()`
```python
def _generate_manifest_from_directory(self, model_path: Path) -> Dict[str, Any]:
    # ... existing code ...
    
    # Check for normalization scaler files
    normalization = {}
    scores_scaler = model_path / "scores_scaler.joblib"
    input_scaler = model_path / "input_scaler.joblib"
    
    if scores_scaler.exists():
        normalization["scores_scaler"] = "scores_scaler.joblib"
        # Try to detect method from scaler object
        try:
            scaler = joblib.load(scores_scaler)
            normalization["scores_method"] = type(scaler).__name__.lower()
        except:
            normalization["scores_method"] = "unknown"
    
    if input_scaler.exists():
        normalization["input_scaler"] = "input_scaler.joblib"
        try:
            scaler = joblib.load(input_scaler)
            normalization["input_method"] = type(scaler).__name__.lower()
        except:
            normalization["input_method"] = "unknown"
    
    # UMAP rescaling is standard in EMUSES
    if normalization:
        normalization["embeddings_rescaling"] = True
        manifest["normalization"] = normalization
    
    return manifest
```

### 3. Inference Phase - InferenceStage Loading

#### File: `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/emuses/pipelines/inference_stage.py`

**Enhanced Model Loading** (Method: `_load_trained_models_with_context()`):
```python
def _load_trained_models_with_context(self, context):
    # ... existing UMAP and prediction model loading ...
    
    # Load normalization scalers from manifest
    model_dir = Path(self.model_path)
    model_manager = ModelIOManager(base_path=model_dir)
    manifest = model_manager._load_or_generate_manifest(model_dir)
    
    normalization_info = manifest.get("normalization", {})
    
    # Load input scaler if present
    input_scaler_path = normalization_info.get("input_scaler")
    if input_scaler_path:
        scaler_file = model_dir / input_scaler_path
        if scaler_file.exists():
            try:
                models['input_scaler'] = joblib.load(scaler_file)
                logger.info(f"Loaded input scaler ({normalization_info.get('input_method', 'unknown')}) from {scaler_file}")
            except Exception as e:
                logger.warning(f"Failed to load input scaler: {e}")
    
    # Load scores scaler if present
    scores_scaler_path = normalization_info.get("scores_scaler")
    if scores_scaler_path:
        scaler_file = model_dir / scores_scaler_path
        if scaler_file.exists():
            try:
                models['scores_scaler'] = joblib.load(scaler_file)
                logger.info(f"Loaded scores scaler ({normalization_info.get('scores_method', 'unknown')}) from {scaler_file}")
            except Exception as e:
                logger.warning(f"Failed to load scores scaler: {e}")
    
    return models
```

**Scaler Application in Pipeline**:
```python
def _transform_features_with_umap(self, input_features, models):
    # Apply input normalization if scaler available
    if 'input_scaler' in models and models['input_scaler'] is not None:
        logger.info("Applying saved input normalization before UMAP transform")
        input_features = models['input_scaler'].transform(input_features)
    
    # ... existing UMAP transformation code ...
    
    return transformed_embeddings
```

## Backward Compatibility Strategy

### Graceful Handling of Legacy Models
- **No normalization section**: Continue normal operation (current behavior)
- **Missing scaler files**: Log warning but continue inference
- **Invalid scaler files**: Log error but don't fail inference
- **Version compatibility**: Works with existing manifest versions

### Migration Path
- **Existing models**: Continue working unchanged
- **New models**: Automatically include normalization when training uses it
- **User transparency**: Clear logging indicates when scalers are used vs. not available

## Validation and Testing Strategy

### File Integrity Verification
- Scaler files included in SHA256 hash verification
- Manifest validates scaler file existence before loading
- Corrupted scaler files detected and reported

### Testing Requirements
1. **Manifest generation**: Verify normalization section created when scalers saved
2. **Scaler loading**: Verify scalers loaded correctly from manifest
3. **Application**: Verify normalization applied during inference
4. **Backward compatibility**: Verify old models without scalers continue working
5. **Error handling**: Verify graceful handling of missing/corrupt scaler files

## Implementation Dependencies

1. **normalize_dataframe enhancement**: May need to modify bcblib function or migrate to sklearn
2. **ModelIOManager extension**: Add normalization detection to manifest generation
3. **InferenceStage integration**: Extend model loading to include scalers
4. **Context updates**: Ensure scalers passed through pipeline context properly

This specification provides complete integration with EMUSES' existing infrastructure while maintaining backward compatibility and following established patterns.