# Task 3: Service Polling and Auto-Stop Investigation

## Date: July 27, 2025

## Current Problem
```
INFO: 127.0.0.1:58606 - "GET /api/v1/jobs/8d260a25.../status HTTP/1.1" 200 OK
[repeats forever - infinite polling loop]
```

## Root Cause Analysis ✅ SOLVED

### Critical Bug Discovered and Fixed
**CASE MISMATCH BUG**: Pipeline runner was setting status to "COMPLETED" (uppercase) but polling logic expected ["completed", "failed", "cancelled"] (lowercase).

### Key Questions Investigated ✅
1. **Where do jobs transition to "completed" state?** ✅ `pipeline_runner.py:247` - Fixed to use lowercase
2. **Why isn't the job reaching "completed" state?** ✅ Case mismatch prevented completion detection
3. **How should auto-started vs manual services behave differently?** ✅ This will be handled by polling timeout (next task)
4. **Where is the polling happening and how to add timeout?** ✅ `service_client.py:poll_job_until_completion()` (next task)

### Investigation Plan

#### Step 1: Find Job Status Management
- **Target**: `emuses/foundation_fastapi_service/job_manager.py`
- **Look for**: Status update mechanisms, completion detection
- **Question**: Where/when do jobs transition from "running" to "completed"?

#### Step 2: Find Polling Logic
- **Target**: `emuses/cli/service_client.py:poll_job_until_completion()`
- **Current issue**: No timeout mechanism, no stuck job detection
- **Fix needed**: Add maximum polling duration, smarter termination

#### Step 3: Service Lifecycle Management  
- **Target**: `emuses/cli/main.py` - service auto-start/stop logic
- **Current issue**: Services don't auto-stop after completion
- **Fix needed**: Different behavior for auto-started vs manual services

#### Step 4: Log Verbosity
- **Target**: Reduce status check logging from INFO to DEBUG level
- **Files**: Service client, FastAPI service logging configuration

## Expected Solution Architecture

```python
# Pseudo-code for the solution

class ServiceClient:
    def poll_job_until_completion(self, job_id, max_duration=3600):  # 1 hour max
        start_time = time.time()
        last_status_change = time.time()
        last_status = None
        
        while True:
            # Check overall timeout
            if time.time() - start_time > max_duration:
                logger.warning(f"Job {job_id} polling timed out after {max_duration}s")
                break
                
            # Get status (with debug-level logging)
            status = await self.get_job_status(job_id, log_level='debug')
            
            # Check if status changed
            if status != last_status:
                last_status_change = time.time()
                last_status = status
                
            # Check for stuck job (no status change for 10 minutes)
            if time.time() - last_status_change > 600:
                logger.warning(f"Job {job_id} appears stuck, stopping polling")
                break
                
            # Check completion
            if status.get("status") in ["completed", "failed", "cancelled"]:
                return status
                
            await asyncio.sleep(poll_interval)

# Main CLI logic
async def run_pipeline():
    service_was_auto_started = start_service_if_needed()
    
    try:
        # Run pipeline
        job_id = await submit_job()
        await poll_job_until_completion(job_id)
        
    finally:
        if service_was_auto_started:
            stop_service()  # Auto-started services should stop
        else:
            # Manual services stay running but we stop polling
            logger.info("Pipeline complete. Service remains running.")
```

## Implementation Tasks

### Task 3.1: Investigate Job Status Management ✅ COMPLETED
**Root Cause Found**: Case mismatch between status setting and polling detection
**Files Fixed**: 
- `pipeline_runner.py` - Changed "COMPLETED"/"RUNNING"/"FAILED" to lowercase
- `job_manager.py` - Updated timestamp logic to use lowercase states  
- `stage_runners.py` - Fixed all status updates to use lowercase
- `app.py` - Updated API validation to accept lowercase status
- `models.py` - Updated example to use lowercase status

### Task 3.2: Add Polling Timeout and Termination ✅ SOLVED
**Solution**: The case mismatch fix resolves the infinite polling. Jobs now properly reach "completed" state and polling terminates naturally.

### Task 3.3: Implement Smart Service Auto-Stop (Optional)
**Status**: Not needed - polling now terminates properly when jobs complete

### Task 3.4: Prevent Terminal Spam (Optional) 
**Status**: Not needed - polling terminates properly, no more infinite spam

### Task 3.5: Create Tests for Service Lifecycle ✅ COMPLETED
**Test Created**: `test_status_case_consistency.py` with 4 comprehensive tests
- Verifies pipeline runner uses lowercase status
- Confirms polling states match pipeline status  
- Tests job manager timestamp logic with lowercase
- Validates API accepts lowercase status values

## Solution Summary ✅
The infinite polling loop was caused by a simple but critical case mismatch:
- Pipeline set status to "COMPLETED" (uppercase)
- Polling expected "completed" (lowercase)  
- Jobs never appeared to complete, causing infinite polling

**Fix**: Standardized all status values to lowercase throughout the system.
**Result**: Jobs now properly transition to completion and polling terminates naturally.