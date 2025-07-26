# EMUSES Technical Context & Implementation Details
**Companion to**: `EMUSES_COMPREHENSIVE_LAD_PLAN.md`  
**Purpose**: Detailed technical context for implementation teams  
**Audience**: Fresh Claude sessions beginning LAD implementation

---

## 🔧 **TECHNICAL IMPLEMENTATION DETAILS**

### **Current Service Architecture**:
```python
User Command (CLI)
    ↓
ServiceManager.ensure_service_running()
    ↓
Auto-start FastAPI service (background subprocess)
    ↓
ServiceClient.submit_job() → HTTP POST to service
    ↓
PipelineRunner.run() → Creates new multiprocessing.Process
    ↓
EMUSESPipeline.run() → Executes stages sequentially
    ↓
Individual Stages (UMAP, Heatmap, Prediction)
```

### **Graceful Shutdown Integration Points**:
```python
# 5 KeyboardInterrupt handlers in emuses/cli/main.py
Lines 540-542: full command
Lines 580-582: umap command  
Lines 620-622: clustering command
Lines 660-662: heatmap command
Lines 700-702: prediction command

# Current pattern (TO BE ENHANCED):
except KeyboardInterrupt:
    typer.echo("\nOperation cancelled by user", err=True)
    raise typer.Exit(code=130)
```

### **Service Communication APIs** (EXISTING):
```python
# emuses/cli/service_client.py
await service_client.get_job_status(job_id)     # Get current progress
await service_client.cancel_job(job_id)         # Cancel specific job
await service_client.check_service_health()     # Health check

# emuses/cli/service_manager.py  
service_manager.stop_service()                  # Graceful service shutdown
service_manager.find_service_process()          # Find running service PID
```

---

## 🐛 **DETAILED BUG ANALYSIS**

### **1. Rerun Functionality Bug**:
**Location**: `emuses/cli/main.py:247`
```python
# CURRENT BROKEN CODE:
command_parts = shlex.split(command)
# This creates: ['/home/tolhsadum/miniforge3/envs/emuses/bin/emuses', 'full', ...]
# But should be: ['full', ...]

result = subprocess.run([sys.executable, '-m', 'emuses.cli'] + command_parts, check=False)
# Results in: python -m emuses.cli /home/tolhsadum/miniforge3/envs/emuses/bin/emuses full ...
# Should be:   python -m emuses.cli full ...
```

**Fix Strategy**:
```python
# PROPOSED FIX:
command_parts = shlex.split(command)
# Skip the first element if it's the full path to emuses executable
if command_parts and ('emuses' in command_parts[0] or command_parts[0].startswith('/')):
    command_parts = command_parts[1:]  # Remove executable path, keep only arguments

result = subprocess.run([sys.executable, '-m', 'emuses.cli'] + command_parts, check=False)
```

### **2. Pipeline Logging Issue**:
**Location**: `emuses/pipelines/pipeline_config.py:174-210`
**Root Cause**: Conflicting logging setups
```python
# ISSUE: Two different logging configurations
# 1. basicConfig() with FileHandler (lines 141-148)
# 2. _configure_logging() with QueueHandler/QueueListener (lines 174-210)

# The _configure_logging() method:
root.handlers.clear()  # Line 196 - CLEARS the FileHandler from basicConfig!
root.addHandler(QueueHandler(LOG_QUEUE))  # Only QueueHandler remains

# If QueueListener fails to start or write, logs disappear
```

**Investigation Strategy**:
1. Check if QueueListener is properly started in main process
2. Verify log directory permissions  
3. Test if multiprocessing context affects QueueHandler
4. Consider simplified logging for single-process execution

### **3. Service Auto-Stop Investigation**:
**Key Areas to Check**:
```python
# emuses/cli/main.py - Service cleanup after job completion
# Does _execute_via_unified_service() properly stop service?

# emuses/cli/service_manager.py:75-78 - atexit handler
atexit.register(self._cleanup_on_exit)
# Is this reliable for all termination scenarios?

# Process lifecycle verification needed
```

---

## 🎯 **PARALLELISM ARCHITECTURE DEEP DIVE**

### **Current Problematic Flow**:
```
Main Process (CLI)
├── Subprocess (FastAPI Service) 
│   └── Multiprocess (PipelineRunner)
│       └── Joblib Parallel (n_jobs=-1) ← CONFLICT HERE
│           └── Multiple worker processes ← BLOCKED by Loky backend
```

### **Phase 1 Status (COMPLETED)**:
```python
# ✅ FIXED: Configuration propagation
args.n_jobs = int(config_dict.get("n_jobs", -1))  # pipeline_runner.py

# ✅ FIXED: HeatmapStage configuration  
n_jobs = getattr(self.config, "n_jobs", -1)       # heatmap_stage.py
results = Parallel(n_jobs=n_jobs, backend="loky")

# ✅ FIXED: Cross-validation parameter passing
def nested_optuna_cv(X, y, optim_dict, n_jobs=-1, ...):  # optuna_cv.py

# ✅ FIXED: Model utilities integration
def build_estimator(model_type, params, n_jobs=-1):      # models_utils.py
```

### **Phase 2 Implementation Strategy** (NOT IMPLEMENTED):
```python
# NEW FILE: emuses/tools/parallelism_utils.py
def get_safe_parallel_backend():
    """Return 'threading' for subprocess, 'loky' for main process"""
    if mp.current_process().name != "MainProcess":
        return "threading"
    return "loky"

def create_safe_parallel(n_jobs=-1, **kwargs):
    """Create Parallel with context-appropriate backend"""
    safe_backend = get_safe_parallel_backend()
    if mp.current_process().name != "MainProcess" and n_jobs != 1:
        safe_n_jobs = 1  # Force single-threaded in subprocess
    else:
        safe_n_jobs = n_jobs
    return Parallel(n_jobs=safe_n_jobs, backend=safe_backend, **kwargs)
```

---

## 📋 **COMPREHENSIVE TEST SCENARIOS**

### **Graceful Shutdown Testing**:
```bash
# Test 1: Service startup interruption
emuses full /tmp/test data.csv --optuna_trials 100
# Press Ctrl+C during "Starting service..." phase
# Expected: Immediate response, clean termination

# Test 2: Job submission interruption  
emuses full /tmp/test data.csv --optuna_trials 100
# Press Ctrl+C during "Submitting job..." phase
# Expected: Immediate response, service cleanup

# Test 3: Optimization interruption
emuses full /tmp/test data.csv --optuna_trials 100
# Press Ctrl+C during "Trial 15/100" phase
# Expected: Status display, confirmation dialog, resume capability

# Test 4: Multiple interruptions
# Press Ctrl+C, choose 'N', then press Ctrl+C again
# Expected: Each interruption handled correctly

# Test 5: Service communication failure during interruption
# Kill service process while interruption handler runs
# Expected: Graceful degradation, allow termination anyway
```

### **Service Reliability Testing**:
```bash
# Test rerun functionality
emuses full "/path with spaces/output" data.csv --scores "scores file.csv"
emuses rerun "/path with spaces/output"  # Should work without errors

# Test logging functionality  
emuses full /tmp/logging_test data.csv --optuna_trials 5
ls -la /tmp/logging_test/log/pipeline.log  # Should exist and contain logs
grep "Trial" /tmp/logging_test/log/pipeline.log  # Should show trial progress

# Test service auto-stop
emuses full /tmp/auto_stop_test data.csv --optuna_trials 3
# Wait for completion
ps aux | grep "emuses.*uvicorn"  # Should show no remaining service processes
```

### **Performance Testing**:
```bash
# Baseline single-threaded
time emuses full /tmp/perf_1 data.csv --n_jobs 1 --optuna_trials 10

# Multi-threaded (should be faster after Phase 2)
time emuses full /tmp/perf_4 data.csv --n_jobs 4 --optuna_trials 10

# Check for parallelism warnings
emuses full /tmp/warn_test data.csv --n_jobs 4 2>&1 | grep "setting n_jobs=1"
# Should be empty after Phase 2 implementation
```

---

## 🏗️ **DEVELOPMENT ENVIRONMENT SETUP**

### **Required Dependencies**:
```python
# Core dependencies (already in environment)
fastapi>=0.68.0
uvicorn>=0.15.0  
typer>=0.4.0
psutil>=5.8.0
joblib>=1.0.0
sklearn>=1.0.0

# Testing dependencies
pytest>=6.0.0
pytest-asyncio>=0.15.0
httpx>=0.24.0  # For FastAPI testing
```

### **Development Commands**:
```bash
# Start development environment
cd /mnt/c/Users/Tolhsadum/PycharmProjects/emuses
conda activate emuses  # Or appropriate environment

# Run existing tests
python -m pytest tests/enhanced-cli-typer/test_timeout_configuration.py -v

# Manual service testing
python -m emuses.foundation_fastapi_service.app  # Direct service start
curl http://localhost:8000/health  # Health check

# CLI testing with logging
python -m emuses.cli full /tmp/test_output /path/to/data.csv --n_jobs 4 -v
```

---

## 🔍 **DEBUGGING STRATEGIES**

### **Service Communication Debugging**:
```python
# Enable debug logging in service_client.py
import logging
logging.getLogger("emuses.cli.service_client").setLevel(logging.DEBUG)

# Check service health manually
async def debug_service():
    client = ServiceHTTPClient("http://localhost:8000")
    health = await client.check_service_health()
    print(f"Service healthy: {health}")
```

### **Multiprocessing Debugging**:
```python
# Add process context logging
import multiprocessing as mp
print(f"Current process: {mp.current_process().name}")
print(f"Process PID: {os.getpid()}")

# Check Joblib backend selection
from joblib import parallel_backend
with parallel_backend('loky') as (ba, n_jobs):
    print(f"Backend: {ba}, n_jobs: {n_jobs}")
```

### **Logging Debugging**:
```python
# Check all active handlers
import logging
root = logging.getLogger()
print(f"Root handlers: {root.handlers}")
for handler in root.handlers:
    print(f"Handler: {type(handler)}, Level: {handler.level}")

# Test QueueListener status
from emuses.pipelines.pipeline_config import LOG_QUEUE
print(f"Queue size: {LOG_QUEUE.qsize()}")
```

---

## 🔗 **EXTERNAL REFERENCES**

### **FastAPI Best Practices**:
- [FastAPI Users](https://fastapi-users.github.io/) - Multi-user authentication
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) - Job management
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/) - Service testing

### **Multiprocessing Patterns**:
- [Joblib Parallel Backends](https://joblib.readthedocs.io/en/latest/parallel.html#parallel-reference-documentation)
- [Python Multiprocessing](https://docs.python.org/3/library/multiprocessing.html) - Process management
- [Loky Backend](https://github.com/joblib/loky) - Joblib backend for multiprocessing

### **Signal Handling**:
- [Python Signal Handling](https://docs.python.org/3/library/signal.html) - KeyboardInterrupt handling
- [Typer Advanced](https://typer.tiangolo.com/tutorial/terminating/) - CLI signal handling

---

**This technical context provides implementation teams with detailed analysis and specific technical solutions for all identified issues in EMUSES development.**