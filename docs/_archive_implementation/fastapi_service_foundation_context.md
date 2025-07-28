# Foundation Context 0a: Core Models & Job Management

## Focus Areas
This context document provides the essential information needed to implement the foundation layer (models and job management) for the FastAPI service. It includes core pipeline structures, job management patterns, and data model requirements.

## Core Pipeline Components

### EMUSESPipeline Structure
The FastAPI service wraps the existing `EMUSESPipeline` class without modification. Key aspects:

```python
class EMUSESPipeline:
    def __init__(self, args):
        self.config = PipelineConfig(args)
        self.output_folder = self.config.output_folder
        self.stages = []
        
    def run(self, progress_callback=None, progress_queue=None):
        # Executes all stages sequentially
        # Returns context dictionary with results
```

### Context Dictionary Pattern
All stages operate on a shared context dictionary that must be preserved:
- Contains dataset matrices, model artifacts, and stage results
- Passed between stages to maintain pipeline state
- Critical for backward compatibility - FastAPI must not modify this pattern

### PipelineConfig Structure
Configuration follows this structure (needed for API models):
```python
@dataclass
class PipelineConfig:
    # Input data
    input_file: str
    scores_file: str
    label_dataset_file: Optional[str] = None
    
    # Output configuration
    output_folder: str
    
    # Pipeline stages
    umap_stage_enabled: bool = True
    heatmap_stage_enabled: bool = True
    prediction_stage_enabled: bool = True
```

## Job Management Requirements

### Job Lifecycle States
Jobs must track these states:
- `SUBMITTED` - Job received, not yet started
- `RUNNING` - Pipeline execution in progress
- `COMPLETED` - Pipeline finished successfully
- `FAILED` - Pipeline encountered error
- `CANCELLED` - Job terminated by user request

### Job Directory Structure
Each job needs isolated workspace:
```
jobs/
├── {job_id}/
│   ├── input/          # Uploaded files
│   ├── output/         # Pipeline results
│   ├── logs/           # Execution logs
│   └── metadata.json   # Job status, timestamps
```

### Job Metadata Format
```json
{
    "job_id": "uuid4-string",
    "status": "RUNNING",
    "created_at": "ISO timestamp",
    "started_at": "ISO timestamp",
    "completed_at": "ISO timestamp",
    "progress": 0.45,
    "stage": "umap_stage",
    "error_message": null
}
```

## API Model Requirements

### Request Models Needed
1. **PipelineConfigRequest**: API version of PipelineConfig
2. **JobSubmissionRequest**: File uploads + configuration
3. **FileUploadModel**: Multipart form data with size limits

### Response Models Needed  
1. **JobSubmissionResponse**: Job ID and initial status
2. **JobStatusResponse**: Current status, progress, stage info
3. **ErrorResponse**: Standardized error format with codes
4. **ArtifactListResponse**: Available download files

### Error Handling Patterns
- HTTP 400: Invalid configuration or malformed input
- HTTP 404: Job not found
- HTTP 409: Job already exists or conflicting operation
- HTTP 500: Internal pipeline execution error
- HTTP 413: File upload too large

## File Upload Constraints
- Maximum file size: 100MB per file
- Supported formats: CSV, TSV, NPY, NPZ
- Required files: input_file, scores_file
- Optional files: label_dataset_file
- All files validated before job submission

## Security Considerations
- UUID4 job IDs prevent enumeration attacks
- Job directories isolated with path traversal protection
- File uploads validated for type and size
- No job data shared between different job IDs

## Integration Points for Next Sub-Plans

### For 0b (Pipeline Integration)
- JobManager will provide job status update methods
- Context dictionary preservation patterns
- Job directory structure for stage artifacts

### For 0c (Interface Layer)
- Request/response model schemas
- Error response formats and HTTP status mappings
- File upload handling patterns

### For 0d (Security Testing)
- Job directory structure for path traversal testing
- UUID generation requirements for security validation
- File upload limits and validation rules
