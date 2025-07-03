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

**Context Preservation**:
```python
# Deep copy required to prevent corruption
import copy
context_copy = copy.deepcopy(original_context)
# Serialize for inter-process communication
import pickle
context_bytes = pickle.dumps(context_copy)
```

**Progress Callback Integration**:
- Rate limited to max 1 update per second
- Include current stage, progress percentage, ETA
- Queue-based communication between processes
- Update job metadata in real-time

## Stage Runner Implementation Requirements

### UMAPStage Wrapper
```python
class UMAPStageRunner:
    def __init__(self, job_manager: JobManager):
        self.job_manager = job_manager
        
    async def run_stage(self, job_id: str, context: dict) -> dict:
        # Validate parameters against stage requirements
        # Apply resource limits (memory, CPU)
        # Execute stage with progress tracking
        # Update job status and artifacts
```

### Parameter Validation
- Validate UMAP parameters: n_components, n_neighbors, min_dist
- Check clustering parameters: min_cluster_size, min_samples
- Verify Optuna optimization settings: n_trials, timeout
- Ensure input data shapes and types are compatible

### Resource Limits
- Memory monitoring during execution
- CPU time limits per optimization trial
- Disk space limits for artifact storage
- Process termination on resource exhaustion

## Background Pipeline Runner

### Async Wrapper Requirements
```python
class PipelineRunner:
    async def execute_pipeline(self, job_id: str, config: PipelineConfig) -> dict:
        # Set up ProcessPoolExecutor with resource limits
        # Load data and initialize context
        # Execute stages with progress callbacks
        # Handle errors and update job status
        # Return final context with results
```

### Error Handling Patterns
- Capture and log all exceptions
- Update job status to FAILED with error message
- Clean up partial artifacts on failure
- Preserve context state for debugging
- Implement retry logic for transient failures

### Progress Tracking Implementation
```python
def progress_callback(stage_name: str, progress: float, message: str):
    # Rate limited updates (max 1/second)
    # Update job metadata with current status
    # Send real-time updates to API clients
    # Include ETA calculations when possible
```

## Integration Points for Next Sub-Plans

### For 0c (Interface Layer) Updates Needed
After this sub-plan completes, update `context_0c_interface.md` with:

**PipelineRunner Interface**:
- `async execute_pipeline(job_id, config)` method signature
- Background execution patterns and ProcessPoolExecutor usage
- Progress callback mechanisms and rate limiting
- Context preservation patterns for API integration

**Stage Runner Classes**:
- UMAPStageRunner, HeatmapStageRunner, PredictionStageRunner APIs  
- Parameter validation requirements for each stage
- Resource limit configurations and monitoring
- Artifact organization patterns for API serving

**Background Processing Details**:
- Process isolation and cleanup procedures
- Memory management for large context dictionaries
- Error handling and job status update patterns
- Timeout handling and graceful termination

### For 0d (Security Testing) Updates Needed
After this sub-plan completes, update `context_0d_security.md` with:

**Background Process Security**:
- ProcessPoolExecutor resource limits and isolation
- Process cleanup verification for security testing
- Memory usage patterns for performance testing
- Context serialization for memory spike detection

**Resource Management**:
- Memory monitoring and leak detection requirements
- Process isolation verification for concurrent jobs
- Resource cleanup after job completion
- Timeout enforcement and process termination

**Progress Callback Security**:
- Rate limiting implementation details for load testing
- Callback queue management and memory usage
- Progress update frequency and resource impact
