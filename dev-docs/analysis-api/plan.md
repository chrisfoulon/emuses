# Analysis API Enhancement - LAD Implementation Plan

## Implementation Overview

**Goal**: Complete Analysis API Enhancement with critical infrastructure fixes and comprehensive analysis capabilities  
**Duration**: 3.5 weeks across 3 focused sub-plans  
**Focus**: Fix ModelIOManager methods, expose analysis functions, enable inference visualization  
**Dependencies**: ✅ FastAPI infrastructure, existing analysis functions, CLI framework established

## Progress Tracking Protocol
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"  
3. Run tests to verify completion: `python scripts/dev_test_runner.py`
4. Only mark complete after successful testing
5. Update context files with implementation examples

## Implementation Strategy: ENHANCE Existing Infrastructure

**Integration Decision**: **ENHANCE** existing analysis functions and infrastructure  
**Rationale**: Production-ready analysis functions exist, comprehensive FastAPI/CLI framework ready for extension  
**Critical Blocker**: ModelIOManager missing methods must be fixed first

## Sub-Plan Breakdown

### Sub-Plan 0A: Critical Infrastructure Fixes ║ Foundation repair ║ CRITICAL ║ 1 week ✅ **COMPLETED**

### Sub-Plan 0A-Extended: Complete EMUSES Model Registry Redesign ║ Foundation Enhancement ║ CRITICAL ║ 2 weeks

**Focus**: Transform model registry from individual components to complete EMUSES models with intelligent deduplication

**See Detailed Planning**: `/dev-docs/analysis-api/model-registry-redesign/` for comprehensive LAD Phase 0/1 documentation

**Critical Discovery**: Current registry treats UMAP/HDBSCAN/predictions as separate models, but complete EMUSES models must be managed as single cohesive units for sharing and analysis workflows.

- [x] **Task 0A.1: Implement ModelIOManager Missing Methods** ✅ **COMPLETED** ║ `tests/model_registry/test_model_io_manager.py` ║ Core infrastructure ║ L
  - [x] 0A.1.a: Implement `validate_model(model_path) -> Dict[str, Any]` method in `/emuses/tools/model_io.py`
  - [x] 0A.1.b: Implement `install_model(source_path, destination_path, name) -> str` method  
  - [x] 0A.1.c: Add manifest generation from directory structure for models without manifests
  - [x] 0A.1.d: Add directory hash calculation for integrity verification
  - [x] 0A.1.e: Integration with existing `_generate_manifest()` and file hash utilities

- [x] **Task 0A.2: Fix CI Pipeline Dependencies** ✅ **COMPLETED** ║ `tests/model_registry/conftest.py` ║ Build infrastructure ║ S
  - [x] 0A.2.a: Resolve `ModuleNotFoundError: No module named 'fastapi_users'` in CI
  - [x] 0A.2.b: Add conditional imports and pytest.skip for optional dependencies
  - [ ] 0A.2.c: Verify main branch CI passes with all model registry tests
  - [ ] 0A.2.d: Ensure feature branch lightweight CI continues to function

- [x] **Task 0A.3: Enable HDBSCAN Model Registration** ✅ **COMPLETED** ║ `tests/cli/test_models_hdbscan.py` ║ Model type support ║ S  
  - [x] 0A.3.a: Add HDBSCAN to registerable model types in LocalModelRegistry
  - [x] 0A.3.b: Update CLI model installation to support HDBSCAN models
  - [x] 0A.3.c: Test HDBSCAN model discovery and installation workflow
  - [x] 0A.3.d: Fix ModelIOManager integration issue in LocalModelRegistry

- [x] **Task 0A.4: LocalModelRegistry Integration Testing** ✅ **COMPLETED** ║ `tests/model_registry/test_local_registry_real.py` ║ Infrastructure validation ║ M
  - [x] 0A.4.a: Create integration tests using real ModelIOManager methods (no mocks)
  - [x] 0A.4.b: Test complete model installation workflow: validate → install → register
  - [x] 0A.4.c: Verify model registry operations work with new ModelIOManager methods
  - [x] 0A.4.d: Test error handling for invalid models and installation failures

### Sub-Plan 0B: Analysis API & CLI Implementation ║ Core features ║ HIGH ║ 1.5 weeks  

**Focus**: Expose analysis functions through FastAPI endpoints and CLI commands

Copilot Notes: ####

### Statistical Mapping Methods Analysis & Plan Impact

**Discovery**: After investigating `new_pipeline_test` function, we identified two distinct approaches for generating statistical/effect-size maps, each serving different analytical purposes.

#### Method 1: Kernel Regression Optimization (from new_pipeline_test)
**What it is**: 
- **EXCLUSIVELY for sigma optimization**: Uses Optuna to find optimal kernel sigma parameters for each target variable
- Applies kernel regression with nested cross-validation for statistical rigor
- Generates correlation grids and effect-size maps on **scaled embeddings** for each target variable
- **IGNORE from new_pipeline_test**: Prediction models, summary dataframes, performance metrics (modern pipeline handles these)

**Strengths**: Statistically principled, space-descriptive, independent of prediction models, interpretable parameters
**Limitations**: Disconnected from actual trained models, may not reflect real model behavior

#### Method 2: Model-Based Ensemble Predictions (HeatmapStage integration)
**What it is**:
- Uses actual trained prediction models on grid across **scaled UMAP embeddings**
- Applies ensemble predictions for robustness with uncertainty quantification  
- Uses HDBSCAN clustering on spatial coordinates and predictions jointly
- Maps directly reflect what trained models predict
- **Per-target processing**: Generates separate analysis artifacts for each target variable

**Strengths**: Model-representative, ensemble robustness, practical relevance, aligns with current architecture
**Limitations**: Model-dependent, less interpretable than pure statistical approaches

#### Research Evidence & Recommendation
**Neuroimaging Research**: Ensemble approaches provide "accuracy gains" and enable "uncertainty quantification through ensemble variability". Population-based explanation maps "substantially improve coherence and reliability."

**Kernel Regression Evidence**: Comparable performance to deep neural networks with lower computational costs and enhanced interpretability.

#### **STRATEGIC DECISION: Implement Both Methods with Distinct Purposes**

**Primary Approach** (Method 2 - Model-Based): For model interpretation and clinical applications
**Secondary Approach** (Method 1 - Kernel): For statistical validation and space analysis

#### Impact on Implementation Plan:
1. **Task 0B.1** now includes dual-method approach clarification with **per-target variable processing**
2. **Task 0B.3/0B.4** should expose both analysis types with clear use-case documentation
3. **Task 0B.2** must handle parameters for both kernel regression (sigma optimization per target) and model-based (ensemble configuration) approaches
4. **Critical constraint**: Only adapt sigma optimization from `new_pipeline_test` - **DO NOT** modify prediction models, summary dataframes, or performance metrics
5. **Per-target organization**: All analysis artifacts must be organized in corresponding `target_*` folders
6. **Scaled embeddings**: All coordinate operations must use scaled UMAP embeddings, not raw coordinates

#### Architecture Integration Notes:
- **new_pipeline_test**: Extract ONLY sigma optimization logic (Optuna + kernel regression) - ignore all prediction model modifications
- **Target-specific processing**: Each target variable gets independent sigma optimization and correlation analysis
- **Coordinate system**: All analysis operates on scaled embeddings for consistency with modern pipeline
- **Artifact organization**: Maps, correlations, and statistical outputs organized by target variable in `target_*` directories
- **Modern integration**: Current HeatmapStage + features_utils.py provides foundation for Method 2 implementation
- **Remove redundancy**: Eliminate summary dataframes and performance metrics from legacy approach (modern pipeline handles these)

#### **CRITICAL IMPLEMENTATION CONSTRAINTS**:
1. **DO NOT** modify existing prediction models based on `new_pipeline_test`
2. **DO NOT** implement summary dataframes or duplicate performance metrics
3. **DO** extract sigma optimization approach for kernel regression
4. **DO** ensure per-target variable processing for both methods
5. **DO** use scaled embeddings for all coordinate-based operations
6. **DO** organize all outputs in target-specific directory structure

#######

- [ ] **Task 0B.1: Statistical Analysis Requirements Clarification** 🎯 **USER CONSULTATION REQUIRED** ║ Planning session ║ Requirements ║ Planning
  - [ ] 0B.1.a: Review legacy statistical mapping approaches and existing EMUSES functions
  - [ ] 0B.1.b: Clarify requirements for grid predictions, thresholding methods, effect size calculations
  - [ ] 0B.1.c: Identify reusable functions: `input_matrix_stat_map()`, `calculate_correlation_grid()`, `plot_clustering_interactive_with_hover()`
  - [ ] 0B.1.d: Define integration strategy for existing vs new statistical analysis capabilities

- [ ] **Task 0B.2: Analysis Parameter Management System** ║ `tests/tools/test_pipeline_config_extensions.py` ║ Configuration handling ║ M
  - [ ] 0B.2.a: Extend `PipelineConfig` dataclass with statistical analysis parameters
  - [ ] 0B.2.b: Implement parameter validation and default value handling for new analysis fields
  - [ ] 0B.2.c: Add configuration serialization for API request/response (reuse existing patterns)
  - [ ] 0B.2.d: Create parameter transformation utilities for analysis function integration

- [ ] **Task 0B.3: FastAPI Analysis Endpoints** ║ `tests/api/test_analysis_endpoints.py` ║ REST API ║ L
  - [ ] 0B.3.a: Implement `POST /api/v1/analysis/kernel` endpoint with comprehensive parameter validation
  - [ ] 0B.3.b: Implement `POST /api/v1/analysis/correlation` endpoint with request schema validation
  - [ ] 0B.3.c: Add analysis job status tracking and progress monitoring
  - [ ] 0B.3.d: Implement `GET /api/v1/analysis/{job_id}/artifacts/{filename}` for artifact download
  - [ ] 0B.3.e: Add proper error handling, logging, and security validation

- [ ] **Task 0B.4: CLI Analysis Commands** ║ `tests/cli/test_analysis_commands.py` ║ Command interface ║ M
  - [ ] 0B.4.a: Create `emuses models analyze-kernel` command with Rich progress indicators
  - [ ] 0B.4.b: Create `emuses models analyze-correlation` command with parameter validation
  - [ ] 0B.4.c: Add common analysis options: `--output`, `--force`, `--grid-size`, `--threshold`
  - [ ] 0B.4.d: Implement artifact summary display and success confirmation

- [ ] **Task 0B.5: Analysis Artifact Integration** ║ `tests/model_registry/test_analysis_artifacts.py` ║ Artifact management ║ M
  - [ ] 0B.5.a: Extend model registry to support analysis artifact installation
  - [ ] 0B.5.b: Add analysis artifact metadata schema with parent model relationships
  - [ ] 0B.5.c: Implement analysis artifact discovery and listing functionality  
  - [ ] 0B.5.d: Add artifact cleanup and management operations

- [ ] **Task 0B.6: Interactive Visualization System** ║ `tests/visualization/test_interactive_plots.py` ║ Visualization ║ M
  - [ ] 0B.6.a: Restore commented visualization code from HeatmapStage
  - [ ] 0B.6.b: Enhance `plot_clustering_interactive_with_hover()` integration
  - [ ] 0B.6.c: Generate HTML interactive plots with analysis metadata
  - [ ] 0B.6.d: Save visualization artifacts with analysis results

### Sub-Plan 0C: Advanced Features & Integration ║ Enhancement capabilities ║ MEDIUM ║ 1 week

**Focus**: Analysis artifact access, comprehensive testing, advanced API features

**NOTE**: Inference visualization capabilities have been completed through comprehensive CLI parameter enhancement (see `/dev-docs/analysis-api/inference-cli-parameter-fix/`). Remaining tasks focus on analysis-specific API features.

- [x] **Task 0C.1: Enhanced InferenceStage with Analysis Visualization** ✅ **COMPLETED** ║ `dev-docs/analysis-api/inference-cli-parameter-fix/` ║ Inference integration ║ L
  - [x] 0C.1.a: Enhanced inference CLI with comprehensive preprocessing parameters 
  - [x] 0C.1.b: Added all data formatting options (headers, index columns, normalization)
  - [x] 0C.1.c: Added validation mode support with scores processing
  - [x] 0C.1.d: Enhanced InferenceStage integration with modern pipeline architecture

- [ ] **Task 0C.2: Analysis Artifact API** ║ `tests/api/test_artifact_access.py` ║ Programmatic access ║ M
  - [ ] 0C.2.a: Create FastAPI endpoints for analysis artifact discovery
  - [ ] 0C.2.b: Implement permission-controlled access to analysis data  
  - [ ] 0C.2.c: Add programmatic access to embeddings, statistical maps, performance metrics
  - [ ] 0C.2.d: Support custom analysis workflow integration patterns

- [x] **Task 0C.3: Inference Visualization CLI** ✅ **COMPLETED** ║ `dev-docs/analysis-api/inference-cli-parameter-fix/` ║ Advanced CLI ║ M
  - [x] 0C.3.a: Enhanced inference command with comprehensive parameter support
  - [x] 0C.3.b: Added data preprocessing and validation capabilities
  - [x] 0C.3.c: Implemented comprehensive inference workflow with artifact support
  - [x] 0C.3.d: Added progress indicators and comprehensive error handling

- [ ] **Task 0C.4: Research Workflow Integration** ║ `tests/research/test_python_api.py` ║ Python API ║ M  
  - [ ] 0C.4.a: Create Python API for loading analysis artifacts in notebooks/scripts
  - [ ] 0C.4.b: Provide utility functions for custom visualization creation
  - [ ] 0C.4.c: Enable advanced users to extend analysis capabilities
  - [ ] 0C.4.d: Create example notebooks and research workflow documentation

- [ ] **Task 0C.5: Comprehensive Testing Suite** ║ Quality assurance ║ Testing coverage ║ L
  - [ ] 0C.5.a: End-to-end integration tests for complete analysis workflows
  - [ ] 0C.5.b: Performance testing for large-scale analysis scenarios  
  - [ ] 0C.5.c: Security testing for artifact access and permission controls
  - [ ] 0C.5.d: Cross-browser testing for interactive visualizations

- [ ] **Task 0C.6: Documentation and User Guides** ║ User enablement ║ Documentation ║ M
  - [ ] 0C.6.a: Update user guides with analysis API workflows and examples
  - [ ] 0C.6.b: Create analysis visualization tutorials and best practices
  - [ ] 0C.6.c: Document research workflow patterns and Python API usage
  - [ ] 0C.6.d: Create troubleshooting guides for common analysis issues
  - [ ] 0C.6.b: Create analysis visualization tutorials and best practices
  - [ ] 0C.6.c: Document research workflow patterns and Python API usage
  - [ ] 0C.6.d: Create troubleshooting guides for common analysis issues

## Testing Strategy by Component Type

### **API Endpoints** (Integration Testing)
- **Approach**: Real FastAPI app with mocked external dependencies
- **Focus**: Request/response validation, error handling, authentication
- **Coverage Target**: 95% - critical for API reliability

### **CLI Commands** (Integration Testing)
- **Approach**: CliRunner with real filesystem operations in temporary directories
- **Focus**: Parameter validation, user feedback, progress indicators
- **Coverage Target**: 90% - essential for user experience

### **Analysis Functions** (Unit Testing) 
- **Approach**: Isolated testing with test fixtures and known datasets
- **Focus**: Mathematical correctness, parameter handling, artifact generation
- **Coverage Target**: 95% - critical for scientific validity

### **Model Registry Integration** (Component Testing)
- **Approach**: Real database with test fixtures, no external service calls
- **Focus**: Installation workflows, artifact relationships, permission controls  
- **Coverage Target**: 90% - essential for data integrity

## Known Issues - Investigation Required

### Missing .metadata Files in target_* Subdirectories

**Issue**: After implementing normalization fixes, retrained models are missing `.metadata/` directories in `target_*` subdirectories (e.g., `S:\GIN Dropbox\Chris Foulon\EMUSE\HCP_psy\model_registry_final_one_target\target_0\.metadata\`).

**Discovery Context**: During inference testing on 2025-08-26, user retrained model after normalization implementation. The retraining completed successfully and model works for inference, but the target subdirectories lost their `.metadata/` files that contain important prediction model information.

**Impact**: 
- **Inference**: Works correctly (models load and predict successfully)
- **Model Registry**: May not properly detect prediction targets or metadata
- **Analysis API**: Future analysis functions may expect `.metadata/` files for target information

**Root Cause Investigation Attempts** (What didn't work):
1. **Normalization Implementation Review**: The inference mode checks in `emuses_pipeline.py:321` and `emuses_pipeline.py:394-397` prevent normalization during inference but didn't resolve the metadata issue
2. **Model File Pattern Matching**: Fixed glob patterns in `inference_stage.py:326-328` to match new filename patterns, but metadata files are generated elsewhere
3. **optuna_cv.py Fixes**: Fixed 'name' KeyError and optimization_time scope issues, but these were unrelated to metadata generation

**Investigation Focus Areas** (for fresh Claude session):
1. **Target Directory Structure**: Examine how `target_*` subdirectories and `.metadata/` files are generated during training
2. **HeatmapStage Integration**: Check if HeatmapStage or prediction model training generates the `.metadata/` directories
3. **ModelIOManager Role**: Investigate if ModelIOManager or model manifest system should handle `.metadata/` creation
4. **Training vs Inference Logic**: Compare successful old model structure with new model structure to identify missing step
5. **Pipeline Stage Coordination**: Check if metadata generation occurs in a specific pipeline stage that may have been affected

**File Locations to Investigate**:
- `/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/model_registry_final_multi_target/target_0/.metadata/` (working old model)
- `/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/model_registry_final_one_target/target_0/` (missing .metadata)
- `emuses/pipelines/heatmap_stage.py` (prediction model training)
- `emuses/tools/stats_utils.py` (prediction model utilities)
- `emuses/tools/model_io.py` (model saving/loading logic)

**Priority**: HIGH - While inference works, this may block analysis API features and indicates incomplete model training artifacts

**Next Steps**: 
1. Compare directory structures between working and broken models
2. Trace metadata file generation through the training pipeline
3. Identify which training stage creates `.metadata/` directories
4. Fix the metadata generation step that was disrupted by normalization implementation

## Risk Assessment and Mitigation

### **Technical Risks**
- **HIGH - ModelIOManager Methods**: Missing methods block all model operations
  - *Mitigation*: Sub-plan 0A dedicated focus, comprehensive integration testing
- **MEDIUM - Analysis Parameter Complexity**: 19-21 parameters per function
  - *Mitigation*: Structured parameter management, validation layers, user testing
- **LOW - Existing Analysis Functions**: Proven, production-ready functions
  - *Mitigation*: Wrapper approach, minimal changes to core analysis logic

### **Implementation Risks**
- **MEDIUM - API Design Complexity**: Complex parameter management for analysis functions
  - *Mitigation*: User consultation phase (Task 0B.1), iterative refinement
- **MEDIUM - Integration Testing**: Real methods vs mocked dependencies  
  - *Mitigation*: Dedicated integration testing phase, gradual rollout
- **LOW - CLI Integration**: Established Typer patterns and Rich console
  - *Mitigation*: Follow existing model command patterns

## Success Criteria

### **Functional Requirements**
- [ ] ModelIOManager installation workflow fully operational (install_model, validate_model working)
- [ ] Analysis API endpoints respond with valid analysis results and artifacts  
- [ ] CLI analysis commands execute successfully with proper progress indicators
- [ ] Analysis artifacts stored in model registry with proper relationships
- [ ] Inference visualization displays analysis context for new data points

### **Quality Requirements**
- [ ] >90% test coverage for all new functionality (LAD compliance)
- [ ] Performance impact <20% for analysis generation (configurable)
- [ ] Zero regressions in existing EMUSES functionality
- [ ] Comprehensive error handling and user feedback for all failure modes

### **Integration Requirements**
- [ ] Seamless integration with existing FastAPI service and CLI framework
- [ ] Analysis artifacts accessible through model registry permissions system
- [ ] Research-grade access to analysis data for advanced users
- [ ] Complete documentation with working examples and troubleshooting guides

## Maintenance Integration Points

**High Priority Tasks Include Maintenance**:
- Task 0A.1: ModelIOManager implementation includes comprehensive error handling 
- Task 0B.3: FastAPI endpoints include logging and monitoring integration
- Task 0C.5: Testing suite includes maintenance of test coverage standards

**Boy Scout Rule Applications**:
- Complex parameter management improvements during API implementation
- Documentation enhancements for analysis function usage patterns
- Code quality improvements in target files during implementation

## Quality Gates by Sub-Plan

**Sub-Plan 0A Gates**:
- ✅ ModelIOManager methods implemented and tested with real integration
- ✅ All model installation workflows operational without mocks
- ✅ CI pipeline resolving dependencies and passing tests
- ✅ Zero regressions in existing model registry functionality

**Sub-Plan 0B Gates**:
- ✅ Analysis API endpoints functional with parameter validation
- ✅ CLI commands working with progress indicators and error handling  
- ✅ Analysis artifacts generated and registered with proper relationships
- ✅ Interactive visualizations operational and integrated

**Sub-Plan 0C Gates**:
- ✅ Inference visualization displaying analysis artifacts correctly
- ✅ Advanced artifact access functional with permission controls
- ✅ Research workflow tools available with Python API  
- ✅ Comprehensive testing and documentation complete

## Timeline and Dependencies

### **Sub-Plan 0A (Week 1)**
**Dependencies**: None - but blocks all subsequent development  
**Critical Path**: ModelIOManager methods → LocalModelRegistry integration → CI fixes

### **Sub-Plan 0B (Weeks 2-2.5)**  
**Dependencies**: Working ModelIOManager from Sub-plan 0A  
**Critical Path**: Parameter management → API endpoints → CLI commands → Artifact integration

### **Sub-Plan 0C (Weeks 3-3.5)**
**Dependencies**: Analysis API/CLI from Sub-plan 0B  
**Critical Path**: Inference visualization → Advanced API → Testing → Documentation

**Total Duration**: 3.5 weeks for complete implementation with quality validation

This LAD-compliant plan provides systematic implementation with clear dependencies, comprehensive testing, and quality gates while addressing the critical ModelIOManager infrastructure issue that currently blocks model installation workflows.