# CLI Integration Implementation Prompt

**Context**: Enhanced CLI Typer project needs core integration to make CLI commands functional

## 🎯 GOAL
Transform placeholder CLI commands into functional commands that execute pipelines via FastAPI service calls, maintaining 100% backward compatibility with legacy CLI while adding modern features.

## 📍 CURRENT STATE (Critical Assessment)

### ✅ What EXISTS and WORKS:
- **Service client**: `emuses/cli/service_client.py` - ServiceHTTPClient with circuit breaker, retry logic
- **FastAPI service**: `emuses/foundation_fastapi_service/app.py` - endpoints `/api/v1/jobs/pipeline/full`, `/api/v1/jobs/pipeline/stage/{stage_name}`
- **Rich features**: `emuses/cli/rich_features.py` - ProgressTracker, StatusRenderer, TableFormatter classes
- **Interactive mode**: `emuses/cli/interactive_mode.py` - InteractiveWorkflowManager, ParameterValidator classes
- **Shell completion**: `emuses/cli/shell_completion.py` - ShellCompletionManager, CompletionScriptGenerator classes
- **Legacy CLI**: `emuses/scripts/main.py` - functional reference implementation

### ❌ What's BROKEN/MISSING:
- **CLI commands are placeholders**: All commands in `emuses/cli/main.py` print "Not implemented yet" and exit(1)
- **No service integration**: ServiceHTTPClient exists but isn't used by CLI commands
- **No feature integration**: Rich features exist but aren't connected to CLI commands
- **No pipeline execution**: CLI doesn't actually run pipelines

## 🏗️ ARCHITECTURE OVERVIEW

```
Legacy Flow:     CLI → EMUSESPipeline.run() → Results
Target Flow:     CLI → ServiceHTTPClient → FastAPI Service → EMUSESPipeline.run() → Results
```

### Key Files:
- **`emuses/cli/main.py`**: CLI commands (NEEDS IMPLEMENTATION)
- **`emuses/cli/service_client.py`**: HTTP client (COMPLETE, needs integration)
- **`emuses/foundation_fastapi_service/app.py`**: Service endpoints (COMPLETE)
- **`emuses/scripts/main.py`**: Legacy reference (FUNCTIONAL)

## 🔧 IMPLEMENTATION TASKS (Priority Order)

### PHASE 1: Core Command Integration (CRITICAL)

#### Task 1.1: Implement `full` command functionality
**File**: `emuses/cli/main.py`

**Current broken code**:
```python
def full(...):
    typer.echo("EMUSES Full Pipeline - Not implemented yet")
    raise typer.Exit(code=1)
```

**Required implementation**:
1. **Import service client**:
   ```python
   from .service_client import ServiceHTTPClient
   from .rich_features import ProgressTracker, StatusRenderer
   ```

2. **Create service client instance**:
   ```python
   service_client = ServiceHTTPClient(base_url="http://localhost:8000")
   ```

3. **Convert Typer arguments to service API format**:
   ```python
   # Convert Path objects to strings
   pipeline_config = {
       "output_folder": str(output_folder),
       "input_dataset": str(input_dataset),
       "scores": str(scores) if scores else None,
       # ... all other arguments
   }
   ```

4. **Submit job to service**:
   ```python
   job_response = await service_client.submit_full_pipeline_job(pipeline_config)
   job_id = job_response["job_id"]
   ```

5. **Poll for completion with progress display**:
   ```python
   progress_tracker = ProgressTracker()
   while True:
       status = await service_client.get_job_status(job_id)
       if status["status"] == "COMPLETED":
           break
       elif status["status"] == "FAILED":
           raise typer.Exit(code=1)
       progress_tracker.update(status.get("progress", 0))
       await asyncio.sleep(1)
   ```

#### Task 1.2: Handle async execution in sync CLI
**Problem**: Typer commands are sync, service client is async

**Solution**: Use asyncio.run() wrapper:
```python
def full(...):
    asyncio.run(_full_async(...))

async def _full_async(...):
    # Actual implementation here
```

#### Task 1.3: Add service availability fallback
**Requirement**: CLI should work even if service is down

**Implementation**:
```python
try:
    # Try service first
    result = await service_client.submit_full_pipeline_job(config)
except ServiceClientError:
    # Fallback to direct pipeline execution
    typer.echo("Service unavailable, running locally...")
    from emuses.pipelines.emuses_pipeline import EMUSESPipeline
    # Convert back to legacy format and run directly
```

#### Task 1.4: Implement remaining commands
**Commands to implement**: `umap`, `clustering`, `heatmap`, `prediction`
**Pattern**: Same as full command but call respective service endpoints

### PHASE 2: Feature Integration (HIGH PRIORITY)

#### Task 2.1: Integrate Rich features
**File**: `emuses/cli/main.py`

**Add to command implementations**:
```python
from .rich_features import ProgressTracker, StatusRenderer, TableFormatter

# In command functions:
status_renderer = StatusRenderer()
status_renderer.info("Starting pipeline execution...")

progress_tracker = ProgressTracker()
progress_tracker.start("Processing data...")

# After completion:
table_formatter = TableFormatter()
results_table = table_formatter.format_results(results)
typer.echo(results_table)
```

#### Task 2.2: Add interactive mode
**Add --interactive flag to all commands**:
```python
@app.command()
def full(
    # ... existing args
    interactive: bool = typer.Option(False, "--interactive", help="Run in interactive mode")
):
    if interactive:
        from .interactive_mode import InteractiveWorkflowManager
        workflow_manager = InteractiveWorkflowManager()
        workflow_id = workflow_manager.start_workflow("data_processing")
        # Use workflow manager to collect parameters
```

#### Task 2.3: Add shell completion installation
**Add new command**:
```python
@app.command()
def install_completion(
    shell: str = typer.Argument(help="Shell type (bash, zsh, powershell)")
):
    from .shell_completion import ShellCompletionManager
    completion_manager = ShellCompletionManager()
    if completion_manager.install_completion(shell):
        typer.echo(f"Completion installed for {shell}")
    else:
        typer.echo(f"Failed to install completion for {shell}")
        raise typer.Exit(code=1)
```

### PHASE 3: Error Handling & Validation (MEDIUM PRIORITY)

#### Task 3.1: Add comprehensive error handling
**Required patterns**:
```python
try:
    result = await service_client.submit_job(config)
except ServiceClientError as e:
    typer.echo(f"Service error: {e}", err=True)
    raise typer.Exit(code=1)
except ValidationError as e:
    typer.echo(f"Validation error: {e}", err=True)
    raise typer.Exit(code=1)
except Exception as e:
    typer.echo(f"Unexpected error: {e}", err=True)
    raise typer.Exit(code=1)
```

#### Task 3.2: Add argument validation
**Use existing security functions**:
```python
from .security import validate_path, sanitize_input

# In command functions:
validated_output = validate_path(str(output_folder))
validated_input = validate_path(str(input_dataset))
```

### PHASE 4: Testing Integration (LOW PRIORITY)

#### Task 4.1: Update CLI tests
**File**: `tests/enhanced-cli-typer/test_cli_core.py`

**Add integration tests**:
```python
@pytest.mark.asyncio
async def test_full_command_service_integration():
    # Mock service client
    with patch('emuses.cli.main.ServiceHTTPClient') as mock_client:
        mock_client.return_value.submit_full_pipeline_job.return_value = {"job_id": "test-123"}
        mock_client.return_value.get_job_status.return_value = {"status": "COMPLETED"}
        
        # Test command execution
        result = runner.invoke(app, ['full', 'output_dir', 'input_file.csv'])
        assert result.exit_code == 0
```

## 🚨 CRITICAL IMPLEMENTATION NOTES

### 1. Service Client Usage Pattern
```python
# Always use this pattern:
async def _command_async(...):
    service_client = ServiceHTTPClient(base_url="http://localhost:8000")
    
    # Check service health first
    try:
        await service_client.health_check()
    except ServiceClientError:
        # Fallback to local execution
        return await _execute_locally(...)
    
    # Submit job
    job_response = await service_client.submit_job(config)
    job_id = job_response["job_id"]
    
    # Poll with progress
    while True:
        status = await service_client.get_job_status(job_id)
        # Handle status...
```

### 2. Argument Conversion Pattern
```python
# Convert Typer arguments to service API format
def convert_typer_args_to_service_config(**kwargs):
    config = {}
    for key, value in kwargs.items():
        if isinstance(value, Path):
            config[key] = str(value)
        elif isinstance(value, list) and value:
            config[key] = [str(item) for item in value]
        elif value is not None:
            config[key] = value
    return config
```

### 3. Error Handling Pattern
```python
# Always include this error handling
try:
    result = await service_operation()
except ServiceClientError as e:
    typer.echo(f"Service error: {e}", err=True)
    raise typer.Exit(code=1)
except Exception as e:
    typer.echo(f"Unexpected error: {e}", err=True)
    raise typer.Exit(code=1)
```

## ✅ SUCCESS CRITERIA

### Functional Requirements:
1. **All CLI commands execute successfully** (no more "Not implemented yet")
2. **Service integration works** (commands call FastAPI service)
3. **Fallback mode works** (commands work without service)
4. **Progress tracking works** (users see pipeline progress)
5. **Error handling works** (meaningful error messages)

### Backward Compatibility:
1. **All legacy arguments work** (exact same CLI interface)
2. **Same output format** (compatible with existing scripts)
3. **Same exit codes** (compatible with existing automation)

### Testing Requirements:
1. **Unit tests pass** (existing tests continue to work)
2. **Integration tests added** (test service interaction)
3. **End-to-end tests added** (test full pipeline execution)

## 🔍 VERIFICATION COMMANDS

After implementation, verify success with:
```bash
# Test basic functionality
python -m emuses.cli.main full output_test input_test.csv

# Test with service
python -m emuses.cli.main full output_test input_test.csv --verbose

# Test interactive mode
python -m emuses.cli.main full --interactive

# Test completion installation
python -m emuses.cli.main install-completion bash

# Run tests
pytest tests/enhanced-cli-typer/test_cli_core.py -v
```

## 📋 IMPLEMENTATION CHECKLIST

Use this checklist to track progress:

### Phase 1 - Core Integration:
- [ ] Import service client and rich features in main.py
- [ ] Implement async wrapper pattern for all commands
- [ ] Implement full command with service integration
- [ ] Add service availability fallback
- [ ] Implement remaining commands (umap, clustering, heatmap, prediction)
- [ ] Add argument conversion logic
- [ ] Test all commands execute without errors

### Phase 2 - Feature Integration:
- [ ] Add progress tracking to all commands
- [ ] Add status rendering to all commands
- [ ] Add result table formatting
- [ ] Add --interactive flag to all commands
- [ ] Implement interactive workflow integration
- [ ] Add shell completion installation command

### Phase 3 - Polish:
- [ ] Add comprehensive error handling
- [ ] Add argument validation
- [ ] Add logging and debugging output
- [ ] Update help text and documentation

### Phase 4 - Testing:
- [ ] Update existing tests to pass
- [ ] Add service integration tests
- [ ] Add end-to-end pipeline tests
- [ ] Add error handling tests

## 🚫 COMMON PITFALLS TO AVOID

1. **Don't modify service client** - it's complete and tested
2. **Don't modify FastAPI service** - it's complete and tested
3. **Don't break existing tests** - only add new functionality
4. **Don't change command signatures** - maintain backward compatibility
5. **Don't remove TODO comments** - replace with actual implementation
6. **Don't forget async/await** - service client is async
7. **Don't skip error handling** - users need meaningful errors

## 🎯 PRIORITY FOCUS

**Start with Phase 1 Task 1.1** - implement just the `full` command first. Get it working completely before moving to other commands. This establishes the pattern and proves the integration works.

**Success metric**: User can run `python -m emuses.cli.main full output_dir input.csv` and see actual pipeline execution with progress tracking.

---

This implementation will transform the CLI from a facade into a fully functional modern CLI that achieves the project's goals.