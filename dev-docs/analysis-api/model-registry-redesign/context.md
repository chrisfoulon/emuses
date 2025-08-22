# Model Registry Architecture Fix - Implementation Context

⚠️ **CRITICAL STATUS CORRECTION**: Previous context was incorrect - implementation contains fundamental architectural violations

## What This Feature Actually Fixes

### The Fundamental Problem (Clearly Documented)
Previous implementation created **architectural violations** by treating EMUSES model components (UMAP, HDBSCAN, prediction) as separable entities. This is **fundamentally wrong**.

**EMUSES Truth**: Models are complete training folder units where all components are trained together and are NOT interchangeable between datasets.

### The Correct Solution
**Registry as EMUSES Folder Lookup Service**: Map model IDs to complete folder paths, preserve existing InferenceStage unchanged.

## Level 1: Plain English Summary

### What EMUSES Models Actually Are
**Complete training folder** (`model_registry_final/`) containing:
- UMAP model for dimensionality reduction
- HDBSCAN model for clustering  
- Prediction models (ensemble in `target_*` directories)
- Training metadata and manifests
- **All trained together** on same dataset (atomic unit)

### What Registry Should Do
**Path lookup service ONLY**:
1. Register complete EMUSES training folders
2. Map model IDs to folder paths
3. Validate folder contains complete structure
4. Provide path resolution for CLI/API convenience

### What Registry Should NEVER Do
❌ Register individual components separately  
❌ Create model abstractions or wrappers  
❌ Duplicate InferenceStage functionality  
❌ Pattern-based component detection

### What Currently Works (Preserve Unchanged)
**InferenceStage** already handles complete model folders perfectly:
```python
# This works and should remain unchanged
config = PipelineConfig(model_path="/path/to/model_registry_final/", ...)
inference_stage = InferenceStage(config)
results = inference_stage.run()  # Complete pipeline: UMAP → Scale → Predict
```

## Level 2: API Integration Table

| Symbol | Purpose | Inputs | Outputs | Side-effects |
|--------|---------|--------|---------|--------------|
| `LocalModelRegistry.get_model_path()` | Resolve model ID to folder path | model_id: str | Path to EMUSES folder | None |
| `LocalModelRegistry.install_model()` | Register complete EMUSES folder | folder_path: Path, name: str | model_id: str | Registry entry created |
| `inference --model-id` | CLI inference with registry lookup | model_id, data_path | Inference results | None |
| `InferenceStage.run()` | Complete EMUSES inference pipeline | model_path: Path, data_path: Path | Predictions + metadata | None (existing code) |
| `_validate_emuses_folder()` | Validate complete folder structure | folder_path: Path | bool (valid/invalid) | None |

## Level 3: Code Integration Points

### Registry Path Resolution (Core Integration)
```python
# CORRECT: Registry as simple lookup service
class LocalModelRegistry:
    def get_model_path(self, model_id: str) -> Path:
        """Resolve model ID to complete EMUSES training folder path.
        
        Returns
        -------
        Path
            Path to complete EMUSES folder containing all components
        """
        if model_id not in self.models:
            raise KeyError(f"Model not found: {model_id}")
        return Path(self.models[model_id])

# Usage with existing InferenceStage (unchanged)
registry = LocalModelRegistry()
folder_path = registry.get_model_path("HCP_Model_v1_abc123")
config = PipelineConfig(model_path=folder_path, data_path=data_path)
inference_stage = InferenceStage(config)
results = inference_stage.run()  # Existing proven code
```

### CLI Enhancement (Minimal Change)
```python
def inference(
    model: Optional[Path] = typer.Option(None, help="Path to model directory"),
    model_id: Optional[str] = typer.Option(None, help="Registry model ID"),
    data: Path = typer.Argument(..., help="Path to input data"),
    # ... existing parameters unchanged
):
    """Run inference with EMUSES model (file path or registry ID)."""
    
    # Validation: exactly one of model or model_id required
    if not (model or model_id) or (model and model_id):
        raise typer.BadParameter("Provide either --model or --model-id, not both")
    
    # Registry path resolution (only addition)
    if model_id:
        registry = LocalModelRegistry()
        model = registry.get_model_path(model_id)
    
    # Use existing InferenceStage (completely unchanged)
    config = PipelineConfig(model_path=model, data_path=data, ...)
    inference_stage = InferenceStage(config)
    return inference_stage.run()
```

### EMUSES Folder Validation
```python
def _validate_emuses_folder(self, folder_path: Path) -> bool:
    """Validate complete EMUSES training folder structure.
    
    Required components:
    - model_manifest.json (root manifest)
    - *umap*.joblib (UMAP model file)
    - *hdbscan*.joblib (HDBSCAN model file)
    - target_*/model_manifest.json (prediction manifests)
    - target_*/best_pipeline_fold*.joblib (CV fold models)
    
    Future requirement:
    - feature_models/*.joblib (PCA/kPCA/Autoencoder)
    """
    # Check core components
    has_root_manifest = (folder_path / "model_manifest.json").exists()
    has_umap = len(list(folder_path.glob("*umap*.joblib"))) > 0
    has_hdbscan = len(list(folder_path.glob("*hdbscan*.joblib"))) > 0
    
    # Check prediction ensemble
    target_dirs = list(folder_path.glob("target_*"))
    has_predictions = any(
        (target_dir / "model_manifest.json").exists() and
        len(list(target_dir.glob("best_pipeline_fold*.joblib"))) > 0
        for target_dir in target_dirs
    )
    
    return has_root_manifest and has_umap and has_hdbscan and has_predictions
```

## Architecture Violations to Remove

### Files to Delete Completely
```python
# ❌ DELETE: emuses/models/complete_emuses_model.py
class CompleteEmusesModel:  # WRONG - parallel abstraction
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.registry = LocalModelRegistry()
        # This creates competing system with InferenceStage
    
    def predict(self, data):  # WRONG - duplicates InferenceStage
        # InferenceStage already does this perfectly

# ❌ DELETE: emuses/api/complete_model_endpoints.py  
@router.get("/models/{model_id}/components")
def get_model_components():  # WRONG - treats as separable
    # Components should never be accessed individually
```

### Code to Revert
```python
# ❌ REVERT: Changes to emuses/pipelines/inference_stage.py
# Remove registry integration added to InferenceStage
self.complete_model_id = getattr(config, 'complete_model_id', None)
self.complete_model = None
# InferenceStage should remain file-based only

# ❌ REVERT: Changes to emuses/cli/main.py  
# Remove --complete-model option added to inference command
# Keep original signature: inference(model: Path, data: Path, ...)
```

### Pattern Detection to Remove
```python
# ❌ REMOVE: Component detection patterns in model_io.py
def _detect_umap_component(self, model_path: Path):  # WRONG approach
def _detect_hdbscan_component(self, model_path: Path):  # WRONG approach  
def _detect_prediction_component(self, model_path: Path):  # WRONG approach
# These ignore native EMUSES folder structure
```

## Critical Missing Component: Feature Augmentation Models

### Current Gap (Must Address)
EMUSES training may use feature augmentation models that are **essential for inference**:

```python
# Missing models that MUST be tracked:
feature_models/
├── pca_model_v1_0_0.joblib           # PCA for GWD dimensionality reduction
├── kpca_model_v1_0_0.joblib          # Kernel PCA for non-linear reduction  
└── autoencoder_v1_0_0.joblib         # Neural network feature models
```

**Why Critical**: New data must use the SAME feature transformations as training data. Without these models, inference pipeline is incomplete.

### Implementation Required
```python
# Enhanced folder validation (Phase 4)
def _validate_emuses_folder_with_features(self, folder_path: Path) -> bool:
    """Enhanced validation including feature augmentation models."""
    
    # Core validation (existing)
    is_valid_core = self._validate_emuses_folder(folder_path)
    
    # Feature augmentation check (new requirement)
    feature_dir = folder_path / "feature_models"
    if feature_dir.exists():
        # Validate feature models are properly stored
        pca_models = list(feature_dir.glob("*pca*.joblib"))
        kpca_models = list(feature_dir.glob("*kpca*.joblib"))
        ae_models = list(feature_dir.glob("*autoencoder*.joblib"))
        
        # At least one feature model type should exist if directory present
        has_feature_models = len(pca_models + kpca_models + ae_models) > 0
        return is_valid_core and has_feature_models
    
    return is_valid_core  # Feature models optional for now
```

## Testing Strategy with Real Data

### Integration Testing Requirements
```python
# CRITICAL: Test with actual EMUSES training output
real_folder = Path("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/model_registry_final")

def test_registry_with_real_emuses_folder():
    """Test registry using actual EMUSES training output."""
    registry = LocalModelRegistry()
    
    # Test registration
    model_id = registry.install_model(real_folder, name="test_model")
    
    # Test path resolution  
    resolved_path = registry.get_model_path(model_id)
    assert resolved_path == real_folder
    
    # Test InferenceStage integration (critical test)
    config = PipelineConfig(model_path=resolved_path, ...)
    inference_stage = InferenceStage(config)
    results = inference_stage.run()  # Must work unchanged
    assert results is not None
```

### Error Condition Testing
```python
def test_error_conditions():
    """Test registry error handling."""
    registry = LocalModelRegistry()
    
    # Invalid folder structure
    with pytest.raises(ValueError):
        registry.install_model("/invalid/path", name="invalid")
    
    # Missing model ID
    with pytest.raises(KeyError):
        registry.get_model_path("nonexistent_id")
    
    # Corrupted manifest files
    # Missing component files
    # Invalid folder permissions
```

## Implementation Dependencies

### Existing Components to Preserve
- **InferenceStage**: Complete inference pipeline (keep unchanged)
- **ModelIOManager**: Manifest loading/saving (use existing functionality)
- **Native manifests**: `model_manifest.json` files (use as-is, don't create parallel metadata)
- **EMUSES folder structure**: Native training output structure (respect completely)

### Components to Modify
- **LocalModelRegistry**: Enhance for folder-based registration only
- **CLI commands**: Add --model-id option to inference command
- **Model validation**: Focus on complete folder validation, not pattern detection

### Components to Remove
- **CompleteEmusesModel**: Delete entire artificial abstraction
- **Complete model API endpoints**: Delete parallel REST API
- **Component detection patterns**: Remove pattern-based logic
- **Complete model tests**: Delete tests for wrong architecture

## Development Constraints (No Production)

### Simplified Requirements (No Backward Compatibility)
- ✅ Can delete violations directly (no migration needed)
- ✅ Can break existing registry entries (no production data)
- ✅ Can change APIs without versioning (no external users)
- ✅ Can use git revert for recovery (no complex rollback)

### Development Protections (Maintain)
- ⚠️ Don't break core EMUSES pipeline functionality
- ⚠️ Don't break other CLI commands or API modules
- ⚠️ Don't break test suite compatibility
- ⚠️ Maintain development workflow integrity

## Success Criteria

### Functional Validation
- Registry resolves model IDs to complete EMUSES folder paths ✅
- InferenceStage works unchanged with registry-resolved paths ✅
- CLI supports both --model and --model-id options ✅
- Only complete EMUSES folders can be registered ✅
- Feature augmentation models tracked and validated ✅

### Architectural Validation  
- No model abstractions or wrappers exist ✅
- Native EMUSES folder structure preserved ✅
- Registry functions as service layer only ✅
- InferenceStage functionality completely unchanged ✅

### Quality Validation
- Integration tests with real EMUSES folders pass ✅
- Documentation reflects correct architecture ✅
- No duplicate inference functionality exists ✅
- All system components remain functional ✅

---

**Key Implementation Principle**: Registry provides convenience (model ID lookup) without changing EMUSES architecture (complete folders + proven InferenceStage).