# EMUSES Project Memory

## Status Maintenance Instructions

**IMPORTANT**: Always read and update `PROJECT_STATUS.md` when:
- Starting new development sessions
- Completing major tasks or features  
- Moving between development phases
- Adding new pending work

## Quick Status for New Sessions

**Current Status**: Analysis API Enhancement - Phase 2B Enhanced Installation Workflow IN PROGRESS (1/6 tasks complete) 🔄

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

### **ARCHITECTURE REVISION REQUIRED**: Phase 2 Hash Stability Issues ⚠️
- **Critical Discovery**: Content hash implementation includes file paths → breaks cross-platform model sharing
- **Impact**: Complex deduplication algorithms built on unstable hash foundation
- **Analysis**: LAD Phase 0 architectural discovery identified Git-style content-addressable storage needed
- **Decision**: Simplify deduplication to basic exact hash matching, remove complex algorithms

### **COMPLETED BUT REVERTING**: Phase 2A-2B Complex Implementation ❌
- **Implemented**: Complex deduplication algorithms, interactive workflows, performance fingerprinting
- **Issue**: Built on path-sensitive hashing that breaks when models transferred between systems
- **Keeping**: Basic duplicate detection, batch installation, semantic IDs, atomic operations
- **Reverting**: Interactive workflows, performance fingerprinting, complex similarity algorithms

### **CURRENT PRIORITY**: Phase 2C Hash Stability & Simplification ⚠️
- **Task**: Fix content hash implementation for filesystem independence
- **Focus**: Git-style content-addressable storage + simple exact hash matching
- **Location**: `emuses/tools/model_io.py` - `_calculate_content_hash()` method
- **Status**: Phase 2C - Hash Stability Fix (0/4 tasks complete)

### **PHASE 2C**: Hash Stability & Deduplication Simplification (0/4 complete)
- **Task 2C.1**: Fix content hash implementation for filesystem independence ⏳
- **Task 2C.2**: Simplify deduplication to basic exact hash matching ⏳  
- **Task 2C.3**: Remove complex algorithms and interactive workflows ⏳
- **Task 2C.4**: Update tests and documentation for simplified approach ⏳
- **Then Phase 2D**: Storage optimization and concurrent safety (remaining 2/6 tasks)
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