# Analysis API Enhancement - Session Handoff

## Current Implementation Status

### ✅ COMPLETED: Foundation & Partial Enhancement (Tasks 3.1-3.2.a)
- **Model Registry System**: Production ready with comprehensive testing (2,138 tests, 99.1% health)
- **Triple Grid Analysis Components**: All modular components implemented and tested
- **Phase 3 Progress**: 
  - ✅ **Task 3.1**: Folder Structure Updates COMPLETE
    - `prediction-grids/` → `prediction-heatmaps/` in GridCreator ✅
    - `correlation-grids/` → `correlation-heatmaps/` in CorrelationGridCreator ✅
    - Backwards compatibility maintained, all tests passing
  - ✅ **Task 3.2.a**: Enhanced RegionStatisticalAnalyzer with dual analysis parameters ✅
    - Added `significance_source` parameter ('prediction' vs 'correlation')  
    - Added `percentile_threshold` parameter for symmetric ranges (default: 5% → 5%-95%)
    - ⚠️ **CRITICAL ISSUE DISCOVERED**: Current implementation is simplified and incomplete!

### 🚨 CRITICAL PROBLEM IDENTIFIED

**Current RegionStatisticalAnalyzer.create_statistical_maps()** only saves raw significance region indices but **SKIPS THE ACTUAL STATISTICAL WORKFLOW** that generates the per-cluster effect size maps seen in legacy runs.

**Missing Implementation**:
1. **Grid→Sample Mapping**: Map 10,000 grid coordinates back to ~500 training sample indices  
2. **Full Clustering Workflow**: Use existing `perform_region_clustering()` + `compute_statistical_analysis()`
3. **Per-Cluster Effect Maps**: Generate `effect_size_map_target_0_cluster_X_{high|low}_cluster_X.{nii|csv}` files
4. **Complete Visualization**: Base heatmaps + cluster overlay plots

### 📋 IMMEDIATE NEXT STEPS (PRIORITY ORDER)

#### **Task 3.2.a.5: CRITICAL - Fix create_statistical_maps() Implementation** 
**CURRENT ACTIVE TASK** - Must be completed before continuing

**Problem**: Current method at `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/emuses/tools/region_statistical_analyzer.py:209` is incomplete
**Required**: Implement full statistical workflow based on codebase analysis

**Implementation Steps**:
1. **Grid→Sample Mapping Algorithm**: 
   ```python
   # Map grid indices to training sample indices using KNN
   from sklearn.neighbors import NearestNeighbors
   nbrs = NearestNeighbors(n_neighbors=1).fit(training_embeddings)
   distances, sample_indices = nbrs.kneighbors(significant_grid_coords)
   ```

2. **Integrate Existing Methods**: 
   ```python
   # Use existing clustering and statistical analysis
   cluster_labels = self.perform_region_clustering(mapped_sample_coords)  
   statistical_maps = self.compute_statistical_analysis(input_matrix, cluster_sample_indices)
   ```

3. **Generate Per-Cluster Effect Maps**:
   ```python
   # Use existing save_statistical_maps with proper naming
   from emuses.tools.output_utils import save_statistical_maps
   save_statistical_maps(statistical_maps, output_folder, input_type, output_format_info, 
                        filename_prefix=f"effect_size_map_target_{target}_cluster")
   ```

4. **Proper File Naming**: Follow legacy pattern: `effect_size_map_target_0_cluster_X_{high|low}_cluster_X.{nii|csv}`

#### **Task 3.2.b: Update HeatmapStage Integration** 
- **Current Issue**: `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/emuses/pipelines/heatmap_stage.py:1068` calls OLD method signature
- **Required**: Update to use new dual analysis pattern with CLI parameter support

#### **Task 3.3: Visualization Implementation**
- **Base Heatmaps**: Use patterns from `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/emuses/tools/visualisation.py:164-174`
- **Cluster Overlays**: Use patterns from `visualisation.py:188-204`

### 🔍 COMPLETE TARGET FILE STRUCTURE (Based on Legacy Analysis)

```
target_0/
├── prediction-heatmaps/           # ✅ COMPLETE - Updated folder naming
│   ├── prediction_values.npy, confidence_values.npy, combined_values.npy
│   ├── prediction_heatmap_target_0.png      # 🔄 TODO: Base heatmap + UMAP scatter
│   ├── prediction_heatmap_target_0_cluster_X_{high|low}_overlay.png  # 🔄 TODO: Cluster overlays
│   └── prediction_metadata.json
├── correlation-heatmaps/          # ✅ COMPLETE - Updated folder naming
│   ├── correlation_values_pearson.npy, correlation_values_spearman.npy
│   ├── correlation_heatmap_target_0.png     # 🔄 TODO: Base correlation heatmap + UMAP scatter
│   ├── correlation_heatmap_target_0_cluster_Y_{high|low}_overlay.png  # 🔄 TODO: Cluster overlays
│   └── correlation_metadata.json
├── prediction-effects/            # ✅ PARTIAL - Folder creation works, content generation broken
│   ├── low_significance_regions.npy   # ✅ Grid indices (< 5th percentile)
│   ├── high_significance_regions.npy  # ✅ Grid indices (> 95th percentile)  
│   ├── effect_size_map_target_0_cluster_0_high_cluster_0.nii    # 🚨 MISSING - Per-cluster effect maps
│   ├── effect_size_map_target_0_cluster_1_high_cluster_1.nii    # 🚨 MISSING - Need full workflow
│   ├── effect_size_map_target_0_cluster_3_low_cluster_3.nii     # 🚨 MISSING - Current method incomplete
│   └── metadata.json             # ✅ Basic metadata works
├── correlation-effects/           # ✅ PARTIAL - Same issue as prediction-effects
│   ├── low_significance_regions.npy, high_significance_regions.npy  # ✅ Grid indices work
│   ├── effect_size_map_target_0_cluster_X_{high|low}_cluster_X.nii  # 🚨 MISSING - Need full workflow
│   └── metadata.json
└── interactive_plots/             # ✅ EXISTING - No changes needed
    └── interactive_clustering_target_0.html
```

## Development Context

### **Key Codebase Analysis Results**:
- **Visualization Patterns** ✅: `visualisation.py:plot_clustering()` has exact patterns needed
- **Statistical Workflow** ✅: `stats_utils.py:input_matrix_stat_map()` + `output_utils.py:save_statistical_maps()`  
- **HeatmapStage Integration** ⚠️: Line 1068 needs update to dual analysis pattern
- **Missing Grid→Sample Mapping** 🔍: Key algorithmic gap identified

### **Testing Strategy**:
- **Current Baseline**: `python scripts/dev_test_runner.py` shows 13/13 tests passing
- **New Tests**: `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/tests/analysis_api/test_dual_effects.py` (3 tests passing)
- **Folder Tests**: `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/tests/analysis_api/test_folder_naming.py` (4 tests passing)

### **Current Session State**:
- **Working Directory**: `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/`
- **Branch**: `feature/analysis-api-enhancement` (clean status)
- **Analysis Notes**: `/tmp/codebase_analysis_notes.md` (comprehensive codebase analysis completed)

## CRITICAL NEXT SESSION INSTRUCTIONS

### **Immediate Action Required**:
1. **Start with Task 3.2.a.5**: Fix the incomplete `create_statistical_maps()` method
2. **Follow 02_iterative_implementation.md**: Use TDD approach with failing tests first
3. **Reference Legacy Run**: `/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/testatoto/` for file naming patterns
4. **Use Existing Codebase Patterns**: Don't rebuild from scratch, enhance existing modular architecture

### **Key Implementation Insight**:
The **RegionStatisticalAnalyzer already has all the methods needed** (`perform_region_clustering`, `compute_statistical_analysis`, integration with `save_statistical_maps`). The current `create_statistical_maps()` method was implemented as a simplified version but needs to be enhanced to use the **full sophisticated workflow**.

### **Architecture Strategy**:
- **Keep modular design**: Separate components for grid creation, correlation, statistical analysis
- **Enhance existing methods**: Don't rebuild, just connect the existing sophisticated pipeline
- **Use visualization.py patterns**: For consistent plotting style matching existing codebase

## Success Criteria

**Phase 3 Complete When**:
- ✅ Folder structure updated (DONE)  
- 🔄 **create_statistical_maps() generates actual per-cluster effect size maps** (CRITICAL)
- 🔄 Base heatmap visualizations with UMAP scatter overlay  
- 🔄 HeatmapStage integration updated for dual analysis with CLI parameters
- ✅ All tests pass (current: 17/17 analysis tests passing)

The foundation is solid, but the **core statistical workflow needs completion** before moving to visualization and integration tasks.