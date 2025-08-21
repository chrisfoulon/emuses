# EMUSES Project Memory

## Status Maintenance Instructions

**IMPORTANT**: Always read and update `PROJECT_STATUS.md` when:
- Starting new development sessions
- Completing major tasks or features  
- Moving between development phases
- Adding new pending work

## Quick Status for New Sessions

**Current Status**: Analysis API Enhancement - Phase 2A Deduplication Core COMPLETE (6/6 tasks) - Phase 2B Enhanced Installation Workflow starting 🔄

**Key Status Files**:
- **PROJECT_STATUS.md** - Central project status
- **.lad/CLAUDE.md** - Static development guidelines and patterns
- **dev-docs/analysis-api/** - Current feature development context

## Project Mission
**EMUSES** enables neuroimaging research across three contexts:
- **Individual Researchers**: Local model development 
- **Research Labs**: Collaborative sharing with workspaces
- **Scientific Community**: Public registry with peer review

**Current Phase**: Analysis API Enhancement - Sub-Plan 0A-Extended (Model Registry Redesign)

## Recent Achievements

### Major Milestones Completed ✅
- **Model Registry System**: Production ready with comprehensive testing (2,138 tests, 99.1% health)
- **Multi-User Service Implementation**: Complete enterprise-ready multi-user service with HashiCorp Vault integration
- **Progressive Disclosure Documentation**: 38,000+ words restructured with 60-85% cognitive load reduction
- **FastAPI Documentation Serving**: Unified development server with environment-aware serving
- **Documentation Organization**: Clear separation of user docs/ vs internal dev-docs/
- **LAD Compliance**: Separated static guidelines from dynamic project tracking
- **Analysis API Enhancement - Phase 1**: Complete Model Registry Redesign with atomic operations ✅
  - Complete EMUSES model detection and validation
  - Atomic transaction framework with rollback capability
  - Enhanced metadata storage with component tracking and hashes
  - Configuration and content hash indexing for duplicate detection
  - Full backward compatibility with existing individual component models

## Active Development Context

**Current Branch**: `feature/analysis-api-enhancement`
**Active Phase**: Analysis API Enhancement development

### **COMPLETED**: Analysis API Enhancement - Model Registry Redesign Phase 1 ✅
- **Sub-Plan**: 0A-Extended (Complete EMUSES Model Registry Redesign)  
- **Phase 1 Status**: COMPLETE - Foundation & Atomic Operations implemented
- **Feature Location**: `dev-docs/analysis-api/model-registry-redesign/`
- **Implementation**: Complete model detection, atomic transactions, enhanced metadata, hash indexing
- **Testing**: 28 new tests across complete model detection, transactions, metadata, and hash indexing
- **API Cleanup**: Removed unnecessary backward compatibility code

### **COMPLETED**: Analysis API Enhancement - Model Registry Redesign Phase 2A (6/6) ✅
- **Tasks Complete**: Complete deduplication core system with all algorithms and user interaction frameworks
- **Implementation**: 
  - Multi-level duplicate detection (configuration hash matching, content similarity analysis, performance fingerprint comparison)
  - Interactive and batch duplicate resolution workflows with rich user feedback
  - Force duplicate installation system with comprehensive multi-level warnings and safety mechanisms
  - Performance benchmarking framework with regression detection and baseline management
- **Testing**: 14 comprehensive tests covering all detection algorithms, resolution workflows, force installation, and performance monitoring
- **Features**: Production-ready deduplication pipeline with user control, safety mechanisms, and performance optimization

### **CURRENT PRIORITY**: Enhanced Installation Workflow - Task 0A-Ext.4.a
- **Task**: Update LocalModelRegistry.install_model() with complete model support and atomic operations
- **Focus**: Integration of deduplication engine with model registry installation workflow
- **Location**: `tests/model_registry/test_enhanced_installation.py`
- **Status**: Starting Phase 2B - Enhanced Installation Workflow (6 tasks remaining)

### **PHASE 2B**: Analysis API Enhancement - Enhanced Installation Workflow (0/6 complete)
- **Task 0A-Ext.4.a**: Enhanced model registry integration with deduplication ⏳
- **Task 0A-Ext.4.b**: Interactive CLI duplicate resolution ⏳
- **Task 0A-Ext.4.c**: Batch API duplicate handling ⏳
- **Task 0A-Ext.4.d**: Semantic model ID generation and versioning ⏳
- **Task 0A-Ext.4.e**: Storage optimization with component sharing ⏳
- **Task 0A-Ext.4.f**: Concurrent access safety and mutex/locking ⏳
- **Then Phase 3**: Interface Integration and CLI implementation

### **Known Issues**: Optuna Parameter Space Conflicts (low priority)
- **Problem**: EMUSES crashes when changing `--prediction_optim_dict` during resume
- **Solution**: Simple conflict detection with timestamped study creation
- **Documentation**: Complete analysis in `dev-docs/issues/optim_dict_resume_conflict.md`
- **Status**: Deferred (workaround exists)

## Development Workflow

### **Testing Strategy**
- **Pre-push**: `python scripts/dev_test_runner.py` (saves GitHub education credits)
- **Full validation**: `pytest -q --tb=short` (when needed for comprehensive validation)
- **Feature branches**: Lightweight CI (13 tests, ~1 minute)
- **Main branch**: Full CI with services (~30 minutes)

### **Development Pattern**
1. Test locally first with `python scripts/dev_test_runner.py`
2. Push to feature branch (fast feedback, minimal credits)
3. Merge to main when ready (comprehensive validation)

## Common Commands

### **Essential Testing**
- **Pre-push testing**: `python scripts/dev_test_runner.py`
- **Category testing**: `python scripts/test_runners/comprehensive_test_runner.py --category security`
- **Full validation**: `python scripts/test_runners/comprehensive_test_runner.py --all`
- **Coverage analysis**: `python scripts/coverage/comprehensive_coverage_analysis.py --workers 8`

### **Development Commands**
- **CLI**: `python -m emuses.cli`
- **Test specific modules**: `pytest tests/module/ -xvs`
- **Security tests**: `pytest tests/security/ -q --tb=short`

### **Guidelines**
- Use `/scripts/test_runners/` for project-wide validation
- Never run `subprocess.run(["pytest", ...])` from within test files
- See `/scripts/README.md` for comprehensive testing approach

---
*Last Updated: 2025-08-21 - Model Registry Redesign Phase 2A complete, Phase 2B enhanced installation workflow starting*
*Static guidelines in `.lad/CLAUDE.md` | Historical details in `dev-docs/project-history/`*