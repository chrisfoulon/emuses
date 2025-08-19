# Analysis API Enhancement - Comprehensive Implementation Plan

## Implementation Overview

**Goal**: Complete Analysis Ecosystem with inference visualization and advanced artifact access  
**Duration**: 3-4 weeks (critical bug fixes + comprehensive enhancement)  
**Focus**: Fix core infrastructure, implement statistical analysis generation, enable inference visualization  
**Dependencies**: ✅ FastAPI infrastructure, ModelIOManager, inference system

## Progress Tracking Protocol
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"  
3. Run tests to verify completion
4. Only mark complete after successful testing

## Task Breakdown

### Phase 1: Critical Infrastructure Fixes ║ Core system repairs ║ Foundation fixes ║ H

**Risk**: HIGH - Current model installation is completely broken  
**Priority**: CRITICAL - Must be fixed before any other development

- [ ] **Task 1.1: Fix ModelIOManager.install_model() method** ⚠️ **CRITICAL BUG**
  - [ ] 1.1.a: Implement missing `install_model(model_path, destination_path, name)` method
  - [ ] 1.1.b: Return unique model_id string as expected by LocalModelRegistry  
  - [ ] 1.1.c: Handle file copying, directory creation, metadata preservation
  - [ ] 1.1.d: Add comprehensive error handling and validation
  - **Complexity**: Medium (2-3 days) | **Risk**: High (breaking change prevention) | **Files**: `model_io.py`

- [ ] **Task 1.2: Fix ModelIOManager.validate_model() method** ⚠️ **CRITICAL BUG** 
  - [ ] 1.2.a: Implement missing `validate_model(model_path)` method
  - [ ] 1.2.b: Return manifest dict with name, version, type, description
  - [ ] 1.2.c: Validate model file structure and required metadata
  - [ ] 1.2.d: Add clear validation error messages
  - **Complexity**: Medium (1-2 days) | **Risk**: Medium (validation logic) | **Files**: `model_io.py`

- [ ] **Task 1.3: Enable HDBSCAN model registration** 🔧 **ENHANCEMENT**
  - [ ] 1.3.a: Add HDBSCAN models to registerable model types
  - [ ] 1.3.b: Update CLI commands to support HDBSCAN model installation
  - [ ] 1.3.c: Test HDBSCAN model discovery and installation workflow
  - [ ] 1.3.d: Document HDBSCAN model registration in user guides
  - **Complexity**: Low (1 day) | **Risk**: Low (extension of existing pattern) | **Files**: `models_commands.py`

### Phase 2: Statistical Analysis Generation ║ Core analysis features ║ Analysis capabilities ║ M

**Focus**: Generate statistical maps, effect size maps, interactive visualizations during HeatmapStage

- [ ] **Task 2.1: Grid Ensemble Prediction System**
  - [ ] 2.1.a: Implement `_generate_grid_predictions()` for 100x100 embedding space grids
  - [ ] 2.1.b: Use InferenceStage-style ensemble predictions for consistency
  - [ ] 2.1.c: Generate confidence scores and uncertainty quantification
  - [ ] 2.1.d: Save grid prediction artifacts for later visualization use
  - **Complexity**: Medium (2-3 days) | **Risk**: Medium (integration complexity) | **Files**: `heatmap_stage.py`

- [ ] **Task 2.2: Statistical Map Generation System**
  - [ ] 2.2.a: Implement cluster-based effect size comparisons in original feature space
  - [ ] 2.2.b: Generate statistical maps using existing `input_matrix_stat_map()`
  - [ ] 2.2.c: Apply prediction thresholds: `(prediction + confidence) / 2`
  - [ ] 2.2.d: Save statistical maps in multiple formats (PNG, NPZ, CSV)
  - **Complexity**: Medium (2-3 days) | **Risk**: Low (uses existing functions) | **Files**: `heatmap_stage.py`

- [ ] **Task 2.3: Interactive Visualization System** 
  - [ ] 2.3.a: Restore and enhance commented visualization code from HeatmapStage
  - [ ] 2.3.b: Generate HTML interactive plots using `plot_clustering_interactive_with_hover()`
  - [ ] 2.3.c: Create embeddingss colored by scores and cluster assignments
  - [ ] 2.3.d: Save interactive plots with hover data and metadata
  - **Complexity**: Low (1-2 days) | **Risk**: Low (restoration of existing code) | **Files**: `heatmap_stage.py`

### Phase 3: Extended Analysis Artifact Access ║ Advanced user capabilities ║ Artifact management ║ M

**Focus**: Provide comprehensive access to analysis artifacts for inference visualization and advanced analysis

- [ ] **Task 3.1: Analysis Artifact Package System**
  - [ ] 3.1.a: Extend ModelIOManager to save analysis artifacts alongside models
  - [ ] 3.1.b: Create structured artifact packages (models + analysis data + permissions)
  - [ ] 3.1.c: Implement artifact bundle installation and access
  - [ ] 3.1.d: Add permission controls for sensitive training data access
  - **Complexity**: High (3-4 days) | **Risk**: Medium (new system integration) | **Files**: `model_io.py`, `local_model_registry.py`

- [ ] **Task 3.2: Training Data Preservation System**
  - [ ] 3.2.a: Save raw embeddings (UMAP coordinates) as `.npy` files
  - [ ] 3.2.b: Save scaled embeddings and preprocessing parameters
  - [ ] 3.2.c: Save cluster labels and clustering model parameters
  - [ ] 3.2.d: Save training labels with privacy/permission controls
  - **Complexity**: Medium (2-3 days) | **Risk**: Low (data preservation extension) | **Files**: `heatmap_stage.py`, `UMAP_utils.py`

### Phase 4: Inference Visualization Integration ║ Advanced inference capabilities ║ Visualization enhancement ║ H

**Focus**: Enable visualization of new data points on existing heatmaps and clusters

- [ ] **Task 4.1: Enhanced InferenceStage with Visualization**
  - [ ] 4.1.a: Extend InferenceStage to load analysis artifacts alongside models  
  - [ ] 4.1.b: Generate overlay visualizations showing new data on existing heatmaps
  - [ ] 4.1.c: Assign new data points to existing clusters using trained HDBSCAN models
  - [ ] 4.1.d: Display relevant effect size maps for clusters containing new data
  - **Complexity**: High (4-5 days) | **Risk**: High (complex integration) | **Files**: `inference_stage.py`

- [ ] **Task 4.2: Inference Visualization CLI Enhancement**
  - [ ] 4.2.a: Add `--visualize` flag to `emuses inference` command
  - [ ] 4.2.b: Generate inference overlay plots as HTML files
  - [ ] 4.2.c: Export relevant effect size maps and cluster assignments
  - [ ] 4.2.d: Create comprehensive inference visualization reports
  - **Complexity**: Medium (2-3 days) | **Risk**: Medium (CLI integration) | **Files**: `main.py`, CLI commands

### Phase 5: Advanced User API ║ Programmatic access ║ Research flexibility ║ M

**Focus**: Provide programmatic access to raw analysis data for advanced users

- [ ] **Task 5.1: Analysis Artifact API**
  - [ ] 5.1.a: Create FastAPI endpoints for artifact discovery and download
  - [ ] 5.1.b: Implement permission-controlled access to training data
  - [ ] 5.1.c: Provide programmatic access to embeddings, labels, clusters
  - [ ] 5.1.d: Enable custom analysis workflow support
  - **Complexity**: Medium (3-4 days) | **Risk**: Medium (API design complexity) | **Files**: FastAPI endpoints

- [ ] **Task 5.2: Research Workflow Integration**
  - [ ] 5.2.a: Create Python API for loading analysis artifacts
  - [ ] 5.2.b: Provide utility functions for custom visualization creation
  - [ ] 5.2.c: Enable advanced users to extend analysis capabilities
  - [ ] 5.2.d: Document research workflow patterns and examples
  - **Complexity**: Medium (2-3 days) | **Risk**: Low (utility extension) | **Files**: New utility modules

### Phase 6: Testing and Documentation ║ Quality assurance ║ User enablement ║ L

**Focus**: Comprehensive testing and documentation for all new capabilities

- [ ] **Task 6.1: Comprehensive Testing Suite**
  - [ ] 6.1.a: Unit tests for all new methods (install_model, validate_model, etc.)
  - [ ] 6.1.b: Integration tests for analysis artifact generation and access
  - [ ] 6.1.c: End-to-end tests for inference visualization workflows
  - [ ] 6.1.d: Performance tests for large-scale analysis scenarios
  - **Complexity**: High (4-5 days) | **Risk**: Medium (comprehensive coverage) | **Testing**: >90% coverage target

- [ ] **Task 6.2: User Documentation and Examples**
  - [ ] 6.2.a: Update user guides with analysis artifact workflows
  - [ ] 6.2.b: Create inference visualization examples and tutorials
  - [ ] 6.2.c: Document advanced user API and research workflows
  - [ ] 6.2.d: Create troubleshooting guides for common issues
  - **Complexity**: Medium (3-4 days) | **Risk**: Low (documentation) | **Deliverables**: Complete user guides

### Phase 7: CI Pipeline Fixes ║ Infrastructure repair ║ Build system ║ M

**Focus**: Fix CI pipeline issues preventing successful builds on main branch

- [ ] **Task 7.1: Dependency Resolution Fixes** ⚠️ **CI BLOCKING**
  - [ ] 7.1.a: Fix `ModuleNotFoundError: No module named 'fastapi_users'` in model_registry tests
  - [ ] 7.1.b: Add missing dependencies to requirements files or CI configuration
  - [ ] 7.1.c: Resolve import errors in `tests/model_registry/conftest.py:17`
  - [ ] 7.1.d: Test model registry test suite runs successfully
  - **Complexity**: Low (1 day) | **Risk**: Low (dependency management) | **Files**: CI config, requirements files

- [ ] **Task 7.2: CI Pipeline Validation and Testing**
  - [ ] 7.2.a: Run full CI pipeline locally to identify all failing tests
  - [ ] 7.2.b: Fix additional CI pipeline issues discovered during testing
  - [ ] 7.2.c: Validate main branch CI passes with all tests
  - [ ] 7.2.d: Ensure feature branch CI continues to work with lightweight testing
  - **Complexity**: Medium (2-3 days) | **Risk**: Medium (CI stability) | **Files**: CI workflows, test configurations

**CI Error Context**:
```bash
# Current main branch CI failure:
Run pytest tests/model_registry/ tests/tools/ tests/unit/ -v --maxfail=10 --tb=short
ImportError while loading conftest '/home/runner/work/emuses/emuses/tests/model_registry/conftest.py'.
tests/model_registry/conftest.py:17: in <module>
    from emuses.multi_user_service.models import User
emuses/multi_user_service/models.py:10: in <module>
    from fastapi_users.db import SQLAlchemyBaseUserTableUUID
E   ModuleNotFoundError: No module named 'fastapi_users'
Error: Process completed with exit code 4
```

**CI Strategy**:
- **Feature Branches**: Lightweight CI (13 tests, ~1 minute, minimal credits)
- **Main Branch**: Full CI with PostgreSQL/Redis services (comprehensive validation)
- **Fix Priority**: Resolve main branch CI first, then validate feature branch CI compatibility

## Testing Strategy

### Component Testing Approach (LAD Guidelines)
- **ModelIOManager fixes**: Unit tests with mock file systems and validation scenarios
- **Analysis generation**: Integration tests with realistic neuroimaging datasets
- **Inference visualization**: End-to-end tests with known training/inference data pairs
- **Artifact access**: Permission and security testing with multi-user scenarios

### Quality Assurance Requirements
- **Functional Correctness**: All analysis results match existing function outputs
- **No Regressions**: Existing workflows continue to work without modification
- **Performance**: Analysis and visualization generation within acceptable limits
- **Security**: Permission controls properly isolate sensitive training data

## Risk Assessment and Mitigation

### Technical Risks
- **HIGH - Model Installation System**: Critical infrastructure is broken
  - *Mitigation*: Fix install_model() and validate_model() first, comprehensive testing
- **MEDIUM - Inference Integration**: Complex integration with existing InferenceStage
  - *Mitigation*: Progressive enhancement approach, maintain backward compatibility
- **LOW - Analysis Generation**: Uses existing, proven functions
  - *Mitigation*: Wrapper approach, minimal changes to core analysis logic

### Implementation Risks  
- **MEDIUM - Code Breaking**: Changes to core ModelIOManager could break existing workflows
  - *Mitigation*: Extensive testing, gradual rollout, feature flags for new capabilities
- **LOW - Performance**: Analysis artifact generation could impact pipeline performance
  - *Mitigation*: Make analysis generation configurable, optimize artifact access patterns

## Success Criteria

### Functional Requirements
- [ ] Model installation system is fully functional (install_model, validate_model working)
- [ ] Statistical analysis artifacts generated during HeatmapStage execution
- [ ] Inference visualization shows new data placement on existing analysis
- [ ] Advanced users can access raw analysis data for custom workflows
- [ ] All existing EMUSES functionality preserved without regressions

### Quality Requirements  
- [ ] >90% test coverage for all new functionality (LAD compliance)
- [ ] Performance impact <20% for analysis generation (configurable)
- [ ] Complete documentation with working examples
- [ ] Security controls properly implemented for sensitive data access

### User Experience Requirements
- [ ] Seamless integration with existing EMUSES workflows
- [ ] Clear progression from basic to advanced analysis capabilities
- [ ] Comprehensive inference visualization without complex setup
- [ ] Research-grade access to raw data for advanced users

## Time and Complexity Estimates

### Development Time Breakdown
- **Phase 1 (Critical Fixes)**: 1 week (HIGH PRIORITY)
- **Phase 2 (Analysis Generation)**: 1.5 weeks 
- **Phase 3 (Artifact Access)**: 1 week
- **Phase 4 (Inference Visualization)**: 1.5 weeks
- **Phase 5 (Advanced API)**: 1 week
- **Phase 6 (Testing/Documentation)**: 1 week
- **Phase 7 (CI Pipeline Fixes)**: 0.5 weeks (CI repair)

**Total Estimated Duration**: 3.5-4.5 weeks for complete implementation

### Complexity Assessment
- **High Complexity**: Inference visualization integration, analysis artifact packaging
- **Medium Complexity**: Statistical analysis generation, artifact access system
- **Low Complexity**: HDBSCAN registration, interactive visualization restoration

This comprehensive plan transforms EMUSES from a model training system into a complete analysis ecosystem with inference visualization and advanced research capabilities while fixing critical infrastructure bugs and maintaining full backward compatibility.