# Inference Pipeline - Component Baseline Summary

## Existing Components to Integrate With

### Core Training Components

#### **HeatmapStage** (Primary Integration Point)
- **Location**: `emuses/pipelines/heatmap_stage.py:83-900`
- **Relevant functionality**: Sophisticated prediction model training with nested Optuna CV, multi-target support, AE pretraining
- **Integration approach**: InferenceStage loads models trained by HeatmapStage's `nested_optuna_cv` system
- **Dependencies**: ModelIOManager, optuna, kernel regression utilities
- **Model Output**: Saves trained models in target-specific directories (e.g., `target_0/`, `target_1/`)
- **Key Methods**:
  - `_optimise_target()`: Trains models for individual targets
  - `_generate_performance_csv_files()`: Creates performance summaries

#### **ModelIOManager** (Model Persistence)
- **Location**: `emuses/tools/model_io.py`
- **Relevant functionality**: Model saving/loading with metadata tracking
- **Integration approach**: Enhance with manifest generation for integrity verification
- **Dependencies**: joblib, pathlib, json
- **Extension needs**: 
  - Add `model_manifest.json` generation in `save_model()`
  - Add integrity verification in `load_model()`
  - Version auto-increment logic

### UMAP Transform Infrastructure

#### **UMAP Transform Capabilities**
- **Location**: `emuses/tools/UMAP_utils.py:load_umap_model()`
- **Relevant functionality**: Trained UMAP model loading and transform operations
- **Integration approach**: InferenceStage uses existing transform logic for new data
- **Current patterns**: Already implemented in validation workflow at `emuses/pipelines/umap_stage.py:210-235`
- **Key functionality**: 
  - `trained_umap.transform(new_features)`
  - Rescaling logic: `(embeddings - min) / (max - min)`

#### **UMAPStage Transform Logic**
- **Location**: `emuses/pipelines/umap_stage.py:210-235`
- **Relevant functionality**: Reference implementation for feature transformation
- **Integration approach**: Extract and reuse transform + rescaling patterns
- **Current implementation**:
```python
self.test_embeddings = self.trained_umap.transform(test_features)
self.test_embeddings = (self.test_embeddings - self.train_embeddings_min) / \
                      (self.train_embeddings_max - self.train_embeddings_min)
```

### CLI and API Infrastructure

#### **CLI Framework**
- **Location**: `emuses/cli/main.py`
- **Relevant functionality**: Command registration, argument parsing, configuration loading
- **Integration approach**: Add `inference` command following existing patterns
- **Current command structure**: `full`, `umap`, `clustering`, `heatmap`, `prediction`
- **Extension pattern**: Use typer decorators, maintain consistency with existing commands

#### **FastAPI Service**
- **Location**: `emuses/foundation_fastapi_service/app.py`
- **Relevant functionality**: REST API endpoints, request/response handling
- **Integration approach**: Add `/api/v1/inference` endpoint
- **Dependencies**: FastAPI, Pydantic models, background task support
- **Extension pattern**: Follow existing endpoint patterns with proper error handling

### Configuration and Context Management

#### **Pipeline Context System**
- **Location**: `emuses/pipelines/emuses_pipeline.py`
- **Relevant functionality**: Context management, data flow between stages
- **Integration approach**: InferenceStage follows PipelineStage interface
- **Context patterns**: 
  - `prediction_train_coords` - UMAP embeddings
  - `prediction_train_labels` - Target labels
  - Random seed management via `context["random_seeds"]`

#### **PipelineStage Base Class**
- **Location**: `emuses/pipelines/pipeline_stage.py`
- **Relevant functionality**: Stage interface definition, common functionality
- **Integration approach**: InferenceStage inherits from PipelineStage
- **Interface requirements**: `run(self, context, progress_queue=None)`

### Observability Integration

#### **Observability System**
- **Location**: `emuses/observability/`
- **Relevant functionality**: Metrics tracking, structured logging, performance monitoring
- **Integration approach**: InferenceStage leverages existing observability infrastructure
- **Key components**:
  - `metrics.py`: Prometheus metrics collection
  - `logging.py`: Structured logging with context
  - `context.py`: Observability context management
- **Integration patterns**: Use `@track_scientific_operation` decorator, metric collection

### Legacy Components (To Retire)

#### **PredictionStage** (Legacy - Retire)
- **Location**: `emuses/pipelines/prediction_stage.py`
- **Status**: Legacy implementation superseded by HeatmapStage
- **Retirement plan**: Move to `docs/_archived_features/prediction_stage/`
- **Justification**: HeatmapStage provides superior functionality with Optuna optimization

## Data Structures and Models

### **Training Model Artifacts** (From HeatmapStage)
- **Structure**: Target-specific directories (`target_0/`, `target_1/`, etc.)
- **Contents**: 
  - Trained models (joblib pickles)
  - Optuna studies and trials
  - Performance metrics (CSV files)
  - Model metadata
- **Integration**: InferenceStage loads entire model bundles per target

### **UMAP Model Artifacts**
- **Model files**: `umap_model.pkl`, trained UMAP transformer
- **Metadata**: Training bounds for rescaling (`train_embeddings_min`, `train_embeddings_max`)
- **Storage**: Via ModelIOManager with metadata tracking

### **Context Data Flow**
- **Training context**: Models saved with training configuration hashes
- **Inference context**: New data transformation through saved models
- **Consistency**: Same random seeds and configuration for reproducible results

## Integration Architecture

### **Training → Inference Workflow**
1. **HeatmapStage**: Trains sophisticated prediction models with Optuna
2. **ModelIOManager**: Saves models with metadata (enhanced with manifests)
3. **InferenceStage**: Loads trained models and applies to new data
4. **CLI/API**: Provides user interfaces for inference operations

### **Data Flow Pattern**
```
New Data → UMAP Transform → Trained Models → Predictions
     ↑           ↑              ↑           ↑
Load Data   Load UMAP      Load Models   Format Results
```

### **Key Integration Points**
- **Model Loading**: InferenceStage uses ModelIOManager to load HeatmapStage artifacts
- **Transform Pipeline**: Reuses UMAPStage transform logic for consistency
- **Context Management**: Maintains same context patterns for data flow
- **Observability**: Integrates with existing metrics and logging infrastructure

## Success Integration Criteria

- [ ] InferenceStage loads models trained by HeatmapStage without modification
- [ ] UMAP transforms produce identical results to training workflow
- [ ] Model manifests provide integrity verification for all artifacts
- [ ] CLI/API interfaces follow existing EMUSES patterns
- [ ] Observability provides performance metrics for inference operations
- [ ] Backward compatibility maintained with existing model storage

This baseline establishes clear integration points for implementing InferenceStage while leveraging EMUSES' sophisticated existing infrastructure.