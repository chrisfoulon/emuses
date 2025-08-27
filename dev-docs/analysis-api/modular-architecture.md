# Modular Function Architecture - Statistical Analysis Enhancement

## Overview

This document outlines the modular function architecture for implementing grid creation and statistical analysis functionality in HeatmapStage. The design prioritizes maintainability, testability, and future CLI independence.

## Core Architecture Principles

1. **Separation of Concerns**: Grid creation and statistical analysis as distinct modules
2. **Pipeline Integration**: Functions work within HeatmapStage context after nested CV training
3. **Future CLI Readiness**: Modular design enables future standalone CLI implementation
4. **Per-Target Processing**: Each target variable processed independently

## Module Structure

### 1. GridCreator Class (`/emuses/tools/grid_creator.py`)

```python
class GridCreator:
    """
    Creates prediction heatmaps using 100x100 coordinate grids and simplified inference.
    
    Executes AFTER nested CV training when models are available in pipeline context.
    """
    
    def __init__(self, grid_size: int = 100, confidence_method: str = "cv_ensemble"):
        self.grid_size = grid_size  # Default 100x100 grid
        self.confidence_method = confidence_method  # "5_model" or "cv_ensemble"
    
    def generate_coordinate_grid(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Generate 100x100 linspace coordinate grid on rescaled embeddings (0-1).
        
        Parameters
        ----------
        embeddings : np.ndarray
            Rescaled UMAP embeddings (prediction_train_coords from context)
        
        Returns
        -------
        np.ndarray
            Grid coordinates shape (10000, 2) for 100x100 grid
        """
        
    def simplified_inference(self, 
                           grid_coords: np.ndarray,
                           trained_models: dict,
                           target_name: str) -> tuple[np.ndarray, np.ndarray]:
        """
        Run inference on grid coordinates using trained models from context.
        
        Skips input data transformation since we start with grid coordinates.
        Includes denormalization to original value range.
        
        Parameters
        ----------
        grid_coords : np.ndarray
            100x100 grid coordinates
        trained_models : dict
            Trained models from pipeline context (after nested CV)
        target_name : str
            Target variable name for model selection
            
        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Predictions and confidence values for grid points
        """
        
    def aggregate_confidence(self, 
                           model_confidences: list[np.ndarray]) -> np.ndarray:
        """
        Aggregate confidence from 5 model predictions.
        
        Methods:
        - "5_model": Average of 5 model-specific confidences
        - "cv_ensemble": 1 - std of ensemble predictions
        
        Parameters
        ----------
        model_confidences : list[np.ndarray]
            Confidence values from each model
            
        Returns
        -------
        np.ndarray
            Aggregated confidence values
        """
    
    def create_prediction_heatmaps(self,
                                 embeddings: np.ndarray,
                                 trained_models: dict,
                                 target_data: dict,
                                 output_folder: Path,
                                 denormalize: bool = True) -> dict:
        """
        Main interface: Create prediction*confidence heatmaps for all targets.
        
        Creates target_*/heatmaps/ folder structure with artifacts.
        
        Parameters
        ----------
        embeddings : np.ndarray
            Rescaled embeddings (0-1 coordinates)
        trained_models : dict
            Models from pipeline context
        target_data : dict
            Target variable data and metadata
        output_folder : Path
            Base output directory
        denormalize : bool
            Whether to denormalize predictions to original range
            
        Returns
        -------
        dict
            Results with artifact paths and metadata
        """
```

### 2. StatisticalAnalyzer Class (`/emuses/tools/statistical_analyzer.py`)

```python
class StatisticalAnalyzer:
    """
    Creates statistical maps using effect size analysis with process_column(s) integration.
    
    Uses raw input data for statistical comparison between embedding regions.
    """
    
    def __init__(self, region_threshold: float = 0.1, method: str = "process_column"):
        self.region_threshold = region_threshold  # Threshold for region selection
        self.method = method  # Effect size calculation method
    
    def select_regions(self,
                      embeddings: np.ndarray,
                      cluster_labels: np.ndarray,
                      threshold: float) -> dict:
        """
        Select regions in embedding space using thresholds and clustering.
        
        Parameters
        ----------
        embeddings : np.ndarray
            Rescaled UMAP embeddings
        cluster_labels : np.ndarray
            Cluster assignments from HDBSCAN
        threshold : float
            Selection threshold for regions
            
        Returns
        -------
        dict
            Selected regions with coordinates and indices
        """
    
    def calculate_effect_size(self,
                            region_indices: np.ndarray,
                            input_matrix: np.ndarray,
                            target_scores: np.ndarray) -> dict:
        """
        Calculate effect size between region datapoints and others using process_column(s).
        
        Parameters
        ----------
        region_indices : np.ndarray
            Indices of datapoints in selected region
        input_matrix : np.ndarray
            Raw input data used for UMAP training
        target_scores : np.ndarray
            Target variable scores
            
        Returns
        -------
        dict
            Effect size statistics and significance tests
        """
    
    def create_statistical_maps(self,
                              embeddings: np.ndarray,
                              input_matrix: np.ndarray,
                              target_data: dict,
                              cluster_labels: np.ndarray,
                              output_folder: Path) -> dict:
        """
        Main interface: Create statistical maps for all targets.
        
        Creates target_*/statistical-maps/ folder structure with artifacts.
        
        Parameters
        ----------
        embeddings : np.ndarray
            Rescaled embeddings for region selection
        input_matrix : np.ndarray
            Raw input data for statistical analysis
        target_data : dict
            Target variable data and metadata
        cluster_labels : np.ndarray
            Cluster assignments for region selection
        output_folder : Path
            Base output directory
            
        Returns
        -------
        dict
            Results with artifact paths and statistical maps
        """
```

### 3. HeatmapStage Integration (`/emuses/pipelines/heatmap_stage.py`)

```python
class HeatmapStage(PipelineStage):
    def run(self, context, progress_queue=None):
        # ... existing pipeline logic until nested CV training completes ...
        
        # Statistical Analysis Enhancement (after nested CV training)
        if getattr(self.config, "enable_statistical_analysis", False):
            self._run_statistical_analysis(context)
    
    def _run_statistical_analysis(self, context):
        """
        Execute grid creation and statistical analysis after nested CV training.
        
        Models are available in context, no need for loading from disk.
        """
        # Get required data from context
        prediction_train_coords = context.get("prediction_train_coords")  # 0-1 scaled
        prediction_train_labels = context.get("prediction_train_labels")  # Target scores
        trained_models = context.get("trained_models")  # From nested CV
        cluster_labels = context.get("prediction_train_cluster_labels")
        
        # Raw input data for statistical analysis
        prediction_train_features = context.get("prediction_train_features")
        
        # Per-target processing
        target_names = context.get("target_names", [])
        
        for target_idx, target_name in enumerate(target_names):
            target_output = Path(self.config.output_folder) / f"target_{target_name}"
            
            # Grid Creation
            if getattr(self.config, "enable_heatmaps", True):
                grid_creator = GridCreator(
                    grid_size=getattr(self.config, "grid_size", 100),
                    confidence_method=getattr(self.config, "confidence_method", "cv_ensemble")
                )
                
                heatmap_results = grid_creator.create_prediction_heatmaps(
                    embeddings=prediction_train_coords,
                    trained_models=trained_models,
                    target_data={target_name: prediction_train_labels[:, target_idx]},
                    output_folder=target_output
                )
                
                context[f"heatmap_results_{target_name}"] = heatmap_results
            
            # 3. Region-Based Statistical Analysis
            if getattr(self.config, "enable_statistical_maps", True):
                region_analyzer = RegionStatisticalAnalyzer(
                    visualization_threshold=getattr(self.config, "visualization_threshold", 0.2),
                    effect_size_threshold=getattr(self.config, "effect_size_threshold", 0.5),
                    min_cluster_size=getattr(self.config, "min_cluster_size", 3)
                )
                
                # Use correlation values from correlation grid as reference (or prediction values)
                reference_values = correlation_results.get("correlation_values", 
                                                         prediction_results.get("prediction_values"))
                
                statistical_results = region_analyzer.create_region_statistical_maps(
                    embeddings=prediction_train_coords,
                    input_matrix=prediction_train_features,
                    target_data={target_name: prediction_train_labels[:, target_idx]},
                    cluster_labels=cluster_labels,
                    reference_values=reference_values,
                    output_folder=target_output
                )
                
                context[f"statistical_results_{target_name}"] = statistical_results
        
        # Interactive visualization integration
        if getattr(self.config, "interactive_plot", False):
            self._create_interactive_visualizations(context)
    
    def _create_interactive_visualizations(self, context):
        """
        Enhance interactive visualizations with statistical analysis metadata.
        """
        # Integration with plot_clustering_interactive_with_hover
        # Add heatmap and statistical map overlays
        pass
```

## Configuration Integration

### Configuration Options

```python
# In pipeline configuration
enable_statistical_analysis: bool = True
enable_heatmaps: bool = True
enable_statistical_maps: bool = True

# Grid creation parameters
grid_size: int = 100
confidence_method: str = "cv_ensemble"  # "5_model" or "cv_ensemble"

# Statistical analysis parameters  
region_threshold: float = 0.1
effect_size_method: str = "process_column"

# Visualization
interactive_plot: bool = True
```

## Artifact Organization

### Per-Target Directory Structure (Grid-Based Organization)

```
target_cognitive_flexibility/
├── prediction-grids/
│   ├── prediction_heatmap.png
│   ├── confidence_heatmap.png  
│   ├── combined_heatmap.png (prediction*confidence)
│   ├── prediction_values.npy              # Grid prediction values for region filtering
│   └── prediction_metadata.json
├── correlation-grids/
│   ├── correlation_heatmap.png
│   ├── correlation_values.npy             # Grid correlation values for region filtering
│   ├── optimized_sigma.json
│   └── correlation_metadata.json
├── statistical-maps-prediction/       # Statistical maps using prediction grid for filtering
│   ├── cluster_0_effect_size_map.csv      # Effect size maps for clusters ≥3 points
│   ├── cluster_0_effect_size_map.png
│   ├── cluster_1_effect_size_map.csv
│   ├── cluster_1_effect_size_map.png
│   ├── prediction_based_filtering.csv    # Two-stage filtering results
│   ├── cluster_assignments.npy            # High-confidence region clusters
│   └── statistical_metadata.json
├── statistical-maps-correlation/      # Statistical maps using correlation grid for filtering
│   ├── cluster_0_effect_size_map.csv      # Different clusters than prediction-based
│   ├── cluster_0_effect_size_map.png
│   ├── cluster_2_effect_size_map.csv      # May have different cluster IDs
│   ├── cluster_2_effect_size_map.png
│   ├── correlation_based_filtering.csv   # Two-stage filtering results
│   ├── cluster_assignments.npy            # High-confidence region clusters
│   └── statistical_metadata.json
└── interactive/
    ├── prediction_grid_visualization.html # Prediction grid + statistical maps overlay
    ├── correlation_grid_visualization.html # Correlation grid + statistical maps overlay
    ├── combined_analysis_comparison.html   # Side-by-side comparison of both methods
    └── metadata.json
```

**Key Point**: Statistical maps will be **different** in `statistical-maps-prediction/` vs `statistical-maps-correlation/` because:
- Different grid values used for region filtering (prediction vs correlation)
- Different high-confidence regions identified  
- Different clustering results within regions
- Different effect size maps for different clusters

## Testing Strategy

### Unit Testing

- **GridCreator**: Test coordinate generation, inference, confidence aggregation
- **StatisticalAnalyzer**: Test region selection, effect size calculation  
- **HeatmapStage**: Test integration without breaking existing pipeline

### Integration Testing

- **Pipeline Integration**: Test complete workflow from nested CV to artifacts
- **Per-Target Processing**: Test independent target variable handling
- **Artifact Generation**: Test file creation and metadata consistency

## Future CLI Independence

### Design Considerations

The modular architecture enables future CLI implementation by:

1. **Model Loading**: GridCreator/StatisticalAnalyzer can accept pre-loaded models
2. **Data Normalization**: Functions can handle normalization state externally  
3. **File Management**: Artifact creation separated from pipeline context
4. **Configuration**: Parameter passing through function interfaces

### CLI Implementation Path (When Ready)

```python
# Future CLI implementation approach
def analyze_statistical_maps_cli(model_id: str, **kwargs):
    # Load model and data from registry
    registry = get_model_registry()
    model_data = registry.load_model(model_id)
    
    # Initialize analyzers
    grid_creator = GridCreator(**grid_params)
    stat_analyzer = StatisticalAnalyzer(**stat_params)
    
    # Execute analysis
    results = stat_analyzer.create_statistical_maps(
        embeddings=model_data.embeddings,
        input_matrix=model_data.input_matrix,
        target_data=model_data.targets,
        cluster_labels=model_data.clusters,
        output_folder=output_path
    )
```

This enhanced modular architecture provides the foundation for sophisticated **triple analysis system** implementation (prediction + correlation + region-based statistical maps) while preserving future CLI independence options and leveraging existing EMUSES statistical analysis patterns.