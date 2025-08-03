# Inference Pipeline Implementation - Context

## Current State Analysis

### Existing Infrastructure Assessment

**Model Persistence Foundation**: EMUSES has robust model storage through ModelIOManager with:
- Comprehensive model artifact management (UMAP, HDBSCAN, prediction models)
- Optuna study serialization and metadata tracking
- Versioned artifact storage with flexible naming
- Support for both individual models and complete pipeline bundles

**UMAP Transform Capabilities**: Existing infrastructure supports inference through:
- `load_umap_model()` function in emuses/tools/UMAP_utils.py
- Transform workflow: `trained_umap.transform(new_features)`
- Rescaling logic for new embeddings using training min/max bounds
- Integration with validation workflow (70% of inference functionality exists)

**Validation Workflow Pattern**: Current implementation provides strong foundation:
- UMAPStage.run() already implements new data transformation
- Automatic rescaling: `(embeddings - min_coords) / (max_coords - min_coords)`
- Complete inference + evaluation pipeline in validation mode
- Context management for prediction keys and feature alignment

### Current Deployment Architecture

EMUSES supports three deployment modes that inference must work across:

1. **Local Mode**: File-based model storage in user directories
2. **Multi-User Mode**: Database-backed model management with user permissions  
3. **Production Mode**: Cloud storage with full registry capabilities

**Critical Design Requirement**: Models must be "born portable" - work in any deployment mode regardless of where they were created.

## Technical Architecture Analysis

### ModelIOManager Capabilities (emuses/tools/model_io.py)

**Current Strengths**:
- Comprehensive artifact management with save_model() and load_model()
- Metadata tracking including training configuration and Optuna studies
- Support for complex nested model structures (prediction_models folder)
- Flexible output directory management

**Enhancement Opportunities**:
- Add automatic manifest generation during save_model()
- Implement integrity verification during load_model()
- Include version auto-increment logic
- Extend metadata to include environment and dependency information

### UMAP Transform Pipeline (emuses/pipelines/umap_stage.py)

**Existing Transform Logic** (lines 210-235):
```python
# Current validation workflow implements inference
if test_features is not None:
    self.test_embeddings = self.trained_umap.transform(test_features)
    # Rescaling using training bounds
    self.test_embeddings = (self.test_embeddings - self.train_embeddings_min) / \
                          (self.train_embeddings_max - self.train_embeddings_min)
```

**Key Insights**:
- Transform capability already exists and is tested
- Rescaling logic ensures new embeddings fit training coordinate space
- Context updates provide all necessary metadata for inference
- Integration point exists for new InferenceStage implementation

### CLI Integration Points (emuses/cli/main.py)

**Current Command Structure**:
- `full`: Complete pipeline execution
- `umap`: UMAP embedding generation
- `clustering`: Clustering analysis
- `heatmap`: Multi-target prediction
- `prediction`: Prediction model training

**Inference Integration Strategy**:
- Add `inference` command maintaining CLI pattern consistency
- Auto-detect validation vs pure inference based on label presence
- Reuse existing argument parsing and configuration loading
- Maintain backward compatibility with all existing commands

## Implementation Strategy

### Phase 0: Universal Model Format (Foundation)

**Manifest Structure Design**:
```json
{
  "model_info": {
    "name": "model_name",
    "version": "1.0.0", 
    "created_at": "2025-01-15T14:30:00Z",
    "emuses_version": "2.1.0",
    "description": "Human-readable description"
  },
  "file_integrity": {
    "umap_model.pkl": {
      "size": 1048576,
      "sha256": "a1b2c3d4e5f6...",
      "modified": "2025-01-15T14:25:00Z"
    }
  },
  "training_context": {
    "config_hash": "abc123def456",
    "optuna_study_hash": "def456ghi789", 
    "random_seeds": {"master": 42, "umap": 12345}
  },
  "compatibility": {
    "min_emuses_version": "2.0.0",
    "python_version": "3.9+",
    "required_packages": ["umap-learn>=0.5.0", "hdbscan>=0.8.0"]
  }
}
```

**Implementation Requirements**:
- Automatic generation in ModelIOManager.save_model()
- Verification in ModelIOManager.load_model() with optional strict mode
- File hashing utilities using hashlib.sha256()
- Version auto-increment based on existing model versions

### Phase 1: Unified Inference Command

**InferenceStage Design**:
```python
class InferenceStage(PipelineStage):
    def __init__(self, config):
        # Load trained models from manifest
        # Initialize inference context
        
    def execute(self, context):
        # Auto-detect validation vs pure inference
        # Transform features through trained UMAP
        # Run ensemble predictions
        # Format results appropriately
```

**Command Interface**:
```bash
# Auto-detects mode based on label presence
emuses inference --model /path/to/model --data /path/to/data [--output /path/to/results]

# Force validation mode even without labels
emuses inference --model /path/to/model --data /path/to/data --validate

# API equivalent
POST /api/v1/inference
{
  "model_path": "/path/to/model",
  "data_path": "/path/to/data", 
  "output_path": "/path/to/results",
  "validate": false
}
```

## Research Utilities Specifications

### Model Verification and Citation Support

**Scientific Reproducibility Requirements**:
- Complete model provenance tracking for publications
- Automated citation generation in standard academic formats
- Integrity verification for collaborative research
- Change detection for model evolution tracking
- Reproduction guide generation for peer review

**Implementation Commands**:
```bash
# Basic integrity verification
emuses verify --model /path/to/model

# Generate publication citation
emuses cite --model /path/to/model --format bibtex

# Export complete provenance
emuses trace --model /path/to/model --output provenance.json

# Generate reproduction guide
emuses reproduce --model /path/to/model --output reproduction_guide.md

# Detect changes since training
emuses diff --model /path/to/model
```

### Research Workflow Integration

**Publication Support**:
- BibTeX citation generation with proper metadata
- Provenance export for supplementary materials
- Reproduction guides for peer review
- Version tracking for method citations

**Collaboration Features**:
- Model integrity verification before analysis
- Change detection to prevent data corruption
- Version comparison for method evolution
- Compatible metadata for cross-team sharing

## Context Files for Implementation

### Core Architecture Files
```bash
# Model persistence and loading
emuses/tools/model_io.py              # Primary integration point
emuses/tools/UMAP_utils.py            # Transform capabilities

# Pipeline integration  
emuses/pipelines/pipeline_stage.py    # Base class for InferenceStage
emuses/pipelines/umap_stage.py        # Transform logic reference
emuses/pipelines/emuses_pipeline.py   # Context management patterns

# CLI and API integration
emuses/cli/main.py                    # Command registration
emuses/foundation_fastapi_service/app.py  # API endpoint addition
```

### Testing Infrastructure
```bash
# Validation patterns
tests/tools/test_umap_utils.py        # Transform testing patterns
tests/foundation_fastapi_service/     # API testing infrastructure  
tests/enhanced-cli-typer/             # CLI testing patterns

# Integration validation
tests/integration/test_real_world_pipeline.py  # End-to-end testing
```

### Configuration and Documentation
```bash
# Implementation guidance
EMUSES_INFERENCE_AND_MODEL_SHARING_LAD.md  # Complete implementation plan
docs/LAD_Implementation_Guide.md           # LAD process guidelines

# Example workflows
clean_run.ipynb                       # Reference implementation patterns
```

## Success Metrics

### Technical Validation
- **Inference Accuracy**: Results identical to validation workflow (1e-10 tolerance)
- **Manifest Integrity**: 100% detection rate for file modifications
- **Performance**: <5% overhead for inference operations vs direct model loading
- **Compatibility**: Models work across all deployment modes without modification

### Research Utility Validation  
- **Citation Quality**: Publication-ready citations meeting journal standards
- **Reproducibility**: Complete reproduction guides enabling exact result replication
- **Collaboration**: Successful model sharing across research teams
- **Version Tracking**: Clear model evolution documentation

### User Experience Metrics
- **Ease of Use**: Single command inference workflow
- **Error Handling**: Clear diagnostic messages for common issues
- **Documentation**: Comprehensive usage examples and troubleshooting guides
- **Backward Compatibility**: Zero breaking changes to existing workflows

This context provides the technical foundation for implementing inference capabilities that meet both immediate research needs and long-term collaboration requirements while maintaining EMUSES' commitment to scientific rigor and reproducibility.