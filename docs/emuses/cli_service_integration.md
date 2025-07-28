# EMUSES CLI Service Integration

The EMUSES CLI provides seamless integration with the FastAPI service, enabling both local auto-start functionality and remote service connections. This service-first design ensures consistency between local development and remote deployment while maintaining the familiar CLI interface.

<details>
<summary><strong>🚀 Service Integration Modes - Local and Remote Execution</strong></summary>

## Auto-Start Local Service Mode (Default)

The CLI automatically starts a local FastAPI service when needed, providing seamless local execution:

```bash
# Standard CLI usage - auto-starts local service
emuses --input-dataset data/input.csv --scores data/scores.csv --output results/
```

**What happens internally**:
1. CLI checks if local service is running on `localhost:8000`
2. If not running, automatically starts FastAPI service in background
3. Uses TestClient or HTTP client to communicate with service
4. Pipeline executes through service API
5. Service shuts down gracefully when CLI completes

## Remote Service Mode

Connect to a remote EMUSES service instance:

```bash
# Connect to remote service
emuses --service http://remote-server:8000 --input-dataset data/input.csv --scores data/scores.csv --output results/
```

**Service URL Formats**:
- `http://localhost:8000` - Local service (explicit)
- `https://emuses.research.org` - Remote HTTPS service
- `http://cluster-node:8000` - HPC cluster service

## Service Discovery and Health Checking

The CLI performs automatic service discovery:

```bash
# Check service status
emuses --service http://localhost:8000 --health-check

# Output:
# ✓ Service is healthy at http://localhost:8000
# ✓ Version: 1.0.0
# ✓ Response time: 45ms
```

**Health Check Process**:
1. Attempt connection to `/api/health` endpoint
2. Validate service version compatibility
3. Check response time and availability
4. Report service status and capabilities

## Connection Management

The CLI provides robust connection handling:

```bash
# Configure connection parameters
emuses --service http://remote:8000 \
       --timeout 120 \
       --retries 3 \
       --pool-connections 10 \
       --input-dataset data/input.csv \
       --scores data/scores.csv \
       --output results/
```

**Connection Parameters**:
- `--timeout`: Request timeout in seconds (default: 300)
- `--retries`: Maximum retry attempts (default: 3)
- `--pool-connections`: Connection pool size (default: 20)
- `--rate-limit`: Requests per second limit (default: 10)

## Offline Fallback Mode

When service connection fails, CLI can fall back to local execution:

```bash
# Enable offline fallback
emuses --service http://remote:8000 \
       --offline-fallback \
       --input-dataset data/input.csv \
       --scores data/scores.csv \
       --output results/
```

**Fallback Behavior**:
1. Attempt connection to specified service
2. If connection fails after retries, warn user
3. Switch to local pipeline execution
4. Continue with standard EMUSES pipeline
5. Log fallback decision for debugging

</details>

<details>
<summary><strong>🔧 Developer Integration Patterns</strong></summary>

## Service Client Architecture

The CLI uses a sophisticated HTTP client with resilience patterns:

### Circuit Breaker Pattern
```python
from emuses.cli.service_client import ServiceHTTPClient

client = ServiceHTTPClient(
    base_url="http://localhost:8000",
    circuit_breaker_threshold=5,    # Open circuit after 5 failures
    circuit_breaker_timeout=60.0,   # Reset circuit after 60 seconds
    max_retries=3,
    retry_backoff_factor=2.0
)
```

**Circuit Breaker States**:
- **Closed**: Normal operation, requests proceed
- **Open**: Service unavailable, requests fail immediately
- **Half-Open**: Testing service recovery, limited requests allowed

### Connection Pooling
```python
# Efficient connection reuse
client = ServiceHTTPClient(
    pool_connections=20,    # Number of connection pools
    pool_maxsize=100,      # Max connections per pool
    max_concurrent_requests=5  # Concurrent request limit
)
```

### Retry Logic with Exponential Backoff
```python
# Configurable retry behavior
client = ServiceHTTPClient(
    max_retries=3,
    retry_backoff_factor=2.0,  # 1s, 2s, 4s delays
    max_retry_delay=60.0       # Cap retry delay
)
```

## Service Manager Integration

The CLI includes automatic service lifecycle management:

### Auto-Start Configuration
```python
from emuses.cli.service_manager import ServiceManager

manager = ServiceManager(
    host="127.0.0.1",
    port=8000,
    startup_timeout=30.0,
    shutdown_timeout=10.0,
    auto_start=True,           # Enable auto-start
    background_mode=True       # Run as background process
)
```

### Service Lifecycle Methods
```python
# Start service if not running
await manager.ensure_service_running()

# Check service status
is_running = await manager.is_service_running()

# Stop service gracefully
await manager.stop_service()

# Cleanup on exit
manager.cleanup_on_exit()
```

### Process Management
The service manager handles:
- **Port availability checking** - Prevents conflicts
- **Process monitoring** - Tracks service health
- **Graceful shutdown** - Clean resource cleanup
- **Error recovery** - Automatic restart on failure

## CLI Command Translation

CLI arguments are automatically translated to API requests:

### Pipeline Configuration Mapping
```python
# CLI arguments
cli_args = {
    "input_dataset": "data/input.csv",
    "scores": "data/scores.csv", 
    "output_folder": "results/",
    "umap_trials": 50,
    "hdbscan_trials": 20
}

# Translated to API request
api_request = {
    "pipeline_config": {
        "input_dataset": "/absolute/path/to/data/input.csv",
        "scores": "/absolute/path/to/data/scores.csv",
        "output_folder": "/absolute/path/to/results",
        "umap_trials": 50,
        "hdbscan_trials": 20
    },
    "job_name": "CLI Pipeline Job",
    "description": "Executed via EMUSES CLI"
}
```

### Path Resolution and Validation
```python
# Secure path handling
from emuses.cli.security import validate_path, sanitize_input

# Windows/WSL path conversion
def convert_paths_for_service(config: dict) -> dict:
    """Convert local paths to service-accessible paths."""
    converted = config.copy()
    
    for path_key in ['input_dataset', 'scores', 'output_folder']:
        if path_key in converted:
            # Convert Windows paths to WSL if needed
            # Resolve relative paths to absolute
            # Validate path exists and is accessible
            converted[path_key] = resolve_service_path(converted[path_key])
    
    return converted
```

## Progress Monitoring Integration

The CLI provides real-time progress monitoring for service jobs:

### Progress Tracking
```python
from emuses.cli.rich_features import ProgressTracker

async def monitor_job_progress(client: ServiceHTTPClient, job_id: str):
    """Monitor and display job progress with rich formatting."""
    
    tracker = ProgressTracker()
    
    while True:
        status = await client.get_job_status(job_id)
        
        tracker.update(
            stage=status.get('current_stage'),
            progress=status.get('progress', 0.0),
            message=status.get('message', '')
        )
        
        if status['status'] in ['completed', 'failed', 'cancelled']:
            break
            
        await asyncio.sleep(2)  # Poll every 2 seconds
```

### Rich Output Formatting
```python
from emuses.cli.rich_features import StatusRenderer, TableFormatter

# Format job status with colors and styling
renderer = StatusRenderer()
renderer.display_job_status(job_status)

# Format job list as table
formatter = TableFormatter()
formatter.display_jobs_table(jobs_list)
```

## Error Handling and Recovery

### Service Error Translation
```python
def translate_service_error(service_error: dict) -> str:
    """Translate service API errors to user-friendly CLI messages."""
    
    error_messages = {
        'VALIDATION_ERROR': 'Invalid configuration: {message}',
        'JOB_NOT_FOUND': 'Job not found. It may have been cancelled or expired.',
        'ARTIFACT_NOT_FOUND': 'Output file not found: {message}',
        'PAYLOAD_TOO_LARGE': 'File too large. Maximum size is 1GB.',
        'SYSTEM_ERROR': 'Service error occurred. Please try again.'
    }
    
    error_code = service_error.get('error_code', 'SYSTEM_ERROR')
    message = service_error.get('message', 'Unknown error')
    
    template = error_messages.get(error_code, 'Service error: {message}')
    return template.format(message=message)
```

### Graceful Degradation
```python
async def execute_with_fallback(config: dict):
    """Execute pipeline with service fallback logic."""
    
    try:
        # Attempt service execution
        return await execute_via_service(config)
        
    except ServiceClientError as e:
        if config.get('offline_fallback', False):
            logger.warning(f"Service unavailable: {e}. Falling back to local execution.")
            return execute_local_pipeline(config)
        else:
            raise e
```

## Testing Integration

### TestClient Usage
```python
from fastapi.testclient import TestClient
from emuses.api.main import create_app

# Local testing with service
def test_cli_service_integration():
    app = create_app()
    client = TestClient(app)
    
    # Submit job via TestClient
    response = client.post("/api/v1/jobs/pipeline/full", json=config)
    assert response.status_code == 201
    
    job_id = response.json()['job_id']
    
    # Monitor job completion
    while True:
        status_response = client.get(f"/api/v1/jobs/{job_id}/status")
        status = status_response.json()['status']
        
        if status in ['completed', 'failed']:
            break
```

### Mock Service Testing
```python
# Mock service for CLI testing
@pytest.fixture
def mock_service():
    with patch('emuses.cli.service_client.ServiceHTTPClient') as mock:
        mock.return_value.submit_pipeline_job.return_value = {
            'job_id': 'test-job-123',
            'status': 'submitted'
        }
        yield mock
```

</details>

## Configuration Management

### Service Endpoint Configuration
```bash
# Environment variable
export EMUSES_SERVICE_URL="http://remote-server:8000"

# CLI argument (takes precedence)
emuses --service http://localhost:8000 --input-dataset data/input.csv
```

### Connection Parameters
```bash
# Comprehensive service configuration
emuses --service http://remote:8000 \
       --service-timeout 300 \
       --service-retries 5 \
       --service-pool-size 20 \
       --rate-limit 10.0 \
       --enable-circuit-breaker \
       --offline-fallback \
       --input-dataset data/input.csv \
       --scores data/scores.csv \
       --output results/
```

## Interactive Mode Integration

The CLI's interactive mode seamlessly works with service integration:

```bash
# Interactive mode with service
emuses --interactive --service http://remote:8000

# Guided workflow:
# 1. Service connection validation
# 2. File path resolution and upload
# 3. Configuration parameter selection
# 4. Job submission and monitoring
# 5. Result download and local storage
```

## Security Considerations

### Path Security
- **Path Traversal Protection**: Validate all file paths
- **Access Control**: Ensure user can only access authorized files
- **Sanitization**: Clean user input to prevent injection attacks

### Network Security
- **TLS Support**: HTTPS connections for remote services
- **Authentication**: Token-based authentication support (when configured)
- **Rate Limiting**: Respect service rate limits and implement client-side throttling

### Data Privacy
- **Secure Transmission**: Encrypt data in transit
- **Temporary Files**: Secure handling of uploaded data
- **Cleanup**: Remove temporary files after processing

## Performance Optimization

### Connection Reuse
- **Persistent Connections**: HTTP connection pooling
- **Session Management**: Efficient session lifecycle
- **Request Batching**: Optimize multiple API calls

### Progress Optimization
- **Efficient Polling**: Adaptive polling intervals
- **Caching**: Cache service responses when appropriate
- **Async Operations**: Non-blocking progress monitoring

## Migration from Direct Pipeline Execution

For users migrating from direct pipeline execution to service-based execution:

1. **Transparent Migration**: No changes to CLI commands required
2. **Performance Benefits**: Background execution and progress monitoring
3. **Resource Management**: Better memory and CPU utilization
4. **Scalability**: Seamless transition to remote execution

The service integration maintains 100% backward compatibility while providing enhanced capabilities for both local development and production deployment scenarios.

For complete API reference, see [API Service Documentation](api_service.md).

For deployment and configuration details, see [Service Deployment Guide](service_deployment.md).