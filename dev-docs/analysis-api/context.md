# Statistical Analysis Enhancement - Implementation Context

## Level 1: Plain English Summary

EMUSES has **production-ready statistical analysis capabilities** implemented as modular components (GridCreator, CorrelationGridCreator, RegionStatisticalAnalyzer) with FastAPI integration and HeatmapStage pipeline integration. The components implement the scientifically superior **two-heatmap approach** that separates UMAP manifold topology analysis from trained model prediction analysis.

**Current Status**: 85% feature complete. Core methodology working correctly with existing trained models (no kernel regression training). Enhancement needed for: folder naming ("grids" → "heatmaps"), dual effect size maps, and scatter plot visualizations.

**Integration Strategy**: ENHANCE existing modular components rather than rebuild. Components are production-quality with 90%+ test coverage and proper architectural integration after nested CV training.

**Critical Success Factor**: Maintain methodological purity (no model training during analysis) while adding missing visualization and organizational features.

## Level 2: API Integration Table

| Component | Purpose | Inputs | Outputs | Integration Point |
|-----------|---------|--------|---------|------------------|
| **GridCreator** | Prediction heatmap generation | embeddings, trained_models, target_data | prediction_values.npy, combined_values.npy, metadata | HeatmapStage after nested CV |
| **CorrelationGridCreator** | UMAP topology correlation analysis | embeddings, target_data, sigma_method="median" | pearson_correlation.npy, spearman_correlation.npy | HeatmapStage after nested CV |
| **RegionStatisticalAnalyzer** | Effect size maps from significant regions | embeddings, target_scores, input_matrix | cluster_effect_size.nii, metadata.json | Called twice: prediction + correlation |
| **HeatmapStage** | Pipeline integration orchestrator | context, prediction_train_coords, Y matrix | Complete analysis artifacts | After nested CV training |
| **compute_sigma_median** | Stable sigma calculation | embeddings | median sigma value | CorrelationGridCreator dependency |
| **save_statistical_maps** | Format conversion utility | stat_maps, output_folder, input_type | .nii/.npy/.csv files | RegionStatisticalAnalyzer output |

## Level 3: Code Integration Examples

### Current Working Integration (HeatmapStage)
```python
# Location: emuses/pipelines/heatmap_stage.py:958
def _execute_triple_grid_analysis(self, context, embeddings, target_matrix, output_folder, logger):
    # Import working modular components
    from emuses.tools.grid_creator import GridCreator
    from emuses.tools.correlation_grid_creator import CorrelationGridCreator  
    from emuses.tools.region_statistical_analyzer import RegionStatisticalAnalyzer
    
    # 1. PREDICTION ANALYSIS (uses existing trained models)
    prediction_models = context.get("prediction_models", [])  # No retraining!
    grid_creator = GridCreator(grid_size=100)
    prediction_results = grid_creator.create_prediction_heatmaps(
        embeddings=embeddings,
        trained_models=prediction_models,
        target_data={target_name: target_scores},
        output_folder=target_output,  # Currently creates "grids" folder
        denormalize=True
    )
    
    # 2. CORRELATION ANALYSIS (uses median sigma, no optimization)
    correlation_creator = CorrelationGridCreator(grid_size=100)
    correlation_results = correlation_creator.create_correlation_heatmaps(
        embeddings=embeddings,
        target_data={target_name: target_scores}, 
        output_folder=target_output,  # Currently creates "grids" folder
        optimize_sigma=False,  # CRITICAL: No model training
        sigma_method="median"
    )
    
    # 3. STATISTICAL ANALYSIS (currently single call)
    statistical_analyzer = RegionStatisticalAnalyzer()
    statistical_results = statistical_analyzer.create_statistical_maps(
        embeddings=embeddings,
        target_scores=target_scores,
        input_matrix=input_matrix,
        dataset_type=dataset_type,
        output_folder=target_output,  # Single analysis only
        target_name=target_name
    )
```

### FastAPI Integration Pattern
```python
# Location: emuses/foundation_fastapi_service/app.py
@app.post("/api/v1/analysis/heatmaps", status_code=201)
async def create_analysis_heatmaps(request: HeatmapsRequest) -> AnalysisResponse:
    """Generate prediction and correlation heatmaps using existing trained models."""
    
    # Model registry integration (working)
    registry = get_model_registry()
    model_path = registry.get_model_path(request.model_id)
    
    # Load existing trained models (no retraining)
    model_data = ModelIOManager(model_path.parent).load_model(model_path.name)
    
    # Execute modular analysis components
    analyzer = StatisticalAnalysisOrchestrator()
    results = await analyzer.execute_heatmap_analysis(
        embeddings=model_data.embeddings,
        trained_models=model_data.prediction_models,  # Existing models only
        target_data=model_data.target_data,
        output_folder=output_folder
    )
```

### Data Flow Architecture
```python
# Current pipeline flow (working)
Context Flow:
├── Nested CV Training Complete → context["prediction_models"] available
├── HeatmapStage Integration → _execute_triple_grid_analysis()
├── Extract Data: prediction_train_coords, Y matrix, trained_models  
├── Modular Analysis:
│   ├── GridCreator → prediction-grids/ (NEEDS: → prediction-heatmaps/)
│   ├── CorrelationGridCreator → correlation-grids/ (NEEDS: → correlation-heatmaps/)
│   └── RegionStatisticalAnalyzer → statistical-maps/ (NEEDS: dual analysis)
└── Artifact Storage → Model registry installation
```

## Enhancement Requirements (From User)

### 1. Folder Structure Updates
**Current**: `prediction-grids/`, `correlation-grids/`
**Required**: `prediction-heatmaps/`, `correlation-heatmaps/`

### 2. Dual Effect Size Maps  
**Current**: Single statistical analysis call
**Required**: 
- `prediction-effects/` - Effect maps from prediction*confidence significance  
- `correlation-effects/` - Effect maps from correlation significance

### 3. Scatter Plot Visualizations
**Current**: Only .npy numerical data
**Required**: `heatmap_plot.png` files with heatmap + UMAP training points overlay

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

## Architecture Integration Points

### Integration Strategy (From LAD Phase 0)
**Decision**: ENHANCE existing modular components (85% requirement coverage)
**Quality Assessment**: Production-ready, well-tested (13/13 tests passing)
**Rationale**: Build on proven architecture rather than rebuild

### Dependencies (All Working)
- **Model Registry**: Complete and operational for artifact management
- **Pipeline Integration**: HeatmapStage after nested CV training
- **Statistical Utilities**: `compute_sigma_median`, `input_matrix_stat_map`, `save_statistical_maps`
- **UMAP Infrastructure**: Rescaled embeddings from `prediction_train_coords`

### Compatibility Requirements
- **Backwards Compatibility**: Maintain existing API interfaces
- **Data Format Consistency**: Keep .npy numerical outputs + add .png visualizations
- **Pipeline Timing**: Continue integration after nested CV training
- **Methodology Preservation**: NO kernel regression training, existing models only

## Maintenance Opportunities

### High Priority (Address During Implementation)
- **No maintenance issues found** - Code is production-quality

### Boy Scout Rule Opportunities  
- [ ] `GridCreator`: Add plotting functionality while updating folder names
- [ ] `CorrelationGridCreator`: Add plotting functionality while updating folder names  
- [ ] `RegionStatisticalAnalyzer`: Enhance for dual-analysis pattern during integration

## Critical Implementation Constraints

### Scientific Methodology (NON-NEGOTIABLE)
1. **No Model Training**: Must use `context["prediction_models"]` exclusively
2. **Median Sigma Only**: Use `compute_sigma_median()`, no optimization
3. **Two-Heatmap Separation**: Maintain distinction between prediction and correlation analysis

### Technical Architecture (WORKING)
1. **Modular Design**: Enhance existing components, don't rebuild
2. **Pipeline Integration**: After nested CV when models available
3. **Error Handling**: Graceful failure for individual components
4. **Testing Coverage**: Maintain 90%+ coverage with component-aware strategies

### Enhancement Scope (SPECIFIC)
1. **Folder Naming**: "grids" → "heatmaps" in output paths
2. **Dual Analysis**: Run RegionStatisticalAnalyzer twice with different significance sources
3. **Visualization**: Add matplotlib scatter overlay on heatmap background

---

**Context Status**: Complete LAD Phase 01 analysis with multi-level documentation  
**Architecture Decision**: ENHANCE existing production-quality components  
**Implementation Approach**: Targeted enhancements maintaining methodological and architectural integrity