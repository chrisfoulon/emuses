# Inference Pipeline Implementation - Plan

## Implementation Overview

This plan implements universal inference capabilities for EMUSES with manifest-based model integrity and comprehensive research utilities. The implementation follows a 2-phase approach building on existing ModelIOManager and UMAP transform capabilities.

**🚀 ENHANCED WITH OBSERVABILITY**: This implementation leverages the observability infrastructure from Phase 3 to provide metric-driven development, performance tracking, and research insights throughout the inference pipeline.

## Phase 0: Universal Model Format (1 week)

### Goal
Establish manifest-based model integrity and versioning for all EMUSES models with "born portable" compatibility.

### Core Components

#### 1. Enhanced ModelIOManager with Observability (emuses/tools/model_io.py)
```python
import time
from emuses.observability import metrics, logger  # From Phase 3

class ModelIOManager:
    def save_model(self, model, model_name, version=None, description="", tags=None):
        """Save model with automatic manifest generation and metrics tracking"""
        start_time = time.time()
        try:
            # Existing save logic
            # NEW: Generate manifest.json after model save
            manifest_path = os.path.join(model_folder, "model_manifest.json")
            self._generate_manifest(model_folder, version, description, tags)
            
            # Observability integration
            save_duration = time.time() - start_time
            metrics.model_save_duration.observe(save_duration)
            metrics.models_saved_total.inc()
            logger.info("Model saved", extra={
                "model_name": model_name, 
                "version": version,
                "save_duration": save_duration,
                "model_size_mb": self._get_model_size_mb(model_folder)
            })
            
        except Exception as e:
            metrics.model_save_errors_total.inc()
            logger.error("Model save failed", extra={"model_name": model_name, "error": str(e)})
            raise
        
    def load_model(self, model_name, verify_integrity=True):
        """Load model with optional integrity verification and performance tracking"""
        start_time = time.time()
        try:
            # Existing load logic  
            # NEW: Verify manifest if verify_integrity=True
            if verify_integrity:
                verify_start = time.time()
                self._verify_manifest(model_folder)
                metrics.model_verification_duration.observe(time.time() - verify_start)
            
            load_duration = time.time() - start_time
            metrics.model_load_duration.observe(load_duration)
            metrics.models_loaded_total.inc()
            logger.info("Model loaded", extra={
                "model_name": model_name,
                "load_duration": load_duration,
                "integrity_verified": verify_integrity
            })
            
        except Exception as e:
            metrics.model_load_errors_total.inc()
            logger.error("Model load failed", extra={"model_name": model_name, "error": str(e)})
            raise
```

#### 2. Manifest Structure
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

#### 3. Research Utilities (CLI Commands)

**Model Verification**:
```bash
# Basic integrity check
emuses verify --model /path/to/model
# Output: ✓ Model integrity verified (model_name v1.0.0)

# Detailed verification 
emuses verify --model /path/to/model --detailed
# Output: Comprehensive file-by-file verification results

# Strict cryptographic verification
emuses verify --model /path/to/model --strict  
# Output: Full re-hashing validation (slower but definitive)
```

**Model Information and Citation**:
```bash
# Get model metadata
emuses info --model /path/to/model
# Output: Model name, version, creation date, compatibility info

# Generate publication citations
emuses cite --model /path/to/model --format bibtex
# Output: Publication-ready BibTeX citation

emuses cite --model /path/to/model --format apa
# Output: APA format citation

# Export complete provenance
emuses trace --model /path/to/model --output model_trace.json
# Output: Complete model provenance for supplementary materials

# Generate reproducibility guide
emuses reproduce --model /path/to/model --output reproduction_guide.md
# Output: Step-by-step reproduction instructions
```

**Change Detection**:
```bash
# Check for modifications
emuses diff --model /path/to/model
# Output: List of changed files since model creation

# Compare model versions
emuses compare --model1 /path/to/model_v1 --model2 /path/to/model_v2
# Output: Side-by-side comparison of two model versions
```

### Implementation Tasks - Phase 0

#### ModelIOManager Enhancements
- [ ] Add manifest generation to `save_model()` method
- [ ] Add manifest verification to `load_model()` method  
- [ ] Create file hashing utilities using hashlib.sha256()
- [ ] Implement version auto-increment logic
- [ ] Add backward compatibility for models without manifests

#### Research Utilities Implementation
- [ ] Create `verify` command with basic/detailed/strict modes
- [ ] Create `info` command for model metadata display
- [ ] Create `cite` command with multiple format support (bibtex, apa, nature)
- [ ] Create `trace` command for complete provenance export
- [ ] Create `reproduce` command for reproducibility guides
- [ ] Create `diff` command for change detection
- [ ] Create `compare` command for model version comparison

#### Testing and Validation
- [ ] Unit tests for manifest generation and verification
- [ ] Integration tests with existing model storage
- [ ] Backward compatibility tests with pre-manifest models
- [ ] Cross-platform compatibility validation
- [ ] Performance benchmarks for integrity checking

## Phase 1: Unified Inference Command (1 week)

### Goal
Enable inference on trained models with automatic detection of validation vs pure inference modes.

### Core Components

#### 1. InferenceStage with Observability Integration (emuses/pipelines/inference_stage.py)
```python
import time
from emuses.observability import metrics, logger, create_span

class InferenceStage(PipelineStage):
    def __init__(self, config):
        """Initialize inference stage with model loading and metrics setup"""
        self.model_path = config.model_path
        self.data_path = config.data_path
        self.output_path = config.output_path
        self.validate_mode = config.validate_mode
        
    def execute(self, context):
        """Run inference with comprehensive performance tracking and research insights"""
        with create_span("inference_pipeline") as span:
            start_time = time.time()
            
            try:
                # Load trained models from manifest (leverages ModelIOManager metrics)
                model_load_start = time.time()
                trained_models = self._load_trained_models()
                span.set_attribute("model_path", self.model_path)
                
                # Load new data with performance tracking
                data_load_start = time.time()
                new_features = self._load_features(self.data_path)
                data_load_duration = time.time() - data_load_start
                metrics.inference_data_load_duration.observe(data_load_duration)
                span.set_attribute("input_samples", len(new_features))
                
                # Auto-detect validation vs inference mode
                has_labels = self._detect_labels()
                mode = "validation" if (has_labels or self.validate_mode) else "inference"
                span.set_attribute("inference_mode", mode)
                
                # Transform features through trained UMAP (critical performance path)
                transform_start = time.time()
                transformed_features = self._transform_features(new_features, trained_models)
                transform_duration = time.time() - transform_start
                metrics.umap_transform_duration.observe(transform_duration)
                metrics.samples_transformed_total.inc(len(new_features))
                
                # Run predictions with per-model performance tracking
                predict_start = time.time()
                predictions = self._predict(transformed_features, trained_models)
                predict_duration = time.time() - predict_start
                metrics.ensemble_prediction_duration.observe(predict_duration)
                metrics.predictions_generated_total.inc(len(predictions))
                
                # Calculate validation metrics if in validation mode
                validation_metrics = None
                if mode == "validation":
                    validation_start = time.time()
                    validation_metrics = self._calculate_validation_metrics(predictions)
                    metrics.validation_computation_duration.observe(time.time() - validation_start)
                    
                    # Track accuracy for research insights
                    if 'accuracy' in validation_metrics:
                        metrics.inference_validation_accuracy.observe(validation_metrics['accuracy'])
                
                # Calculate overall performance metrics
                total_duration = time.time() - start_time
                throughput = len(new_features) / total_duration
                metrics.inference_pipeline_duration.observe(total_duration)
                metrics.inference_throughput_samples_per_sec.observe(throughput)
                
                # Structured logging for research and debugging
                logger.info("Inference pipeline completed", extra={
                    "mode": mode,
                    "samples_processed": len(new_features),
                    "model_path": self.model_path,
                    "total_duration_sec": round(total_duration, 3),
                    "data_load_sec": round(data_load_duration, 3),
                    "transform_sec": round(transform_duration, 3),
                    "prediction_sec": round(predict_duration, 3),
                    "throughput_samples_per_sec": round(throughput, 2),
                    "validation_accuracy": validation_metrics.get('accuracy') if validation_metrics else None
                })
                
                # Format and save results with performance breakdown
                results = self._format_results(predictions, mode, {
                    'total_duration_ms': total_duration * 1000,
                    'performance_breakdown': {
                        'data_load_ms': data_load_duration * 1000,
                        'umap_transform_ms': transform_duration * 1000,
                        'prediction_ms': predict_duration * 1000,
                        'throughput_samples_per_sec': throughput
                    },
                    'validation_metrics': validation_metrics
                })
                self._save_results(results)
                
                return results
                
            except Exception as e:
                metrics.inference_pipeline_errors_total.inc()
                logger.error("Inference pipeline failed", extra={
                    "model_path": self.model_path,
                    "error": str(e),
                    "duration_before_error_sec": time.time() - start_time
                })
                span.record_exception(e)
                raise
        
    def _load_trained_models(self):
        """Load all models from trained model folder with integrity verification"""
        # ModelIOManager already provides metrics via Phase 3 integration
        # Load UMAP, HDBSCAN, and prediction models with manifest verification
        # Return model bundle with metadata
        
    def _transform_features(self, features, models):
        """Transform new data through trained UMAP with performance tracking"""
        # Apply trained UMAP transformation
        # Use existing rescaling logic from UMAPStage
        # Individual UMAP performance already tracked via metrics
        # Return transformed embeddings
        
    def _predict(self, embeddings, models):
        """Run ensemble predictions with per-model performance insights"""
        # Apply trained prediction models
        # Track individual model performance for ensemble analysis
        # Handle both single and multi-target predictions
        # Return prediction results with confidence scores and model breakdown
```

#### 2. CLI Command Integration (emuses/cli/main.py)
```python
@app.command()
def inference(
    model: str = typer.Argument(..., help="Path to trained model"),
    data: str = typer.Argument(..., help="Path to new data for inference"),
    output: Optional[str] = typer.Option(None, help="Output path for results"),
    validate: bool = typer.Option(False, help="Force validation mode"),
    verify: bool = typer.Option(True, help="Verify model integrity")
):
    """Run inference on trained EMUSES model"""
    # Create inference configuration
    config = InferenceConfig(
        model_path=model,
        data_path=data, 
        output_path=output,
        validate_mode=validate,
        verify_integrity=verify
    )
    
    # Execute inference stage
    stage = InferenceStage(config)
    context = create_inference_context(config)
    results = stage.execute(context)
    
    # Display results summary
    console.print(f"✓ Inference completed: {results['predictions_count']} predictions")
    if results['mode'] == 'validation':
        console.print(f"📊 Validation accuracy: {results['accuracy']:.3f}")
```

#### 3. API Endpoint (emuses/foundation_fastapi_service/app.py)
```python
@app.post("/api/v1/inference")
async def run_inference(request: InferenceRequest):
    """Run inference on trained model"""
    try:
        # Create inference stage
        config = InferenceConfig.from_request(request)
        stage = InferenceStage(config)
        
        # Execute inference
        context = create_inference_context(config)
        results = stage.execute(context)
        
        return InferenceResponse(
            status="completed",
            predictions=results['predictions'],
            mode=results['mode'],
            processing_time_ms=results['processing_time_ms'],
            model_info=results['model_info']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Inference failed: {str(e)}"
        )

class InferenceRequest(BaseModel):
    model_identifier: str
    data_path: str  
    output_path: Optional[str] = None
    validate: bool = False
    verify_integrity: bool = True

class InferenceResponse(BaseModel):
    status: str
    predictions: List[float]
    mode: str  # "inference" or "validation"
    processing_time_ms: float
    model_info: Dict[str, Any]
    metrics: Optional[Dict[str, float]] = None  # Only for validation mode
```

### Implementation Tasks - Phase 1

#### InferenceStage Development
- [ ] Create `InferenceStage` class with model loading
- [ ] Implement automatic validation vs inference mode detection
- [ ] Add feature transformation using existing UMAP logic
- [ ] Implement ensemble prediction with confidence scoring
- [ ] Create inference result formatting and output

#### CLI Integration
- [ ] Add `inference` command to CLI with proper arguments
- [ ] Implement argument validation and error handling
- [ ] Add progress indicators for long-running inference
- [ ] Create result summary display with rich formatting
- [ ] Add comprehensive help text and examples

#### API Integration  
- [ ] Add inference endpoint to FastAPI service
- [ ] Create Pydantic models for request/response
- [ ] Implement proper error handling and validation
- [ ] Add background task support for large datasets
- [ ] Create OpenAPI documentation with examples

#### Testing and Validation
- [ ] Unit tests for InferenceStage components
- [ ] Integration tests with existing model artifacts
- [ ] API endpoint testing with real models
- [ ] CLI command testing with various data formats
- [ ] End-to-end workflow validation

## File Structure

### New Files Created
```
emuses/
├── pipelines/
│   └── inference_stage.py           # NEW: Unified inference implementation
├── tools/
│   └── model_io.py                  # ENHANCED: Manifest generation/verification
└── cli/
    └── main.py                      # ENHANCED: New inference command

tests/
├── pipelines/
│   └── test_inference_stage.py      # NEW: InferenceStage unit tests
├── tools/
│   └── test_model_io_manifest.py    # NEW: Manifest functionality tests
└── integration/
    └── test_inference_workflow.py   # NEW: End-to-end inference tests
```

### Enhanced Files
```
emuses/foundation_fastapi_service/app.py     # Add inference endpoint
emuses/cli/main.py                           # Add inference command
emuses/tools/model_io.py                     # Add manifest capabilities
```

## Success Criteria

### Technical Validation
- [ ] Inference produces identical results to validation workflow (1e-10 tolerance)
- [ ] Manifest verification detects file modifications with 100% accuracy  
- [ ] Research utilities generate publication-ready outputs
- [ ] Zero performance overhead for inference operations
- [ ] 100% backward compatibility with existing model storage

### User Experience
- [ ] Single command inference: `emuses inference --model M --data D`
- [ ] Clear mode detection (inference vs validation)
- [ ] Comprehensive error messages with suggestions
- [ ] Rich progress indicators and result summaries
- [ ] Complete documentation with examples

### Research Integration with Observability Benefits
- [ ] Publication-ready citations in multiple formats
- [ ] Complete reproducibility documentation with performance baselines
- [ ] Model integrity verification for collaboration
- [ ] Version tracking with change detection
- [ ] Cross-platform model compatibility
- [ ] **Performance benchmarking**: Automatic collection of inference performance data for optimization
- [ ] **Research insights**: Detailed metrics on model loading, UMAP transforms, and prediction times
- [ ] **Reproducibility metrics**: Track inference consistency across different hardware/environments
- [ ] **Usage analytics**: Monitor which models are used most frequently for research prioritization
- [ ] **Error analysis**: Comprehensive error tracking and debugging information

## Testing Strategy

### Unit Testing
- Manifest generation and verification accuracy
- File hashing and integrity checking 
- Model loading with different manifest versions
- Research utility output validation
- InferenceStage component testing

### Integration Testing  
- End-to-end inference workflow validation
- Cross-deployment model compatibility
- API and CLI result consistency
- Backward compatibility with existing models
- Performance regression testing

### Real-World Validation
- Test with actual EMUSES model artifacts
- Validate research utility outputs with domain experts
- Cross-platform compatibility verification
- Large dataset inference performance testing
- Multi-user model sharing scenarios

This implementation plan establishes EMUSES as the standard for reproducible neuroimaging model sharing while maintaining complete backward compatibility and scientific rigor.