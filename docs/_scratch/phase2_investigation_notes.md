# Phase 2 Critical Issues Investigation

## Date: July 27, 2025
## Session: Post-implementation bug fixes

---

## TASK 1: TEST FAILURES INVESTIGATION

### Current Status
- Test: `test_auto_start.py::TestAutoStartService::test_auto_start_service_lifecycle`
- Error: `assert 404 == 200` - health check endpoint mismatch
- Expected: `/health` 
- Actual: `/api/health`

### Root Cause Analysis
```bash
INFO:     127.0.0.1:43014 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:43028 - "GET /health HTTP/1.1" 404 Not Found
```

**Issue**: Test expects `/health` but service only provides `/api/health`

### Files to Fix
1. `tests/enhanced-cli-typer/test_auto_start.py` - update health check URLs
2. Any other tests expecting `/health` instead of `/api/health`

---

## TASK 2: SQLITE FILE MANAGEMENT INVESTIGATION

### Current Problem
- SQLite files created in `/tmp/emuses_sqlite_XXXXX/`
- Files NOT copied back to output folder after completion
- User loses access to optimization databases
- Temp folders are cleaned up (deleted) without preservation

### Current Cleanup Function Analysis
```python
def cleanup_temp_sqlite_location(temp_location: Path, output_folder: Path) -> None:
    # Lists files for debugging
    temp_files = list(temp_location.glob("*"))
    # But then just DELETES everything:
    shutil.rmtree(temp_location, ignore_errors=True)  # ❌ NO COPYING
```

### Where SQLite Files Are Created
1. `emuses/tools/UMAP_utils.py` - `setup_optuna_storage_safe("umap_nested_optimization", output_folder)`
2. `emuses/tools/optuna_cv.py` - `setup_optuna_storage_safe(f"optuna_{target_tag}", output_folder)`
3. `emuses/tools/ae_optuna.py` - `setup_optuna_storage_safe("ae_pretraining", output_folder)`

### Missing Integration Points
- Cleanup function exists but is NEVER called from the main pipeline
- No mechanism to copy SQLite files back to output folder
- No user notification about SQLite file locations

---

## TASK 3: SERVICE POLLING INVESTIGATION

### Current Problem
```
INFO: 127.0.0.1:58606 - "GET /api/v1/jobs/8d260a25.../status HTTP/1.1" 200 OK
[repeats forever]
```

### Polling Logic Analysis
- `poll_job_until_completion()` waits for completion_states: `["completed", "failed", "cancelled"]`
- User's job likely stays in "running" state even after finishing
- No timeout mechanism to break infinite loops
- Service doesn't auto-stop after job completion

### Key Questions to Investigate
1. Where do jobs transition to "completed" state?
2. Why isn't the job reaching "completed" state?
3. How should auto-started services vs manual services behave differently?
4. How to prevent terminal spam while maintaining useful logging?

### Files to Investigate
1. `emuses/foundation_fastapi_service/job_manager.py` - job status updates
2. `emuses/cli/service_client.py:poll_job_until_completion()` - polling logic
3. `emuses/cli/main.py` - service lifecycle management

---

## IMPLEMENTATION PLAN

### Phase 1: Test Fixes (2-3 hours)
1. Fix health endpoint URLs in tests
2. Increase test timeouts for service startup
3. Validate all tests pass

### Phase 2: SQLite Management (3-4 hours)
1. Enhance cleanup function to copy files before deletion
2. Find pipeline completion points and integrate cleanup calls
3. Add user notifications about SQLite file locations
4. Create tests for file copying behavior

### Phase 3: Service Lifecycle (4-5 hours)
1. Investigate job status transition mechanism
2. Add polling timeout and termination logic
3. Implement smart auto-stop (different for auto-started vs manual services)
4. Reduce log verbosity during normal operation
5. Add tests for service lifecycle behavior

---

## NEXT STEPS
Starting with TASK 1: Fix test failures