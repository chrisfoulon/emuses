# Analysis API Enhancement - Session Summary

## Context
The goal was to understand and plan the integration of statistical map generation capabilities back into EMUSES HeatmapStage. The current HeatmapStage performs model training/optimization but lacks the analysis capabilities that were in legacy commented code.

## Major Discoveries & Corrections

### ❌ Initial Misunderstandings (Corrected)
1. **Statistical Maps**: Initially thought they were prediction heatmaps on 2D embedding grid
   - **ACTUALLY**: Effect size comparisons between inside vs outside cluster points in original high-dimensional feature space

2. **Out-of-sample validation**: Thought we needed to modify Optuna CV to track fold indices
   - **ACTUALLY**: CV scores from `nested_optuna_cv` are already out-of-sample validated (lines 215-216)

3. **Data preparation**: Thought complex data preparation methods were needed
   - **ACTUALLY**: Data is already properly formatted in context (`prediction_train_coords`, `prediction_train_labels`)

4. **Ensemble predictions**: Initially wanted to expose old `run_kernel_heatmap_analysis()` functions
   - **ACTUALLY**: Should use InferenceStage approach for consistency with existing API

### ✅ What Already Exists in EMUSES
- **Out-of-sample validation**: CV scores from Optuna CV (scientifically valid)
- **Ensemble prediction infrastructure**: Both `ensemble_predict()` function and InferenceStage approach  
- **Statistical functions**: `input_matrix_stat_map()`, `calculate_correlation_grid()`
- **Visualization functions**: `plot_clustering_interactive_with_hover()`
- **Data formatting**: Context already contains properly formatted data
- **Model training**: Complete Optuna CV optimization pipeline

### ❌ What's Actually Missing (Needs Implementation)
1. **Grid ensemble predictions**: 100x100 grid predictions on normalized 0-1 embedding space for thresholding
2. **Statistical map generation**: Cluster-based effect size comparisons in original feature space
3. **Interactive visualizations**: Code exists but is commented out in HeatmapStage

## Corrected Understanding of Statistical Maps

**Process**:
1. Get HDBSCAN cluster labels
2. For each cluster: identify indices of points inside vs outside cluster
3. Compare **original input features** (high-dimensional) between inside/outside groups
4. Compute effect sizes for each feature dimension using `input_matrix_stat_map()`
5. Apply threshold filter: `(prediction_value + confidence) / 2` to determine significant points
6. **Result**: Statistical map with input data dimensionality (NOT embedding space dimensionality)

## Technical Decisions Made

### Ensemble Predictions
- **Decision**: Use InferenceStage approach instead of `ensemble_predict()` function
- **Reason**: Better integration with existing API, already handles uncertainty properly

### Grid Predictions  
- **Requirements**: 100x100 grid on embedding space (normalized 0-1), configurable grid size
- **Purpose**: For thresholding significant points in statistical map generation
- **Implementation**: Create `linspace` grid, use ensemble predictions like InferenceStage

### Integration Strategy
- **Approach**: Add capabilities AFTER existing Optuna CV workflow
- **Benefits**: No complex modifications to working code, uses existing infrastructure
- **Pipeline**: `Current Workflow (Optuna CV) → Grid Predictions → Statistical Maps → Visualizations → Complete Output`

## Available EMUSES Infrastructure

### Model Architectures
- **"kernel"**: Custom KernelRegressor/KernelLogisticRegressor (Nadaraya-Watson)
- **"rf"**: Random Forest (sklearn RandomForestRegressor/Classifier)
- **"elastic"**: Elastic Net (sklearn ElasticNet/LogisticRegression)

### Uncertainty Quantification
- **Ensemble disagreement**: Standard deviation across CV fold predictions  
- **Model-intrinsic**: Different methods per architecture (RF: bootstrap variance, Kernel: local density, Elastic: regularization strength)
- **Research-backed**: Heterogeneous ensemble calibration possible but complex

### Existing Functions to Use
- `ensemble_predict()` in `kernel_regression_utils.py` (returns mean, std)
- InferenceStage ensemble approach (confidence scores)
- `input_matrix_stat_map()` in `stats_utils.py` (effect size calculations)
- `calculate_correlation_grid()` in `correlation_maps_utils.py`
- `plot_clustering_interactive_with_hover()` in `visualisation.py`

## Implementation Plan Summary

### Phase 1: Grid Prediction Generation
- Create 100x100 grid on normalized embedding space (0-1)
- Use InferenceStage-style ensemble predictions for consistency
- Return grid coordinates, ensemble predictions, and confidence scores

### Phase 2: Statistical Map Generation  
- Get cluster labels (from context or compute with HDBSCAN)
- For each cluster: inside vs outside point indices
- Apply prediction threshold: `(prediction + confidence) / 2`
- Compute effect sizes in original feature space using `input_matrix_stat_map()`
- Return statistical maps with input data dimensionality

### Phase 3: Interactive Visualizations
- Restore commented visualization code from HeatmapStage
- Use existing `plot_clustering_interactive_with_hover()` function
- Generate HTML plots for each score vector

## Configuration Options to Add
```python
statistical_map_grid_size: int = 100           # Grid size for predictions
generate_statistical_maps: bool = True         # Enable statistical maps  
generate_grid_predictions: bool = True         # Enable grid predictions
prediction_threshold_method: str = "median"    # Thresholding method
effect_size_test: str = "cohen_d"             # Effect size calculation method
interactive_plot: bool = False                # Enable interactive visualizations
```

## Next Steps
1. **Implement grid prediction generation** using InferenceStage approach
2. **Implement cluster-based statistical map generation** using existing EMUSES functions
3. **Restore interactive visualizations** from commented HeatmapStage code
4. **Add configuration options** for grid size, thresholds, effect size methods
5. **Test integration** with existing EMUSES pipeline
6. **Validate outputs** match legacy behavior expectations

## Key Insight
The integration is **much simpler** than initially thought because most infrastructure already exists. We mainly need to **call existing functions** in the right sequence rather than create new complex infrastructure.

## Files Modified/Created
- `/dev-docs/analysis-api/corrected_integration_plan.md` - Detailed implementation plan
- `/dev-docs/analysis-api/statistical_map_integration_pseudocode.md` - Original pseudo-code (contains some outdated approaches)
- `/dev-docs/analysis-api/session_summary.md` - This summary

## Status for Next Session
Ready to begin implementation of the three missing capabilities using the corrected understanding and existing EMUSES infrastructure.