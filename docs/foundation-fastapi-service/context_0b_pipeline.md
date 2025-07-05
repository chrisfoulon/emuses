# Pipeline Integration Context 0b: Stage & Pipeline Runners

## Focus Areas
This context extends the foundation with pipeline execution wrappers and stage-specific runners. It covers background execution, context preservation, and progress tracking for the EMUSES pipeline stages.

## Inherited from 0a Foundation

### JobManager Class API
The JobManager provides complete job lifecycle management:

**Core Methods:**
- `generate_job_id() -> UUID`: Generate cryptographically secure job IDs
- `create_job_directory(job_id) -> Path`: Create secure job workspace
- `update_job_status(job_id, status, progress=None, stage=None, message=None)`: Thread-safe status updates
- `get_job_status(job_id) -> Dict`: Retrieve current job status
- `update_job_metadata(job_id, metadata)`: Update job metadata with sanitization
- `cleanup_old_jobs() -> List[UUID]`: Clean up completed jobs based on policy

**Job Directory Structure:**
```
jobs/
├── {job_id}/
│   ├── input/          # Uploaded files and input data
│   ├── output/         # Pipeline results and artifacts
│   │   ├── umap/       # UMAP stage outputs
│   │   ├── heatmap/    # Heatmap stage outputs
│   │   └── prediction/ # Prediction stage outputs
│   ├── logs/           # Execution logs and progress
│   └── metadata.json   # Job status, timestamps, configuration
```

### Pydantic Models for Pipeline Configuration
Core models available for pipeline integration:

**PipelineConfigRequest**: API configuration model
- `input_file`, `scores_file`, `label_dataset_file` (optional)
- `output_folder_path`: Maps to job output directory
- `umap_stage_enabled`, `heatmap_stage_enabled`, `prediction_stage_enabled`
- Compatible with existing `PipelineConfig` via field filtering

**JobStatusResponse**: Status tracking model
- `job_id`, `status`, `progress` (0.0-1.0)
- `current_stage`, `total_stages`, `message`
- `created_at`, `started_at`, `completed_at` timestamps

**Job Status Update Patterns for Pipeline Integration:**
```python
# Stage transition pattern
job_manager.update_job_status(job_id, "RUNNING", progress=0.0, current_stage="umap_stage")

# Progress updates within stage
job_manager.update_job_status(job_id, "RUNNING", progress=0.33, message="UMAP optimization trial 15/50")

# Stage completion
job_manager.update_job_status(job_id, "RUNNING", progress=0.33, current_stage="heatmap_stage")

# Pipeline completion
job_manager.update_job_status(job_id, "COMPLETED", progress=1.0, message="Pipeline completed successfully")
```

## EMUSES Pipeline Integration

### Stage Execution Pattern
All stages follow this interface that must be preserved:
```python
class PipelineStage:
    def run(self, context: dict, progress_queue=None) -> dict:
        # Updates context in-place and returns it
        # progress_queue allows real-time progress updates
```

### Individual Stage Classes
Each stage needs a wrapper for independent execution:

**UMAPStage**: Dimensionality reduction and clustering
- Input: Data matrices from context['input_matrix'] 
- Output: UMAP embeddings, cluster labels, trained model
- Progress: Optuna optimization iterations (can be 100+ trials)
- Artifacts: umap_model.pkl, embeddings.npy, cluster_labels.npy

**HeatmapStage**: Multi-target prediction with nested CV
- Input: Embeddings and scores from context
- Output: Trained models, performance reports  
- Progress: Nested cross-validation folds and target iterations
- Artifacts: models/*.pkl, performance_*.csv

**PredictionStage**: Test evaluation with optional GWD features
- Input: Trained models and test data from context
- Output: Predictions and evaluation metrics
- Progress: Model evaluation across test samples
- Artifacts: predictions.csv, evaluation_metrics.json

### Background Execution Requirements

**ProcessPoolExecutor Integration**:
- Isolate pipeline execution in separate process
- Prevent memory leaks from long-running jobs
- Resource limits: max 4 processes, 8GB memory per job
- Timeout limits: 2 hours for full pipeline, 30 minutes per stage

## Stage Runner Implementation Details

### Completed Stage Runners (Task 3)

**UMAPStageRunner**:
- Validates UMAP parameters: n_components (2-50), n_neighbors (2-200), min_dist (0.0-1.0)
- Resource monitoring with memory limit (8GB) and CPU limit (90%)
- Progress tracking with rate limiting (1 update/second)
- Artifact organization: best_umap_model.joblib, embeddings.npy, cluster files
- Timeout: 30 minutes for UMAP optimization

**HeatmapStageRunner**:
- Validates parameters: cv_folds (2-20), test_size (0.1-0.5), max_iter (100-10000)
- Progress tracking for nested cross-validation iterations
- Artifact organization: model files, performance reports
- Timeout: 30 minutes for multi-target prediction

**PredictionStageRunner**:
- Validates test data and trained models availability
- Progress tracking for model evaluation
- Artifact organization: predictions.csv, evaluation_metrics.json
- Timeout: 15 minutes for prediction evaluation

### Resource Monitoring Components

**ResourceMonitor**:
- Memory usage monitoring (default 8GB limit)
- CPU usage monitoring (default 90% limit)
- Graceful resource limit enforcement
- Exception handling for monitoring failures

**ProgressTracker**:
- Rate-limited progress updates (max 1 update/second)
- Thread-safe progress reporting
- Integration with JobManager status updates
- Progress message formatting and stage tracking

### Common Infrastructure

**BaseStageRunner**:
- Context validation for required keys
- Parameter validation with acceptable ranges
- Path safety validation to prevent directory traversal
- Async execution with monitoring and timeout support
- Artifact organization with secure file handling

## Parameter Validation Guidelines (IMPORTANT)

**CRITICAL RULE**: Parameter validation should ONLY check for breaking values that would cause crashes or invalid states. DO NOT impose arbitrary "sensible" ranges that limit user flexibility.

**What TO validate**:
- Type checking (ensure parameters are correct type)
- Breaking values (n_components < 1, negative values where positive required)
- Zero/null values that would crash algorithms
- Data structure constraints (empty arrays, dimension mismatches)

**What NOT to validate**:
- Arbitrary upper limits unless specified in library documentation
- "Sensible" performance ranges (let users choose)
- Preference parameters that don't break functionality

**Resource Management Guidelines**:
- Memory limits: Default to 75% of available system memory
- CPU limits: Default to reasonable percentage (80-90%)
- Make all limits easily configurable via constructor parameters
- Never hardcode specific values like "8GB"

**Example corrections**:
- ❌ UMAP n_neighbors: (2, 200) - arbitrary upper limit
- ✅ UMAP n_neighbors: > 0 - only check breaking values
- ❌ Memory limit: 8GB hardcoded
- ✅ Memory limit: 75% of psutil.virtual_memory().total

## Level 2 API Reference

| Class | Method | Purpose | Parameters |
|-------|---------|---------|------------|
| `UMAPStageRunner` | `run_stage(job_id, context)` | Execute UMAP stage with validation | job_id: str, context: dict |
| `HeatmapStageRunner` | `run_stage(job_id, context)` | Execute heatmap stage with tracking | job_id: str, context: dict |
| `PredictionStageRunner` | `run_stage(job_id, context)` | Execute prediction stage | job_id: str, context: dict |
| `ResourceMonitor` | `start_monitoring()` | Begin resource usage monitoring | None |
| `ResourceMonitor` | `check_resources()` | Check if limits exceeded | Returns: bool |
| `ProgressTracker` | `update_progress(progress, message)` | Rate-limited progress update | progress: float, message: str |
| `BaseStageRunner` | `_validate_context(context, keys)` | Validate context has required keys | context: dict, keys: list |
| `BaseStageRunner` | `_validate_parameters(config, ranges)` | Validate parameters in ranges | config: object, ranges: dict |
| `BaseStageRunner` | `_is_safe_path(path)` | Check path safety | path: Path, Returns: bool |

## Pipeline Runner Implementation (Task 4 - COMPLETED)

### Real EMUSES Pipeline Execution

**Implementation Status**: ✅ **PRODUCTION READY** - Real EMUSES pipeline execution fully implemented and validated.

**Key Achievement**: PipelineRunner now executes the actual EMUSES pipeline stages instead of placeholder logic, creating all expected output artifacts and matching CLI behavior exactly.

### PipelineRunner Class API

**Core Methods:**
- `__init__(job_manager, max_workers=4, memory_limit_ratio=0.75, pipeline_timeout=1800)`: Initialize with resource limits
- `execute_pipeline(job_id, context, progress_callback=None) -> Dict[str, Any]`: Execute real EMUSES pipeline asynchronously  
- `_setup_prediction_context(context) -> Dict[str, Any]`: Setup context keys required by EMUSESPipeline
- `_execute_pipeline_stages(context, progress_callback) -> Dict[str, Any]`: Execute real stage.run() methods
- `_create_progress_callback(job_id) -> Callable`: Create progress callback for job status updates

**Critical Implementation Details:**

1. **Context Setup for Prediction Stage**:
   ```python
   # Required context keys setup before stage execution
   prediction_config = load_prediction_config("prediction_params.json")
   context.update({
       "prediction_train_features": prediction_config.train_features,
       "prediction_train_labels": prediction_config.train_labels
   })
   ```

2. **Real Stage Execution Pattern**:
   ```python
   # Actual stage execution (NOT placeholder)
   if config.umap_stage_enabled:
       context = umap_stage.run(context, progress_queue)
   if config.heatmap_stage_enabled:
       context = heatmap_stage.run(context, progress_queue)  
   if config.prediction_stage_enabled:
       context = prediction_stage.run(context, progress_queue)
   ```

3. **Output Path Handling**:
   ```python
   # Ensure output_folder is Path object, not string
   config.output_folder = Path(config.output_folder)
   context["output_folder"] = config.output_folder
   ```

**Integration Testing Approach:**

**CLI vs API Comparison Test**: `tests/integration/test_cli_vs_api_comparison.py`
- Runs identical EMUSES pipeline through both CLI and API interfaces
- Validates both create identical output files and directory structure
- Confirms API executes real pipeline (not placeholder) by checking artifact creation
- Tests demonstrate production readiness and behavioral equivalence

**Artifact Validation**:
- UMAP stage: Creates embeddings, UMAP models, cluster labels
- Heatmap stage: Creates prediction models, performance metrics, heatmaps
- Prediction stage: Creates prediction results, evaluation metrics
- All artifacts match CLI output exactly

**Production Readiness Validation**:
- ✅ Real pipeline execution creates all expected artifacts
- ✅ Context setup handles all stage requirements correctly  
- ✅ Background execution isolates processes properly
- ✅ Error handling captures and reports pipeline failures
- ✅ Memory and timeout limits prevent resource exhaustion
- ✅ API behavior matches CLI behavior exactly

### Background Execution Pattern

**ProcessPoolExecutor Integration**: Production-ready background processing
```python
# Real implementation with proper resource management
async with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
    loop = asyncio.get_event_loop()
    future = executor.submit(self._execute_real_pipeline, context, self.memory_limit_ratio)
    result = await loop.run_in_executor(None, future.result)
    return result
```

**Context Preservation:**
- Deep copy validation ensures original context remains unchanged
- Pickle serialization for ProcessPoolExecutor communication
- Handles large dictionaries (>100MB) efficiently
- Numpy array preservation through pickle protocol

**Progress Callback Integration:**
- Rate-limited progress updates to prevent bottlenecks
- Stage-specific progress tracking
- Job status updates through JobManager
- Timeout handling with configurable limits

**Error Handling:**
- Exception capture with job status updates
- Timeout detection and cleanup
- ProcessPoolExecutor resource cleanup
- Graceful degradation on resource exhaustion

**Resource Management:**
- System-proportional memory limits (default 75% of available memory)
- Configurable worker process limits
- Pipeline timeout enforcement (default 1800 seconds)
- Automatic cleanup of background processes

## EMUSESPipeline Integration Requirements (Task 4.5 - IDENTIFIED)

### Current State vs Required State

**Current API Architecture (Problematic)**:
```python
# PipelineRunner._run_pipeline_in_process() - Current Implementation
# 1. Manual argparse.Namespace construction
args = argparse.Namespace()
args.output_folder = str(output_folder)
args.umap_trials = config_dict.get('umap_trials', 10)
# ... manual setup

# 2. Manual context setup
context.update({
    'prediction_train_features': input_matrix,
    'prediction_train_labels': scores,
})

# 3. Direct stage execution bypassing EMUSESPipeline orchestration
umap_stage.run(context)
heatmap_stage.run(context)  
prediction_stage.run(context)
```

**Required API Architecture (EMUSESPipeline Integration)**:
```python
# PipelineRunner._run_pipeline_in_process() - Required Implementation
# 1. Create EMUSESPipeline instance with API data
pipeline = EMUSESPipeline(args_from_api_config)

# 2. Set preprocessed data directly (API receives processed data)
pipeline.input_matrix = context['input_matrix'] 
pipeline.scores = context['scores']
pipeline.dataset_type = context.get('dataset_type', 'matrix')

# 3. Let EMUSESPipeline handle all orchestration, context setup, and preprocessing
result_context = pipeline.run(progress_callback=api_progress_callback)
return result_context
```

### Critical Benefits of EMUSESPipeline Integration

**1. Data Preprocessing Alignment**
- **Current Issue**: API bypasses `load_and_process_data()` logic
- **Solution**: Use EMUSESPipeline's data loading, normalization, and validation
- **Impact**: Consistent data handling for complex real-world datasets

**2. Context Setup Completeness**  
- **Current Issue**: Manual context setup with ~5 keys vs EMUSESPipeline's 15+ keys
- **Solution**: Use EMUSESPipeline's `split_and_prepare_data()` and context initialization
- **Impact**: All stages receive identical context structure as CLI

**3. Random Seed Management**
- **Current Issue**: Different random seed approach than CLI
- **Solution**: Use EMUSESPipeline's component-specific seed generation
- **Impact**: Reproducible results matching CLI exactly

**4. Error Handling & Validation**
- **Current Issue**: Limited data validation in API
- **Solution**: Leverage EMUSESPipeline's comprehensive validation
- **Impact**: Better error messages and data quality checks

### Implementation Strategy

**Phase 1: Direct Integration**
```python
class PipelineRunner:
    async def _execute_pipeline_stages(self, context: Dict[str, Any], progress_callback: Callable):
        """Execute pipeline using EMUSESPipeline for consistency with CLI."""
        
        # Convert API context to EMUSESPipeline args
        args = self._context_to_args(context)
        
        # Create EMUSESPipeline instance
        pipeline = EMUSESPipeline(args)
        
        # Set API-provided data directly
        pipeline.input_matrix = context['input_matrix']
        pipeline.scores = context['scores']
        if 'labelled_input_matrix' in context:
            pipeline.labelled_input_matrix = context['labelled_input_matrix']
            
        # Let EMUSESPipeline handle orchestration
        result_context = pipeline.run(progress_callback=progress_callback)
        
        return result_context

    def _context_to_args(self, context: Dict[str, Any]) -> argparse.Namespace:
        """Convert API context to EMUSESPipeline args format."""
        config_dict = context.get('config', {})
        args = argparse.Namespace()
        
        # Map API config to EMUSESPipeline expected args
        args.output_folder = str(config_dict.get('output_folder'))
        args.umap_trials = config_dict.get('umap_trials', 10)
        args.hdbscan_trials = config_dict.get('hdbscan_trials', 5)
        # ... complete mapping
        
        return args
```

**Phase 2: Progress Callback Integration**
```python
def _create_emuses_progress_callback(self, api_progress_callback):
    """Adapter between EMUSESPipeline and API progress callbacks."""
    def emuses_callback(stage_name, progress, message):
        # Convert EMUSESPipeline progress format to API format
        api_progress_callback(progress, f"{stage_name}: {message}")
    return emuses_callback
```

**Phase 3: Context Preservation**
```python
# Ensure API-specific context is preserved while using EMUSESPipeline
def _merge_contexts(self, api_context, emuses_context):
    """Merge API context with EMUSESPipeline context."""
    # Preserve API job management data
    merged = emuses_context.copy()
    merged.update({
        'job_id': api_context.get('job_id'),
        'api_metadata': api_context.get('api_metadata', {}),
        'pipeline_metadata': emuses_context.get('pipeline_metadata', {})
    })
    return merged
```

### Testing Requirements for Integration

**1. Computational Equivalence Validation**
```python
def test_api_cli_identical_results():
    """Verify API using EMUSESPipeline produces identical results to CLI."""
    # Same dataset through both paths
    cli_results = run_cli_pipeline(dataset)
    api_results = run_api_pipeline_with_emuses_integration(dataset)
    
    # Assert numerical equivalence
    assert_outputs_identical(cli_results, api_results, tolerance=1e-10)
```

**2. Real-World Dataset Validation**
```python  
def test_hcp_dataset_api_consistency():
    """Test API handles complex real-world datasets identically to CLI."""
    # Load HCP dataset
    hcp_data = load_hcp_dataset()
    
    # Process through both interfaces
    cli_artifacts = run_cli_with_hcp(hcp_data)
    api_artifacts = run_api_with_hcp(hcp_data)
    
    # Verify identical artifacts and no data alignment issues
    assert_artifacts_identical(cli_artifacts, api_artifacts)
```

**3. Context Completeness Validation**
```python
def test_context_completeness():
    """Verify API context contains all keys expected by stages."""
    api_context = run_api_pipeline_get_context()
    cli_context = run_cli_pipeline_get_context()
    
    # Check all CLI context keys present in API context
    assert set(cli_context.keys()).issubset(set(api_context.keys()))
```

### Migration Benefits

**Immediate Benefits**:
- ✅ Data alignment issues resolved (missing values, type coercion)
- ✅ Identical preprocessing and validation between API and CLI  
- ✅ Complete context setup for all stages
- ✅ Consistent random seed management and reproducibility

**Long-term Benefits**:
- ✅ Simplified maintenance (single code path for core logic)
- ✅ Automatic inheritance of CLI improvements and bug fixes
- ✅ Reduced technical debt and architectural divergence
- ✅ Confidence in API behavior matching CLI exactly

---
