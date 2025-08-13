# Project Context for Claude Code LAD Framework

## Project Mission
**EMUSES** is a predictive modeling tool for neuroimaging research enabling:
- **Individual Researchers**: Local model development and analysis
- **Research Labs**: Collaborative model sharing with workspace isolation  
- **Scientific Community**: Public model registry with peer review and benchmarking

## Status Maintenance Protocol
**CRITICAL**: Always read and update `PROJECT_STATUS.md` when:
- Starting new development sessions
- Completing major tasks or features
- Moving between development phases

**Current Status**: See `PROJECT_STATUS.md` for authoritative project status and next priorities.

## Code Style Requirements
- **Docstrings**: NumPy-style required for all functions/classes
- **Linting**: Flake8 compliance (max-complexity 10)
- **Testing**: TDD approach, component-aware strategies
- **Coverage**: 90%+ target for new code

## Communication Guidelines
**Objective, European-Style Communication**:
- Avoid excessive enthusiasm - use measured language
- Scientific tone: "This approach has merit" vs "That's a great idea!"
- State problems directly - honest criticism over hedging
- Acknowledge uncertainty: "I cannot verify this will work"
- Present trade-offs rather than unqualified endorsements
- Focus on accuracy over making user feel good

## Current Architecture Patterns

### Model Registry Integration (Phase 4.1 ✅)
- **Factory Pattern**: ModelRegistryFactory for cross-mode registry creation
- **Unified Interface**: BaseModelRegistry with consistent signatures across LOCAL/DATABASE/CLOUD
- **Flexible Parameters**: Methods support both old and new calling patterns
- **Auto-Detection**: Deployment mode detection with fallback logic

### Testing Strategy Guidelines
- **API Endpoints**: Integration testing (real app + mocked external deps)
- **Business Logic**: Unit testing (complete isolation + mocks)
- **Data Processing**: Unit testing (minimal deps + test fixtures)

### Token Optimization for Large Codebases
**Standard test commands:**
- **Large test suites**: Use `2>&1 | tail -n 100` for pytest to capture only final results
- **Coverage reports**: Use `tail -n 150` for comprehensive coverage summary
- **Targeted tests**: Single test runs (`pytest -xvs`) don't need redirection

**Long-running commands (>2 minutes):**
- **Pattern**: `<command> 2>&1 | tee full_output.txt | grep -iE "(warning|error|failed|exception)" | tail -n 30; echo "--- FINAL OUTPUT ---"; tail -n 100 full_output.txt`
- **Rationale**: Captures critical information while optimizing token usage

## Key Integration Decisions (Current Architecture)

| Component | Decision | Strategy | Impact |
|-----------|----------|----------|---------|
| Model Registry Factory | Single endpoints file | Unified interface across modes | Cross-mode compatibility ✅ |
| User Isolation Strategy | Ownership validation helpers | Shared `_get_user_*` functions | Consistent security boundaries ✅ |
| API Schema Strategy | Separate Create/Update/Read schemas | Different Pydantic models per operation | Clean API design ✅ |
| Registry Deployment Mode | Auto-detection with fallback | Factory pattern with mode validation | Seamless mode transitions ✅ |
| Caching Strategy | In-memory cache with TTL/LRU | ModelRegistryCache with user isolation | Query performance optimization ✅ |
| Storage Management UX | Enhanced visibility and reporting | StorageManager with model breakdown and suggestions | Improved user awareness ✅ |
| Database Query Optimization | Strategic indexes + performance monitoring | DatabaseIndexOptimizer with 9 composite indexes | Query performance optimization ✅ |

## Active Development Context

**Current Branch**: `feature/model-registry`
**Active Phase**: Phase 4.7 - Production Deployment Preparation (2/3 complete - 3/4 tasks in 4.7.2 complete)
**Next Implementation**: Disaster recovery procedures - create comprehensive disaster recovery and business continuity procedures

**Recent Completion**: Task 4.7.2.c Graceful Degradation for Partial System Failures (Complete)
- ✅ Degradation Detection: Enhanced health checker to automatically detect and report degradation levels (minimal/moderate/full)
- ✅ Automatic Fallback: Implemented automatic fallback mechanisms from DATABASE/CLOUD to LOCAL mode when services fail
- ✅ Progressive Degradation: Added progressive service degradation with essential operations prioritization during failures
- ✅ Circuit Breaker Integration: Enhanced circuit breaker with graceful failure handling preventing cascading failures
- ✅ User Impact Notifications: User-friendly degradation notifications with clear alternatives and recovery estimates
- ✅ Resource Conservation: Automatic resource conservation during degraded states with background task management
- ✅ Recovery Detection: Automatic detection of service recovery and restoration to full functionality
- ✅ New Endpoints: Added 6 graceful degradation endpoints (/degradation-status, /fallback-status, /degradation-levels, /recovery-status, /user-impact, /resource-conservation)
- ✅ Comprehensive Testing: 8 new graceful degradation tests covering all failure scenarios and recovery patterns

## Common Commands
- **CLI**: `python -m emuses.cli` (not `python -m emuses`)
- **Test Security**: `pytest tests/security/ -q --tb=short` (248 tests)
- **Test Model Registry**: `pytest tests/model_registry/test_local_registry.py -xvs`
- **Test Integration**: `pytest tests/integration/test_unified_interface.py -xvs`
- **Test Caching**: `pytest tests/performance/test_model_registry_caching.py -xvs` (15 tests)
- **Test Storage UX**: `pytest tests/model_registry/test_storage_ux.py -xvs` (32 tests)
- **Test Query Optimization**: `pytest tests/performance/test_database_query_optimization.py -xvs` (7 baseline tests)
- **Test Database Indexes**: `pytest tests/performance/test_database_index_optimization.py -xvs` (12 index tests)
- **Test DB Integration**: `pytest tests/performance/test_database_registry_integration.py -xvs` (10 integration tests)
- **Coverage**: `pytest --cov=emuses --cov-report=term-missing`

---
*Last Updated: 2025-08-13 - Phase 4.7.1 Observability Integration Complete*
*Historical details archived in `docs/project-history/`*