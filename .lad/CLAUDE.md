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
**Active Phase**: Feature-based development approach with LAD-compliant organization
**CORRECTED Development Priorities** (Critical dependency analysis):
1. **Test Suite Stabilization** (Priority 1 - CRITICAL PREREQUISITE) - `docs/test-analysis/`
   - Target: 0% test collection errors (currently 82/425 = 19.3%)
   - Blocks Tasks 4.8.3 (QA validation) and 4.8.4 (release documentation)
2. **Model Registry Final Validation** (Priority 2 - DEPENDS ON #1) - Tasks 4.8.1.b-d, 4.8.3, 4.8.4
3. **Analysis API Enhancement** (Priority 3 - INDEPENDENT) - `docs/analysis-api/`

**Recent Completion**: Task 4.7.2.d Disaster Recovery Procedures (Complete)
- ✅ Backup Validation: Comprehensive backup integrity checking with RPO/RTO targets (15min/30min)
- ✅ Service Restoration: Priority-based dependency ordering (Database → Local → Health → API → Cloud)
- ✅ Recovery Procedures: Failure-specific procedures for database corruption, storage failure, system failure, config loss
- ✅ Emergency Contacts: 24/7 escalation matrix with role-based contact management and communication channels
- ✅ Business Impact Assessment: 1500+ user impact evaluation with SLA risk analysis and regulatory compliance
- ✅ Recovery Testing: Automated test procedures (backup validation, failover test, full recovery simulation)
- ✅ Progress Monitoring: Session-based recovery tracking with completion percentages and step validation
- ✅ Post-Recovery Validation: Comprehensive system health verification and performance metrics validation
- ✅ New Endpoints: Added 8 disaster recovery endpoints (/backup-status, /restoration-plan, /procedure, /emergency-contacts, /business-impact, /run-test, /progress, /post-recovery-validation)
- ✅ Comprehensive Testing: 8 new disaster recovery tests covering all business continuity scenarios

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
- **Test Disaster Recovery**: `pytest tests/tools/test_disaster_recovery.py -xvs` (8 disaster recovery tests)
- **Test All Health Monitoring**: `pytest tests/tools/test_model_registry_health.py tests/tools/test_graceful_degradation.py tests/tools/test_disaster_recovery.py -v` (25 health tests total)
- **Coverage**: `pytest --cov=emuses --cov-report=term-missing`

## Feature Development Structure

### New LAD-Compliant Feature Folders
- **`docs/test-analysis/`**: Comprehensive test error analysis and resolution (Task 4.8.2 reorganized)
  - Complete LAD structure: 00_feature_kickoff.md, context.md, plan.md
  - Systematic approach to resolving 82 test failures with prioritization framework
- **`docs/analysis-api/`**: Effect size map API/CLI integration (New feature)
  - Expose existing `run_kernel_heatmap_analysis()` and `run_heatmap_analysis()` functions
  - FastAPI endpoints, CLI commands, configuration integration

### ⚠️ CORRECTED Strategic Development Approach
**CRITICAL DEPENDENCY IDENTIFIED**: Model registry completion blocked by test failures.

**Revised Approach**:
1. **Test Suite Stabilization** (Priority 1, CRITICAL PREREQUISITE, Blocks QA validation)
   - Target: 0% test collection errors, Focus on P1/P2 model registry affecting fixes
2. **Complete Model Registry** (Priority 2, DEPENDS ON #1, Major milestone) 
3. **Add Analysis API Features** (Priority 3, Independent, Clear business value)

---
*Last Updated: 2025-08-14 - Feature reorganization complete with LAD-compliant structure*
*Historical details archived in `docs/project-history/`*