# EMUSES Project Memory

## Status Maintenance Instructions

**IMPORTANT**: Always read and update `PROJECT_STATUS.md` when:
- Starting new development sessions
- Completing major tasks or features  
- Moving between development phases
- Adding new pending work

## Quick Status for New Sessions

**Current Status**: Analysis API Enhancement - Model Registry Redesign planning complete, ready for implementation

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

## Active Development Context

**Current Branch**: `feature/analysis-api-enhancement`
**Active Phase**: Analysis API Enhancement development

### **CURRENT PRIORITY**: Analysis API Enhancement - Model Registry Redesign
- **Sub-Plan**: 0A-Extended (Complete EMUSES Model Registry Redesign)
- **Duration**: 3 weeks across 3 phases (Foundation → Deduplication → Interface)
- **Feature Location**: `dev-docs/analysis-api/model-registry-redesign/` with comprehensive LAD planning
- **Critical Discovery**: Registry must handle complete EMUSES models as cohesive units
- **Status**: LAD Phase 1d complete - Ready for Phase 1 Foundation implementation
- **Next Step**: Use `plan_1_foundation.md` with LAD Phase 2 iterative implementation

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
*Last Updated: 2025-08-20 - Model Registry Redesign planning complete, ready for Phase 1 implementation*
*Static guidelines in `.lad/CLAUDE.md` | Historical details in `dev-docs/project-history/`*