# File Upload Sub-Plan 0e: Upload Endpoints for Real-World API

## Sub-Plan Scope
**Focus**: File upload endpoints to complete Phase 0 foundation
**Dependencies**: Sub-plan 0a (models completed), 0c (interface layer completed)
**Enables**: Real-world API usage with HCP and other neuroimaging datasets

## Problem Statement

**Current Gap**: API expects files to already exist on server filesystem, blocking real-world usage
**Root Cause**: Task 1.4 implemented `FileUploadModel` (Pydantic models) but not actual upload endpoints
**Impact**: Cannot test with real HCP data, requires manual file placement on server

## Tasks

- [x] Task 9 ║ tests/foundation-fastapi-service/test_file_upload_endpoints.py ║ File upload endpoints with validation and storage ║ M
  - [x] 9.1 Features file upload endpoint with CSV validation and temporary storage
  - [x] 9.2 Scores file upload endpoint with proper content-type validation
  - [x] 9.3 Optional labels file upload endpoint for supervised learning
  - [x] 9.4 Integration with job submission endpoints to use uploaded files
  - [x] 9.5 Temporary file cleanup and job-scoped file management

## Prerequisites Completed in Previous Sub-Plans
- ✅ `FileUploadModel` Pydantic model (Task 1.4)
- ✅ Job management with directory structure (Task 2.2)
- ✅ Path traversal protection (Task 6.1) 
- ✅ Security validation patterns (Task 6.2-6.4)
- ✅ Pipeline execution endpoints (Task 5)

## Context Updates Required

After completing this sub-plan, the following context files will need updates:

### EMUSES_Service_Architecture_Plan.md Updates
- Mark Phase 0 as **100% complete** with upload endpoints
- Update API completeness assessment from "server-side only" to "full real-world API"
- Document that HCP real-world example now works end-to-end

## Implementation Approach

**Endpoint Design**:
```python
POST /api/v1/upload/features
POST /api/v1/upload/scores  
POST /api/v1/upload/labels (optional)
```

**File Management Strategy**:
- Store uploaded files in job-specific temporary directories
- Return file paths for use in subsequent job submission
- Implement automatic cleanup after job completion
- Use existing `secure_filename()` and validation from Task 6

**Integration Pattern**:
- Upload endpoints return file paths
- Job submission endpoints accept either file paths OR uploaded file references
- Maintain backward compatibility with existing file-path-based usage

## Acceptance Criteria
- ✅ Upload endpoints accept CSV files up to 1GB (neuroimaging data size)
- ✅ File validation prevents malformed uploads and security issues
- ✅ Uploaded files can be used directly in pipeline job submissions  
- ✅ Temporary file management with automatic cleanup
- ✅ HCP real-world test (`test_hcp_api_real.py`) works end-to-end
- ✅ Backward compatibility maintained for existing file-path workflows

## Quality Gates
- ✅ flake8 complexity ≤ 10, zero violations
- ✅ mypy strict mode passes
- ✅ pytest coverage ≥ 95% for new upload endpoints
- ✅ Security validation prevents path traversal and malicious uploads
- ✅ Integration with existing job management preserves all functionality
- ✅ Performance meets requirements (1GB upload in reasonable time)

## Completion Status
**Status**: ✅ COMPLETE
**Priority**: HIGH (blocks real-world API usage)
**Estimated Effort**: 4-6 hours (small addition to existing foundation)

**Completed**: All file upload endpoints implemented and tested
- ✅ Features, scores, and labels upload endpoints working
- ✅ CSV validation and security checks in place  
- ✅ Integration with job submission verified
- ✅ Temporary file management and cleanup implemented
- ✅ Rate limiting and error handling functioning
- ✅ All tests passing (13/13 tests pass with TESTING_MODE=true)

<details><summary>📝 Extended Details (for ChatGPT / humans)</summary>

### Rationale
<reasoning>
This sub-plan addresses the critical gap preventing real-world API usage. The FastAPI foundation is architecturally complete but missing file upload endpoints essential for a production API. Since Task 1.4 only implemented Pydantic models (not endpoints), and all other tasks are complete, a focused sub-plan 0e provides the minimal addition needed to complete Phase 0 without reopening completed work.
</reasoning>

### Resources
- Files to open:
  - `emuses/foundation_fastapi_service/app.py` (add upload endpoints)
  - `emuses/foundation_fastapi_service/models.py` (use existing FileUploadModel)
  - `emuses/foundation_fastapi_service/job_manager.py` (file cleanup integration)
- External APIs / libs:
  - FastAPI `UploadFile` and `File` (already imported)
  - pathlib `Path` for file management
  - existing security utilities from Task 6

### Risks & Mitigations
- 🚨 File storage security issues – Use existing `secure_filename()` and path validation from Task 6.1
- 🚨 Disk space exhaustion from large uploads – Implement file size limits and cleanup policies  
- 🚨 Breaking existing file-path workflows – Maintain dual support for paths and uploads
- 🚨 Integration complexity with job management – Reuse existing job directory patterns from Task 2.2

### Acceptance-Checks
| Test file                                              | Assertion                                    | Metric                |
|--------------------------------------------------------|----------------------------------------------|-----------------------|
| tests/foundation-fastapi-service/test_file_upload_endpoints.py | Upload endpoints accept valid CSV files | response time ≤ 10s |
| tests/foundation-fastapi-service/test_file_upload_endpoints.py | File validation rejects malformed uploads | 100% security coverage |
| tests/foundation-fastapi-service/test_file_upload_endpoints.py | Job submission works with uploaded files | end-to-end success |
| test_hcp_api_real.py | HCP real-world example completes successfully | pipeline identical to CLI |

### Testing Strategy
**Integration Testing Approach:**
- **Upload endpoints**: Integration testing with real FastAPI app and file uploads
- **Job integration**: End-to-end testing with upload → job submission → execution pipeline
- **Security validation**: Test malicious file uploads, path traversal attempts, size limits
- **Cleanup testing**: Verify temporary files are properly cleaned up after job completion

</details>
