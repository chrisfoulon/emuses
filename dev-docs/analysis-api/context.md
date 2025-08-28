# Analysis API Enhancement - Implementation Context

## Level 1: Plain English Summary

EMUSES has **modern statistical analysis capabilities** under development in HeatmapStage and advanced statistical analysis in the `new_pipeline_test` function. However, these are **NOT exposed through API/CLI interfaces**. Legacy functions (`run_kernel_heatmap_analysis`, `run_heatmap_analysis`) exist but are **outdated guides** that should NOT be used as the foundation.

The enhancement needs to **implement statistical maps and heatmap analysis functionality** by:
1. **Extracting modern approaches** from `new_pipeline_test` (advanced sigma optimization, nested CV)  
2. **Completing the statistical analysis code** in HeatmapStage (currently commented)
3. **Creating API/CLI interfaces** for the modern statistical analysis pipeline

**Critical Understanding**: This is **NOT** a simple service layer addition - it requires implementing sophisticated statistical analysis functionality based on modern patterns, not exposing existing "production-ready" functions.

**Statistical Maps Definition**: Feature-space statistical maps generated via `input_matrix_stat_map` (returns input_matrix format: features × observations) then converted to original data format via `save_statistical_maps` (images/NIfTI/spreadsheets/.npy). Not limited to brain regions - applies to any feature space (pixels, voxels, spreadsheet columns, etc.).

**Foundation Status**: Model registry system, multi-user service, and inference performance fixes are complete. HeatmapStage provides the modern pipeline architecture foundation.

## Level 2: API Integration Table

| Component | Purpose | Current Status | Integration Approach |
|-----------|---------|----------------|---------------------|
| **new_pipeline_test** | Advanced statistical analysis with Optuna optimization | ✅ Modern implementation exists | Extract sigma optimization and statistical mapping logic |
| **HeatmapStage** | Modern prediction pipeline with statistical analysis | ⚠️ Statistical analysis commented out | Complete and expose statistical analysis functionality |
| **Legacy Functions** | Old statistical analysis implementations | ❌ Outdated guides only | **DO NOT USE** - for reference only |
| **FastAPI Service** | REST API endpoints | 🔧 Needs statistical analysis endpoints | Implement `/analysis/statistical-maps`, `/analysis/heatmaps` |
| **CLI Commands** | Command-line interface | 🔧 Needs analysis commands | Implement `analyze-statistical-maps`, `analyze-heatmaps` |
| **Interactive Visualization** | HTML interactive plots | ⚠️ Function exists, not integrated | Integrate `plot_clustering_interactive_with_hover` |
| **Model Registry** | Model ID resolution and artifact storage | ✅ Complete and functional | Use for model lookup and artifact management |

## Level 3: Code Integration Examples

### Modern Statistical Analysis Function (To Be Extracted)

```python
# Location: /emuses/tools/stats_utils.py:1477
def new_pipeline_test(
    embeddings,                   # np.ndarray: UMAP embeddings 
    combined_input_matrix,        # np.ndarray: Original input data
    scores_vectors_dict,          # dict: Score vectors for analysis
    output_folder,                # str: Output directory
    grid_size=100,               # int: Heatmap grid resolution
    dataset_type="image",        # str: Input data type
    cluster_labels=None,         # np.ndarray: Cluster assignments
    optuna_trials=50,            # int: Optuna optimization trials
    model_selection=None,        # list: Model types ['gp', 'rf', 'gb', 'kr', 'xgb']
    # ... additional parameters
) -> dict:
    """
    Enhanced pipeline function with robust model selection and parallel training.
    
    Key Features:
    1. Extracts VOI_vector from scores_vectors_dict
    2. Robust nested CV with Optuna optimization for kernel sigma
    3. Aggregates candidate sigma values for robust final_sigma
    4. Uses final_sigma for GWD matrix and summary features
    5. Multiple model types with hyperparameter optimization
    6. Statistical mapping with proper cross-validation
    """
```

### HeatmapStage Statistical Analysis (To Be Completed)

```python
# Location: /emuses/pipelines/heatmap_stage.py (currently commented lines 431-686)
# ENHANCEMENT AFTER NESTED CV TRAINING

class HeatmapStage(PipelineStage):
    def run(self, context, progress_queue=None):
        # Modern pipeline integration - AFTER nested CV training
        prediction_train_coords = context.get("prediction_train_coords")  # Scaled embeddings (0-1)
        prediction_train_labels = context.get("prediction_train_labels")  # Target scores
        trained_models = context.get("trained_models")  # Available after nested CV
        
        # Triple Analysis Implementation:
        # 1. Prediction Grid: 100x100 coordinates → simplified inference → prediction*confidence heatmaps
        # 2. Correlation Grid: 100x100 coordinates → GWD vectors → correlation with target scores
        # 3. Statistical Maps: Two-stage filtering (vis + effect thresholds) → region clustering → effect size
        # 4. Sigma optimization via kernel regression for correlation analysis
        # 5. Region-based clustering: HDBSCAN within high-confidence regions (≥3 points per cluster)
        # 6. Feature-space statistical analysis via input_matrix_stat_map (returns input_matrix format)
        # 7. Format conversion via save_statistical_maps (input_matrix → original format: images/NIfTI/spreadsheets/.npy)
        # 8. Per-target processing: statistical-maps/, heatmaps/, correlation-maps/ folders
        # 9. Enhanced interactive visualization with region-based clustering metadata
```

### Target FastAPI Implementation Pattern

```python
# To be implemented in /emuses/foundation_fastapi_service/app.py
from emuses.tools.statistical_analysis import GridCreator, StatisticalAnalyzer  # New modules needed

class StatisticalAnalysisRequest(BaseModel):
    model_id: str = Field(..., description="Registry model ID")
    analysis_type: str = Field(..., description="heatmap or statistical-maps")
    
    # Grid creation parameters
    grid_size: int = Field(100, description="Grid resolution (100x100 default)")
    confidence_method: str = Field("cv_ensemble", description="5_model or cv_ensemble")
    denormalize: bool = Field(True, description="Denormalize predictions to original range")
    
    # Statistical mapping parameters  
    region_threshold: float = Field(0.1, description="Region selection threshold")
    effect_size_method: str = Field("process_column", description="Effect size calculation method")

@app.post("/api/v1/analysis/statistical-maps", status_code=201)
async def run_statistical_maps_analysis(request: StatisticalAnalysisRequest) -> AnalysisResponse:
    """Execute modern statistical maps analysis based on new_pipeline_test approach."""
    
    # Model registry integration
    registry = get_model_registry()
    model_path = registry.get_model_path(request.model_id)
    
    # Load model data with modern pipeline
    model_io = ModelIOManager(model_path.parent)
    model_data = model_io.load_model(model_path.name)
    
    # Initialize modern statistical analyzer
    analyzer = ModernStatisticalAnalyzer(
        optuna_trials=request.optuna_trials,
        model_types=request.model_types,
        grid_size=request.grid_size
    )
    
    # Execute grid creation and statistical analysis
    if request.analysis_type == "heatmaps":
        grid_creator = GridCreator(
            grid_size=request.grid_size,
            confidence_method=request.confidence_method
        )
        results = grid_creator.create_prediction_heatmaps(
            embeddings=model_data.metadata.scaled_embeddings,  # 0-1 coordinates
            trained_models=model_data.metadata.trained_models,  # From context
            target_data=model_data.metadata.target_data,
            output_folder=output_folder,
            denormalize=request.denormalize
        )
    else:  # statistical-maps
        stat_analyzer = StatisticalAnalyzer(
            threshold=request.region_threshold,
            method=request.effect_size_method
        )
        results = stat_analyzer.create_statistical_maps(
            embeddings=model_data.metadata.scaled_embeddings,
            input_matrix=model_data.metadata.input_matrix,  # Raw input data
            target_data=model_data.metadata.target_data,
            output_folder=output_folder
        )
    
    # Registry artifact installation
    analysis_id = registry.install_analysis_artifacts(
        model_path=output_folder,
        parent_model_id=request.model_id,
        analysis_type="statistical_maps",
        results=results
    )
    
    return AnalysisResponse(
        job_id=analysis_id,
        status="completed",
        analysis_type="statistical-maps",
        artifacts=list(results.get('artifacts', []))
    )
```

### Target CLI Implementation Pattern (DEFERRED)

```python
# To be implemented in /emuses/cli/models_commands.py (DEFERRED - see Phase 3)
@models_app.command(help="Generate statistical maps analysis (DEFERRED)")
def analyze_statistical_maps(
    model_id: Annotated[str, typer.Option("--model-id", help="Registry model ID")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o")] = None,
    grid_size: Annotated[int, typer.Option("--grid-size")] = 100,
    confidence_method: Annotated[str, typer.Option("--confidence")] = "cv_ensemble",
    analysis_type: Annotated[str, typer.Option("--type")] = "statistical-maps",
) -> None:
    """Generate statistical analysis - REQUIRES model loading, normalization handling complexity."""
    
    # Registry integration
    registry = get_model_registry()
    model_path = registry.get_model_path(model_id)
    model_data = ModelIOManager(model_path.parent).load_model(model_path.name)
    
    # Parse model types
    model_type_list = [m.strip() for m in model_types.split(",")]
    
    # Setup output with per-target organization
    if output is None:
        output = model_path / "statistical_analysis"
    
    with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
        if per_target:
            # Process each target independently (from Copilot Notes)
            for target_name in model_data.metadata.target_names:
                task = progress.add_task(f"Analyzing target: {target_name}...", total=None)
                target_output = output / f"target_{target_name}"
                
                # Extract target-specific data
                target_scores = {target_name: model_data.metadata.scores_vectors[target_name]}
                
                # Run modern statistical analysis
                analyzer = ModernStatisticalAnalyzer(optuna_trials, model_type_list, grid_size)
                results = analyzer.run_statistical_analysis(
                    embeddings=model_data.metadata.scaled_embeddings,
                    scores_vectors_dict=target_scores,
                    combined_input_matrix=model_data.metadata.input_matrix,
                    output_folder=target_output
                )
                progress.complete_task(task)
        else:
            # Combined analysis
            task = progress.add_task("Running combined statistical analysis...", total=None)
            analyzer = ModernStatisticalAnalyzer(optuna_trials, model_type_list, grid_size)
            results = analyzer.run_statistical_analysis(
                embeddings=model_data.metadata.scaled_embeddings,
                scores_vectors_dict=model_data.metadata.scores_vectors,
                combined_input_matrix=model_data.metadata.input_matrix,
                output_folder=output
            )
            progress.complete_task(task)
    
    # Registry integration
    analysis_id = registry.install_analysis_artifacts(output, model_id, "statistical_maps")
    console.print(f"✅ Statistical maps analysis completed: [green]{analysis_id}[/green]")
```

## Critical Implementation Requirements (Corrected Understanding)

### What Actually Exists vs What Needs To Be Built

**✅ EXISTING MODERN FOUNDATIONS**:
- **HeatmapStage pipeline architecture** with modern optimization
- **new_pipeline_test function** with advanced statistical analysis
- **Model registry system** with artifact management
- **Scaled embeddings infrastructure** (prediction_train_coords)
- **Interactive visualization function** (plot_clustering_interactive_with_hover)

**🔧 NEEDS TO BE IMPLEMENTED**:
- **Statistical analysis module** extracting logic from new_pipeline_test
- **HeatmapStage statistical functionality** (uncomment and complete)
- **FastAPI endpoints** for statistical analysis
- **CLI commands** for analysis execution
- **Interactive visualization integration** with HTML generation
- **Per-target processing workflows** with proper artifact organization

### Implementation Architecture (Corrected)

**NOT Service Layer Addition** - This requires:
1. **Extract sophisticated statistical analysis** from new_pipeline_test
2. **Complete statistical analysis in HeatmapStage** (currently commented)
3. **Implement new ModernStatisticalAnalyzer class** 
4. **Create API/CLI interfaces** around statistical analysis functionality
5. **Integrate interactive visualization system**

### Dual-Method Analysis Approach (From Copilot Notes)

**Method 1: Kernel Regression Optimization**
- **Source**: Extract from `new_pipeline_test` lines 1581-1650
- **Approach**: Optuna optimization for robust sigma selection with nested CV
- **Purpose**: Statistical validation and space analysis

**Method 2: Model-Based Ensemble Predictions** 
- **Source**: HeatmapStage commented code + new_pipeline_test model comparison
- **Approach**: Multiple model types (GP, RF, GB, KR, XGBoost) with hyperparameter optimization
- **Purpose**: Model interpretation and clinical applications (PRIMARY)

### Critical Constraints (From Copilot Notes - Still Valid)

- **Per-target processing**: Each target variable processed independently in `target_*` directories
- **Scaled embeddings**: All operations use scaled UMAP embeddings (prediction_train_coords)
- **DO NOT use legacy functions**: run_kernel_heatmap_analysis is outdated reference only
- **DO build on modern architecture**: HeatmapStage + new_pipeline_test patterns

## Architecture Integration Notes

**Correct Implementation Flow**:
```
API/CLI Request → Model Registry Lookup → Load Model Data → 
ModernStatisticalAnalyzer.run_analysis() → 
  ├── Extract from new_pipeline_test (sigma optimization)
  └── Complete HeatmapStage statistical analysis (heatmaps, visualization)
→ Per-Target Processing → Artifact Generation → Registry Installation → Response
```

**Implementation Complexity**: 
- **Previous Wrong Assessment**: MEDIUM (service layer)
- **Corrected Assessment**: MEDIUM-HIGH (HeatmapStage enhancement with grid creation)
- **Effort**: 7-10 days (grid creation + statistical analysis + API integration + modular design)

## Technical Implementation Details (User Clarifications)

### 1. Prediction Grid Workflow
1. **Timing**: AFTER nested CV training in HeatmapStage (models available in context)
2. **Grid Generation**: 100x100 linspace on rescaled embeddings (0-1 coordinate system)
3. **Simplified Inference**: Skip input transformation, use trained models from context, denormalize predictions
4. **Confidence**: Aggregate 5-model confidence OR CV ensemble confidence (1-std approach)
5. **Output**: prediction*confidence heatmaps in target_*/heatmaps/ folders

### 2. Correlation Grid Workflow (NEW - from legacy analysis)
1. **GWD Computation**: For each grid point, compute Gaussian-Weighted Distance vectors to all training embeddings
2. **Sigma Optimization**: Use kernel regression optimization for optimal sigma parameter (from new_pipeline_test)
3. **Correlation Analysis**: Correlate GWD vectors with raw target scores (Pearson/Spearman/point-biserial methods)
4. **Grid Creation**: Generate correlation heatmap showing regions that correlate with target scores
5. **Output**: Correlation maps in target_*/correlation-maps/ folders

### 3. Region-Based Statistical Analysis Workflow (ENHANCED)
1. **Two-Stage Filtering**: 
   - **Visualization threshold** (e.g., 0.2): Points for plotting/display
   - **Effect size threshold** (e.g., 0.5): Stricter threshold for statistical analysis
2. **Region Selection**: Use correlation values OR prediction values to identify high-confidence regions
3. **Clustering Within Regions**: Apply HDBSCAN cluster assignments within selected regions
4. **Effect Size Calculation**: For each cluster with ≥3 points, compute effect size via input_matrix_stat_map
5. **Statistical Test**: Mann-Whitney tests between cluster points vs all other points
6. **Output**: Effect size maps for each qualifying cluster in target_*/statistical-maps/ folders

### 4. Grid-Based Statistical Analysis Strategy
- **Prediction-based statistical maps**: Use prediction grid values for region filtering → cluster within regions → effect size maps in `statistical-maps-prediction/`
- **Correlation-based statistical maps**: Use correlation grid values for region filtering → cluster within regions → effect size maps in `statistical-maps-correlation/`  
- **Different results**: Statistical maps will differ based on which grid method is used for filtering/clustering
- **Multiple clusters per region**: If HDBSCAN separates region into multiple clusters, create separate effect size maps for each qualifying cluster

### Enhanced Modular Function Architecture
- **PredictionGridCreator class**: 100x100 coordinate generation, simplified inference, confidence aggregation
- **CorrelationGridCreator class**: GWD vector computation, sigma optimization, correlation analysis (multiple methods)
- **RegionStatisticalAnalyzer class**: Two-stage filtering, region-based clustering, effect size calculation
- **Sigma optimization integration**: Extract from new_pipeline_test for kernel regression optimization
- **Legacy pattern reuse**: Leverage existing calculate_correlation_grid, compute_gwd_for_point, input_matrix_stat_map
- **Per-target processing**: Independent analysis for each target variable with triple folder structure

### CLI Independence Assessment (DEFERRED)
- **Complexity**: Model loading, normalization handling, file management outside pipeline
- **Decision**: DEFER unless very low risk and high success chance
- **Future**: Modular design reduces future implementation effort

This context provides the **corrected and clarified understanding** that the branch needs to implement HeatmapStage enhancement with **triple analysis system**: prediction grids + GWD-based correlation grids + region-based statistical maps, executed AFTER nested CV training with sophisticated two-stage filtering and clustering analysis.