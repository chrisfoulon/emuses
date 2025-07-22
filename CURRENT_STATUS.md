# EMUSES Package Current Status & Solutions

## Current Problems Identified

### 1. Duplicate API Service Implementations

**Problem**: We have two parallel FastAPI service implementations:
- `emuses/foundation_fastapi_service/` (1,173+ lines, production-ready with rate limiting, file uploads, security)
- `emuses/api/` (simpler implementation created during CLI integration)

**Root Cause**: LAD framework weakness in existing work discovery led to creating parallel implementations instead of integration.

**Impact**: Resource duplication, confusion, potential conflicts

### 2. CLI Service Integration Issues

**Problem**: CLI auto-start service mechanism experiencing timeout issues
- Service fails to start within 30-second timeout
- User reported: "Service failed to become ready within timeout"

**Technical Details**:
- CLI uses unified service architecture (removed dual execution paths)
- Auto-starts local FastAPI service via uvicorn subprocess
- Health check polling fails to detect service readiness

### 3. Legacy Code Uncertainty

**Problem**: Multiple legacy files with unclear necessity:
- `emuses/scripts/main.py` (legacy argparse interface)
- `debug_cli_test.py` (temporary debugging script)
- Various service management components

**User Constraint**: Must keep legacy main.py until new system proves equivalent results

## Decided Solutions

### 1. API Service Consolidation Strategy

**Decision**: Integrate both services while maintaining functionality
- **Phase 1**: Fix current simple API issues first
- **Phase 2**: Deep integration planning using Opus 4 for architectural decisions
- **Phase 3**: Execute integration following detailed plan
- **Phase 4**: Migrate and validate against legacy system

**Rationale**: 
- Simple API is closer to working state despite being less feature-rich
- Foundation service has better production features but hasn't been tested as thoroughly
- Integration leverages best of both

### 2. CLI Service Timeout Fix

**Approach**: Investigate and resolve service startup/health check issues
- Check uvicorn startup process
- Verify health endpoint functionality
- Adjust timeout or startup sequence as needed

### 3. Legacy Code Management

**Policy**: Conservative cleanup approach
- Keep legacy main.py until proven equivalence
- Remove only clearly temporary/debug files
- Document all decisions in version control

## Current Sprint Priorities

1. **Fix CLI service timeout** (blocking user workflows)
2. **Plan API service integration** (architectural foundation)  
3. **Clean up temporary files** (maintenance)
4. **Validate against legacy system** (quality assurance)

## Technical Architecture Notes

### Service Auto-Start Mechanism
```python
# CLI starts service via:
service_process = _start_local_service(port=8000)
_wait_for_service_ready(service_url, timeout=30)
```

### Health Check Pattern
```python
# Uses foundation service health endpoint:
GET /api/health -> {"status": "healthy", "timestamp": "...", "version": "1.0.0"}
```

### Current Service URLs
- Foundation Service: `emuses.foundation_fastapi_service.app:app`
- Simple API: `emuses.api.main:app`

## Next Steps

1. Immediate: Debug and fix service timeout
2. Planning: Design service integration architecture
3. Implementation: Execute integration plan
4. Validation: Prove equivalence with legacy system