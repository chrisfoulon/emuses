# EMUSES Project Memory

## Status Maintenance Instructions

**IMPORTANT**: Always read and update `PROJECT_STATUS.md` when:
- Starting new development sessions
- Completing major tasks or features  
- Moving between development phases
- Adding new pending work

## Quick Status for New Sessions

**Current Status**: Model Registry Architecture Fix - LAD Review Integration Complete - Ready for Implementation ⚠️

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
- **Analysis API Enhancement - Phase 2**: Hash Stability & Storage Optimization ✅
  - Git-style content-addressable storage for cross-platform model sharing
  - Simplified exact-match duplicate detection with 0% false positive rate
  - Shared component storage optimization reducing disk usage
  - Thread-safe concurrent access with comprehensive mutex/locking
  - 16 new tests covering hash stability, storage optimization, and concurrent safety

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

### **COMPLETED**: Analysis API Enhancement - Model Registry Redesign Phase 2 ✅
- **Phase 2C**: Hash Stability & Deduplication Simplification - ALL COMPLETE ✅
  - ✅ Fixed content hash implementation for filesystem independence (Git-style content addressing)
  - ✅ Simplified deduplication to basic exact hash matching
  - ✅ Removed complex algorithms and interactive workflows
  - ✅ Updated tests and documentation for simplified approach
- **Phase 2D**: Storage Optimization & Concurrent Safety - ALL COMPLETE ✅
  - ✅ Implemented storage optimization with shared component storage
  - ✅ Added concurrent access testing and mutex/locking for registry operations
- **Implementation**: Hash stability fixes, storage optimization, concurrent safety
- **Testing**: 16 additional tests for hash stability, storage optimization, and concurrent access

### **CRITICAL STATUS CORRECTION**: Previous Claims Were Incorrect ⚠️
- **Discovery**: Implementation contains fundamental architectural violations
- **Issue**: CompleteEmusesModel class treats EMUSES components as separable (architecturally wrong)
- **Truth**: EMUSES models are complete folder units, components NOT interchangeable
- **Action Required**: Delete violations, implement registry as folder lookup service only
- **Status**: LAD review integration complete, validated implementation plan ready
- **Location**: `dev-docs/analysis-api/model-registry-redesign/`

### **URGENT: Implementation Requirements** ⚠️
- **MANDATORY READING**: `dev-docs/analysis-api/model-registry-redesign/review-integration/architectural_guardrails.md`
- **MANDATORY TEST**: `dev-docs/analysis-api/model-registry-redesign/review-integration/proof_of_concept_test.py`
- **Implementation Plan**: `dev-docs/analysis-api/model-registry-redesign/plan.md` (6 phases, LAD-validated)
- **Context**: `dev-docs/analysis-api/model-registry-redesign/context.md` (correct architecture)
- **Session Handover**: `dev-docs/analysis-api/model-registry-redesign/SESSION_HANDOVER.md`

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
*Last Updated: 2025-08-22 - CRITICAL: Architecture violations discovered, LAD review integration complete, corrected implementation plan ready*
*Static guidelines in `.lad/CLAUDE.md` | Historical details in `dev-docs/project-history/`*