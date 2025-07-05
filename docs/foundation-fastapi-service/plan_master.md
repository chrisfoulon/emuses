# Foundation FastAPI Service - TDD Plan (Complete Master Plan)

## Top-Level Checklist

- [ ] Task 1 ║ tests/foundation-fastapi-service/test_api_models.py ║ Pydantic request/response models with validation and serialization ║ S
  - [ ] 1.1 Pipeline configuration models inheriting from PipelineConfig
  - [ ] 1.2 Job submission, status, and artifact response models
  - [ ] 1.3 Error response models with standardized error codes
  - [ ] 1.4 File upload and multipart form data models with size limits

- [ ] Task 2 ║ tests/foundation-fastapi-service/test_job_manager.py ║ Job lifecycle management with UUID generation, status tracking, and directory organization ║ M
  - [ ] 2.1 Secure UUID job ID generation and validation with entropy checks
  - [ ] 2.2 Job directory structure creation with path traversal protection
  - [ ] 2.3 Job status persistence and updates with concurrency locks
  - [ ] 2.4 Job metadata tracking with sanitization and cleanup policies

- [ ] Task 3 ║ tests/foundation-fastapi-service/test_stage_runners.py ║ Individual stage execution with context loading and artifact organization ║ M
  - [ ] 3.1 UMAPStage wrapper with parameter validation and resource limits
  - [ ] 3.2 HeatmapStage wrapper with optimization progress tracking
  - [ ] 3.3 PredictionStage wrapper with test evaluation mode
  - [ ] 3.4 Stage-specific artifact organization with secure file handling

- [x] Task 4 ║ tests/foundation-fastapi-service/test_pipeline_runner.py ║ Background pipeline execution with context preservation and progress callbacks ║ L
  - [x] 4.1 EMUSESPipeline async wrapper with ProcessPoolExecutor and resource limits - **COMPLETED**: Real EMUSES pipeline execution with context setup
  - [x] 4.2 Context dictionary preservation with deep copy validation - **COMPLETED**: Context setup and validation implemented
  - [x] 4.3 Progress callback integration with rate limiting - **COMPLETED**: Progress tracking with job status updates
  - [x] 4.4 Error handling and exception capture with job status updates - **COMPLETED**: Comprehensive error handling and resource management
  - [ ] **4.5 EMUSESPipeline Integration Refactor** - **HIGH PRIORITY**: Refactor PipelineRunner to use EMUSESPipeline internally for data preprocessing, context setup, and stage orchestration identical to CLI

- [ ] Task 5 ║ tests/foundation-fastapi-service/test_api_endpoints.py ║ FastAPI endpoint integration with request/response handling ║ L
  - [ ] 5.1 Pipeline execution endpoints with input validation
  - [ ] 5.2 Stage-specific endpoints with parameter sanitization
  - [ ] 5.3 Job status and progress endpoints with rate limiting
  - [ ] 5.4 Artifact management endpoints with secure download paths

- [ ] Task 6 ║ tests/foundation-fastapi-service/test_security_validation.py ║ Security testing and input validation ║ M
  - [ ] 6.1 Path traversal protection for file uploads and job directories
  - [ ] 6.2 Input sanitization for malformed JSON, oversized files, invalid UUIDs
  - [ ] 6.3 Pydantic deserialization limits and safe error handling
  - [ ] 6.4 Negative tests for 4xx/5xx responses and boundary conditions

- [ ] Task 7 ║ tests/foundation-fastapi-service/test_concurrency_performance.py ║ Concurrency and performance testing ║ M
  - [ ] 7.1 Multiple simultaneous job submissions with race condition detection
  - [ ] 7.2 Resource cleanup verification (directories, processes, memory)
  - [ ] 7.3 Load testing with performance budgets and timeouts
  - [ ] 7.4 Memory spike detection during context serialization
  - [x] 7.5 Cross-platform file locking verification (Windows/Linux compatibility) - **COMPLETED**: Platform-specific locking implemented with Windows msvcrt fallback

- [ ] Task 8 ║ tests/foundation-fastapi-service/test_compatibility.py ║ Backward compatibility verification with existing CLI and Python imports ║ M
  - [ ] 8.1 CLI interface unchanged (python main.py full continues working)
  - [ ] 8.2 Python imports unchanged (from emuses.pipelines import EMUSESPipeline)
  - [ ] 8.3 Context pattern preservation (exact dictionary passing between stages)
  - [x] 8.4 Computational result equivalence (API vs CLI produces identical outputs) - **COMPLETED**: CLI vs API comparison test validates identical behavior and artifacts
  - [ ] 8.5 API/CLI unification via EMUSESPipeline - **IDENTIFIED**: API should use EMUSESPipeline class for consistent context setup and data handling like CLI

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

## Real-World Testing Improvements (Post-HCP Dataset Analysis)

**Cross-Platform Compatibility Issues**
✅ RESOLVED: Task 7.5 - Windows file locking compatibility implemented
- **Issue**: `fcntl` module not available on Windows causing job manager failures
- **Solution**: Platform-specific locking with `msvcrt` on Windows, graceful fallback
- **Status**: Cross-platform file locking implemented in `job_manager.py`

**API/CLI Execution Path Divergence**
🔄 IDENTIFIED: Task 8.5 - API should use EMUSESPipeline for consistency
- **Issue**: API executes stages directly while CLI uses EMUSESPipeline class orchestration
- **Impact**: Data alignment, context setup, and validation differences between API and CLI
- **Root Cause**: API PipelineRunner bypasses EMUSESPipeline's data preprocessing and context management
- **Required**: Refactor API to use EMUSESPipeline for identical execution path

**Real-World Data Validation Requirements**
🔄 PENDING: Enhanced data validation for production datasets
- **Issue**: Missing value handling, data type coercion, and index alignment failures
- **Context**: Real HCP dataset exposed validation gaps not caught by synthetic test data
- **Required**: Robust data validation pipeline with informative error messages

**Optuna Trial Optimization for Development**
✅ COMPLETED: Reduced trial counts for faster testing cycles
- **Implementation**: Configurable trial counts with lower defaults for development/testing
- **Benefit**: Faster iteration cycles during development and CI testing
