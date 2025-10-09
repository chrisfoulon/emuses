# EMUSES Architecture Principles - MANDATORY READING FOR ALL CLAUDE SESSIONS

**⚠️ CRITICAL: READ THIS FIRST BEFORE ANY MODEL REGISTRY WORK ⚠️**

## What Went Wrong Previously

A Claude session implemented a "complete model" system that **FUNDAMENTALLY VIOLATED** EMUSES architecture by treating model components as separable entities. This created parallel abstractions that competed with existing proven code.

**The core mistake**: Building `CompleteEmusesModel` class and treating UMAP, HDBSCAN, and prediction models as interchangeable components between different training runs.

## EMUSES Architecture Truth (Non-Negotiable)

### What EMUSES Models Actually ARE

**EMUSES Model = Complete Training Run Folder** (atomic unit)

```
model_registry_final/  ← This ENTIRE folder IS the "EMUSES model"
├── model_manifest.json                    # Root manifest (HDBSCAN-focused)
├── best_umap_model_v1_0_0_joblib1_5_1.joblib      # UMAP component
├── hdbscan_model_v1_0_0_joblib1_5_1.joblib        # HDBSCAN component
├── embeddings.npy                         # Training embeddings
├── cluster_labels.npy                     # Training cluster labels
├── input_matrix.npy                       # Original features
├── target_0/                              # Prediction models directory
│   ├── model_manifest.json               # Target-specific manifest
│   ├── best_pipeline_fold0_v1_0_0_joblib1_5_1.joblib  # CV fold 0
│   ├── best_pipeline_fold1_v1_0_0_joblib1_5_1.joblib  # CV fold 1
│   ├── best_pipeline_fold2_v1_0_0_joblib1_5_1.joblib  # CV fold 2
│   ├── best_pipeline_fold3_v1_0_0_joblib1_5_1.joblib  # CV fold 3
│   └── best_pipeline_fold4_v1_0_0_joblib1_5_1.joblib  # CV fold 4
├── databases/                             # Optuna study databases
├── performance_summary/                   # Training performance data
└── plots/                                # Visualization outputs
```

### Critical Architecture Rules

#### ✅ ALWAYS TRUE
1. **All components trained together** on the same dataset
2. **Components are NOT interchangeable** between different EMUSES folders
3. **Folder is atomic unit** - cannot separate or mix components
4. **Each folder contains multiple manifests** (root + target-specific)
5. **InferenceStage already works perfectly** with complete folders

#### ❌ NEVER TRUE  
1. **Components are NOT separable** between training runs
2. **Components are NOT reusable** across different datasets
3. **UMAP from folder A + HDBSCAN from folder B = INVALID**
4. **Individual component registration = ARCHITECTURAL VIOLATION**

## What Registry Should DO (Correct Approach)

### Registry Role: EMUSES Folder Lookup Service ONLY

```python
# CORRECT: Registry as path resolution service
class LocalModelRegistry:
    def get_model_path(self, model_id: str) -> Path:
        """Resolve model ID to complete EMUSES training folder path."""
        # Simple lookup - NO model abstractions
        
def inference_with_registry(model_id: str, data_path: Path):
    registry = LocalModelRegistry()
    folder_path = registry.get_model_path(model_id)  # Registry lookup
    
    # Use existing proven InferenceStage (unchanged)
    config = PipelineConfig(model_path=folder_path, data_path=data_path)
    inference_stage = InferenceStage(config)
    return inference_stage.run()  # Existing working code
```

### Registry Operations (Allowed)
- ✅ Map model IDs to complete folder paths
- ✅ Validate folder contains complete EMUSES structure
- ✅ Store metadata about complete training runs
- ✅ Provide path resolution for CLI/API convenience

## What Registry Should NEVER DO (Forbidden)

### Architectural Violations (Never Implement These)

```python
# ❌ NEVER: Individual component registration
registry.register_umap_model(umap_path)  # WRONG
registry.register_hdbscan_model(hdbscan_path)  # WRONG
registry.register_prediction_model(pred_path)  # WRONG

# ❌ NEVER: Model abstractions or wrappers
class CompleteEmusesModel:  # WRONG - parallel abstraction
    def load_components(self):  # WRONG - treats as separable
        self.umap = load_umap()
        self.hdbscan = load_hdbscan()  # WRONG

# ❌ NEVER: Component detection patterns  
def _detect_umap_component():  # WRONG - ignores folder structure
def _detect_hdbscan_component():  # WRONG - pattern-based detection
def _detect_prediction_component():  # WRONG - treats as separate

# ❌ NEVER: Duplicate inference functionality
class CompleteModel:
    def predict(self, data):  # WRONG - duplicates InferenceStage
        # InferenceStage already does this perfectly
```

## Existing Code That Works (Preserve Unchanged)

### InferenceStage (Perfect As-Is)
```python
# This ALREADY works with complete EMUSES folders
config = PipelineConfig(model_path="/path/to/model_registry_final/", ...)
inference_stage = InferenceStage(config)
results = inference_stage.run()  # Complete pipeline: UMAP → Scale → Predict
```

**Do NOT modify InferenceStage** - it already handles complete model folders perfectly.

### Native EMUSES Manifests (Use As-Is)
- `model_manifest.json` (root) - contains HDBSCAN metadata
- `target_0/model_manifest.json` - contains prediction metadata
- Use existing manifest data, don't create parallel metadata

## Critical Missing Component: Feature Augmentation Models

### Currently Missing (Must Be Added)
```
model_registry_final/
├── feature_models/                        # MISSING DIRECTORY
│   ├── pca_model_v1_0_0.joblib           # PCA for GWD dimensionality reduction
│   ├── kpca_model_v1_0_0.joblib          # Kernel PCA for non-linear reduction
│   └── autoencoder_v1_0_0.joblib         # Neural network feature models
```

**These are ESSENTIAL for inference** - new data must use the SAME feature transformations as training data.

## Error Prevention for Future Sessions

### Before Any Implementation, Ask:
1. **"Am I creating model abstractions?"** → If yes, STOP - architectural violation
2. **"Am I treating components as separable?"** → If yes, STOP - wrong approach  
3. **"Am I duplicating InferenceStage functionality?"** → If yes, STOP - use existing
4. **"Does this work with complete EMUSES folders?"** → Must be YES

### Red Flags (Stop Immediately If You See These)
- Creating classes that wrap individual components
- Pattern-based detection of UMAP/HDBSCAN/prediction files
- Registering individual models separately
- Building inference methods that compete with InferenceStage
- Treating manifests as incomplete metadata needing enhancement

### Green Flags (Correct Approach)
- Simple path lookup from model ID to folder
- Preserving InferenceStage completely unchanged
- Working with native EMUSES folder structure
- Using existing manifest data without modification
- Testing with real `model_registry_final/` outputs

## Implementation Requirements

### Must Validate BEFORE Any Changes
```python
# Test this works with real EMUSES folder FIRST
def test_basic_concept():
    real_folder = Path("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/model_registry_final")
    
    # Simple registry concept
    registry_lookup = {"test_model": real_folder}
    resolved_path = registry_lookup["test_model"]
    
    # Must work with existing InferenceStage unchanged
    config = PipelineConfig(model_path=resolved_path, ...)
    inference_stage = InferenceStage(config)
    result = inference_stage.run()
    
    assert result is not None  # Must succeed
```

### CLI Enhancement (Correct Way)
```python
def inference(
    model: Optional[Path] = None,  # Existing file-based option
    model_id: Optional[str] = None,  # New registry option
    data: Path = ...,
):
    if model_id:
        registry = LocalModelRegistry()
        model = registry.get_model_path(model_id)  # Simple lookup
    
    # Use existing InferenceStage (no changes)
    config = PipelineConfig(model_path=model, data_path=data)
    inference_stage = InferenceStage(config)
    return inference_stage.run()
```

## Success Criteria

### Functional Requirements
- ✅ Registry resolves model IDs to complete folder paths
- ✅ InferenceStage works unchanged with resolved paths
- ✅ CLI supports both --model and --model-id options
- ✅ Only complete EMUSES folders can be registered

### Architectural Requirements  
- ✅ No model abstractions or wrappers created
- ✅ Native EMUSES folder structure preserved
- ✅ Existing InferenceStage functionality unchanged
- ✅ Registry as service layer only, not model layer

### Quality Requirements
- ✅ Integration tests with real EMUSES folders pass
- ✅ Feature augmentation models tracked and validated
- ✅ Documentation reflects correct architecture
- ✅ No duplicate inference functionality created

---

**Remember**: The goal is registry CONVENIENCE, not architectural CHANGE. EMUSES already works perfectly - we're just adding model ID lookup for user convenience.