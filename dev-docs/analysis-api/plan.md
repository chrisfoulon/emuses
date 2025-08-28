# Statistical Analysis Enhancement - LAD Implementation Plan

## Task Complexity Assessment

**Task Complexity**: MEDIUM  
**Implementation Approach**: ENHANCE existing production-quality modular components  
**Key Challenges**: Dual effect analysis integration, visualization enhancement, folder structure updates  
**Resource Requirements**: 2-3 implementation sessions, minimal disruption to working system

## Integration Impact Assessment (From LAD Phase 0)

**Strategy**: ENHANCE existing components (85% requirement coverage)
- [x] **Architecture Assessment**: Production-ready modular components identified
- [x] **Integration Points**: HeatmapStage after nested CV training (working)
- [x] **Compatibility**: Backwards compatible enhancements to existing APIs
- [x] **Quality Validation**: 90%+ test coverage, 13/13 development tests passing

## Progress Tracking Protocol

**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"  
3. Run tests to verify completion: `python scripts/dev_test_runner.py`
4. Only mark complete after successful testing
5. Update context files with implementation examples

## Scientific Methodology Framework (NON-NEGOTIABLE)

### Two-Heatmap Approach (Validated)
**Why This Framework Works**:
- **Separates intrinsic manifold structure from predictive relationships**
- **No kernel regression variability issues** 
- **Robust and interpretation-stable**
- **Provides three complementary explainability perspectives**

#### Heatmap 1: Prediction×Confidence
- **Purpose**: Shows actual trained model behavior across embedding space
- **Method**: Uses existing models from `context["prediction_models"]` 
- **Formula**: `prediction_mean * (1.0 / (1.0 + prediction_std))`
- **Interpretation**: "How do the models we'll use for prediction behave?"

#### Heatmap 2: Correlation 
- **Purpose**: Shows UMAP's learned manifold structure correlation with target
- **Method**: Uses median pairwise distance sigma (NO optimization/training)
- **Formula**: `pearsonr(gwd_vector, target_scores)` for each grid point
- **Interpretation**: "How does inherent data topology relate to target patterns?"

### Critical Implementation Requirements
1. **No Model Training**: Must use `context["prediction_models"]` exclusively
2. **Median Sigma Only**: Use `compute_sigma_median()`, no optimization
3. **Two-Heatmap Separation**: Maintain distinction between prediction and correlation analysis

## Implementation Phases

### ✅ Phase 1: HeatmapStage Enhancement (COMPLETE)
- [x] GridCreator: Prediction heatmaps with existing models
- [x] CorrelationGridCreator: Median sigma correlation analysis  
- [x] RegionStatisticalAnalyzer: Effect size maps with clustering

### ✅ Phase 2: API & CLI Integration (COMPLETE)
- [x] FastAPI endpoints: `/api/v1/analysis/heatmaps`, `/api/v1/analysis/statistical-maps`
- [x] Enhanced parameter management with correlation methods
- [x] HeatmapStage integration after nested CV training

### Phase 3: Enhancement Implementation ║ Folder Structure & Visualization Updates ║ MEDIUM ║ 2-3 sessions

- [ ] **Task 3.1: Folder Structure Updates** ║ `tests/analysis_api/test_folder_naming.py` ║ Update "grids" → "heatmaps" in modular tools ║ S
  - [ ] 3.1.a: Update GridCreator output folder naming
    - [ ] 3.1.a.1: Change `prediction-grids/` → `prediction-heatmaps/` in create_prediction_heatmaps()
    - [ ] 3.1.a.2: Update folder creation logic and path references
    - [ ] 3.1.a.3: Verify backwards compatibility with existing artifacts
  - [ ] 3.1.b: Update CorrelationGridCreator output folder naming  
    - [ ] 3.1.b.1: Change `correlation-grids/` → `correlation-heatmaps/` in create_correlation_heatmaps()
    - [ ] 3.1.b.2: Update folder creation logic and path references
    - [ ] 3.1.b.3: Verify backwards compatibility with existing artifacts

- [ ] **Task 3.2: Dual Effect Size Maps Implementation** ║ `tests/analysis_api/test_dual_effects.py` ║ Separate prediction and correlation effect analysis ║ M
  - [ ] 3.2.a: Enhance RegionStatisticalAnalyzer for dual analysis pattern
    - [ ] 3.2.a.1: Add significance_source parameter to create_statistical_maps()
    - [ ] 3.2.a.2: Update output folder naming based on significance source
    - [ ] 3.2.a.3: Maintain consistent metadata format across both analyses
  - [ ] 3.2.b: Update HeatmapStage integration for dual analysis calls
    - [ ] 3.2.b.1: Run RegionStatisticalAnalyzer for prediction significance → prediction-effects/
    - [ ] 3.2.b.2: Run RegionStatisticalAnalyzer for correlation significance → correlation-effects/
    - [ ] 3.2.b.3: Use appropriate quantile thresholds (95th percentile for prediction, 95th percentile absolute for correlation)

- [ ] **Task 3.3: Heatmap Visualization with Scatter Overlay** ║ `tests/analysis_api/test_heatmap_plotting.py` ║ Add matplotlib plotting with UMAP scatter overlay ║ M  
  - [ ] 3.3.a: Implement heatmap plotting functionality in GridCreator
    - [ ] 3.3.a.1: Add matplotlib heatmap generation (imshow) for combined_values
    - [ ] 3.3.a.2: Overlay UMAP training embeddings as scatter points
    - [ ] 3.3.a.3: Color-code scatter points by target scores for interpretability
    - [ ] 3.3.a.4: Save as heatmap_plot.png in prediction-heatmaps/ folder
  - [ ] 3.3.b: Implement heatmap plotting functionality in CorrelationGridCreator
    - [ ] 3.3.b.1: Add matplotlib heatmap generation for correlation values
    - [ ] 3.3.b.2: Overlay UMAP training embeddings as scatter points
    - [ ] 3.3.b.3: Color-code scatter points by target scores for interpretability
    - [ ] 3.3.b.4: Save as heatmap_plot.png in correlation-heatmaps/ folder

- [ ] **Task 3.4: Integration Testing & Validation** ║ `tests/analysis_api/test_enhancement_integration.py` ║ End-to-end validation of enhancements ║ M
  - [ ] 3.4.a: Validate folder structure changes
    - [ ] 3.4.a.1: Verify prediction-heatmaps/ and correlation-heatmaps/ creation
    - [ ] 3.4.a.2: Verify prediction-effects/ and correlation-effects/ creation  
    - [ ] 3.4.a.3: Confirm backwards compatibility with existing model registry
  - [ ] 3.4.b: Validate dual effect analysis
    - [ ] 3.4.b.1: Confirm different effect maps from prediction vs correlation significance
    - [ ] 3.4.b.2: Verify proper quantile threshold application
    - [ ] 3.4.b.3: Validate metadata consistency across both analyses
  - [ ] 3.4.c: Validate visualization outputs
    - [ ] 3.4.c.1: Verify heatmap_plot.png generation in both heatmap folders
    - [ ] 3.4.c.2: Confirm scatter overlay integration with proper color coding
    - [ ] 3.4.c.3: Test visualization with different target value ranges
  - [ ] 3.4.d: Methodology preservation validation
    - [ ] 3.4.d.1: **CRITICAL**: Verify no model training occurs during analysis
    - [ ] 3.4.d.2: Confirm median sigma usage (no kernel regression optimization)
    - [ ] 3.4.d.3: Validate two-heatmap methodological separation maintained

## Expected File Structure (After Enhancement)

```
target_0/
├── prediction-heatmaps/           # Enhanced folder naming
│   ├── prediction_values.npy      # Raw predictions on grid
│   ├── confidence_values.npy      # Confidence from model variance 
│   ├── combined_values.npy        # prediction*confidence heatmap
│   ├── grid_coordinates.npy       # 100x100 coordinate grid
│   ├── heatmap_plot.png          # NEW: Heatmap + UMAP scatter overlay
│   └── metadata.json             # Analysis parameters
├── correlation-heatmaps/          # Enhanced folder naming  
│   ├── pearson_correlation.npy    # Pearson correlation heatmap
│   ├── spearman_correlation.npy   # Spearman correlation heatmap
│   ├── point_biserial_correlation.npy  # Point-biserial heatmap
│   ├── heatmap_plot.png          # NEW: Heatmap + UMAP scatter overlay
│   └── metadata.json             # Sigma value, analysis parameters
├── prediction-effects/            # NEW: Effect maps from prediction significance
│   ├── cluster_X_effect_size.nii  # Effect size maps per significant cluster
│   ├── metadata.json             # Cluster information, thresholds
│   └── significant_regions.npy   # 95th percentile significant regions
├── correlation-effects/           # NEW: Effect maps from correlation significance  
│   ├── cluster_Y_effect_size.nii  # Effect size maps per significant cluster
│   ├── metadata.json             # Cluster information, thresholds  
│   └── significant_regions.npy   # 95th percentile significant regions
└── interactive_plots/
    └── interactive_clustering_target_0.html
```

## Testing Strategy by Component Type

### **Modular Components** (Unit Testing)
- **GridCreator, CorrelationGridCreator**: Isolated testing with mock dependencies
- **Focus**: Folder naming, plotting functionality, parameter handling
- **Coverage Target**: 95% - critical for output format consistency

### **Pipeline Integration** (Integration Testing)  
- **HeatmapStage**: Real pipeline context with test fixtures
- **Focus**: Dual analysis orchestration, artifact organization, error handling
- **Coverage Target**: 90% - essential for pipeline reliability

### **Visualization Components** (Component Testing)
- **Plotting Functions**: Real matplotlib operations with test image comparison
- **Focus**: Scatter overlay accuracy, color coding, file generation
- **Coverage Target**: 85% - important for user visualization experience

## Risk Assessment and Mitigation

### **Technical Risks**
- **MEDIUM - Dual Analysis Orchestration**: Running RegionStatisticalAnalyzer twice with different significance sources
  - *Mitigation*: Leverage existing parameter patterns, incremental testing, clear significance source tracking
- **LOW - Folder Structure Changes**: Simple path updates in established codebase
  - *Mitigation*: Systematic testing of path references, backwards compatibility verification
- **LOW - Visualization Integration**: Adding matplotlib plotting to existing numerical analysis
  - *Mitigation*: Separate plotting logic, optional visualization generation, error handling for plot failures

### **Integration Risks**  
- **LOW - Pipeline Compatibility**: Changes to working HeatmapStage integration
  - *Mitigation*: Maintain existing interfaces, add functionality without breaking changes
- **LOW - Performance Impact**: Additional plotting and dual analysis overhead
  - *Mitigation*: Benchmark performance impact, optimize plotting if necessary

## Success Criteria

### **Functional Requirements**
- [ ] Folder structure: prediction-heatmaps/ and correlation-heatmaps/ created correctly
- [ ] Dual effect maps: prediction-effects/ and correlation-effects/ with different analyses
- [ ] Heatmap visualizations: heatmap_plot.png files with scatter overlay in both heatmap folders
- [ ] Methodology preservation: No model training, median sigma only, two-heatmap separation

### **Quality Requirements**
- [ ] >90% test coverage maintained for enhanced functionality
- [ ] All development tests passing (13/13)
- [ ] Performance impact <10% for visualization generation
- [ ] Zero regressions in existing EMUSES functionality

### **Integration Requirements**
- [ ] Backwards compatible with existing model registry and API endpoints
- [ ] Proper artifact organization in model registry system
- [ ] Enhanced visualization accessible through existing interfaces
- [ ] Complete documentation with working examples

## Maintenance Integration Points

### High Priority Tasks Include Maintenance
- Task 3.1: Folder structure updates include path reference cleanup and consistency improvements
- Task 3.3: Visualization implementation includes error handling standardization
- Task 3.4: Integration testing includes performance monitoring and optimization opportunities

## Completed Infrastructure (Do Not Modify)

### ✅ Two-Heatmap Methodology (Working & Validated)
- Prediction×confidence analysis using existing trained models
- Correlation analysis using median sigma (no kernel regression training)
- Scientific validation: separates manifold topology from predictive relationships

### ✅ Modular Architecture (Production-Ready)
- GridCreator, CorrelationGridCreator, RegionStatisticalAnalyzer
- 90%+ test coverage with component-aware testing strategies
- HeatmapStage integration after nested CV training

### ✅ API & Pipeline Integration (Complete)
- FastAPI endpoints with model registry integration
- Pipeline timing after nested CV when trained models available
- Error handling and graceful component failure

---

**Implementation Status**: Ready to begin Phase 3 - Enhancement Implementation  
**Next Step**: Task 3.1 - Folder Structure Updates  
**Key Success Factor**: Maintain scientific methodology while adding organizational and visualization enhancements to proven modular architecture

*This plan follows LAD Phase 00 (Existing Work Discovery) and Phase 01 (Autonomous Context Planning) methodologies for systematic enhancement of production-quality components.*