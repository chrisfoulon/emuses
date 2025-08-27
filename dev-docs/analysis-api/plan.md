# Analysis API Enhancement - LAD Implementation Plan

## Implementation Overview

**Goal**: Implement statistical maps and heatmap analysis functionality in HeatmapStage with API/CLI interfaces  
**Approach**: ENHANCE HeatmapStage with grid creation and statistical analysis after nested CV training  
**Foundation**: Model registry, multi-user service, and inference fixes are complete and operational  
**Core Implementation**: Extract from new_pipeline_test + complete HeatmapStage statistical analysis (lines 431-686)  

## Progress Tracking Protocol
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"  
3. Run tests to verify completion: `python scripts/dev_test_runner.py`
4. Only mark complete after successful testing
5. Update context files with implementation examples

## Task Complexity Assessment
- **Task Complexity**: **MEDIUM-HIGH**
- **Implementation Approach**: HeatmapStage enhancement with modular grid creation and statistical analysis functions
- **Key Challenges**: Grid generation with simplified inference, statistical analysis implementation, confidence aggregation
- **Resource Requirements**: 7-10 days focused development across 3 phases

## Implementation Strategy

### LAD Phase 00: Existing Work Discovery Results ✅
- **Integration Decision**: **ENHANCE** HeatmapStage pipeline with statistical analysis functionality
- **Existing Quality**: Modern foundations in new_pipeline_test + HeatmapStage architecture
- **Coverage**: 40% (pipeline architecture exists, statistical analysis commented/incomplete)
- **Rationale**: Build on modern patterns, avoid legacy function approaches

### LAD Phase 01: Implementation Planning ✅  
- **Multi-level context**: Completed with corrected technical understanding
- **Architecture understanding**: HeatmapStage enhancement after nested CV training
- **Maintenance opportunities**: Modular function design for maintainability
- **Testing strategy**: Component-aware (unit for functions, integration for pipeline)

## Feature Requirements (Corrected Technical Approach)

### Triple-Analysis Implementation  
1. **Prediction Grid**: 100x100 coordinate grid → simplified inference → prediction*confidence heatmaps
2. **Correlation Grid**: 100x100 coordinate grid → GWD vectors → correlation with target scores (Pearson/Spearman/point-biserial)
3. **Statistical Maps**: Region-based analysis → two-stage filtering → clustering within regions → effect size maps

### Critical Implementation Constraints  
- **Pipeline Timing**: AFTER nested CV model training in HeatmapStage (models loaded in context)
- **Grid Coordinates**: 100x100 linspace on rescaled embeddings (0-1 coordinate system)
- **Sigma Optimization**: Kernel regression optimization for optimal sigma parameter (correlation grids)
- **Two-Stage Filtering**: Visualization threshold (0.2) + effect size threshold (0.5) for region selection
- **Region-Based Clustering**: HDBSCAN clusters within high-confidence regions (≥3 points per cluster)
- **Per-target artifacts**: Grid-based organization with `prediction-grids/`, `correlation-grids/`, `statistical-maps-prediction/`, and `statistical-maps-correlation/` folders in each `target_*/` directory
- **Multiple Correlation Methods**: Support Pearson, Spearman, point-biserial correlation analysis
- **Effect Size Calculation**: Mann-Whitney tests via input_matrix_stat_map function
- **Grid-Based Statistical Maps**: Different statistical maps based on filtering method (prediction-based vs correlation-based regions)

## Implementation Phases

### Phase 1: HeatmapStage Enhancement ║ Triple Grid System & Statistical Analysis ║ HIGH ║ 4-5 days

- [ ] **Task 1.1: Prediction Grid Creation System** ║ `tests/analysis_api/test_prediction_grid.py` ║ 100x100 coordinate grid with simplified inference ║ M
  - [ ] 1.1.a: Create grid coordinate generation function (100x100 linspace on 0-1 rescaled embeddings)
  - [ ] 1.1.b: Implement simplified inference function (skip input transformation, use context models)
  - [ ] 1.1.c: Add confidence aggregation (5-model confidence or CV ensemble 1-std approach)
  - [ ] 1.1.d: Implement prediction*confidence heatmap generation with denormalization

- [ ] **Task 1.2: Correlation Grid Creation System** ║ `tests/analysis_api/test_correlation_grid.py` ║ GWD-based correlation analysis ║ M
  - [ ] 1.2.a: Implement GWD vector computation for grid points (compute_gwd_for_point integration)
  - [ ] 1.2.b: Add sigma optimization via kernel regression (extract from new_pipeline_test)
  - [ ] 1.2.c: Implement multiple correlation methods (Pearson, Spearman, point-biserial)
  - [ ] 1.2.d: Create correlation heatmap generation with target score correlation analysis

- [ ] **Task 1.3: Region-Based Statistical Analysis** ║ `tests/analysis_api/test_region_statistical_analysis.py` ║ Two-stage filtering with clustering ║ M
  - [ ] 1.3.a: Implement two-stage threshold filtering (visualization + effect size thresholds)
  - [ ] 1.3.b: Add region-based clustering analysis (HDBSCAN clusters within high-confidence regions)
  - [ ] 1.3.c: Integrate input_matrix_stat_map for effect size calculation (Mann-Whitney tests)
  - [ ] 1.3.d: Create statistical maps for clusters with ≥3 points per cluster

### Phase 2: API & CLI Integration ║ FastAPI Endpoints & CLI Commands ║ HIGH ║ 2-3 days

- [ ] **Task 2.1: FastAPI Analysis Endpoints** ║ `tests/analysis_api/test_analysis_endpoints.py` ║ REST API endpoints for triple analysis ║ L
  - [ ] 2.1.a: Implement `POST /api/v1/analysis/statistical-maps` endpoint with region-based analysis
  - [ ] 2.1.b: Implement `POST /api/v1/analysis/heatmaps` endpoint (prediction + correlation grids)
  - [ ] 2.1.c: Add per-target processing with grid-based folder organization (prediction-grids/, correlation-grids/, statistical-maps-prediction/, statistical-maps-correlation/)
  - [ ] 2.1.d: Implement error handling, correlation method validation, sigma optimization support

- [ ] **Task 2.2: Enhanced Parameter Management** ║ `tests/analysis_api/test_parameter_management.py` ║ Triple analysis request models ║ M
  - [ ] 2.2.a: Create enhanced request models (correlation methods, sigma optimization, threshold parameters)
  - [ ] 2.2.b: Add two-stage filtering parameter validation (visualization + effect size thresholds)
  - [ ] 2.2.c: Implement correlation method selection and validation (Pearson/Spearman/point-biserial)
  - [ ] 2.2.d: Add cluster size threshold and region-based analysis parameter handling

- [ ] **Task 2.3: HeatmapStage Integration** ║ `tests/analysis_api/test_heatmap_stage_integration.py` ║ Pipeline enhancement and artifacts ║ L
  - [ ] 2.3.a: Uncomment and enhance HeatmapStage statistical analysis code (lines 431-686)
  - [ ] 2.3.b: Integrate triple grid system after nested CV training (models available in context)
  - [ ] 2.3.c: Implement per-target artifact organization with grid-based statistical maps (statistical-maps-prediction/, statistical-maps-correlation/)
  - [ ] 2.3.d: Add interactive visualization enhancement with plot_clustering_interactive_with_hover

### Phase 3: CLI Commands & Documentation ║ Command-line Interface & User Experience ║ MEDIUM ║ 2-3 days

- [ ] **Task 3.1: CLI Analysis Commands (DEFERRED)** ║ `tests/analysis_api/test_cli_commands.py` ║ Independent CLI analysis execution ║ L
  - [ ] 3.1.a: Design modular functions for future CLI independence (model loading, normalization)
  - [ ] 3.1.b: Assess CLI implementation complexity vs value (DEFERRED unless high success/low risk)
  - [ ] 3.1.c: Document CLI independence requirements for future implementation
  - [ ] 3.1.d: Create foundation for standalone analysis commands

- [ ] **Task 3.2: Interactive Visualization Enhancement** ║ `tests/analysis_api/test_visualization.py` ║ HTML plots with statistical analysis metadata ║ M
  - [ ] 3.2.a: Enhance plot_clustering_interactive_with_hover integration with statistical maps
  - [ ] 3.2.b: Add heatmap visualization with prediction*confidence overlays
  - [ ] 3.2.c: Create visualization artifact preservation in per-target folders
  - [ ] 3.2.d: Implement responsive design and metadata integration

- [ ] **Task 3.3: Documentation & Testing** ║ `tests/analysis_api/test_documentation.py` ║ User guides and comprehensive testing ║ S
  - [ ] 3.3.a: Update user guides with HeatmapStage statistical analysis workflows
  - [ ] 3.3.b: Document grid creation and statistical maps generation approaches
  - [ ] 3.3.c: Create troubleshooting guides for confidence aggregation and denormalization
  - [ ] 3.3.d: Comprehensive testing across modular functions and pipeline integration

## Testing Strategy by Component Type

### **API Endpoints** (Integration Testing)
- **Approach**: Real FastAPI app with mocked external dependencies
- **Focus**: Request/response validation, model registry integration, error handling
- **Coverage Target**: 95% - critical for API reliability

### **CLI Commands** (Integration Testing)
- **Approach**: CliRunner with real filesystem operations in temporary directories  
- **Focus**: Parameter validation, progress indicators, registry lookup workflows
- **Coverage Target**: 90% - essential for user experience

### **Analysis Orchestration** (Unit Testing)
- **Approach**: Isolated testing with mocked analysis functions and test fixtures
- **Focus**: Parameter transformation, method selection, per-target processing logic
- **Coverage Target**: 95% - critical for dual-method coordination

### **Artifact Management** (Component Testing)
- **Approach**: Real registry operations with test databases, no external service calls
- **Focus**: Installation workflows, artifact relationships, metadata handling
- **Coverage Target**: 90% - essential for data integrity

## Maintenance Integration Points

### High Priority Tasks Include Maintenance
- Task 1.2: FastAPI endpoints include logging and monitoring integration following existing patterns
- Task 1.3: CLI commands include error handling standardization across analysis workflows
- Task 3.3: Documentation includes analysis function documentation enhancement opportunities

### Boy Scout Rule Applications
- Parameter management system optimization during API implementation
- Error handling standardization across analysis workflows during CLI development  
- Analysis function integration pattern improvements during orchestration development

## Risk Assessment and Mitigation

### **Technical Risks**
- **HIGH - Triple Grid System Complexity**: Prediction + correlation + statistical maps with different methodologies
  - *Mitigation*: Modular class design, incremental testing, reuse existing GWD/correlation patterns
- **HIGH - Sigma Optimization Integration**: Extract kernel regression optimization for correlation grids
  - *Mitigation*: Leverage existing compute_sigma_median and new_pipeline_test sigma optimization patterns
- **MEDIUM - Region-Based Statistical Analysis**: Two-stage filtering + clustering within regions + effect size calculation
  - *Mitigation*: Reuse existing input_matrix_stat_map function, incremental cluster size validation
- **MEDIUM - Correlation Method Support**: Multiple correlation methods with proper validation
  - *Mitigation*: Leverage existing correlation_maps_utils.py patterns, comprehensive parameter validation

### **Implementation Risks** 
- **MEDIUM - HeatmapStage Integration**: Uncomment and enhance lines 431-686 without breaking existing pipeline
  - *Mitigation*: Careful testing, modular integration, preserve existing functionality
- **MEDIUM - Denormalization Logic**: Ensure predictions denormalized to original value range correctly
  - *Mitigation*: Reuse existing denormalization patterns from InferenceStage
- **LOW - Registry Integration**: Established patterns and working model registry system
  - *Mitigation*: Follow existing registry integration patterns from inference implementation

## Success Criteria

### **Functional Requirements**
- [ ] HeatmapStage generates triple grid system: prediction*confidence + GWD correlation + statistical maps
- [ ] Correlation grids use sigma optimization and multiple correlation methods (Pearson/Spearman/point-biserial)
- [ ] Region-based statistical analysis with two-stage filtering and clustering within high-confidence regions
- [ ] Per-target processing creates grid-based folders: prediction-grids/, correlation-grids/, statistical-maps-prediction/, statistical-maps-correlation/ in target_*/ directories
- [ ] API endpoints support triple analysis with correlation method selection and threshold parameters
- [ ] Effect size maps generated for clusters with ≥3 points using input_matrix_stat_map (Mann-Whitney tests)

### **Quality Requirements**
- [ ] >90% test coverage for all new functionality (LAD compliance)
- [ ] Performance impact <20% for analysis generation compared to direct function calls
- [ ] Zero regressions in existing EMUSES functionality (model registry, inference, CLI)
- [ ] Comprehensive error handling and user feedback for all failure modes
- [ ] Per-target processing working correctly with scaled embeddings usage

### **Integration Requirements**
- [ ] Seamless integration with existing FastAPI service and CLI framework
- [ ] Analysis artifacts accessible through model registry permissions system  
- [ ] Target-specific directory organization working with registry artifact management
- [ ] Complete documentation with working examples and dual-method use case guidance

## Completed Infrastructure (Do Not Modify)

### ✅ Model Registry System (6 phases complete + quality fixes)
- `ModelIOManager.validate_model()` and `install_model()` methods functional
- CLI `--model-id` option working with registry lookup
- LocalModelRegistry operations fully tested and operational

### ✅ Multi-User Service Implementation  
- FastAPI-Users integration with enterprise security (HashiCorp Vault)
- Admin CLI commands for user management, quotas, system monitoring
- Production-ready with comprehensive documentation

### ✅ Inference Performance & Normalization Fixes
- UMAP embedding scaling (`embedding_scaling.json` saving/loading)
- Input scaler bug fixes in EMUSESPipeline (`is_labelled=True` branch)
- Dual CSV output in InferenceStage (raw + normalized predictions)
- "Zero predictions" issue resolved with proper embedding scaling

### ✅ Modern Analysis Foundations (Ready for Enhancement)
- **new_pipeline_test** in `/emuses/tools/stats_utils.py:1477` - Advanced statistical analysis with Optuna optimization
- **HeatmapStage** in `/emuses/pipelines/heatmap_stage.py:431-686` - Commented statistical analysis code to be completed
- **plot_clustering_interactive_with_hover** - Interactive visualization function ready for integration
- **Scaled embeddings infrastructure** - prediction_train_coords available in pipeline context

---

**Implementation Status**: Ready to begin Phase 1 - HeatmapStage Enhancement with Triple Grid System  
**Next Step**: Task 1.1 - Prediction Grid Creation System implementation  
**Key Success Factor**: Implement sophisticated correlation + region-based analysis while maintaining modular design for maintainability

*This plan follows LAD Phase 00 (Existing Work Discovery) and Phase 01 (Autonomous Context Planning) methodologies for systematic implementation with proper integration assessment and architectural understanding.*