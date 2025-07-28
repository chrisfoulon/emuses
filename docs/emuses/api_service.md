# EMUSES API Service

EMUSES provides a comprehensive REST API service that enables remote execution of neuroimaging analysis pipelines through a FastAPI-based service architecture. The service supports full pipeline execution, individual stage processing, job management, and artifact handling with built-in security, rate limiting, and monitoring capabilities.

<details>
<summary><strong>📋 API Reference - Complete Endpoint Guide</strong></summary>

## Base Configuration

- **Base URL**: `http://localhost:8000` (default)
- **API Version**: `v1`
- **Documentation**: Available at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc)
- **OpenAPI Schema**: Available at `/api/openapi.json`

## Authentication & Rate Limiting

The service implements IP-based rate limiting (disabled in testing mode):
- **Pipeline Jobs**: 50 submissions per hour per IP
- **Stage Jobs**: 100 submissions per hour per IP  
- **Status Checks**: 300 requests per minute per IP
- **File Downloads**: 200 downloads per minute per IP
- **File Uploads**: 10 uploads per minute per IP

## Pipeline Execution Endpoints

### Submit Full Pipeline Job
```http
POST /api/v1/jobs/pipeline/full
Content-Type: application/json

{
  "pipeline_config": {
    "input_dataset": "/path/to/input.csv",
    "scores": "/path/to/scores.csv", 
    "output_folder": "/path/to/output",
    "label_dataset": "/path/to/labels.csv"  // optional
  },
  "job_name": "Experiment 001",           // optional
  "description": "Initial analysis"       // optional
}
```

**Response**: `201 Created`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "submitted",
  "created_at": "2025-07-28T10:30:00Z",
  "started_at": null,
  "completed_at": null,
  "progress": 0.0,
  "current_stage": null,
  "total_stages": 3,
  "message": "Job submitted successfully"
}
```

### Submit Single Stage Job
```http
POST /api/v1/jobs/pipeline/stage/{stage_name}
Content-Type: application/json
```

**Valid stage names**: `umap`, `heatmap`, `prediction`

**Request/Response**: Same format as full pipeline, but only executes specified stage.

## Job Management Endpoints

### Get Job Status
```http
GET /api/v1/jobs/{job_id}/status
```

**Response**: `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "created_at": "2025-07-28T10:30:00Z", 
  "started_at": "2025-07-28T10:30:15Z",
  "completed_at": null,
  "progress": 0.65,
  "current_stage": "umap_stage",
  "total_stages": 3,
  "message": "Processing UMAP dimensionality reduction"
}
```

**Status Values**: `submitted`, `running`, `completed`, `failed`, `cancelled`

### Get Job Logs
```http
GET /api/v1/jobs/{job_id}/logs
```

**Response**: `200 OK`
```json
{
  "logs": [
    "2025-07-28T10:30:15Z [INFO] Starting UMAP stage",
    "2025-07-28T10:30:45Z [INFO] UMAP optimization completed",
    "2025-07-28T10:31:00Z [INFO] Starting clustering optimization"
  ]
}
```

### List Jobs
```http
GET /api/v1/jobs?status=running&limit=20&offset=0
```

**Query Parameters**:
- `status` (optional): Filter by status (`submitted`, `running`, `completed`, `failed`, `cancelled`)
- `limit` (default: 50, max: 100): Number of jobs to return
- `offset` (default: 0): Pagination offset

**Response**: `200 OK`
```json
{
  "jobs": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "running",
      "created_at": "2025-07-28T10:30:00Z",
      "job_name": "Experiment 001",
      "progress": 0.65
    }
  ],
  "total_count": 45,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

### Cancel/Delete Job
```http
DELETE /api/v1/jobs/{job_id}
```

**Response**: `200 OK`
```json
{
  "message": "Job cancelled successfully"
}
```

## Artifact Management Endpoints

### List Job Artifacts
```http
GET /api/v1/jobs/{job_id}/artifacts
```

**Response**: `200 OK`
```json
{
  "artifacts": [
    {
      "filename": "best_umap_model.joblib",
      "size": 1024000,
      "modified_at": "2025-07-28T11:00:00Z",
      "content_type": "application/octet-stream"
    },
    {
      "filename": "embeddings.npy", 
      "size": 2048000,
      "modified_at": "2025-07-28T11:00:30Z",
      "content_type": "application/octet-stream"
    }
  ]
}
```

### Download Job Artifact
```http
GET /api/v1/jobs/{job_id}/artifacts/{filename}
```

**Response**: `200 OK` with file content and appropriate headers.

## File Upload Endpoints

### Upload Features File
```http
POST /api/v1/upload/features
Content-Type: multipart/form-data

file: [CSV file up to 1GB]
```

**Response**: `201 Created`
```json
{
  "file_id": "20250728_103000_123456_features",
  "filename": "patient_features.csv",
  "file_path": "/tmp/emuses_uploads/job_123/features.csv",
  "content_type": "text/csv",
  "size": 1024000,
  "upload_time": "2025-07-28T10:30:00Z"
}
```

### Upload Scores File
```http
POST /api/v1/upload/scores
Content-Type: multipart/form-data

file: [CSV file up to 1GB]
```

### Upload Labels File
```http
POST /api/v1/upload/labels
Content-Type: multipart/form-data

file: [CSV file up to 1GB]
```

**Note**: Features and scores uploads use identical response format.

## Health Check Endpoint

### Service Health Check
```http
GET /api/health
```

**Response**: `200 OK`
```json
{
  "status": "healthy",
  "timestamp": "2025-07-28T10:30:00Z",
  "version": "1.0.0"
}
```

## Error Responses

All endpoints return standardized error responses:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Invalid input configuration", 
  "timestamp": "2025-07-28T10:30:00Z"
}
```

**Common Error Codes**:
- `VALIDATION_ERROR` (400): Invalid request parameters
- `JOB_NOT_FOUND` (404): Job ID not found
- `ARTIFACT_NOT_FOUND` (404): Artifact file not found
- `PAYLOAD_TOO_LARGE` (413): Request exceeds size limits
- `SYSTEM_ERROR` (500): Internal server error

</details>

<details>
<summary><strong>🔧 Developer Implementation Guide</strong></summary>

## Service Architecture

The EMUSES API service follows a layered architecture:

```
FastAPI Application (emuses.api.main)
    ↓
Foundation Service (emuses.foundation_fastapi_service.app)
    ↓
Job Manager (emuses.foundation_fastapi_service.job_manager)
    ↓  
Pipeline Runner (emuses.foundation_fastapi_service.pipeline_runner)
    ↓
EMUSES Pipeline (emuses.pipelines.emuses_pipeline)
```

## Core Components

### Application Factory
```python
from emuses.api.main import create_app

app = create_app()  # Returns configured FastAPI instance
```

The factory pattern enables consistent service instantiation across different deployment scenarios (local, remote, testing).

### Job Management System

Jobs are managed through a secure lifecycle:

1. **Job Creation**: UUID4 generation with entropy validation
2. **Directory Structure**: Isolated job directories with security protections
3. **Status Tracking**: Thread-safe status updates with file locking
4. **Artifact Management**: Secure file handling with path traversal protection
5. **Cleanup**: Configurable job retention policies

### Pipeline Integration

The service executes EMUSES pipelines through:

```python
# Pipeline context structure
pipeline_context = {
    "config": pipeline_config,
    "input_dataset": config["input_dataset"],
    "scores_dataset": config["scores"]
}

# Asynchronous execution
asyncio.create_task(
    pipeline_runner.execute_pipeline(job_id, pipeline_context)
)
```

### Security Features

- **Path Traversal Protection**: Filename sanitization and validation
- **Request Size Limits**: 1GB default for neuroimaging data
- **Rate Limiting**: IP-based throttling (configurable)
- **Input Validation**: Pydantic models with comprehensive validation
- **File Upload Security**: Content-type validation and secure storage

### Error Handling Patterns

```python
# Standardized error responses
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
        }
    )
```

### Configuration Management

The service supports environment-based configuration:

```python
# Environment variables
TESTING_MODE = os.getenv("TESTING_MODE", "false").lower() == "true"
RATE_LIMITING_ENABLED = os.getenv("RATE_LIMITING_ENABLED", "true").lower() == "true"
EMUSES_JOB_STORAGE = os.getenv("EMUSES_JOB_STORAGE", default_path)
```

### Windows/WSL Path Handling

Automatic path conversion for cross-platform compatibility:

```python
def _convert_windows_path_to_wsl(file_path: str) -> str:
    """Convert Windows paths to WSL format when running in WSL environment."""
    # Converts C:\path\file.txt to /mnt/c/path/file.txt
```

### Middleware Stack

1. **CORS Middleware**: Cross-origin request handling
2. **Request Size Limiter**: Payload size validation
3. **Rate Limiter**: IP-based request throttling (conditional)
4. **Exception Handlers**: Standardized error responses

### Testing Configuration

Testing mode automatically:
- Disables rate limiting
- Uses temporary directories for job storage
- Bypasses certain security validations
- Enables additional debugging features

### Integration Patterns

**Local Service Integration**:
```python
from fastapi.testclient import TestClient
from emuses.api.main import create_app

client = TestClient(create_app())
response = client.post("/api/v1/jobs/pipeline/full", json=config)
```

**Remote Service Integration**:
```python
# Use HTTP client with built-in resilience patterns
# (circuit breaker, retry logic, connection pooling)
```

### Monitoring and Observability

- **Health Endpoints**: Service status monitoring
- **Structured Logging**: JSON-formatted log messages
- **Job Progress Tracking**: Real-time progress updates
- **Performance Metrics**: Request timing and resource usage
- **Error Tracking**: Comprehensive error reporting

</details>

## Common Use Cases

### Basic Pipeline Execution
Submit neuroimaging data for full pipeline analysis with UMAP dimensionality reduction, clustering, and prediction stages.

### Stage-Specific Processing
Execute individual pipeline stages for focused analysis or debugging purposes.

### Batch Processing
Submit multiple jobs for processing different datasets or parameter configurations.

### Result Management
Monitor job progress, retrieve execution logs, and download generated artifacts.

### File Management
Upload large neuroimaging datasets securely and manage temporary file storage.

## Integration Notes

The API service is designed to work seamlessly with:
- **EMUSES CLI**: Auto-start local service or connect to remote instances
- **Jupyter Notebooks**: Direct API integration for interactive analysis
- **HPC Systems**: Job submission through SLURM/PBS integration
- **Cloud Platforms**: Scalable deployment with load balancing

## Performance Characteristics

- **Request Handling**: Asynchronous FastAPI with connection pooling
- **File Processing**: Streaming upload/download for large files (up to 1GB)
- **Job Execution**: Background processing with progress tracking
- **Resource Management**: Configurable cleanup policies and storage limits
- **Scalability**: Horizontal scaling support through stateless design

For deployment guidance and advanced configuration options, see [Service Deployment Guide](service_deployment.md).

For CLI integration patterns and client-side usage, see [CLI Service Integration](cli_service_integration.md).