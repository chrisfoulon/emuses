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
