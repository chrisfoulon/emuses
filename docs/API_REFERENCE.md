# 🔌 EMUSES API Complete Reference

**Comprehensive REST API documentation for programmatic access to EMUSES scientific analysis platform**

This reference covers all API endpoints with detailed request/response examples, authentication, error handling, and integration patterns for scientific research workflows.

> **💡 Interactive API Documentation**  
> For live, interactive API exploration, start the EMUSES service and visit:
> - **Swagger UI**: `http://localhost:8000/api/docs`
> - **ReDoc**: `http://localhost:8000/api/redoc`
> - **OpenAPI Schema**: `http://localhost:8000/api/openapi.json`

## 📋 **API Overview**

### **Base URLs**
- **Local Development**: `http://localhost:8000`
- **Production**: `https://your-emuses-instance.org`
- **API Prefix**: All endpoints use `/api/v1/` prefix

### **API Categories**
| Category | Endpoints | Description |
|----------|-----------|-------------|
| **Pipeline Execution** | 2 endpoints | Submit and manage analysis jobs |
| **Job Management** | 5 endpoints | Monitor job status and logs |
| **File Upload** | 3 endpoints | Upload scientific data |
| **Inference** | 2 endpoints | Run predictions on trained models |
| **Task Management** | 4 endpoints | Async task monitoring and control |
| **Artifact Management** | 2 endpoints | Download analysis results |
| **Health & Monitoring** | 20 endpoints | System health and diagnostics |
| **Model Registry** | 14 endpoints | Model management (multi-user mode) |

### **Authentication**
```http
# Multi-user mode requires authentication
Authorization: Bearer <your-jwt-token>

# Local mode (default) - no authentication required
```

### **Rate Limiting**
- **Default**: 100 requests per hour per IP
- **Authenticated**: 1000 requests per hour per user
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## 🔬 **Pipeline Execution API**

### `POST /api/v1/jobs/pipeline/full` - Submit Full Pipeline

Submit a complete EMUSES analysis pipeline including UMAP, heatmap, and prediction modeling.

#### Request

**Headers**
```http
Content-Type: multipart/form-data
Authorization: Bearer <token> (if multi-user mode)
```

**Form Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `features_file` | file | Yes | CSV file with scientific features |
| `scores_file` | file | Yes | CSV file with cognitive/behavioral scores |
| `labels_file` | file | No | CSV file with additional labels |
| `job_name` | string | No | Custom job name for identification |
| `n_neighbors` | integer | No | UMAP n_neighbors parameter (default: 15) |
| `min_dist` | float | No | UMAP min_dist parameter (default: 0.1) |
| `n_jobs` | integer | No | Parallel processing jobs (default: -1) |
| `config` | file | No | JSON configuration file |

#### Examples

**cURL**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/pipeline/full" \
  -H "Content-Type: multipart/form-data" \
  -F "features_file=@brain_features.csv" \
  -F "scores_file=@cognitive_scores.csv" \
  -F "job_name=motor_cortex_analysis" \
  -F "n_neighbors=20" \
  -F "min_dist=0.05"
```

**Python**
```python
import requests

url = "http://localhost:8000/api/v1/jobs/pipeline/full"
files = {
    'features_file': open('brain_features.csv', 'rb'),
    'scores_file': open('cognitive_scores.csv', 'rb')
}
data = {
    'job_name': 'my_analysis',
    'n_neighbors': 15,
    'min_dist': 0.1
}

response = requests.post(url, files=files, data=data)
print(response.json())
```

**JavaScript/Node.js**
```javascript
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('features_file', fs.createReadStream('brain_features.csv'));
form.append('scores_file', fs.createReadStream('cognitive_scores.csv'));
form.append('job_name', 'my_analysis');
form.append('n_neighbors', '15');

fetch('http://localhost:8000/api/v1/jobs/pipeline/full', {
    method: 'POST',
    body: form
})
.then(response => response.json())
.then(data => console.log(data));
```

#### Response

**Success (202 Accepted)**
```json
{
  "status": "accepted",
  "job_id": "job_abc123def456",
  "message": "Pipeline job submitted successfully",
  "estimated_duration": "180-300 seconds",
  "poll_url": "/api/v1/jobs/job_abc123def456/status",
  "artifacts_url": "/api/v1/jobs/job_abc123def456/artifacts"
}
```

**Error (400 Bad Request)**
```json
{
  "error": "Invalid input format",
  "details": {
    "features_file": "Missing required headers: subject_id",
    "scores_file": "Must be CSV format"
  },
  "code": "E201"
}
```

#### Use Cases
- **Research Automation**: Programmatic analysis submission
- **Batch Processing**: Submit multiple analyses
- **Integration**: Embed in research pipelines

---

### `POST /api/v1/jobs/pipeline/stage/{stage}` - Submit Stage-Specific Job

Submit individual pipeline stages (umap, heatmap, inference) for granular control.

#### Parameters
- **Path**: `stage` - Pipeline stage: `umap`, `heatmap`, `inference`

#### Request (UMAP Stage Example)

**Form Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `features_file` | file | Yes | Input features CSV |
| `job_name` | string | No | Custom job name |
| `n_neighbors` | integer | No | UMAP neighbors (default: 15) |
| `min_dist` | float | No | UMAP min distance (default: 0.1) |
| `n_components` | integer | No | Output dimensions (default: 2) |
| `metric` | string | No | Distance metric (default: 'euclidean') |
| `random_state` | integer | No | Random seed for reproducibility |

#### Examples

**Submit UMAP Job**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/pipeline/stage/umap" \
  -F "features_file=@brain_connectivity.csv" \
  -F "job_name=umap_exploration" \
  -F "n_neighbors=30" \
  -F "random_state=42"
```

**Submit Heatmap Job**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/pipeline/stage/heatmap" \
  -F "embeddings_file=@umap_embeddings.npy" \
  -F "scores_file=@cognitive_scores.csv" \
  -F "job_name=correlation_heatmap"
```

**Submit Inference Job**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/pipeline/stage/inference" \
  -F "model_file=@trained_model.pkl" \
  -F "data_file=@new_subjects.csv" \
  -F "job_name=prediction_task"
```

#### Use Cases
- **Modular Analysis**: Run individual pipeline components
- **Method Development**: Test specific algorithms
- **Custom Workflows**: Build custom analysis pipelines

---

## 📊 **Job Management API**

### `GET /api/v1/jobs/{job_id}/status` - Get Job Status

Retrieve current status and progress information for a submitted job.

#### Parameters
- **Path**: `job_id` - Unique job identifier

#### Request
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/job_abc123def456/status"
```

#### Response

**Running Job**
```json
{
  "job_id": "job_abc123def456",
  "status": "running",
  "progress": {
    "current_stage": "umap_training",
    "completion_percentage": 45,
    "stages_completed": ["data_validation", "preprocessing"],
    "stages_remaining": ["umap_training", "heatmap_generation", "model_training"]
  },
  "timing": {
    "submitted_at": "2024-08-16T14:30:15Z",
    "started_at": "2024-08-16T14:30:18Z",
    "estimated_completion": "2024-08-16T14:33:30Z",
    "elapsed_seconds": 127
  },
  "resources": {
    "cpu_usage": "23%",
    "memory_usage": "1.2GB",
    "gpu_usage": null
  }
}
```

**Completed Job**
```json
{
  "job_id": "job_abc123def456", 
  "status": "completed",
  "results": {
    "umap_embeddings": "job_abc123def456/umap_embeddings.npy",
    "heatmap_data": "job_abc123def456/heatmap_data.npy",
    "trained_model": "job_abc123def456/models/trained_model.pkl",
    "performance_metrics": {
      "r_squared": 0.847,
      "rmse": 0.234,
      "cross_val_score": 0.823
    }
  },
  "timing": {
    "submitted_at": "2024-08-16T14:30:15Z",
    "started_at": "2024-08-16T14:30:18Z", 
    "completed_at": "2024-08-16T14:33:42Z",
    "total_duration_seconds": 207
  },
  "artifacts_count": 8,
  "artifacts_size": "12.3MB"
}
```

**Failed Job**
```json
{
  "job_id": "job_abc123def456",
  "status": "failed",
  "error": {
    "code": "E201",
    "message": "Data validation failed",
    "details": "Missing required column 'subject_id' in features file",
    "stage": "data_validation",
    "timestamp": "2024-08-16T14:30:25Z"
  },
  "logs_available": true,
  "retry_possible": true
}
```

#### Job Status Values
- **`queued`**: Job waiting to start
- **`running`**: Job currently executing
- **`completed`**: Job finished successfully
- **`failed`**: Job encountered an error
- **`cancelled`**: Job was cancelled by user/admin

---

### `GET /api/v1/jobs/{job_id}/logs` - Get Job Logs

Retrieve execution logs for debugging and monitoring job progress.

#### Parameters
- **Path**: `job_id` - Unique job identifier
- **Query**: 
  - `lines` (integer): Number of recent lines (default: 100)
  - `level` (string): Log level filter (`debug`, `info`, `warning`, `error`)
  - `stage` (string): Filter by pipeline stage

#### Request
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/job_abc123def456/logs?lines=50&level=info"
```

#### Response
```json
{
  "job_id": "job_abc123def456",
  "log_entries": [
    {
      "timestamp": "2024-08-16T14:30:18Z",
      "level": "info",
      "stage": "data_validation", 
      "message": "Starting data validation for 1068 subjects"
    },
    {
      "timestamp": "2024-08-16T14:30:20Z",
      "level": "info",
      "stage": "data_validation",
      "message": "Features file validated: 1068 rows, 284 columns"
    },
    {
      "timestamp": "2024-08-16T14:30:45Z",
      "level": "info", 
      "stage": "umap_training",
      "message": "UMAP training started with n_neighbors=15, min_dist=0.1"
    },
    {
      "timestamp": "2024-08-16T14:32:12Z",
      "level": "info",
      "stage": "umap_training", 
      "message": "UMAP training completed in 87 seconds"
    }
  ],
  "total_lines": 156,
  "showing_lines": 50,
  "log_level": "info"
}
```

#### Use Cases
- **Debugging**: Diagnose failed jobs
- **Monitoring**: Track job progress in real-time
- **Optimization**: Identify performance bottlenecks

---

### `DELETE /api/v1/jobs/{job_id}` - Cancel Job

Cancel a running or queued job.

#### Parameters
- **Path**: `job_id` - Unique job identifier

#### Request
```bash
curl -X DELETE "http://localhost:8000/api/v1/jobs/job_abc123def456" \
  -H "Authorization: Bearer <token>"
```

#### Response
```json
{
  "job_id": "job_abc123def456",
  "status": "cancelled",
  "message": "Job cancelled successfully",
  "cleanup_status": "completed",
  "partial_results_available": false
}
```

---

### `GET /api/v1/jobs` - List Jobs

List jobs with filtering and pagination options.

#### Query Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `queued`, `running`, `completed`, `failed` |
| `user_id` | string | Filter by user (admin only) |
| `limit` | integer | Number of results (default: 20, max: 100) |
| `offset` | integer | Pagination offset (default: 0) |
| `sort` | string | Sort by: `created`, `status`, `duration` |
| `order` | string | Sort order: `asc`, `desc` (default: `desc`) |

#### Request
```bash
curl -X GET "http://localhost:8000/api/v1/jobs?status=completed&limit=10&sort=created"
```

#### Response
```json
{
  "jobs": [
    {
      "job_id": "job_abc123def456",
      "job_name": "motor_cortex_analysis",
      "status": "completed",
      "submitted_at": "2024-08-16T14:30:15Z",
      "duration_seconds": 207,
      "user_id": "jane_researcher"
    },
    {
      "job_id": "job_xyz789ghi012", 
      "job_name": "working_memory_study",
      "status": "completed",
      "submitted_at": "2024-08-16T13:45:22Z",
      "duration_seconds": 334,
      "user_id": "john_scientist"
    }
  ],
  "pagination": {
    "total": 47,
    "limit": 10,
    "offset": 0,
    "has_more": true
  }
}
```

---

## 📁 **Artifact Management API**

### `GET /api/v1/jobs/{job_id}/artifacts` - List Job Artifacts

List all output files and results generated by a completed job.

#### Parameters
- **Path**: `job_id` - Unique job identifier

#### Request
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/job_abc123def456/artifacts"
```

#### Response
```json
{
  "job_id": "job_abc123def456",
  "artifacts": [
    {
      "filename": "umap_embeddings.npy",
      "path": "job_abc123def456/umap_embeddings.npy",
      "size": "2.1MB",
      "type": "numpy_array",
      "stage": "umap_training",
      "description": "2D UMAP embeddings for visualization",
      "download_url": "/api/v1/jobs/job_abc123def456/artifacts/umap_embeddings.npy"
    },
    {
      "filename": "trained_model.pkl",
      "path": "job_abc123def456/models/trained_model.pkl", 
      "size": "0.8MB",
      "type": "sklearn_model",
      "stage": "model_training",
      "description": "Trained predictive model",
      "download_url": "/api/v1/jobs/job_abc123def456/artifacts/trained_model.pkl"
    },
    {
      "filename": "analysis_report.md",
      "path": "job_abc123def456/reports/analysis_report.md",
      "size": "15KB", 
      "type": "markdown",
      "stage": "reporting",
      "description": "Human-readable analysis summary",
      "download_url": "/api/v1/jobs/job_abc123def456/artifacts/analysis_report.md"
    },
    {
      "filename": "heatmap_visualization.png",
      "path": "job_abc123def456/visualizations/heatmap_visualization.png",
      "size": "1.2MB",
      "type": "image", 
      "stage": "heatmap_generation",
      "description": "Brain-behavior correlation heatmap",
      "download_url": "/api/v1/jobs/job_abc123def456/artifacts/heatmap_visualization.png"
    }
  ],
  "total_artifacts": 8,
  "total_size": "12.3MB"
}
```

#### Use Cases
- **Result Discovery**: Find available analysis outputs
- **Data Download**: Programmatic access to results
- **Workflow Integration**: Chain analysis results

---

### `GET /api/v1/jobs/{job_id}/artifacts/{filename}` - Download Artifact

Download specific analysis results or output files.

#### Parameters
- **Path**: `job_id` - Unique job identifier
- **Path**: `filename` - Name of file to download

#### Request
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/job_abc123def456/artifacts/umap_embeddings.npy" \
  --output umap_embeddings.npy
```

#### Response
- **Success**: Binary file content with appropriate `Content-Type` header
- **Headers**: `Content-Disposition`, `Content-Length`, `Content-Type`

#### Python Example
```python
import requests
import numpy as np

# Download UMAP embeddings
response = requests.get(
    "http://localhost:8000/api/v1/jobs/job_abc123def456/artifacts/umap_embeddings.npy"
)

# Save to file
with open("embeddings.npy", "wb") as f:
    f.write(response.content)

# Load directly into numpy
embeddings = np.load("embeddings.npy")
print(f"Embeddings shape: {embeddings.shape}")
```

---

## 📤 **File Upload API**

### `POST /api/v1/upload/features` - Upload Features File

Upload scientific features file for analysis.

#### Request
```bash
curl -X POST "http://localhost:8000/api/v1/upload/features" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@brain_features.csv" \
  -F "description=Motor cortex connectivity features"
```

#### Response
```json
{
  "file_id": "file_feat_abc123",
  "filename": "brain_features.csv",
  "size": "15.2MB",
  "validation": {
    "status": "valid",
    "rows": 1068,
    "columns": 284,
    "subjects_detected": 1068,
    "missing_values": 0
  },
  "upload_url": "/api/v1/files/file_feat_abc123",
  "expires_at": "2024-08-23T14:30:15Z"
}
```

### `POST /api/v1/upload/scores` - Upload Scores File

Upload cognitive/behavioral scores for prediction tasks.

#### Request
```bash
curl -X POST "http://localhost:8000/api/v1/upload/scores" \
  -F "file=@cognitive_scores.csv" \
  -F "description=Fluid intelligence scores"
```

### `POST /api/v1/upload/labels` - Upload Labels File

Upload additional label information for analysis.

#### Request
```bash
curl -X POST "http://localhost:8000/api/v1/upload/labels" \
  -F "file=@group_labels.csv" \
  -F "description=Subject group assignments"
```

---

## 🤖 **Inference API**

### `POST /api/v1/inference` - Synchronous Inference

Run immediate predictions on new data using trained models.

#### Request
```json
{
  "model_path": "job_abc123def456/models/trained_model.pkl",
  "data": [
    [0.23, 0.45, 0.67, 0.12],
    [0.34, 0.56, 0.78, 0.23],
    [0.45, 0.67, 0.89, 0.34]
  ],
  "subject_ids": ["subj_001", "subj_002", "subj_003"],
  "output_format": "json"
}
```

#### Response
```json
{
  "predictions": [
    {
      "subject_id": "subj_001",
      "prediction": 115.7,
      "confidence": 0.89
    },
    {
      "subject_id": "subj_002", 
      "prediction": 98.3,
      "confidence": 0.76
    },
    {
      "subject_id": "subj_003",
      "prediction": 127.1,
      "confidence": 0.92
    }
  ],
  "model_info": {
    "model_type": "Ridge Regression",
    "features_expected": 284,
    "performance_metrics": {
      "r_squared": 0.847,
      "rmse": 0.234
    }
  },
  "processing_time_ms": 23
}
```

### `POST /api/v1/inference/async` - Asynchronous Inference

Submit inference job for large datasets or batch processing.

#### Request
```json
{
  "model_path": "job_abc123def456/models/trained_model.pkl",
  "data_file_id": "file_data_xyz789",
  "job_name": "batch_prediction",
  "output_format": "csv"
}
```

#### Response
```json
{
  "task_id": "task_inf_abc123",
  "status": "queued",
  "estimated_completion": "2024-08-16T14:35:30Z",
  "poll_url": "/api/v1/tasks/task_inf_abc123",
  "result_url": "/api/v1/tasks/task_inf_abc123/result"
}
```

---

## 📊 **Health & Monitoring API**

### `GET /api/health` - Basic Health Check

Simple health check endpoint for load balancers and monitoring.

#### Request
```bash
curl -X GET "http://localhost:8000/api/health"
```

#### Response
```json
{
  "status": "healthy",
  "timestamp": "2024-08-16T14:30:15Z",
  "version": "0.9.0"
}
```

### `GET /api/v1/registry/health` - Registry Health Check

Detailed health check for model registry system.

#### Response
```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "redis": "healthy", 
    "model_storage": "healthy",
    "background_workers": "healthy"
  },
  "metrics": {
    "total_models": 156,
    "active_jobs": 3,
    "queue_size": 2,
    "uptime_seconds": 1320543
  },
  "last_check": "2024-08-16T14:30:15Z"
}
```

### `GET /api/v1/registry/health/detailed` - Detailed System Health

Comprehensive health information including performance metrics.

#### Response
```json
{
  "status": "healthy",
  "system": {
    "cpu_usage": 23.4,
    "memory_usage": 2156,
    "memory_total": 8192,
    "disk_usage": 47.3,
    "disk_total": 100.0
  },
  "database": {
    "status": "healthy",
    "connections": 12,
    "max_connections": 100,
    "query_time_avg_ms": 23.4,
    "slow_queries": 0
  },
  "redis": {
    "status": "healthy",
    "memory_usage": 45.2,
    "connected_clients": 8,
    "operations_per_second": 127
  },
  "models": {
    "total": 156,
    "healthy": 154,
    "corrupted": 2,
    "orphaned": 0
  },
  "jobs": {
    "queued": 2,
    "running": 3,
    "completed_24h": 47,
    "failed_24h": 2
  }
}
```

### Additional Health Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/registry/ready` | Kubernetes readiness probe |
| `GET /api/v1/registry/live` | Kubernetes liveness probe |
| `GET /api/v1/registry/service-discovery` | Service discovery information |
| `GET /api/v1/registry/degradation-status` | Graceful degradation status |
| `GET /metrics` | Prometheus metrics |

---

## 📚 **Error Handling**

### Standard Error Response Format

All API errors follow a consistent format:

```json
{
  "error": "Human-readable error message",
  "code": "E001",
  "details": {
    "field": "specific error details",
    "validation_errors": ["list of issues"]
  },
  "timestamp": "2024-08-16T14:30:15Z",
  "request_id": "req_abc123def456"
}
```

### HTTP Status Codes

| Status | Meaning | Usage |
|--------|---------|-------|
| 200 | OK | Successful request |
| 202 | Accepted | Job submitted successfully |
| 400 | Bad Request | Invalid request format |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 413 | Payload Too Large | File size exceeds limit |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |
| 503 | Service Unavailable | System maintenance |

### Error Codes Reference

| Code | Category | Description |
|------|----------|-------------|
| E001-E099 | General | Generic API errors |
| E100-E199 | Authentication | Auth and permission errors |
| E200-E299 | Validation | Data validation errors |
| E300-E399 | Processing | Job execution errors |
| E400-E499 | Storage | File and storage errors |
| E500-E599 | System | Infrastructure errors |

---

## 🚀 **Integration Examples**

### Python Integration
```python
import requests
import time

class EmusesClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def submit_analysis(self, features_file, scores_file, **kwargs):
        """Submit full pipeline analysis"""
        url = f"{self.base_url}/api/v1/jobs/pipeline/full"
        files = {
            'features_file': open(features_file, 'rb'),
            'scores_file': open(scores_file, 'rb')
        }
        
        response = self.session.post(url, files=files, data=kwargs)
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, job_id, polling_interval=30):
        """Wait for job completion with progress updates"""
        url = f"{self.base_url}/api/v1/jobs/{job_id}/status"
        
        while True:
            response = self.session.get(url)
            status_data = response.json()
            
            status = status_data['status']
            if status == 'completed':
                return status_data
            elif status == 'failed':
                raise Exception(f"Job failed: {status_data.get('error', {}).get('message')}")
            
            # Show progress
            if 'progress' in status_data:
                progress = status_data['progress']
                print(f"Progress: {progress['completion_percentage']}% - {progress['current_stage']}")
            
            time.sleep(polling_interval)
    
    def download_artifacts(self, job_id, output_dir="./results"):
        """Download all job artifacts"""
        import os
        
        # List artifacts
        artifacts_url = f"{self.base_url}/api/v1/jobs/{job_id}/artifacts"
        response = self.session.get(artifacts_url)
        artifacts = response.json()['artifacts']
        
        # Download each artifact
        os.makedirs(output_dir, exist_ok=True)
        for artifact in artifacts:
            download_url = f"{self.base_url}{artifact['download_url']}"
            file_response = self.session.get(download_url)
            
            file_path = os.path.join(output_dir, artifact['filename'])
            with open(file_path, 'wb') as f:
                f.write(file_response.content)
            
            print(f"Downloaded: {artifact['filename']} ({artifact['size']})")

# Usage example
client = EmusesClient()

# Submit analysis
job = client.submit_analysis(
    'brain_features.csv',
    'cognitive_scores.csv',
    job_name='my_analysis',
    n_neighbors=20
)

print(f"Job submitted: {job['job_id']}")

# Wait for completion
result = client.wait_for_completion(job['job_id'])
print(f"Analysis completed in {result['timing']['total_duration_seconds']} seconds")

# Download results
client.download_artifacts(job['job_id'])
```

### R Integration
```r
library(httr)
library(jsonlite)

# EMUSES R Client
submit_emuses_analysis <- function(features_file, scores_file, 
                                 base_url = "http://localhost:8000",
                                 job_name = NULL, ...) {
  
  url <- paste0(base_url, "/api/v1/jobs/pipeline/full")
  
  # Prepare form data
  body <- list(
    features_file = upload_file(features_file),
    scores_file = upload_file(scores_file)
  )
  
  # Add optional parameters
  if (!is.null(job_name)) body$job_name <- job_name
  extra_params <- list(...)
  body <- c(body, extra_params)
  
  # Submit request
  response <- POST(url, body = body, encode = "multipart")
  stop_for_status(response)
  
  return(content(response, "parsed"))
}

# Wait for job completion
wait_for_completion <- function(job_id, base_url = "http://localhost:8000",
                               polling_interval = 30) {
  
  url <- paste0(base_url, "/api/v1/jobs/", job_id, "/status")
  
  repeat {
    response <- GET(url)
    status_data <- content(response, "parsed")
    
    if (status_data$status == "completed") {
      return(status_data)
    } else if (status_data$status == "failed") {
      stop(paste("Job failed:", status_data$error$message))
    }
    
    # Show progress
    if (!is.null(status_data$progress)) {
      cat(sprintf("Progress: %d%% - %s\n", 
                  status_data$progress$completion_percentage,
                  status_data$progress$current_stage))
    }
    
    Sys.sleep(polling_interval)
  }
}

# Usage
job <- submit_emuses_analysis(
  "brain_features.csv",
  "cognitive_scores.csv", 
  job_name = "r_analysis",
  n_neighbors = 15
)

cat("Job submitted:", job$job_id, "\n")

result <- wait_for_completion(job$job_id)
cat("Analysis completed!\n")
```

---

## 🔗 **Related Documentation**

- [CLI Reference](docs/CLI_REFERENCE.md) - Complete command-line interface
- [User Guide](docs/USER_GUIDE.md) - Comprehensive usage documentation
- [Research Workflows](docs/RESEARCH_WORKFLOWS.md) - Scientific use patterns
- [Admin Guide](docs/ADMIN_GUIDE.md) - System administration

---

*This API reference provides complete programmatic access to EMUSES neuroimaging analysis capabilities. For additional help with integration, consult the User Guide or submit issues on GitHub.*