# EMUSES Inference and Model Sharing: LAD Implementation Plan

## Executive Summary

This document provides a comprehensive implementation plan for adding inference capabilities and model sharing to EMUSES. The solution leverages existing infrastructure while introducing minimal complexity, following the principle of "born portable" models with universal versioning and integrity tracking.

## Technical Context

### Current State Assessment
- ✅ **Strong Foundation**: EMUSES has robust model persistence (ModelIOManager), UMAP transform capabilities, and multi-deployment architecture
- ✅ **Existing Workflow**: Validation already implements inference + evaluation, providing 70% of needed functionality
- ❌ **Missing Components**: Unified inference workflow, CLI commands, API endpoints, model discovery system

### Key Design Principles
1. **Universal Model Format**: Every model should be "born portable" with versioning/integrity regardless of deployment mode
2. **Manifest-Based Integrity**: Lightweight SHA-256 hashing for tamper detection without file duplication
3. **Cross-Mode Compatibility**: Models created in any deployment mode work in any other mode
4. **Zero Overhead**: No caching, packaging, or system dependencies

## Implementation Strategy

### Phase 0: Universal Model Format (1 week)
**Goal**: Establish manifest-based model integrity and versioning

#### Core Components
1. **Enhanced ModelIOManager** (`emuses/tools/model_io.py`)
   - Generate `model_manifest.json` after every model save
   - Verify manifest integrity on model load
   - Auto-increment version numbers

2. **Manifest Structure**
```json
{
  "model_info": {
    "name": "model_name",
    "version": "1.2.3",
    "created_at": "2025-01-15T14:30:00Z",
    "emuses_version": "2.1.0",
    "description": "Human-readable description"
  },
  "file_integrity": {
    "umap_model.pkl": {
      "size": 1048576,
      "sha256": "a1b2c3d4e5f6...",
      "modified": "2025-01-15T14:25:00Z"
    },
    "hdbscan_model.pkl": {
      "size": 2097152,
      "sha256": "f6e5d4c3b2a1...",
      "modified": "2025-01-15T14:26:00Z"
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

3. **Research Utilities for Scientific Reproducibility**

#### Model Verification
```bash
# Basic integrity check
emuses verify --model /path/to/model

# Detailed verification with change detection
emuses verify --model /path/to/model --detailed

# Compare against original manifest
emuses verify --model /path/to/model --strict
```

#### Model Information and Citation
```bash
# Get model info for citation
emuses info --model /path/to/model

# Generate publication-ready model trace
emuses cite --model /path/to/model [--format bibtex|apa|nature]

# Export complete model provenance report
emuses trace --model /path/to/model --output model_trace.json

# Generate reproducibility report
emuses reproduce --model /path/to/model --output reproduction_guide.md
```

#### Change Detection and Version Tracking
```bash
# Check what changed since training
emuses diff --model /path/to/model

# Compare two model versions
emuses compare --model1 /path/to/model_v1 --model2 /path/to/model_v2

# List all versions of a model (registry mode)
emuses versions --model model-name
```

#### Implementation Tasks
- [ ] Add manifest generation to `ModelIOManager.save_model()`
- [ ] Add manifest verification to `ModelIOManager.load_model()`
- [ ] Create file hashing utilities
- [ ] Add version auto-increment logic
- [ ] Update all pipeline stages to use enhanced ModelIOManager

**Research Utilities (CLI Commands)**:
- [ ] Create `verify` command with integrity checking options
- [ ] Create `info` command for model metadata display
- [ ] Create `cite` command for publication-ready citations
- [ ] Create `trace` command for complete provenance export
- [ ] Create `reproduce` command for reproducibility guides
- [ ] Create `diff` command for change detection
- [ ] Create `compare` command for model version comparison
- [ ] Create `versions` command for version history (registry mode)

### Phase 1: Unified Inference Command (1 week)
**Goal**: Enable inference on trained models with auto-detection of validation vs pure inference

#### Core Components
1. **Inference Pipeline Stage** (`emuses/pipelines/inference_stage.py`)
   - Load trained models from manifest
   - Transform new data through UMAP
   - Run ensemble predictions
   - Auto-detect labels for validation mode

2. **CLI Command**
```bash
# Auto-detects validation vs pure inference based on label presence
emuses inference --model /path/to/model --data /path/to/new/data [--output /path/to/results]
```

3. **API Endpoint**
```python
POST /api/v1/inference
{
  "model_path": "/path/to/model",
  "data_path": "/path/to/data",
  "output_path": "/path/to/results"
}
```

#### Implementation Tasks
- [ ] Create `InferenceStage` class
- [ ] Add `inference` command to CLI (`emuses/cli/main.py`)
- [ ] Add inference API endpoint (`emuses/foundation_fastapi_service/app.py`)
- [ ] Implement label auto-detection logic
- [ ] Create inference result formatting
- [ ] Add comprehensive error handling and logging

### Phase 2: Model Registry by Deployment Mode (3-4 weeks)
**Goal**: Enable model discovery and sharing appropriate to each deployment context

#### Local Mode: File-Based Discovery
**Storage**: `~/.emuses/models/` directory

**Features**:
- Simple model installation via folder copy
- Local model listing and info commands
- Symlink support for shared storage

**CLI Commands**:
```bash
emuses models list
emuses models info model-name
emuses models install /path/to/model [--name custom-name]
emuses inference --model model-name --data data.csv
```

#### Multi-User Mode: Database Registry
**Storage**: Database tables + shared file storage

**Database Schema**:
```sql
CREATE TABLE model_registry (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    owner_id UUID REFERENCES users(id),
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    model_path TEXT,
    manifest_hash VARCHAR(64),
    description TEXT,
    tags TEXT[],
    download_count INTEGER DEFAULT 0
);

CREATE TABLE model_access (
    model_id UUID REFERENCES model_registry(id),
    user_id UUID REFERENCES users(id),
    permission VARCHAR(10) -- 'read', 'write', 'admin'
);
```

**Features**:
- Lab-internal model sharing
- User permissions (public/private within organization)
- Model search and filtering
- Usage analytics

**API Endpoints**:
```python
GET    /api/v1/models               # List available models
GET    /api/v1/models/{model_id}    # Get model details
POST   /api/v1/models               # Register new model
POST   /api/v1/models/{model_id}/inference  # Run inference
DELETE /api/v1/models/{model_id}    # Delete model (owner only)
```

#### Production Mode: Full Registry
**Storage**: Cloud storage + metadata database + caching

**Features**:
- Public community models + private organizational models
- Advanced search with metadata filtering
- Model performance tracking and analytics
- Integration with external registries (optional)
- Automated model validation pipelines

#### Implementation Tasks
- [ ] Design and implement database schema
- [ ] Create model registry service layer
- [ ] Add registry API endpoints to FastAPI service
- [ ] Extend CLI with model management commands
- [ ] Implement file storage abstraction (local/cloud)
- [ ] Add authentication/authorization for model access
- [ ] Create model search and filtering logic
- [ ] Add model usage analytics

## Technical Specifications

### File Structure
```
trained_model_folder/
├── models/
│   ├── umap_model.pkl
│   ├── hdbscan_model.pkl
│   └── prediction_models/
├── artifacts/
│   ├── embeddings.npy
│   ├── rescaling_params.json
│   └── feature_schema.json
├── metadata/
│   ├── training_config.json
│   ├── performance_metrics.json
│   └── optuna_study.json
└── model_manifest.json  # NEW: Universal integrity/version tracking
```

### Key Classes and Modules

#### Enhanced ModelIOManager
```python
class ModelIOManager:
    def save_model(self, model, model_name, version=None, description="", tags=None):
        """Save model with automatic manifest generation"""
        
    def load_model(self, model_name, verify_integrity=True):
        """Load model with optional integrity verification"""
        
    def generate_manifest(self, model_folder):
        """Generate integrity manifest for model folder"""
        
    def verify_manifest(self, model_folder):
        """Verify model integrity against manifest"""
```

#### InferenceStage
```python
class InferenceStage:
    def __init__(self, config):
        """Initialize inference stage with model loading"""
        
    def execute(self, context):
        """Run inference on new data, auto-detect validation mode"""
        
    def load_trained_models(self, model_path):
        """Load all models from trained model folder"""
        
    def transform_features(self, new_features):
        """Transform new data through trained UMAP"""
        
    def predict(self, transformed_features):
        """Run ensemble predictions"""
```

#### ModelRegistry (Multi-user/Production modes)
```python
class ModelRegistry:
    def register_model(self, model_path, metadata):
        """Register model in database"""
        
    def list_models(self, user_id, filters=None):
        """List available models for user"""
        
    def get_model(self, model_id, user_id):
        """Get model with permission check"""
        
    def search_models(self, query, filters=None):
        """Search models by metadata"""
```

### API Specifications

#### Inference Endpoint
```yaml
POST /api/v1/inference:
  summary: Run inference on trained model
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          required: [model_identifier, data_path]
          properties:
            model_identifier:
              type: string
              description: Model path (local) or model name (registry)
            data_path:
              type: string
              description: Path to new data for inference
            output_path:
              type: string
              description: Where to save results (optional)
            validate:
              type: boolean
              description: Force validation mode if labels present
  responses:
    200:
      description: Inference completed successfully
      content:
        application/json:
          schema:
            type: object
            properties:
              job_id:
                type: string
              predictions:
                type: array
              metrics:
                type: object
                description: Performance metrics if validation mode
```

#### Model Registry Endpoints
```yaml
GET /api/v1/models:
  summary: List available models
  parameters:
    - name: public
      in: query
      type: boolean
    - name: tags
      in: query
      type: array
    - name: search
      in: query
      type: string
  responses:
    200:
      description: List of models
      content:
        application/json:
          schema:
            type: object
            properties:
              models:
                type: array
                items:
                  $ref: '#/components/schemas/ModelInfo'

POST /api/v1/models:
  summary: Register new model
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          required: [name, model_path]
          properties:
            name:
              type: string
            model_path:
              type: string
            description:
              type: string
            tags:
              type: array
            is_public:
              type: boolean
```

## Research Utilities Specifications

### Model Citation and Publication Support

#### `emuses cite` Command
**Purpose**: Generate publication-ready citations for research papers
**Output Example**:
```bibtex
@software{emuses_fmri_motor_v1_2_3,
  title={EMUSES fMRI Motor Task Model v1.2.3},
  author={Smith, John and Lab Team},
  year={2025},
  url={https://emuses.org/models/fmri-motor-v1.2.3},
  doi={10.5281/zenodo.1234567},
  version={1.2.3},
  note={UMAP model trained on HCP motor task data, 
        EMUSES v2.1.0, 500 training subjects, 
        SHA-256: a1b2c3d4e5f6...}
}
```

#### `emuses trace` Command  
**Purpose**: Export complete model provenance for supplementary materials
**Output Example**:
```json
{
  "model_provenance": {
    "name": "fmri_motor_task",
    "version": "1.2.3",
    "created_at": "2025-01-15T14:30:00Z",
    "training_duration": "2h 45m",
    "emuses_version": "2.1.0",
    "git_commit": "a1b2c3d4e5f6789...",
    "environment": {
      "python": "3.9.18",
      "umap-learn": "0.5.4",
      "hdbscan": "0.8.33"
    },
    "training_data": {
      "dataset": "HCP Young Adult",
      "subjects": 500,
      "sessions": 2,
      "data_hash": "sha256:abc123..."
    },
    "hyperparameters": {
      "umap": {"n_neighbors": 15, "min_dist": 0.1},
      "hdbscan": {"min_cluster_size": 20},
      "optimization": {"n_trials": 100, "cv_folds": 5}
    },
    "performance": {
      "validation_accuracy": 0.87,
      "cross_validation_score": 0.85,
      "test_metrics": {...}
    },
    "reproducibility": {
      "random_seeds": {"master": 42, "umap": 12345},
      "deterministic": true,
      "reproduction_script": "reproduce_model.py"
    }
  }
}
```

#### `emuses reproduce` Command
**Purpose**: Generate step-by-step reproduction guide  
**Output Example** (`reproduction_guide.md`):
```markdown
# Model Reproduction Guide: fMRI Motor Task v1.2.3

## Requirements
- EMUSES v2.1.0+
- Python 3.9+
- 16GB RAM minimum
- CUDA compatible GPU (recommended)

## Data Requirements
- HCP Young Adult dataset (500 subjects)
- Motor task paradigm data
- Preprocessing: Standard HCP minimal preprocessing

## Exact Reproduction Steps
1. Install EMUSES v2.1.0: `pip install emuses==2.1.0`
2. Download data: `aws s3 cp s3://hcp-openaccess/HCP_1200/ ./`
3. Run training: `emuses full ./output ./data --scores motor_scores.csv --random_state 42`
4. Verify result: `emuses verify --model ./output --strict`

## Expected Results
- Training time: ~2h 45m on V100 GPU
- Final validation accuracy: 0.87 ± 0.02
- Model hash: sha256:a1b2c3d4e5f6...

## Citation
[Generated BibTeX citation]
```

### Model Integrity and Change Detection

#### `emuses verify` Command Options
```bash
# Basic check (fast)
emuses verify --model /path/to/model
# Output: ✓ Model integrity verified (fmri_motor_task v1.2.3)

# Detailed analysis (comprehensive)
emuses verify --model /path/to/model --detailed
# Output: 
#   ✓ All 15 model files verified
#   ✓ Manifest signature valid
#   ✓ Dependencies compatible
#   ✓ No modifications detected
#   Model: fmri_motor_task v1.2.3
#   Created: 2025-01-15 14:30:00 UTC
#   EMUSES: v2.1.0

# Strict verification (cryptographic)
emuses verify --model /path/to/model --strict
# Performs full file re-hashing (slower but definitive)
```

#### `emuses diff` Command
**Purpose**: Show exactly what changed since model creation
**Output Example**:
```
Model: fmri_motor_task v1.2.3
Status: MODIFIED ⚠

Changed files:
  M  prediction_models/model_fold_0.pkl (size: 1048576 → 1048580)
  M  embeddings.npy (modified: 2025-01-16 09:15:00)
  
Unchanged files: 
  ✓  umap_model.pkl
  ✓  hdbscan_model.pkl
  ✓  rescaling_params.json
  
Manifest integrity: BROKEN
Recommendation: Re-run training or restore from backup
```

#### `emuses compare` Command
**Purpose**: Compare two model versions side-by-side
**Output Example**:
```
Comparing Models:
  Model A: fmri_motor_task v1.2.3 (2025-01-15)
  Model B: fmri_motor_task v1.3.0 (2025-01-20)

Differences:
  Training Data:
    A: 500 subjects, HCP motor task
    B: 750 subjects, HCP motor task + WU-Minn
    
  Hyperparameters:
    umap.n_neighbors: 15 → 20
    hdbscan.min_cluster_size: 20 → 25
    
  Performance:
    validation_accuracy: 0.87 → 0.91
    cross_validation_score: 0.85 → 0.89
    
  Model Size:
    Total: 45.2 MB → 67.8 MB
    
Compatibility: BREAKING CHANGES
  - Different embedding dimensionality
  - Incompatible for direct model swapping
```

### Research Workflow Integration

These utilities address key research pain points:

1. **Publication Requirements**: Automatic citation generation and provenance tracking
2. **Peer Review**: Complete reproducibility documentation
3. **Collaboration**: Easy model verification and comparison
4. **Data Management**: Change detection prevents accidental corruption
5. **Version Control**: Clear tracking of model evolution

### Implementation Priority
- **Phase 0**: `verify`, `info`, `trace` (basic research needs)
- **Phase 1**: `cite`, `reproduce` (publication support)  
- **Phase 2**: `diff`, `compare`, `versions` (advanced analysis)

## Security Considerations

### Model Integrity
- **SHA-256 hashing**: Cryptographically secure tamper detection
- **Manifest verification**: Automatic integrity checks on load
- **Immutable storage**: Read-only model files in registry

### Access Control
- **Local mode**: File system permissions
- **Multi-user mode**: Database-backed user permissions
- **Production mode**: Role-based access control (RBAC)

### Data Privacy
- **Model isolation**: Users can only access authorized models
- **Audit logging**: Track model access and usage
- **Data validation**: Ensure input data matches expected schema

## Testing Strategy

### Unit Tests
- [ ] Manifest generation and verification
- [ ] Model loading with integrity checks
- [ ] Inference pipeline components
- [ ] Registry database operations

### Integration Tests
- [ ] End-to-end inference workflow
- [ ] Cross-deployment model compatibility
- [ ] API endpoint functionality
- [ ] CLI command integration

### Performance Tests
- [ ] Large model loading performance
- [ ] Inference throughput benchmarks
- [ ] Registry query performance
- [ ] Concurrent inference handling

## Success Metrics

### Technical Metrics
- Model integrity verification accuracy: 100%
- Cross-platform compatibility rate: 100%
- Inference latency: <10% overhead vs direct model loading
- Registry query response time: <200ms for typical searches

### User Experience Metrics
- Time to share a model: <2 minutes
- Time to discover and use shared model: <5 minutes
- Training-to-inference workflow completion rate: >95%

## Risk Assessment

### Technical Risks
- **Model compatibility**: Different EMUSES versions may have incompatible models
- **Storage scaling**: Large models could impact registry performance
- **Performance overhead**: Integrity checking could slow model loading

### Mitigation Strategies
- **Compatibility metadata**: Version requirements in manifest
- **Lazy loading**: Verify integrity only when explicitly requested
- **Caching strategies**: Cache manifest verification results
- **Progressive rollout**: Phase-based implementation allows validation

## Dependencies and Prerequisites

### Existing EMUSES Components (No Changes Required)
- Core pipeline stages (UMAP, prediction, etc.)
- Multi-deployment architecture
- FastAPI service foundation
- CLI framework

### New Dependencies (Minimal)
- Standard library only: `hashlib`, `json`, `pathlib`
- No additional external packages required

### Database Requirements (Multi-user/Production only)
- PostgreSQL or SQLite for model registry
- File storage: Local filesystem or cloud storage (S3, Azure Blob)

## Conclusion

This implementation plan provides a robust foundation for EMUSES inference and model sharing while maintaining the system's simplicity and flexibility. The manifest-based approach ensures model integrity without overhead, while the phased implementation allows validation and refinement at each step.

The solution is technically sound, leverages existing infrastructure effectively, and provides clear value to users across all deployment scenarios. The universal model format ensures that models created by your team can be seamlessly used by the entire community, establishing EMUSES as the standard for neuroimaging model sharing.

## Next Steps for LAD Process

1. **Technical Review**: Validate technical approach with core team
2. **Priority Validation**: Confirm phase priorities align with user needs
3. **Resource Planning**: Estimate development effort and timeline
4. **Implementation Planning**: Create detailed task breakdown for each phase
5. **Testing Strategy**: Define comprehensive testing approach
6. **Documentation Plan**: Ensure proper documentation for new features