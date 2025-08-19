# Analysis API Enhancement - Technical Context and Architecture

## Current State Analysis

### Critical Infrastructure Issues Discovered ⚠️

#### 1. ModelIOManager Missing Methods (BLOCKING)
**Location**: `emuses/tools/model_io.py`  
**Issue**: Core methods expected by LocalModelRegistry are missing

**Missing Method 1**: `install_model(model_path, destination_path, name=None) -> str`
- **Called from**: `LocalModelRegistry.install_model()` at line 577
- **Expected**: Copy model from source to destination, return unique model_id
- **Current State**: Method doesn't exist, causing `AttributeError`

**Missing Method 2**: `validate_model(model_path) -> Dict[str, Any]`  
- **Called from**: `LocalModelRegistry.install_model()` at line 570
- **Expected**: Return manifest dict `{"name": str, "version": str, "type": str, "description": str}`
- **Current State**: Method doesn't exist, causing `AttributeError`

**Impact**: Model installation via `emuses models install` is completely broken

#### 2. Model Registration Gaps
**HDBSCAN Models**: Currently saved via `ModelIOManager.save_model()` but not discoverable via `emuses models list`
**UMAP Models**: Same issue - saved as files but require manual registration  
**Pattern**: Models are saved during pipeline execution but don't automatically appear in registry

### Existing Analysis Capabilities (Ready for Enhancement)

#### Core Analysis Functions
**Location**: `emuses/tools/kernel_regression_utils.py:646` and `emuses/tools/correlation_maps_utils.py:205`

**`run_kernel_heatmap_analysis()`**: Kernel regression-based effect size mapping
- **Input**: Embeddings, target variables, original data matrix
- **Output**: Statistical maps, effect size plots, uncertainty visualizations
- **Integration**: Uses `save_statistical_maps()` for artifact generation
- **Status**: Mature, extensively tested, ready for integration

**`run_heatmap_analysis()`**: Correlation-based statistical mapping  
- **Input**: Embeddings, target variables, clustering data
- **Output**: Correlation heatmaps, cluster-based statistical maps
- **Integration**: Uses same artifact pipeline as kernel analysis
- **Status**: Production ready, well-integrated with existing pipeline

#### Current Artifact Generation Pipeline
**Pattern**: Both analysis functions use standardized output through `save_statistical_maps()`
```python
save_statistical_maps(
    stat_maps=analysis_results,
    output_folder=output_folder,
    input_type="image|nifti|spreadsheet",
    output_format_info=format_info,
    filename_prefix="stat_map",
    save_output=True,
    generate_plots=True
)
```

**Generated Artifacts**:
- **NIfTI files**: `stat_map_cluster_{cluster}.nii.gz` (medical imaging format)
- **PNG plots**: `stat_map_cluster_{cluster}.png` (statistical visualizations)
- **CSV data**: `stat_map_cluster_{cluster}.csv` (tabular statistical data)

### Current Model and Artifact Storage Patterns

#### Model Storage (Functional)
**UMAP Models**: Saved via `ModelIOManager.save_model()` in `UMAP_utils.py:855`
```python
umap_filepath = manager.save_model(
    model=best_umap_model,
    model_name="best_umap_model",
    model_type="umap",
    config={"best_params": best_params},
    description="Best UMAP model from optimization",
    tags=["optimization", "final_model"]
)
```

**HDBSCAN Models**: Saved via `ModelIOManager.save_model()` in `UMAP_utils.py:713`  
```python
hdbscan_manager.save_model(
    model=best_clusterer,
    model_name="hdbscan_model",
    model_type="hdbscan",
    config={...clustering_parameters...},
    description="HDBSCAN clustering model",
    tags=["clustering", "hdbscan", "optimization"]
)
```

#### Data Artifact Storage (Ready for Extension)
**Embeddings**: `np.save(output_folder / "best_embeddings.npy", best_embeddings)`
**Cluster Labels**: `np.save(cluster_labels_path, best_labels)`
**Performance Metrics**: CSV files with CV scores and fold results

### Model Registry Architecture (Production Ready)

#### Database Schema Analysis  
**Location**: `emuses/multi_user_service/models.py`
**Schema**: Flexible `ModelRegistry` table with JSON tags and classification fields

**Key Fields for Analysis Integration**:
- `model_type`: Can accommodate `"analysis_artifact_*"` types
- `tags`: JSON array perfect for analysis categorization 
- `model_path`: File system path to artifacts
- `manifest_hash`: SHA-256 integrity verification
- `workspace_id`: Scoped access for multi-user scenarios

#### FastAPI Artifact Serving (Ready to Use)
**Endpoint**: `/api/v1/jobs/{job_id}/artifacts/{filename}`
**Capability**: Serves ANY file type with proper content-type detection
**Security**: Path traversal protection, filename sanitization
**Integration**: Works seamlessly with job-based artifact storage

### Inference System Integration Points

#### Current InferenceStage Architecture
**Location**: `emuses/pipelines/inference_stage.py`
**Flow**: Load models → Transform features → Predict → Save results

**Key Integration Points**:
1. **`_transform_features()`**: New data → UMAP embeddings (embedding coordinates)
2. **`_predict_with_progress()`**: Embeddings → prediction values + confidence  
3. **Result formatting**: Currently saves predictions to CSV files

**Enhancement Opportunity**: After step 1, we can visualize transformed embeddings on existing training analysis artifacts

#### Model Loading Pattern
**Current**: Loads UMAP and prediction models using `ModelIOManager.load_model()`
**Enhancement**: Extend to load analysis artifacts (embeddings, clusters, heatmaps) alongside models

### Analysis Ecosystem Architecture Design

#### Complete Analysis Artifact Package Structure
```
model_package/
├── models/                          # Reusable inference models (EXISTING)
│   ├── best_umap_model.joblib       # Transform new data to embeddings
│   ├── hdbscan_model.joblib         # Assign new data to existing clusters
│   └── prediction_models/           # Generate predictions for new data
├── analysis/                        # Analysis artifacts (NEW)
│   ├── training_data/               # Training context for visualization
│   │   ├── embeddings.npy           # Original training UMAP coordinates  
│   │   ├── scaled_embeddings.npy    # Preprocessed coordinates
│   │   ├── cluster_labels.npy       # Training cluster assignments
│   │   └── training_labels.npy      # Target variables (permission-controlled)
│   ├── statistical_maps/            # Generated during training
│   │   ├── effect_size_maps/        # Per-cluster effect size visualizations
│   │   ├── grid_predictions/        # 100x100 spatial prediction grids
│   │   └── statistical_plots/       # PNG/HTML statistical visualizations  
│   ├── interactive_plots/           # HTML Plotly visualizations
│   │   ├── embeddings_clustering.html   # Interactive clustering plots
│   │   └── embeddings_scores.html       # Score-colored embedding plots
│   └── metadata/
│       └── analysis_manifest.json   # Analysis parameters and metadata
```

#### Permission System Integration
**Public Access**: Statistical maps, interactive plots, grid predictions
**Researcher Access**: Training embeddings, cluster data, analysis parameters  
**Admin Access**: Raw training labels and sensitive data

### Integration Strategy with Existing Systems

#### No Breaking Changes Required
**Model Registry**: Existing schema accommodates analysis artifacts via `model_type` and `tags`
**FastAPI**: Current artifact serving works for any file type
**Job System**: Analysis artifacts fit existing job output directory structure
**CLI**: Model installation pattern extends to analysis artifact installation

#### Backward Compatibility Preservation
**Existing Workflows**: All current EMUSES functionality continues unchanged
**Progressive Enhancement**: Analysis features are additive, not replacements
**Configuration Driven**: New capabilities enabled via configuration flags

### Implementation Integration Points

#### Phase 1: ModelIOManager Fixes (Critical)
**Files Modified**: `emuses/tools/model_io.py`
**Methods Added**: `install_model()`, `validate_model()`
**Integration**: Enables basic model registry functionality
**Risk**: High (core infrastructure changes require extensive testing)

#### Phase 2: HeatmapStage Enhancement
**File Modified**: `emuses/pipelines/heatmap_stage.py`  
**Location**: After existing Optuna CV loop (around line 427)
**Integration**: Add analysis artifact generation using existing functions
**Risk**: Low (uses existing `save_statistical_maps()` pattern)

#### Phase 3: InferenceStage Enhancement  
**File Modified**: `emuses/pipelines/inference_stage.py`
**Integration Point**: After `_transform_features()`, before results saving
**New Capabilities**: Load training artifacts, generate overlay visualizations
**Risk**: Medium (complex but well-defined integration points)

#### Phase 4: FastAPI Extension
**New Files**: Analysis artifact serving endpoints
**Integration**: Leverage existing job artifact serving infrastructure  
**Scope**: Permission-controlled access to training data and analysis results
**Risk**: Medium (API design complexity, security considerations)

### Development Architecture Patterns

#### Existing EMUSES Patterns to Follow
**ModelIOManager**: Consistent save/load pattern with metadata and manifest generation
**FastAPI Endpoints**: Job-based artifact serving with security validation
**CLI Commands**: Typer-based commands with comprehensive help and validation
**Configuration**: YAML-based configuration with validation and defaults

#### LAD Compliance Requirements  
**Testing**: >90% coverage target for new functionality
**Documentation**: NumPy-style docstrings, comprehensive user guides
**Code Quality**: Flake8 compliance, Boy Scout Rule for improvements
**Architecture**: Component-aware testing, TDD approach for new features

### Technical Dependencies and Readiness

#### All Required Dependencies Available
**Core Libraries**: numpy, pandas, scipy, sklearn, matplotlib (all present)
**EMUSES Libraries**: All analysis functions already available and tested
**Infrastructure**: FastAPI, model registry, CLI framework all production ready

#### No New Infrastructure Required
**Database**: Existing ModelRegistry schema accommodates analysis artifacts
**File System**: Current artifact storage patterns extend to analysis data
**API**: Existing endpoint patterns work for analysis artifact serving
**Security**: Current permission system extends to analysis data access

This context provides comprehensive understanding of how the Analysis API Enhancement integrates with existing EMUSES architecture while fixing critical bugs and adding advanced analysis capabilities without breaking changes.