# Service Logging and Polling Improvements Plan

## Problem Statement

### Issue 1: CLI Status Polling Failures
- CLI successfully submits jobs to FastAPI service
- Status polling requests fail after 4 retry attempts during pipeline execution
- Service appears to become unresponsive during intensive pipeline operations
- User loses visibility into pipeline progress

### Issue 2: Missing Pipeline Logs in CLI
- When using service mode, pipeline logs only appear in service terminal
- Users lose valuable feedback about pipeline progress, stage completion, and results
- Poor user experience compared to local execution mode

## Current State Analysis

### Service Architecture
- FastAPI service runs pipeline in background using `asyncio.create_task()`
- CLI polls `/api/v1/jobs/{job_id}/status` every 2 seconds
- Service writes logs to stdout/stderr (only visible in service terminal)
- Status endpoint may be blocked by intensive pipeline operations

### CLI Behavior
- Uses `ServiceHTTPClient` with 4 retry attempts
- 30-second timeout per request
- Exponential backoff between retries
- Falls back to local execution on persistent failures

## Solution Design

### Phase 1: Fix Status Polling Issues (Immediate)

#### 1.1 Increase Status Polling Resilience
**File**: `/home/chrisfoulon/neuro_apps/emuses/emuses/cli/service_client.py`
- Increase timeout from 30s to 60s for status requests
- Increase retry attempts from 4 to 8
- Add longer exponential backoff (2s, 4s, 8s, 16s, 32s, 60s, 120s, 240s)
- Add specific handling for different HTTP error codes

#### 1.2 Improve Service Response Time
**File**: `/home/chrisfoulon/neuro_apps/emuses/emuses/foundation_fastapi_service/app.py`
- Ensure status endpoints are non-blocking
- Add async/await to all status-related operations
- Implement proper async job status storage

#### 1.3 Add Status Endpoint Monitoring
**File**: `/home/chrisfoulon/neuro_apps/emuses/emuses/foundation_fastapi_service/app.py`
- Add timing metrics to status endpoints
- Add logging for status request processing
- Monitor for blocking operations

### Phase 2: Smart Log Forwarding (Long-term)

#### 2.1 Service-Side Log Capture
**File**: `/home/chrisfoulon/neuro_apps/emuses/emuses/foundation_fastapi_service/pipeline_runner.py`

```python
class PipelineRunner:
    def setup_job_logging(self, job_id: str) -> str:
        """Setup job-specific log file and return path."""
        job_dir = get_job_manager().get_job_directory(job_id)
        log_file = job_dir / "pipeline.log"
        
        # Create custom logger for this job
        logger = logging.getLogger(f"job_{job_id}")
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        
        return str(log_file)
    
    async def execute_pipeline(self, job_id: str, context: dict):
        """Execute pipeline with job-specific logging."""
        log_file = self.setup_job_logging(job_id)
        
        # Redirect pipeline stdout/stderr to log file
        with open(log_file, 'a') as f:
            # Execute pipeline with redirected output
            await self._run_pipeline_with_logging(job_id, context, f)
```

#### 2.2 CLI-Side Log Streaming
**File**: `/home/chrisfoulon/neuro_apps/emuses/emuses/cli/main.py`

```python
async def stream_job_logs(job_id: str, service_client: ServiceHTTPClient):
    """Stream job logs in real-time."""
    log_endpoint = f"/api/v1/jobs/{job_id}/logs/stream"
    
    async def log_streamer():
        try:
            async with service_client.stream_logs(log_endpoint) as stream:
                async for line in stream:
                    print(line.strip())
        except Exception as e:
            logger.debug(f"Log streaming error: {e}")
    
    return asyncio.create_task(log_streamer())

async def _execute_via_service(pipeline_type: str, config: dict, status_renderer, progress_tracker):
    """Execute pipeline via service with log streaming."""
    service_client = ServiceHTTPClient(base_url="http://localhost:8000")
    
    # Submit job
    job_response = await service_client.submit_pipeline_job(pipeline_type, config)
    job_id = job_response["job_id"]
    
    # Start log streaming
    log_task = await stream_job_logs(job_id, service_client)
    
    # Poll for completion
    try:
        while True:
            status = await service_client.get_job_status(job_id)
            if status["status"] in ["COMPLETED", "FAILED"]:
                break
            await asyncio.sleep(5)  # Increased polling interval
    finally:
        log_task.cancel()
```

#### 2.3 Add Log Streaming Endpoint
**File**: `/home/chrisfoulon/neuro_apps/emuses/emuses/foundation_fastapi_service/app.py`

```python
@app.get("/api/v1/jobs/{job_id}/logs/stream")
async def stream_job_logs(job_id: str):
    """Stream job logs in real-time."""
    job_dir = get_job_manager().get_job_directory(job_id)
    log_file = job_dir / "pipeline.log"
    
    async def log_generator():
        try:
            with open(log_file, 'r') as f:
                # Seek to end and follow
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        yield f"data: {line}\n\n"
                    else:
                        await asyncio.sleep(0.5)
        except FileNotFoundError:
            yield "data: Log file not found\n\n"
    
    return StreamingResponse(log_generator(), media_type="text/plain")
```

## Implementation Timeline

### Week 1: Status Polling Fixes
- Day 1-2: Implement resilient status polling in CLI
- Day 3-4: Fix service status endpoint responsiveness
- Day 5: Testing and validation

### Week 2: Log Forwarding Foundation
- Day 1-2: Implement service-side log capture
- Day 3-4: Add log streaming endpoint
- Day 5: Basic CLI log streaming

### Week 3: Integration and Polish
- Day 1-2: Integrate log streaming with status polling
- Day 3-4: Error handling and edge cases
- Day 5: Testing and documentation

## Testing Strategy

### Unit Tests
- Test status polling with various failure scenarios
- Test log file creation and streaming
- Test concurrent log streaming and status polling

### Integration Tests
- Test full pipeline execution with log streaming
- Test service restart scenarios
- Test multiple concurrent jobs

### Performance Tests
- Measure impact of log streaming on service performance
- Test with large pipeline outputs
- Validate memory usage with long-running pipelines

## Risk Mitigation

### Status Polling Risks
- **Risk**: Increased timeouts may delay error detection
- **Mitigation**: Implement smart timeout based on pipeline stage
- **Risk**: Service may still become unresponsive
- **Mitigation**: Maintain fallback to local execution

### Log Streaming Risks
- **Risk**: Log files may grow very large
- **Mitigation**: Implement log rotation and size limits
- **Risk**: Multiple clients streaming same logs
- **Mitigation**: Implement connection limits and rate limiting

## Success Metrics

### Immediate (Phase 1)
- Status polling success rate > 95%
- Reduced CLI timeout failures
- Maintained service responsiveness during pipeline execution

### Long-term (Phase 2)
- Users see pipeline logs in CLI when using service mode
- Log streaming latency < 1 second
- No performance degradation in pipeline execution

## Alternative Approaches Considered

### Alternative 1: Embedded Service Mode
- Start service in foreground from CLI
- **Pros**: Simple implementation, full log visibility
- **Cons**: Defeats API benefits, no concurrent job support

### Alternative 2: WebSocket Real-time Logs
- Use WebSocket for bidirectional log streaming
- **Pros**: Lower latency, real-time updates
- **Cons**: More complex implementation, connection management

### Alternative 3: Polling-based Log Retrieval
- CLI polls for new log lines periodically
- **Pros**: Simple HTTP-based approach
- **Cons**: Higher latency, more API calls

**Selected Approach**: Smart log forwarding (Option 3) provides the best balance of implementation complexity and user experience.

## Conclusion

This plan addresses both the immediate CLI stability issues and the long-term logging visibility problem. The phased approach ensures we can deliver quick wins while building towards a robust logging solution that maintains the benefits of the API architecture.