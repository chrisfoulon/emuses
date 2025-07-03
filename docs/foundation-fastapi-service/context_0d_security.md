# Security & Performance Context 0d: Comprehensive System Testing

## Focus Areas
This context provides complete system visibility for security validation, performance testing, and backward compatibility verification. It includes all components from previous sub-plans and their security/performance implications.

## Complete System Architecture

### Foundation Layer (0a)

**JobManager Security Features**:
- **UUID4 Generation**: Cryptographically secure UUID generation with entropy validation
  - Entropy requirement: 100 unique UUIDs should have 100 unique 8-character prefixes
  - Validation: `validate_job_id()` ensures proper UUID4 format
- **Path Traversal Protection**: Comprehensive directory traversal prevention
  - Validates: `../`, `..\\`, absolute paths, control characters
  - Safe directory creation: `create_job_directory()` with `0o700` permissions
- **Concurrency Safety**: Thread-safe status updates with per-job locking
  - File locking: `fcntl.LOCK_EX` for atomic metadata updates
  - Lock management: Per-job locks with cleanup on job deletion

**Job Directory Structure Security**:
```
jobs/
├── {job_id}/          # UUID4 validation prevents traversal
│   ├── input/         # 0o700 permissions, owner-only access
│   ├── output/        # Isolated artifact storage
│   │   ├── umap/      # Stage-specific subdirectories
│   │   ├── heatmap/   # Prevents artifact collisions
│   │   └── prediction/
│   ├── logs/          # Execution logs isolation
│   └── metadata.json  # Atomic updates with file locking
```

**Pydantic Models Security**:
- **Input Validation**: Comprehensive request validation
  - File size limits: 100MB per file, enforced by `FileUploadModel`
  - Content type validation: MIME type checking
  - Field validation: Required fields, format validation
- **Metadata Sanitization**: `_sanitize_metadata_value()` implementation
  - XSS Prevention: HTML escaping of string values
  - Path traversal removal: Strips `../` and `..\\` patterns
  - Control character removal: Filters null bytes and control characters

**Job Metadata Security Requirements**:
- **Sanitization Rules**:
  - HTML escape all string values to prevent XSS
  - Remove path traversal patterns (`../`, `..\\`)
  - Strip control characters (0x00-0x1f, 0x7f-0x9f)
  - Recursive sanitization for nested objects and arrays
- **Cleanup Policies**:
  - Configurable retention: `cleanup_after_days` parameter
  - Status-based cleanup: Only completed/failed/cancelled jobs
  - Atomic cleanup: Directory removal with lock cleanup

**UUID Generation Entropy Requirements**:
- **Cryptographic Security**: Uses `uuid.uuid4()` system entropy
- **Collision Resistance**: 100 generated UUIDs must be unique
- **Prefix Uniqueness**: First 8 characters must be unique across 100 UUIDs
- **Format Validation**: Ensures proper UUID4 version field

### Pipeline Integration Layer (0b)
**PipelineRunner**: Async wrapper, ProcessPoolExecutor, context preservation
- Security concern: Process isolation, resource limits
- Performance concern: Memory usage, process cleanup

**Stage Runners**: UMAPStage, HeatmapStage, PredictionStage wrappers
- Security concern: Parameter validation, resource limits
- Performance concern: Background execution, progress tracking

**Background Processing**: Progress callbacks, error handling, resource limits
- Security concern: Callback rate limiting, error information leakage
- Performance concern: Context serialization, memory spikes

### Interface Layer (0c)
**FastAPI Endpoints**: Complete endpoint inventory
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

**HTTP Security Implementations**:
- Path traversal protection in artifact downloads
- File upload validation (100MB limit, type checking)
- Rate limiting: 100 req/min global, 5 jobs/hour per IP
- Input sanitization for all parameters
- UUID validation with injection protection
- Error responses without information leakage

**Performance Characteristics**:
- Response time budget: ≤ 500ms for status endpoints
- Concurrent request handling: 10+ simultaneous jobs
- Memory usage patterns during file uploads
- Background process resource consumption

## Security Testing Requirements

### Path Traversal Protection Testing
**File Upload Endpoints**:
```python
# Test malicious file paths
test_paths = [
    "../../../etc/passwd",
    "..\\..\\windows\\system32\\config\\sam", 
    "....//....//etc/passwd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "file:///etc/passwd",
    "/dev/null",
    "CON", "PRN", "AUX"  # Windows reserved names
]
```

**Artifact Download Endpoints**:
```python
# Test directory traversal in artifact paths
for job_id in valid_job_ids:
    for path in malicious_paths:
        response = client.get(f"/api/v1/jobs/{job_id}/artifacts/{path}")
        assert response.status_code in [400, 403, 404]
        assert "etc/passwd" not in response.text
```

**Job Directory Creation**:
```python
# Test job directory isolation
job_dirs = [f"jobs/{job_id}" for job_id in test_job_ids]
for job_dir in job_dirs:
    # Verify no access outside job directory
    # Check symbolic link resolution
    # Test permissions and ownership
```

### Input Validation & Sanitization Testing
**JSON Payload Attacks**:
```python
# Test oversized payloads (>10MB)
# Test deeply nested JSON structures
# Test malformed JSON with control characters
# Test Unicode normalization attacks
# Test JSON deserialization bombs
```

**UUID Parameter Testing**:
```python
malicious_uuids = [
    "'; DROP TABLE jobs; --",
    "../../../secret",
    "%00truncated",
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",  # weak entropy
    "00000000-0000-0000-0000-000000000000",  # null UUID
]
```

**File Upload Abuse**:
```python
# Test oversized files (>100MB)
# Test malicious file content (ZIP bombs, XML bombs)
# Test executable file uploads
# Test files with malicious names
# Test simultaneous upload abuse
```

### Rate Limiting & DDoS Protection
**Endpoint Abuse Testing**:
```python
# Test global rate limit (100 req/min)
# Test job submission limit (5 jobs/hour)
# Test status check flooding (60 req/min per job)
# Test progress update abuse
# Test concurrent connection limits
```

**Resource Exhaustion Testing**:
```python
# Test memory exhaustion through large uploads
# Test disk space exhaustion through job creation
# Test CPU exhaustion through concurrent jobs
# Test process limit exhaustion
```

## Performance Testing Requirements

### Concurrency & Race Condition Testing
**Simultaneous Job Submissions**:
```python
async def test_concurrent_submissions():
    # Submit 10+ jobs simultaneously
    # Verify no race conditions in job ID generation
    # Check job directory creation isolation
    # Validate status updates under concurrent access
    # Monitor resource cleanup after completion
```

**Database/Metadata Concurrency**:
```python
# Test concurrent job status updates
# Test concurrent metadata reads/writes
# Test job directory cleanup race conditions
# Test progress callback concurrency
```

### Memory & Resource Management Testing
**Context Serialization Performance**:
```python
# Test large context dictionary serialization (>1GB)
# Monitor memory spikes during pickle/unpickle
# Test context deep copy performance
# Validate memory cleanup after job completion
```

**ProcessPoolExecutor Resource Testing**:
```python
# Test maximum concurrent processes (4 limit)
# Test memory limit enforcement (8GB per job)
# Test timeout enforcement (2 hours pipeline, 30 min stage)
# Test process cleanup after job failure
# Test resource limit enforcement under load
```

**Background Process Monitoring**:
```python
# Monitor memory usage during pipeline execution
# Test process isolation between jobs
# Validate cleanup after job completion
# Test resource limit enforcement
```

### Load Testing & Performance Budgets
**Response Time Testing**:
```python
# Status endpoints: ≤ 500ms under normal load
# Job submission: ≤ 2000ms including file upload
# Artifact download: ≤ 1000ms for typical files
# Progress updates: ≤ 100ms for real-time feel
```

**Throughput Testing**:
```python
# Sustained load: 10+ concurrent jobs
# Peak load: 50+ concurrent requests
# Job completion rate: all jobs complete within timeout
# Error rate: <1% under normal load, <5% under peak load
```

## Backward Compatibility Testing Requirements

### CLI Interface Preservation
**Command Verification**:
```bash
# Test existing CLI still works
python main.py full --input data.csv --scores scores.csv --output results/
python main.py umap --input data.csv --output results/
python main.py heatmap --input data.csv --scores scores.csv --output results/
python main.py prediction --input data.csv --scores scores.csv --output results/
```

**Output Format Validation**:
```python
# Compare CLI vs API output files
# Verify identical directory structure
# Check file naming conventions
# Validate CSV/JSON format compatibility
```

### Python API Preservation
**Import Compatibility**:
```python
# Test existing import statements
from emuses.pipelines import EMUSESPipeline
from emuses.pipelines.umap_stage import UMAPStage
from emuses.pipelines.heatmap_stage import HeatmapStage
from emuses.pipelines.prediction_stage import PredictionStage

# Test class interface preservation
pipeline = EMUSESPipeline(args)
pipeline.init_data()
pipeline.add_stage(UMAPStage(config))
results = pipeline.run()
```

**Context Pattern Preservation**:
```python
# Test exact dictionary passing between stages
# Verify no modification of context structure
# Check context key preservation
# Validate context value types and formats
```

### Computational Equivalence Testing
**Numerical Precision Validation**:
```python
# Run identical workloads through CLI and API
# Compare outputs with 1e-10 precision
# Test different random seeds for reproducibility
# Verify model artifacts are byte-identical
# Compare performance metrics exactly
```

**Result Verification**:
```python
# Test UMAP embeddings are identical
# Verify clustering labels match exactly
# Check prediction model weights are identical
# Validate performance CSV files match
```

## Quality Gates & Acceptance Criteria

### Security Standards
- OWASP compliance: No critical or high vulnerabilities
- Path traversal protection: 100% coverage of file operations
- Input validation: All endpoints reject malicious inputs
- Rate limiting: Effective against abuse scenarios
- Error handling: No sensitive information leakage

### Performance Standards  
- Response times: Meet all budget requirements under load
- Concurrency: Handle 10+ simultaneous jobs reliably
- Memory management: No leaks during extended testing
- Resource cleanup: 100% cleanup verification
- Load testing: Stable operation under sustained load

### Compatibility Standards
- CLI interface: 100% backward compatibility maintained
- Python imports: All existing code works unchanged
- Context preservation: Exact dictionary patterns maintained
- Computational results: Numerical equivalence within 1e-10 precision
