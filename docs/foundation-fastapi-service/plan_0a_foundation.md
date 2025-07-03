# Foundation Sub-Plan 0a: Core Models & Job Management

## Sub-Plan Scope
**Focus**: Establish foundational data models and job lifecycle management infrastructure
**Dependencies**: None (foundation layer)
**Enables**: Sub-plan 0b (pipeline integration), 0c (API endpoints), 0d (security testing)

## Tasks

- [x] Task 1 ║ tests/foundation-fastapi-service/test_api_models.py ║ Pydantic request/response models with validation and serialization ║ S
  - [x] 1.1 Pipeline configuration models inheriting from PipelineConfig
  - [x] 1.2 Job submission, status, and artifact response models
  - [x] 1.3 Error response models with standardized error codes
  - [x] 1.4 File upload and multipart form data models with size limits

- [x] Task 2 ║ tests/foundation-fastapi-service/test_job_manager.py ║ Job lifecycle management with UUID generation, status tracking, and directory organization ║ M
  - [x] 2.1 Secure UUID job ID generation and validation with entropy checks
  - [x] 2.2 Job directory structure creation with path traversal protection
  - [x] 2.3 Job status persistence and updates with concurrency locks
  - [x] 2.4 Job metadata tracking with sanitization and cleanup policies

## Context Updates Required

After completing this sub-plan, update the following files with foundation knowledge:

### context_0b_pipeline.md Updates
- Document `JobManager` class API and lifecycle methods
- Specify job directory structure for stage artifact storage
- Include Pydantic models for pipeline configuration
- Define job status update patterns for pipeline integration

### context_0c_interface.md Updates  
- Document request/response model schemas for API endpoints
- Include error response formats and HTTP status code mappings
- Specify file upload handling patterns and size limits
- Define job submission and tracking model contracts

### context_0d_security.md Updates
- Document job directory structure for path traversal testing
- Include UUID generation entropy requirements for security validation
- Specify file upload size limits and validation rules
- Define job metadata sanitization requirements

## Acceptance Criteria
- All Pydantic models validate correctly with 100% test coverage
- JobManager handles job lifecycle transitions with concurrency safety
- Directory creation includes path traversal protection
- UUID generation meets cryptographic entropy requirements
- File upload models enforce size limits and type validation
- Error models provide standardized, informative responses

## Quality Gates
- flake8 complexity ≤ 10, zero violations
- mypy strict mode passes
- pytest coverage ≥ 95%
- All docstrings follow NumPy style
