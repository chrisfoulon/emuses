# EMUSES Project Memory

## Status Maintenance Instructions

**IMPORTANT**: Always read and update `PROJECT_STATUS.md` when:
- Starting new development sessions
- Completing major tasks or features  
- Moving between development phases
- Adding new pending work

## Codebase Knowledge Graph & ADR (codebase-memory-mcp)

This project is indexed in codebase-memory-mcp (project name `home-chrisfoulon-neuro_apps-emuses`). Use it as the primary way to explore and modify code, not just Grep/Read:
- **Explore structure**: `search_graph`, `trace_path`, `get_code_snippet`, `get_architecture` before falling back to Grep/Read.
- **Explore rationale**: `manage_adr(project, mode="get"|"sections")` (backed by `.codebase-memory/adr.md`, tracked in git) records *why*, not *what* — algorithm choices (UMAP/HDBSCAN/Optuna/etc.), architectural decisions (atomic model folders, context-dict stage communication, dual-dataset mode, etc.), and known open issues. **Read the relevant section before changing anything in the areas it covers** — several constraints there (e.g., models are atomic folders, not separable components) were previously violated and had to be reverted.
- **Keep the ADR current**: when you make a new architectural/algorithmic decision, or resolve one of the "Known Constraints and Open Issues" entries, update it via `manage_adr(mode="update")` in the same session — it drifts stale exactly like undocumented code if left untouched.
- **Keep the graph current**: after non-trivial edits (new/renamed/moved functions or files), re-index (`index_repository` or `detect_changes`) so `search_graph`/`trace_path` don't return stale results for the rest of the session.

## Quick Status for New Sessions

**Current Status**: Analysis API Enhancement Foundation Complete - Statistical Analysis + Model Registry + Pipeline Consolidation ✅

**Key Status Files**:
- **PROJECT_STATUS.md** - Central project status
- **`lad:lad-standards` skill** - Static development guidelines and patterns (LAD v2 plugin, loaded automatically)
- **dev-docs/test_quality_conventions.md** - EMUSES-specific testing conventions
- **dev-docs/analysis-api/** - Current feature development context

## Project Mission
**EMUSES** enables neuroimaging research across three contexts:
- **Individual Researchers**: Local model development 
- **Research Labs**: Collaborative sharing with workspaces
- **Scientific Community**: Public registry with peer review

**Current Phase**: Analysis API Enhancement - Foundation Complete, Ready for Core Features

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
- **Analysis API Enhancement - All 6 Phases**: Complete Implementation ✅
  - **Phase 0-1**: Prerequisites, validation, and architecture cleanup
  - **Phase 2**: Core registry implementation with path resolution
  - **Phase 3**: CLI --model-id option and API integration with registry lookup
  - **Phase 4**: Feature augmentation implementation (PCA/kPCA/Autoencoder detection)
  - **Phase 5**: Comprehensive testing and performance validation (3.45ms average lookup)
  - **Phase 6**: Documentation updates and final code cleanup
  - All architectural violations removed, system ready for production use
- **Statistical Analysis Production Ready**: Complete effect size map generation working ✅
  - Fixed cluster overlay visualization, ElasticNet performance, correlation sigma optimization
  - 10x faster training, 35% sharper correlation patterns, warning-free execution
  - Validated with 25 effect size maps generated in production workflow
- **Pipeline Inference Consolidation**: Eliminated architectural duplication ✅
  - Removed double dataset processing between CLI and EMUSESPipeline
  - Single pathway through format_args() handles both training and inference
  - All inference features preserved with improved efficiency

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

### **IMPLEMENTATION STATUS**: All 6 Phases Complete + Post-Fixes Applied ✅
- **Final Achievement**: Complete model registry implementation finished and validated
- **CLI Integration**: --model-id option fully functional with validation and registry lookup
- **API Integration**: Both sync and async inference endpoints support model_id with registry resolution
- **Feature Augmentation**: PCA/kPCA/Autoencoder model detection implemented and ready
- **Code Quality**: All linting issues resolved, duplicate functions removed, clean codebase
- **Documentation**: User guide updated to reflect correct folder-based architecture
- **System Validation**: 13/13 development tests passing, registry operations fully functional
- **Performance**: 3.45ms average lookup time with excellent scalability
- **🔧 Post-Implementation Fix (2025-08-24)**: Model manifest metadata corrected for complete EMUSES models
  - **Issue**: Registry showing component metadata (HDBSCAN) instead of complete model descriptions
  - **Fix**: Enhanced validation to override with EMUSES-specific metadata using path-based heuristics
  - **Result**: Complete models now show proper descriptions like "Complete EMUSES analysis model: HCP_cognitive_analysis. Contains: UMAP, HDBSCAN, 2 prediction targets"
- **Status**: Implementation complete with cosmetic fixes applied, ready for production use
- **Location**: `dev-docs/analysis-api/model-registry-redesign/` with comprehensive documentation

### **COMPLETED**: Pipeline Inference Consolidation (2025-08-31) ✅
- **Architectural Consolidation**: Eliminated double dataset processing in CLI inference
  - **Issue**: CLI `_execute_inference_locally` duplicated EMUSESPipeline initialization logic
  - **Solution**: Enhanced `format_args()` to handle inference mode properly, removed duplication
  - **Phases**: A) Pipeline foundation, B) CLI integration, C) Validation, D) Timedelta compatibility
  - **Result**: Single pathway handles both training and inference with proper context consistency
- **Integration Benefits**: Preserved all inference-specific features while improving efficiency
  - **CLI integration**: Simplified args object creation with inference_mode flag
  - **Context consistency**: InferenceStage receives proper inference_features/inference_labels
  - **Validation**: No duplicate processing confirmed, all existing tests pass
- **Location**: `dev-docs/analysis-api/pipeline-inference-consolidation/` with complete documentation
- **Status**: End-to-end consolidation working correctly ✅

### **COMPLETED**: Inference Performance & Normalization Fixes (2025-08-27) ✅
- **Critical Fix**: UMAP embedding scaling for inference - resolved "all predictions identical" issue
  - **Problem**: Inference used raw UMAP embeddings while training used rescaled embeddings → kernel weights = 0
  - **Solution**: UMAPStage saves min/max parameters to `embedding_scaling.json`, InferenceStage loads them
  - **Result**: Proper embedding scaling restored, predictions now vary by sample
- **Normalization System Consolidation**: Complete overhaul of input/output scaling
  - **Fixed**: EMUSESPipeline `is_labelled=True` not saving input scalers to joblib files 
  - **Enhanced**: InferenceStage dual CSV output (raw + normalized predictions)
  - **Improved**: CLI parameter order consistency (`OUTPUT DATA` instead of `DATA OUTPUT`)
  - **Added**: `robust` scores normalization option to CLI enum
- **Code Quality**: Cleaned debug statements, organized imports, production-ready logging
- **Documentation**: Updated model I/O docs with embedding scaling parameters
- **Files Modified**: `umap_stage.py`, `inference_stage.py`, `emuses_pipeline.py`, CLI components
- **Status**: All inference and normalization issues resolved ✅

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
*Last Updated: 2025-08-31 - Analysis API Enhancement Foundation Complete: Statistical Analysis + Model Registry + Pipeline Consolidation*
*Static guidelines in the `lad:lad-standards` skill | Historical details in `dev-docs/project-history/`*