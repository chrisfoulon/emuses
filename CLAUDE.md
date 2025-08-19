# EMUSES Project Memory

## Status Maintenance Instructions

**IMPORTANT**: Always read and update `PROJECT_STATUS.md` when:
- Starting new development sessions
- Completing major tasks or features  
- Moving between development phases
- Adding new pending work

## Quick Status for New Sessions

**Current Status**: Progressive Disclosure Documentation System COMPLETE ✅ + Optuna Resume Conflict Analysis Complete ✅

**Key Status Files**:
- **PROJECT_STATUS.md** - Central project status (updated 2025-08-18)
- **.lad/CLAUDE.md** - Static development guidelines and patterns
- **dev-docs/project-history/** - Historical details archived for reference
- **dev-docs/model-registry/plan_4_integration.md** - Phase 4.2 task breakdown

## Project Mission (Quick Reference)
**EMUSES** enables neuroimaging research across three contexts:
- **Individual Researchers**: Local model development 
- **Research Labs**: Collaborative sharing with workspaces
- **Scientific Community**: Public registry with peer review

**Current Phase**: Phase 4 COMPLETE ✅ - Model Registry Production Ready + Enhanced Developer Experience

## 🎉 Latest Achievements (2025-08-19)

### Documentation Cleanup and Consolidation ✅
- **Issue Tracking**: Moved optim_dict resume conflict analysis to dev-docs/issues/
- **Path References**: Fixed all docs/ → dev-docs/ references across project files
- **CLAUDE.md Consolidation**: Separated static LAD guidelines from dynamic project tracking
- **Repository Organization**: Clear separation of user docs/ vs internal dev-docs/

### Progressive Disclosure Documentation System ✅ **COMPLETED**
1. **Phase 1 COMPLETED** ✅ - CLI_REFERENCE.md progressive disclosure restructuring
   - **4-level hierarchy**: Essential → Advanced → Developer → Admin
   - **60% content reduction** for beginners while preserving all information
   - **Interactive navigation**: Mermaid diagrams and collapsible sections
   - **Technical infrastructure**: JavaScript enhancements, MkDocs validation

2. **Phase 2.1 COMPLETED** ✅ - API_REFERENCE.md progressive disclosure restructuring  
   - **5-level hierarchy**: Getting Started → Pipeline → Job Management → File Operations → Advanced → Monitoring
   - **Developer journey mapping**: Clear progression paths for different integration goals
   - **GitHub Actions deployment**: Modern workflow with automated validation

3. **Phase 2.2 COMPLETED** ✅ - USER_GUIDE.md progressive disclosure restructuring
   - **4-level hierarchy**: Research Contexts → Core Workflows → Advanced Features → Support Resources
   - **85% content reduction** for beginners while preserving 100% information access
   - **15,000+ word document** transformed with comprehensive progressive disclosure

4. **Phase 2.3 COMPLETED** ✅ - RESEARCH_WORKFLOWS.md progressive disclosure restructuring
   - **4-level hierarchy**: Navigation → Data Modality → Research Questions → Advanced Approaches → Templates
   - **Scientific workflow optimization** with expertise-based grouping
   - **1,496 lines** of scientific workflows restructured

5. **Documentation Quality Framework COMPLETED** ✅ - Systematic markdown formatting resolution
   - **All 47 MkDocs warnings resolved**: From poor maintenance to industry excellence
   - **Comprehensive formatting guidelines**: MkDocs Material standards established
   - **Strict mode restored**: Build system validation with zero warnings

### FastAPI Documentation Serving Feature ✅
- **Unified Development Server**: Serve API + docs at `localhost:8000/docs/`
- **Environment-Aware**: Only serves in development mode (not production)
- **Comprehensive Testing**: 3 new test cases, all passing
- **Zero Breaking Changes**: Existing API functionality preserved
- **Manual Validation**: Complete end-to-end testing confirmed working

### Model Registry Production Ready ✅
- **Test Suite Excellence**: 2,138 tests collected with 100% success, 99.1% overall health
- **Documentation Ecosystem**: 38,000+ word documentation created (25% → 100% coverage)
- **Task 4.8.3 (QA validation)** COMPLETED ✅
- **Task 4.8.4 (release documentation)** COMPLETED ✅ 
- All SESSION_HANDOVER tasks completed successfully ✅

### Project Cleanup ✅
- **Obsolete Files Removed**: 9 temporary/audit files cleaned up
- **Repository Hygiene**: Removed completed task scripts and analysis files
- **Security Check**: Verified and removed rerun command with special characters

## Active Development Context

**Current Branch**: `feature/documentation-restructuring`
**Active Phase**: Documentation system consolidation and cleanup ✅ **COMPLETED**
**CURRENT Development Status** (Updated 2025-08-19):

### **COMPLETED PRIORITIES**:
1. **Progressive Disclosure Documentation System** (COMPLETED ✅)
2. **Model Registry Production Ready** (COMPLETED ✅)
3. **FastAPI Documentation Serving** (COMPLETED ✅)
4. **Documentation Cleanup and Consolidation** (COMPLETED ✅)

### **NEXT PRIORITY**: Analysis API Enhancement Development
- **Feature Location**: `dev-docs/analysis-api/` with existing mature functions ready for exposure
- **Scope**: Expose `run_kernel_heatmap_analysis()` and `run_heatmap_analysis()` functions
- **Implementation**: FastAPI endpoints, CLI commands, configuration integration
- **Status**: Ready for development - independent feature with clear business value

### **Recent Issue Analysis**: Optuna Parameter Space Conflicts ✅ **COMPLETED**
- **Problem**: EMUSES crashes when changing `--prediction_optim_dict` during resume
- **Root Cause**: Parameter space mismatch in existing Optuna studies
- **Solution**: Simple conflict detection with timestamped study creation
- **Documentation**: Complete technical analysis in `dev-docs/issues/optim_dict_resume_conflict.md`
- **Implementation**: Deferred to future development (low priority, workaround exists)

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

---
*Last Updated: 2025-08-19 - Documentation consolidation and LAD compliance restoration*
*Development guidelines in `.lad/CLAUDE.md` | Historical details in `dev-docs/project-history/`*