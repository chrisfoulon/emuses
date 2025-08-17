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

## Test Coverage Enhancement Strategy (Evidence-Based)

### Current Achievement: Research Software Excellence
- **Coverage**: 47.1% line coverage - **EXCEEDS research software standards** (30-60% typical)
- **Critical Systems**: 70-100% coverage (Security, Model Registry, Integration)
- **Standards Compliance**: NIH research software guidelines met with focus on reproducibility

### Future Production Enhancement Targets
- **Overall Target**: 60% coverage (balanced for scientific software context)
- **Critical Components**: 80%+ coverage (Security/Auth, Model Registry Core, Data Pipelines)
- **Standard Components**: 60% coverage (CLI, Configuration, Utilities)
- **Priority**: After HeatmapStage development and comprehensive feature testing

### Evidence-Based Rationale
- **Research Analysis**: Comprehensive review of NIH, academic research, and industry standards
- **EMUSES Context**: Neuroimaging research tool (discovery focus, not safety-critical)
- **Resource Balance**: Quality over quantity approach for solo programmer efficiency
- **Implementation Strategy**: Systematic improvement plan documented in model registry plan

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

**Current Branch**: `feature/documentation-restructuring`
**Active Phase**: Progressive disclosure documentation system development
**CURRENT Development Status** (Updated 2025-08-17):

### **MAJOR MILESTONE**: Progressive Disclosure Documentation 🔄 **IN PROGRESS**
1. **Phase 1 COMPLETED** ✅ - CLI_REFERENCE.md progressive disclosure restructuring
   - **4-level hierarchy**: Essential → Advanced → Developer → Admin
   - **60% content reduction** for beginners while preserving all information
   - **Interactive navigation**: Mermaid diagrams and collapsible sections
   - **Technical infrastructure**: JavaScript enhancements, MkDocs validation

2. **Phase 2.1 COMPLETED** ✅ - API_REFERENCE.md progressive disclosure restructuring  
   - **5-level hierarchy**: Getting Started → Pipeline → Job Management → File Operations → Advanced → Monitoring
   - **Developer journey mapping**: Clear progression paths for different integration goals
   - **GitHub Actions deployment**: Modern workflow with automated validation

3. **CRITICAL ISSUE IDENTIFIED** 🚨 - Systematic markdown formatting errors
   - **Root cause**: Missing comprehensive MkDocs Material formatting guidelines
   - **Impact**: Content rendering failures, broken progressive disclosure
   - **Solution required**: Documentation quality framework development

### **COMPLETED PRIORITIES**:
4. **Test Suite Excellence** (ACHIEVED ✅) - `docs/test-analysis/FINAL_TEST_REPORT_2025_08_15.md`
5. **Model Registry Production Ready** (COMPLETED ✅) - Tasks 4.8.3, 4.8.4  
6. **FastAPI Documentation Serving** (COMPLETED ✅) - Unified development server

### **NEXT PRIORITY**: Documentation Quality Framework Development
- **LAD integration**: Comprehensive MkDocs formatting guidelines for Claude
- **Systematic solution**: Prevent future markdown syntax errors  
- **Framework enhancement**: Update prompts for automatic formatting compliance

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

## CI/CD & Testing Workflow (Resource-Efficient Strategy)

### **Before Making Changes**
- **Pre-push Testing**: `python scripts/dev_test_runner.py` (saves GitHub education credits)
- **Full Test Baseline**: `pytest -q --tb=short` (only when needed for comprehensive validation)

### **Development CI Strategy**
- **Feature Branches**: Automatic lightweight CI (13 tests, ~1 minute, ~2-3 credits)
- **Main Branch**: Full CI with PostgreSQL/Redis services (~30 minutes, ~30-60 credits)
- **Manual Dispatch**: Production CI available for pre-merge validation when needed

### **Credit-Conscious Development Pattern**
1. **Develop on feature branches** (triggers fast CI)
2. **Test locally first** with `python scripts/dev_test_runner.py`
3. **Push to feature branch** (fast feedback, minimal credits)
4. **Merge to main only when ready** (triggers comprehensive validation)

⚠️ **IMPORTANT**: Always run `python scripts/dev_test_runner.py` before pushing to catch issues locally and save GitHub education credits.

## Common Commands

### **🎯 Project-Wide Validation (USE THESE)**
- **Category Testing**: `python scripts/test_runners/comprehensive_test_runner.py --category security`
- **Full Validation**: `python scripts/test_runners/comprehensive_test_runner.py --all`
- **Comprehensive Coverage**: `python scripts/coverage/comprehensive_coverage_analysis.py --workers 8`
- **List Categories**: `python scripts/test_runners/comprehensive_test_runner.py --list`

### **🔧 Development Commands**
- **CLI**: `python -m emuses.cli` (not `python -m emuses`)
- **Pre-Push Local Testing**: `python scripts/dev_test_runner.py` (syntax + core tests)

### **🧪 Specific Test Commands (For Development)**
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

### **⚠️ IMPORTANT: Anti-Pattern Prevention**
- **❌ NEVER**: Run `subprocess.run(["pytest", ...])` from within test files
- **✅ ALWAYS**: Use `/scripts/test_runners/` for project-wide validation
- **📖 READ FIRST**: `/scripts/README.md` for comprehensive testing approach

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