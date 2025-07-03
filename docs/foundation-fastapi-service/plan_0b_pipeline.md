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
  - [x] 4.1 EMUSESPipeline async wrapper with ProcessPoolExecutor and resource limits
  - [x] 4.2 Context dictionary preservation with deep copy validation
  - [x] 4.3 Progress callback integration with rate limiting
  - [x] 4.4 Error handling and exception capture with job status updates

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

## Acceptance Criteria
- Individual stage runners execute with parameter validation and resource limits
- PipelineRunner preserves context dictionaries through deep copy validation
- Background execution uses ProcessPoolExecutor with proper resource limits
- Progress callbacks integrate with rate limiting to prevent bottlenecks
- Error handling captures exceptions and updates job status appropriately
- Stage artifacts are organized securely with proper file handling

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
