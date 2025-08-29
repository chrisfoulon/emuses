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

- [x] **Task 3.1: Folder Structure Updates** ║ `tests/analysis_api/test_folder_naming.py` ║ Update "grids" → "heatmaps" in modular tools ║ S ✅
  - [x] 3.1.a: Update GridCreator output folder naming
    - [x] 3.1.a.1: Change `prediction-grids/` → `prediction-heatmaps/` in create_prediction_heatmaps()
    - [x] 3.1.a.2: Update folder creation logic and path references
    - [x] 3.1.a.3: Verify backwards compatibility with existing artifacts
  - [x] 3.1.b: Update CorrelationGridCreator output folder naming  
    - [x] 3.1.b.1: Change `correlation-grids/` → `correlation-heatmaps/` in create_correlation_heatmaps()
    - [x] 3.1.b.2: Update folder creation logic and path references
    - [x] 3.1.b.3: Verify backwards compatibility with existing artifacts

- [x] **Task 3.2: Dual Effect Size Maps Implementation** ║ `tests/analysis_api/test_dual_effects.py` ║ Separate prediction and correlation effect analysis with symmetric percentile thresholds ║ M ✅
  - [x] 3.2.a: Enhance RegionStatisticalAnalyzer for dual analysis pattern
    - [x] 3.2.a.1: Add significance_source parameter to create_statistical_maps()
    - [x] 3.2.a.2: Add percentile_threshold parameter for symmetric range (e.g., 5 → 5%-95% range)
    - [x] 3.2.a.3: Update output folder naming based on significance source
    - [x] 3.2.a.4: Maintain consistent metadata format across both analyses
  - [ ] 3.2.a.5: CRITICAL - Enhance create_statistical_maps() to do full clustering and effect map generation
    - [ ] 3.2.a.5.1: Add grid→sample mapping algorithm (KNN from grid coords to training embeddings)
    - [ ] 3.2.a.5.2: Integrate existing perform_region_clustering() and compute_statistical_analysis()  
    - [ ] 3.2.a.5.3: Generate per-cluster effect maps using input_matrix_stat_map() and save_statistical_maps()
    - [ ] 3.2.a.5.4: Use proper naming: effect_size_map_target_{target}_cluster_{cluster}_{high|low}_cluster_{cluster}.{nii|csv}
  - [ ] 3.2.b: Update HeatmapStage integration for dual analysis calls
    - [ ] 3.2.b.1: Replace old create_statistical_maps() call with new enhanced dual analysis pattern
    - [ ] 3.2.b.2: Add CLI parameter --effect_percentile_threshold (default: 5) to heatmap stage integration
    - [ ] 3.2.b.3: Run dual RegionStatisticalAnalyzer calls:
      - Call 1: prediction×confidence significance → prediction-effects/
      - Call 2: absolute correlation significance → correlation-effects/

- [ ] **Task 3.3: Heatmap Visualization with Scatter Overlay** ║ `tests/analysis_api/test_heatmap_plotting.py` ║ Add matplotlib plotting with UMAP scatter overlay ║ M  
  - [ ] 3.3.a: Implement heatmap plotting functionality in GridCreator
    - [ ] 3.3.a.1: Add base heatmap generation using visualisation.py patterns
      - Use imshow(combined_values.reshape(100, 100)) for heatmap background
      - Add scatter(training_embeddings, c=target_scores) for UMAP overlay
      - Save as: prediction_heatmap_target_{target_id}.png
    - [ ] 3.3.a.2: Add cluster overlay generation (called from RegionStatisticalAnalyzer)
      - Same base heatmap + highlight cluster points with different colors
      - Use pattern: all_points_grey + cluster_points_colored (from visualisation.py:188-204)
      - Save as: prediction_heatmap_target_{target_id}_cluster_{cluster}_{high|low}_overlay.png
  - [ ] 3.3.b: Implement heatmap plotting functionality in CorrelationGridCreator  
    - [ ] 3.3.b.1: Add base correlation heatmap generation using visualisation.py patterns
      - Use imshow(correlation_values.reshape(100, 100)) for heatmap background
      - Add scatter(training_embeddings, c=target_scores) for UMAP overlay
      - Save as: correlation_heatmap_target_{target_id}.png
    - [ ] 3.3.b.2: Add cluster overlay generation (called from RegionStatisticalAnalyzer)
      - Same base + highlight correlation cluster points
      - Save as: correlation_heatmap_target_{target_id}_cluster_{cluster}_{high|low}_overlay.png

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
├── prediction-heatmaps/           # GridCreator output (renamed from prediction-grids) ✅
│   ├── prediction_values.npy      # Raw predictions on 100x100 grid
│   ├── confidence_values.npy      # Confidence from model variance  
│   ├── combined_values.npy        # prediction×confidence heatmap values
│   ├── grid_coordinates.npy       # 100x100 coordinate grid
│   ├── prediction_metadata.json   # Analysis parameters
│   ├── prediction_heatmap_target_0.png      # Base heatmap + UMAP scatter overlay
│   └── prediction_heatmap_target_0_cluster_{X}_{high|low}_overlay.png  # Per-cluster overlays
├── correlation-heatmaps/          # CorrelationGridCreator output (renamed from correlation-grids) ✅
│   ├── correlation_values_pearson.npy    # Pearson correlation heatmap
│   ├── correlation_values_spearman.npy   # Spearman correlation heatmap  
│   ├── grid_coordinates.npy       # 100x100 coordinate grid  
│   ├── correlation_metadata.json  # Sigma value, analysis parameters
│   ├── correlation_heatmap_target_0.png   # Base correlation heatmap + UMAP scatter
│   └── correlation_heatmap_target_0_cluster_{Y}_{high|low}_overlay.png  # Per-cluster overlays
├── prediction-effects/            # RegionStatisticalAnalyzer with prediction×confidence significance
│   ├── low_significance_regions.npy   # < 5th percentile grid indices ✅ 
│   ├── high_significance_regions.npy  # > 95th percentile grid indices ✅
│   ├── effect_size_map_target_0_cluster_0_high_cluster_0.nii    # Per-cluster effect maps (nifti input)
│   ├── effect_size_map_target_0_cluster_1_high_cluster_1.csv    # Per-cluster effect maps (spreadsheet input)  
│   ├── effect_size_map_target_0_cluster_3_low_cluster_3.nii     # Low significance clusters
│   └── metadata.json             # Cluster info, percentile thresholds, sample mapping
├── correlation-effects/           # RegionStatisticalAnalyzer with absolute correlation significance  
│   ├── low_significance_regions.npy   # < 5th percentile grid indices ✅
│   ├── high_significance_regions.npy  # > 95th percentile grid indices ✅
│   ├── effect_size_map_target_0_cluster_0_high_cluster_0.nii    # Per-cluster effect maps
│   ├── effect_size_map_target_0_cluster_2_high_cluster_2.nii    # Additional high clusters  
│   ├── effect_size_map_target_0_cluster_4_low_cluster_4.nii     # Low significance clusters
│   └── metadata.json             # Cluster info, percentile thresholds, sample mapping
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