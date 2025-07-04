# Interface Layer Context 0c: FastAPI Endpoints

## Focus Areas
This context extends foundation and pipeline integration with FastAPI endpoint implementation. It covers HTTP request/response handling, input validation, and artifact management.

## Updates from Pipeline Runner Implementation (Task 4 - COMPLETED)

### PipelineRunner Integration for API Endpoints

**Production-Ready Pipeline Execution**: The PipelineRunner now executes real EMUSES pipeline stages, enabling API endpoints to provide complete pipeline functionality.

**Key Interface Patterns**:
- **Async Execution**: API endpoints use `await pipeline_runner.execute_pipeline(job_id, context)`
- **Real Artifact Creation**: API calls create all expected EMUSES outputs (models, embeddings, plots, metrics)
- **Context Management**: API properly sets up prediction context keys before execution
- **Background Processing**: ProcessPoolExecutor isolation with resource limits and timeouts

**Progress Callback Integration**: Rate-limited progress updates suitable for API response
```python
async def run_pipeline_endpoint(request: PipelineConfigRequest):
    # Real pipeline execution via PipelineRunner
    context = await pipeline_runner.execute_pipeline(job_id, initial_context)
    return JobStatusResponse(job_id=job_id, status="COMPLETED", ...)
```

**Error Handling Patterns**: Exception capture with job status updates
```python
try:
    result = await pipeline_runner.execute_pipeline(job_id, context)
except PipelineExecutionError as e:
    job_manager.update_job_status(job_id, "FAILED", message=str(e))
    raise HTTPException(status_code=500, detail=e.message)
```

## Inherited from 0a Foundation

### Request/Response Model Schemas
Complete Pydantic models for API endpoints:

**PipelineConfigRequest**: Pipeline configuration
```python
{
    "input_file": "data/input.csv",
    "scores_file": "data/scores.csv", 
    "label_dataset_file": "data/labels.csv",  # Optional
    "output_folder_path": "results/job_001",
    "umap_stage_enabled": True,
    "heatmap_stage_enabled": True,
    "prediction_stage_enabled": True
}
```

**JobSubmissionRequest**: Job submission with metadata
```python
{
    "pipeline_config": { /* PipelineConfigRequest */ },
    "job_name": "Experiment 001",           # Optional
    "description": "Initial dataset analysis"  # Optional
}
```

**JobStatusResponse**: Comprehensive job status
```python
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "RUNNING",                    # SUBMITTED|RUNNING|COMPLETED|FAILED|CANCELLED
    "created_at": "2025-07-03T10:30:00Z",
    "started_at": "2025-07-03T10:30:15Z",
    "completed_at": null,
    "progress": 0.65,                       # 0.0-1.0
    "current_stage": "umap_stage",
    "total_stages": 3,
    "message": "Processing UMAP optimization trial 32/50"
}
```

### Error Response Formats and HTTP Status Code Mappings
Standardized error handling with consistent structure:

**ErrorResponse Model**:
```python
{
    "error_code": "VALIDATION_ERROR",
    "message": "Invalid input configuration",
    "details": "The field 'input_file' is required but was not provided",
    "request_id": "req_123456789"          # Optional
}
```

**HTTP Status Code Mappings**:
- `400 Bad Request`: Invalid configuration, validation errors
  - Error codes: `VALIDATION_ERROR`, `INVALID_CONFIG`, `MISSING_FIELDS`
- `404 Not Found`: Job not found, artifact not found
  - Error codes: `JOB_NOT_FOUND`, `ARTIFACT_NOT_FOUND`
- `409 Conflict`: Job already exists, conflicting operation
  - Error codes: `JOB_EXISTS`, `OPERATION_CONFLICT`
- `413 Payload Too Large`: File upload size limits exceeded
  - Error codes: `FILE_TOO_LARGE`, `UPLOAD_LIMIT_EXCEEDED`
- `500 Internal Server Error`: Pipeline execution error, system failure
  - Error codes: `PIPELINE_ERROR`, `SYSTEM_ERROR`, `EXECUTION_FAILED`

### File Upload Handling Patterns and Size Limits
Comprehensive file upload validation and processing:

**FileUploadModel**: Upload validation
```python
{
    "filename": "data.csv",
    "content_type": "text/csv",
    "size": 1024000,                       # Bytes
    "field_name": "input_file"             # Optional form field name
}
```

**Size Limits and Validation Rules**:
- Maximum file size: 100MB per file
- Total upload limit: 500MB per job
- Supported formats: `.csv`, `.tsv`, `.npy`, `.npz`, `.pkl`
- Content-Type validation enforced
- Filename sanitization (no path traversal)

**Upload Processing Pattern**:
```python
# 1. Validate file size and type
# 2. Stream to temporary directory  
# 3. Virus scan (if enabled)
# 4. Move to job input directory
# 5. Update job metadata with file list
```

## Inherited from 0b Pipeline Integration

### PipelineRunner Async Interface
The PipelineRunner provides async pipeline execution for API endpoints:

**API Integration Pattern:**
```python
@app.post("/jobs/{job_id}/execute")
async def execute_pipeline(job_id: str, context: Dict[str, Any]):
    runner = PipelineRunner(job_manager)
    try:
        result = await runner.execute_pipeline(job_id, context)
        return {"status": "success", "result": result}
    except asyncio.TimeoutError:
        return {"status": "error", "message": "Pipeline execution timeout"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

**Background Execution Patterns:**
- ProcessPoolExecutor integration for non-blocking execution
- Job status updates through JobManager during execution
- Progress callback rate limiting for API responsiveness
- Timeout handling with configurable limits (default 1800s)

**Context Serialization for API:**
- Deep copy validation for context preservation
- Pickle serialization for large data handling
- Numpy array compatibility for ML pipeline data
- Memory-efficient processing of contexts >100MB

**Stage-Specific Runner Classes:**
- `UMAPStageRunner`: UMAP dimensionality reduction with optimization tracking
- `HeatmapStageRunner`: Heatmap generation with resource monitoring
- `PredictionStageRunner`: Prediction pipeline with test evaluation mode
- All runners inherit from `BaseStageRunner` with common validation and monitoring

**Progress Callback Mechanisms:**
- Rate-limited updates to prevent API bottlenecks
- Stage-specific progress reporting
- Real-time job status updates
- WebSocket support for live progress streaming (future enhancement)

## FastAPI Endpoint Structure

### Core Endpoint Categories

**Pipeline Execution Endpoints**:
- `POST /api/v1/jobs/pipeline/full` - Submit full pipeline job
- `POST /api/v1/jobs/pipeline/stage/{stage_name}` - Submit single stage job
- `POST /api/v1/jobs/pipeline/resume/{job_id}/{stage_name}` - Resume from stage

**Job Management Endpoints**:
- `GET /api/v1/jobs/{job_id}/status` - Get job status and progress
- `GET /api/v1/jobs/{job_id}/logs` - Get execution logs
- `DELETE /api/v1/jobs/{job_id}` - Cancel/delete job
- `GET /api/v1/jobs` - List jobs (with filtering)

**Artifact Management Endpoints**:
- `GET /api/v1/jobs/{job_id}/artifacts` - List available artifacts
- `GET /api/v1/jobs/{job_id}/artifacts/{filename}` - Download artifact
- `POST /api/v1/jobs/{job_id}/artifacts` - Upload additional files

### Input Validation Patterns

**File Upload Validation**:
```python
class FileUploadRequest:
    files: List[UploadFile] = Field(..., max_items=10)
    
    @validator('files')
    def validate_files(cls, v):
        for file in v:
            # Check file size (max 100MB)
            # Validate file extensions (.csv, .tsv, .npy, .npz)
            # Scan for malicious content
        return v
```

**Parameter Sanitization**:
- Remove/escape special characters from file names
- Validate numeric ranges for UMAP/clustering parameters
- Sanitize string inputs to prevent injection
- Validate UUID format for job IDs

**Rate Limiting Implementation**:
- Global rate limit: 100 requests/minute per IP
- Job submission limit: 5 jobs/hour per IP
- Status check limit: 60 requests/minute per job
- Progress updates: max 1/second per job

### HTTP Request/Response Patterns

**Job Submission Flow**:
```python
@app.post("/api/v1/jobs/pipeline/full")
async def submit_pipeline_job(
    request: PipelineJobRequest,
    files: List[UploadFile] = File(...)
) -> JobSubmissionResponse:
    # 1. Validate request and files
    # 2. Create job ID and directory structure
    # 3. Save uploaded files to job input directory
    # 4. Submit to PipelineRunner background execution
    # 5. Return job ID and initial status
```

**Status Check Flow**:
```python
@app.get("/api/v1/jobs/{job_id}/status")
async def get_job_status(job_id: UUID) -> JobStatusResponse:
    # 1. Validate job ID format
    # 2. Check job exists in system
    # 3. Read current status from metadata
    # 4. Include progress and current stage info
    # 5. Return structured status response
```

**Artifact Download Flow**:
```python
@app.get("/api/v1/jobs/{job_id}/artifacts/{filename}")
async def download_artifact(job_id: UUID, filename: str):
    # 1. Validate job ID and filename
    # 2. Check path traversal protection
    # 3. Verify file exists in job output directory
    # 4. Set appropriate content-type headers
    # 5. Stream file response with proper caching
```

### Error Response Standardization

**HTTP Status Code Mappings**:
- 200: Successful operation
- 201: Job successfully created
- 400: Invalid request parameters or malformed data
- 401: Authentication required (if implemented)
- 403: Access denied to job or resource
- 404: Job or artifact not found
- 409: Conflicting operation (job already exists)
- 413: File upload too large
- 429: Rate limit exceeded
- 500: Internal server error during pipeline execution
- 503: Service temporarily unavailable (resource exhaustion)

**Standardized Error Format**:
```python
class ErrorResponse:
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")  
    details: Optional[dict] = Field(None, description="Additional error context")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    job_id: Optional[UUID] = Field(None, description="Associated job ID if applicable")
```

### Security Implementation Details

**Path Traversal Protection**:
```python
def secure_filename(filename: str) -> str:
    # Remove path separators and parent directory references
    # Limit filename length and character set
    # Prevent hidden files and system files
    return sanitized_filename

def validate_job_path(job_id: UUID, filename: str) -> Path:
    # Construct path within job directory
    # Resolve symbolic links and check bounds
    # Prevent access outside job workspace
    return secure_path
```

**Input Sanitization**:
- JSON payload size limits (10MB max)
- String field length limits
- Numeric range validation
- File type validation beyond extensions
- Content scanning for malicious patterns

## Integration Points for Next Sub-Plan

### For 0d (Security Testing) Updates Needed
After this sub-plan completes, update `context_0d_security.md` with:

**Complete Endpoint Inventory**:
```
POST /api/v1/jobs/pipeline/full
POST /api/v1/jobs/pipeline/stage/{stage_name}
POST /api/v1/jobs/pipeline/resume/{job_id}/{stage_name}
GET /api/v1/jobs/{job_id}/status
GET /api/v1/jobs/{job_id}/logs
DELETE /api/v1/jobs/{job_id}
GET /api/v1/jobs
GET /api/v1/jobs/{job_id}/artifacts
GET /api/v1/jobs/{job_id}/artifacts/{filename}
POST /api/v1/jobs/{job_id}/artifacts
```

**Security-Relevant Implementation Details**:
- Path traversal protection implementation in artifact downloads
- File upload validation and size limits (100MB per file)
- Rate limiting configurations for all endpoints
- Input sanitization patterns for all user inputs
- UUID validation for job ID parameters
- Error response formats that don't leak sensitive information

**Performance Testing Targets**:
- Response time budget: ≤ 500ms for status endpoints
- Concurrent request handling: 10+ simultaneous jobs
- Rate limiting enforcement under load
- Memory usage during file uploads
- Background process resource consumption

**Validation Requirements**:
- All endpoints tested with malformed inputs
- Boundary condition testing for all parameters
- File upload abuse scenarios (oversized, malicious files)
- Path traversal attempts in all file operations
- UUID injection and enumeration attempts
```
