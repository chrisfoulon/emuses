# Foundation FastAPI Service - Plan Split Notice

## Plan Complexity Evaluation Results

**Original Plan Statistics:**
- **Task Count**: 8 tasks (exceeds 6-task threshold ✓)
- **Sub-task Count**: 32 sub-tasks (exceeds 25-30 threshold ✓)
- **Domain Mix**: Models, infrastructure, security, performance across different concerns ✓
- **Dependency Analysis**: Clear architectural boundaries with foundation-first flow ✓

**Splitting Decision**: Plan split into 4 manageable sub-plans with dependency ordering.

## Sub-Plan Structure

The original plan has been split into focused sub-plans:

### 📁 Sub-Plan 0a: Foundation (Tasks 1-2)
**File**: `plan_0a_foundation.md`  
**Context**: `context_0a_foundation.md`  
**Focus**: Core models and job management infrastructure  
**Size**: 2 tasks, 8 sub-tasks ✅

### 📁 Sub-Plan 0b: Pipeline Integration (Tasks 3-4)  
**File**: `plan_0b_pipeline.md`  
**Context**: `context_0b_pipeline.md`  
**Focus**: EMUSES pipeline execution and stage wrappers  
**Size**: 2 tasks, 8 sub-tasks ✅

### 📁 Sub-Plan 0c: Interface Layer (Task 5)
**File**: `plan_0c_interface.md`  
**Context**: `context_0c_interface.md`  
**Focus**: FastAPI endpoints and HTTP handling  
**Size**: 1 task, 4 sub-tasks ✅

### 📁 Sub-Plan 0d: Security & Performance (Tasks 6-8)
**File**: `plan_0d_security.md`  
**Context**: `context_0d_security.md`  
**Focus**: Comprehensive testing with complete system visibility  
**Size**: 3 tasks, 12 sub-tasks ✅

### 📁 Sub-Plan 0e: Upload Endpoints (Task 9)
**File**: `plan_0e_upload.md`  
**Context**: Extends `context_0c_interface.md`  
**Focus**: File upload endpoints for real-world API usage  
**Size**: 1 task, 5 sub-tasks ⚠️ **REQUIRED FOR SESSION 1 COMPLETION**

## Implementation Instructions

**To begin implementation**, use the LAD 04 prompt with SUB_PLAN_ID parameter:

```
Begin the next unchecked task now.
SUB_PLAN_ID: 0e
```

**Execution Order**: 0a → 0b → 0c → 0d → **0e** (dependency-ordered)

**Context Evolution**: Each sub-plan updates context files for subsequent sub-plans.

## Archive Reference

- **Complete Plan**: `plan_master.md` (original plan with all 8 tasks)
- **Split Decision**: `split_decision.md` (detailed rationale and dependencies)

<details><summary>Review-Resolution Log</summary>

### Issues Addressed

**Critical Dependency Inversion (Copilot)**
✅ RESOLVED: Reordered tasks - Models (Task 1) now comes first, followed by Job Manager (Task 2), establishing data contracts before infrastructure

**Missing File Validation Tests (Copilot)**
✅ RESOLVED: Added Task 6 (Security Validation) with comprehensive input validation, including file size limits, malformed JSON, and boundary conditions

**Concurrency Race Conditions (Copilot/ChatGPT)**
✅ RESOLVED: Added Task 7 (Concurrency Performance) for race condition detection and added concurrency locks to Job Manager (Task 2.3)

**Memory Exhaustion Risk (Copilot)**
✅ RESOLVED: Added resource limits to ProcessPoolExecutor (Task 4.1) and memory spike detection (Task 7.4)

**Security & Input Validation Missing (ChatGPT)**
✅ RESOLVED: New Task 6 covers path traversal protection, input sanitization, and safe deserialization

**Negative & Boundary Tests Absent (ChatGPT)**
✅ RESOLVED: Task 6.2 and 6.4 now explicitly cover invalid UUIDs, malformed requests, and 4xx/5xx error responses

**Performance & Resource Cleanup (ChatGPT)**
✅ RESOLVED: Task 7.2 added for resource cleanup verification, Task 2.4 includes cleanup policies

**Test Isolation Gaps (Copilot)**
✅ RESOLVED: Resource cleanup verification in Task 7.2 addresses test directory cleanup

**Progress Callback Bottleneck (Copilot)**
✅ RESOLVED: Added rate limiting to progress callbacks (Task 4.3)

**Pydantic Deserialization Security (Copilot/ChatGPT)**
✅ RESOLVED: Task 6.3 covers deserialization limits and safe error handling

**Context Deep Copy Performance (Copilot)**
✅ RESOLVED: Task 4.2 includes deep copy validation, Task 7.4 monitors memory spikes

**Performance Budget Gaps (Copilot)**
✅ ADDRESSED: Maintained existing metrics but added load testing in Task 7.3

**Resource Accessibility (Copilot)**
✅ NOTED: Referenced files will be verified during Task 3 implementation

**Maintainability Metrics (ChatGPT)**
✅ ADDRESSED: Existing flake8 and mypy requirements cover code quality

</details>

<details><summary>📝 Extended Details (for ChatGPT / humans)</summary>

### Rationale
<reasoning>
The Foundation FastAPI Service follows a test-driven approach to wrap existing EMUSES pipeline stages as REST endpoints while maintaining 100% backward compatibility. The plan prioritizes core job management and background processing infrastructure first, then builds API models and endpoint layers, ensuring each component is thoroughly tested before integration. The approach preserves the existing context dictionary pattern and stage execution logic, minimizing risk while enabling web-based access to the ML pipeline.
</reasoning>

### Resources
- Files to open: 
  - `emuses/pipelines/emuses_pipeline.py` (main orchestrator)
  - `emuses/pipelines/umap_stage.py`, `emuses/pipelines/heatmap_stage.py`, `emuses/pipelines/prediction_stage.py` (individual stages)
  - `emuses/pipelines/pipeline_config.py` (configuration system)
  - `emuses/tools/model_io.py` (artifact management)
- External APIs / libs: 
  - FastAPI, Pydantic, uvicorn (web framework)
  - asyncio, ProcessPoolExecutor (background processing)
  - pytest, httpx (testing)

### Risks & Mitigations
- 🚨 Breaking backward compatibility – Extensive compatibility tests, zero changes to existing stage classes
- 🚨 Context dictionary corruption – Deep copy validation, schema enforcement with Pydantic
- 🚨 Background job memory leaks – Process isolation with ProcessPoolExecutor, job cleanup policies
- 🚨 Concurrent job conflicts – UUID-based job IDs, job-scoped directory isolation
- 🚨 Progress tracking overhead – Lightweight callback system, configurable update intervals

### Acceptance-Checks
| Test file                                              | Assertion                                    | Metric                |
|--------------------------------------------------------|----------------------------------------------|-----------------------|
| tests/foundation-fastapi-service/test_api_models.py   | All request/response models validate        | 100% coverage         |
| tests/foundation-fastapi-service/test_job_manager.py  | Job lifecycle transitions correctly         | flake8 < 5, concurrency safe |
| tests/foundation-fastapi-service/test_stage_runners.py | Individual stages produce expected artifacts| mypy strict mode      |
| tests/foundation-fastapi-service/test_pipeline_runner.py | Background execution preserves context    | runtime ≤ 30s (unit), ≤ 120s (integration) |
| tests/foundation-fastapi-service/test_api_endpoints.py | All endpoints return proper HTTP codes     | response time ≤ 500ms |
| tests/foundation-fastapi-service/test_security_validation.py | Security tests pass, no vulnerabilities | OWASP compliance |
| tests/foundation-fastapi-service/test_concurrency_performance.py | Load tests within limits | 10+ concurrent jobs |
| tests/foundation-fastapi-service/test_compatibility.py | API results identical to CLI results       | numerical precision 1e-10 |

</details>
