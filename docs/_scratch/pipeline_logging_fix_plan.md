# Pipeline Logging Fix Plan

## Problem Summary
Pipeline logs (`{output_folder}/log/pipeline.log`) are always empty even when pipelines complete successfully.

## Root Cause
The multiprocessing logging setup creates a circular reference in service execution:
1. MainProcess logs go to QueueHandler -> LOG_QUEUE
2. QueueListener reads from LOG_QUEUE -> writes to file 
3. But in single-process service execution, this creates a loop where logs disappear

## Current Code Analysis

```python
# In pipeline_config.py:_configure_logging()
if mp.current_process().name != "MainProcess":
    # Child processes: add QueueHandler
    root.addHandler(QueueHandler(LOG_QUEUE))
    return

# Main process: create listener + real handlers
listener = QueueListener(LOG_QUEUE, file, stream, respect_handler_level=True)
listener.start()

# ❌ PROBLEM: Remove all handlers then add QueueHandler
root.handlers.clear()              # Removes direct file handlers
root.addHandler(QueueHandler(LOG_QUEUE))  # Logs go to queue, never to file
```

## Solution Strategy

### Option 1: Context-Aware Logging (RECOMMENDED)
Detect execution context and use appropriate logging strategy:

```python
def _configure_logging(self):
    log_dir = self.output_path / "log"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "pipeline.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Detect execution context
    is_service_execution = self._is_service_execution()
    
    if is_service_execution:
        # Service execution: use direct file handlers (no multiprocessing)
        self._setup_direct_logging(root, log_file)
    else:
        # CLI execution: use multiprocessing-safe logging
        self._setup_multiprocessing_logging(root, log_file)

def _is_service_execution(self) -> bool:
    """Detect if running in FastAPI service context."""
    import inspect
    stack = inspect.stack()
    # Look for FastAPI/Uvicorn in call stack
    for frame_info in stack:
        module_name = frame_info.frame.f_globals.get('__name__', '')
        if 'fastapi' in module_name or 'uvicorn' in module_name:
            return True
        if 'pipeline_runner' in module_name:
            return True
    return False

def _setup_direct_logging(self, root, log_file):
    """Direct logging for service execution."""
    # Clear existing handlers
    root.handlers.clear()
    
    # Add direct handlers
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    stream_handler = logging.StreamHandler(sys.stdout)
    
    # Set formatters
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

def _setup_multiprocessing_logging(self, root, log_file):
    """Multiprocessing-safe logging for CLI execution."""
    # Current implementation (works for CLI)
    if mp.current_process().name != "MainProcess":
        if not any(isinstance(h, QueueHandler) for h in root.handlers):
            root.addHandler(QueueHandler(LOG_QUEUE))
        return

    # Main process: create listener & real handlers
    stream = logging.StreamHandler(sys.stdout)
    file = logging.FileHandler(log_file, mode="a", encoding="utf-8")

    listener = QueueListener(LOG_QUEUE, file, stream, respect_handler_level=True)
    listener.start()

    root.handlers.clear()
    root.addHandler(QueueHandler(LOG_QUEUE))

    atexit.register(listener.stop)
```

### Option 2: Fix QueueListener (ALTERNATIVE)
Keep current design but fix the queue processing:

```python
# Instead of root.addHandler(QueueHandler(LOG_QUEUE))
# Add both queue handler AND direct file handler for main process
root.addHandler(QueueHandler(LOG_QUEUE))
root.addHandler(logging.FileHandler(log_file, mode="a", encoding="utf-8"))
```

## Implementation Plan

### Task 1: Implement Context Detection (1-2 hours)
- Add `_is_service_execution()` method
- Test detection accuracy in both CLI and service contexts

### Task 2: Implement Direct Logging (1 hour)  
- Add `_setup_direct_logging()` method
- Test file logging works in service context

### Task 3: Refactor Logging Setup (1 hour)
- Modify `_configure_logging()` to use context-aware approach
- Preserve existing multiprocessing behavior for CLI

### Task 4: Testing and Validation (1 hour)
- Test CLI execution still works (multiprocessing logs)
- Test service execution creates populated pipeline.log
- Verify no logging performance issues

## Risk Assessment

**LOW RISK** because:
- Changes are isolated to logging configuration
- Preserves existing CLI behavior
- Only affects service execution logging
- Easy to rollback if issues occur

## Expected Outcome
- ✅ Service execution creates populated `pipeline.log` files
- ✅ CLI execution continues to work unchanged  
- ✅ No performance impact on pipeline execution
- ✅ Logs contain meaningful pipeline execution information

## Files to Modify
- `emuses/pipelines/pipeline_config.py` - Main logging configuration
- `tests/enhanced-cli-typer/test_pipeline_logging.py` - New test suite

## Success Criteria
- Service-executed pipelines create non-empty `pipeline.log` files
- CLI-executed pipelines continue to log correctly
- Log files contain informative pipeline execution messages
- No regression in pipeline performance or reliability