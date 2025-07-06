# Pipeline Integration Sub-Plan 0b: Stage & Pipeline Runners

## Sub-Plan Scope
**Focus**: EMUSES pipeline execution wrappers and stage-specific runners
**Dependencies**: Sub-plan 0a (models and job management)
**Enables**: Sub-plan 0c (API endpoints), 0d (security testing)

## Tasks

- [x] Task 3 ║ tests/foundation-fastapi-service/test_stage_runners.py ║ Individual stage execution with context loading and artifact organization ║ M
  - [x] 3.1 UMAPStage wrapper with parameter validation and resource limits
  - [x] 3.2 HeatmapStage wrapper with optimization progress tracking
  - [x] 3.3 PredictionStage wrapper with test evaluation mode
  - [x] 3.4 Stage-specific artifact organization with secure file handling

- [x] Task 4 ║ tests/foundation-fastapi-service/test_pipeline_runner.py ║ Background pipeline execution with context preservation and progress callbacks ║ L
  - [x] 4.1 EMUSESPipeline async wrapper with ProcessPoolExecutor and resource limits - **COMPLETED**: Real EMUSES pipeline execution implemented with context setup for prediction keys (prediction_train_features, prediction_train_labels). CLI vs API comparison test validates identical behavior and artifact creation.
  - [x] 4.2 Context dictionary preservation with deep copy validation - **COMPLETED**: Context setup ensures proper key initialization before stage execution
  - [x] 4.3 Progress callback integration with rate limiting - **COMPLETED**: Progress tracking implemented in PipelineRunner
  - [x] 4.4 Error handling and exception capture with job status updates - **COMPLETED**: Comprehensive error handling with job status management
  - [x] 4.5 **EMUSESPipeline Integration Refactor** - **COMPLETED**: Refactored PipelineRunner to use EMUSESPipeline internally for consistent data preprocessing, context setup, and stage orchestration identical to CLI execution path
    - [x] 4.5.1 Create EMUSESPipeline arguments converter utility (_context_to_emuses_args) - **COMPLETED**: Added utility method that converts API context dictionary to argparse.Namespace compatible with EMUSESPipeline, with type safety, defaults, and data preservation
    - [x] 4.5.2 Create progress callback adapter for EMUSESPipeline format - **COMPLETED**: Added _create_emuses_progress_adapter method that converts between API and EMUSESPipeline progress callback formats with rate limiting, job status integration, and graceful error handling
    - [x] 4.5.3 Implement EMUSESPipeline integration in _run_pipeline_in_process - **COMPLETED**: Refactored _run_pipeline_in_process to use EMUSESPipeline internally, converting context to args, setting up pipeline context, adding stages based on configuration, using progress callback adapter, and running pipeline with result merging
    - [x] 4.5.4 Add context merging utility to preserve API metadata - **COMPLETED**: Added _merge_pipeline_context utility that preserves API-specific metadata while incorporating pipeline execution results and artifacts
    - [x] 4.5.5 Update integration tests for EMUSESPipeline equivalence validation - **COMPLETED**: Added comprehensive tests for EMUSESPipeline integration including equivalence validation, stage configuration testing, error handling, and context preservation verification

## Prerequisites from 0a
- JobManager class with job lifecycle APIs
- Pydantic models for job status and configuration
- Job directory structure patterns
- UUID-based job identification system

## Context Updates Required

After completing this sub-plan, update the following files with pipeline knowledge:

### context_0c_interface.md Updates
- Document `PipelineRunner` async interface and method signatures
- Include stage-specific runner classes and their capabilities
- Specify background execution patterns and ProcessPoolExecutor usage
- Define progress callback mechanisms and rate limiting
- Document context preservation patterns for API integration

### context_0d_security.md Updates
- Document background process details for security testing
- Include ProcessPoolExecutor resource limits and isolation
- Specify progress callback rate limiting for performance testing
- Define context serialization patterns for memory testing
- Document stage artifact file handling for path traversal testing

## Implementation Summary

### Task 4.1: Real EMUSES Pipeline Execution

**Problem Solved**: Replaced placeholder logic with real EMUSES pipeline execution in PipelineRunner.

**Key Implementation Details**:
1. **Context Setup**: Added prediction key initialization (`prediction_train_features`, `prediction_train_labels`) before stage execution to match EMUSESPipeline expectations
2. **Real Stage Execution**: PipelineRunner now calls actual stage.run() methods instead of placeholder logic
3. **Output Path Handling**: Fixed config.output_folder to be Path object instead of string
4. **Integration Testing**: CLI vs API comparison validates identical behavior and artifact creation

**Files Modified**:
- `emuses/foundation_fastapi_service/pipeline_runner.py`: Real stage execution with context setup
- `emuses/pipelines/pipeline_config.py`: Output path handling fixes
- `tests/foundation-fastapi-service/test_pipeline_runner.py`: Real execution validation test
- `tests/integration/test_cli_vs_api_comparison.py`: Integration test comparing CLI and API outputs

**Test Results**:
- Unit test `test_real_pipeline_execution_creates_files` validates real pipeline creates all expected artifacts
- Integration test confirms API and CLI produce identical results and create the same output files
- All EMUSES stages (UMAP, Heatmap, Prediction) execute successfully and create models, embeddings, plots, metrics

**Production Readiness**: The PipelineRunner now executes the complete real EMUSES pipeline with proper error handling, context management, and artifact creation. Background execution is production-ready.

### Task 4.5: EMUSESPipeline Integration Refactor

**Problem Solved**: Refactored PipelineRunner to use EMUSESPipeline internally instead of direct stage execution, ensuring consistent data preprocessing, context setup, and stage orchestration identical to CLI execution path.

**Key Implementation Details**:
1. **Context-to-Args Conversion**: Added `_context_to_emuses_args` utility that converts API context dictionary to argparse.Namespace compatible with EMUSESPipeline, with type safety, defaults, and data preservation
2. **Progress Callback Adapter**: Added `_create_emuses_progress_adapter` that converts between API and EMUSESPipeline progress callback formats with rate limiting, job status integration, and graceful error handling
3. **EMUSESPipeline Integration**: Refactored `_run_pipeline_in_process` to instantiate EMUSESPipeline, set up context with input data, add stages based on configuration, run with progress adapter, and merge results back
4. **Context Merging**: Added `_merge_pipeline_context` utility that preserves API-specific metadata while incorporating pipeline execution results and artifacts
5. **Equivalence Validation**: Added comprehensive tests verifying EMUSESPipeline integration produces equivalent results to CLI execution

**Files Modified**:
- `emuses/foundation_fastapi_service/pipeline_runner.py`: Added context conversion, progress adapter, pipeline integration, and context merging utilities
- `tests/foundation-fastapi-service/test_emuses_pipeline_integration.py`: Comprehensive test coverage for all integration components including equivalence validation

**Test Results**:
- All EMUSESPipeline integration tests pass with mocked components
- Context conversion, progress adaptation, and merging utilities validated
- Stage configuration equivalence tests verify CLI behavior matching
- Error handling tests confirm graceful failure and proper cleanup

**Production Readiness**: PipelineRunner now uses EMUSESPipeline internally for all pipeline execution, ensuring identical behavior to CLI while maintaining API-specific features like progress callbacks and job management.

## Quality Gates
- flake8 complexity ≤ 10, zero violations
- mypy strict mode passes
- pytest coverage ≥ 95%
- Background processes properly isolated and cleaned up
- Context serialization handles large dictionaries efficiently
- Stage execution runtime ≤ 30s for unit tests, ≤ 120s for integration

## Parameter Validation Guidelines
**CRITICAL**: Parameter validation should ONLY check for breaking values that would cause crashes or invalid states. DO NOT impose arbitrary "sensible" ranges.

**What TO validate**:
- Type checking (str, int, float, etc.)
- Breaking negative values (e.g., n_components < 1)
- Zero/null values that would crash algorithms
- Data structure constraints (empty arrays, mismatched dimensions)

**What NOT to validate**:
- Arbitrary upper limits (e.g., n_neighbors < 200)
- "Sensible" ranges (e.g., test_size between 0.1-0.5)
- Performance-related limits unless they cause crashes
- User preference parameters

**Resource limits should be**:
- Proportional to system resources (e.g., 75% of available memory)
- Easily configurable via parameters
- Default to reasonable system-based values
- Never hardcoded to specific values like "8GB"

**Example**: For UMAP n_neighbors, validate > 0, but don't set upper limit unless UMAP documentation specifies one.
