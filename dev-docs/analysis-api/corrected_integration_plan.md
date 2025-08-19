# Statistical Map Generation Integration - CORRECTED PLAN

## Overview
After detailed analysis, the current HeatmapStage performs **model training and optimization** using Optuna CV but lacks the **analysis capabilities** that were in the legacy code. This corrected integration plan adds back the missing functionality using existing EMUSES infrastructure.

## Key Discoveries and Corrections

### ✅ What Already Works (No Changes Needed)
1. **Out-of-sample validation**: CV scores from `nested_optuna_cv` are already scientifically valid (lines 215-216: `score = best_pipe.score(X_te, y_te)`)
2. **Data preparation**: All data is already properly formatted in context (`prediction_train_coords`, `prediction_train_labels`)
3. **Ensemble prediction infrastructure**: Both `ensemble_predict()` function and InferenceStage approach exist
4. **Statistical calculation functions**: `input_matrix_stat_map()`, `calculate_correlation_grid()` already implemented
5. **Visualization functions**: `plot_clustering_interactive_with_hover()` already exists

### ❌ What's Actually Missing
1. **Grid ensemble predictions** for thresholding (100x100 grid on normalized 0-1 embedding space)
2. **Statistical map generation** based on cluster comparisons (inside vs outside cluster in original feature space)
3. **Interactive visualizations** (code exists but is commented out in HeatmapStage)

### 🔧 Corrected Understanding of Statistical Maps
**NOT**: Prediction heatmaps on 2D embedding grid  
**ACTUALLY**: Effect size comparisons between inside vs outside cluster points in original high-dimensional feature space

Process:
1. Get HDBSCAN cluster labels
2. For each cluster: identify indices of points inside vs outside
3. Compare original input features between inside/outside groups  
4. Compute effect sizes for each feature dimension
5. Apply threshold: `(prediction_value + confidence) / 2` to filter significant points
6. Result: Statistical map with input data dimensionality

## Simplified Integration Strategy

```
Current Workflow (Optuna CV) → Grid Predictions → Statistical Maps → Visualizations → Complete Output
```

## Implementation Plan

### Phase 1: Grid Prediction Generation
```python
def _generate_grid_predictions_with_uncertainty(self, embeddings, trained_models, task):
    """
    Generate ensemble predictions on 100x100 grid across embedding space (0-1 normalized).
    Use InferenceStage approach for consistency with existing API.
    """
    # Create 100x100 grid (configurable)
    grid_size = getattr(self.config, 'grid_size', 100)
    x_grid = np.linspace(0, 1, grid_size)
    y_grid = np.linspace(0, 1, grid_size)
    xx, yy = np.meshgrid(x_grid, y_grid)
    grid_coords = np.column_stack([xx.ravel(), yy.ravel()])
    
    # Use InferenceStage-style ensemble prediction
    ensemble_predictions = []
    confidence_scores = []
    
    for target, models in trained_models.items():
        individual_preds = []
        for model in models:
            pred = model.predict(grid_coords)
            individual_preds.append(pred)
        
        # Ensemble mean and confidence (like InferenceStage)
        ensemble_mean = np.mean(individual_preds, axis=0)
        confidence = 1.0 - np.std(individual_preds, axis=0)  # Higher std = lower confidence
        
        ensemble_predictions.append(ensemble_mean)
        confidence_scores.append(confidence)
    
    return {
        'grid_coordinates': grid_coords,
        'grid_shape': (grid_size, grid_size),
        'ensemble_predictions': ensemble_predictions,
        'confidence_scores': confidence_scores
    }
```

### Phase 2: Statistical Map Generation
```python
def _generate_cluster_based_statistical_maps(self, embeddings, labels, input_features, grid_predictions, context, task):
    """
    Generate statistical maps based on cluster comparisons in original feature space.
    """
    from emuses.tools.stats_utils import input_matrix_stat_map
    
    # Get or compute cluster labels
    cluster_labels = self._get_cluster_labels(context, embeddings)
    
    # Apply prediction threshold: (prediction + confidence) / 2
    threshold_mask = self._apply_prediction_threshold(grid_predictions, embeddings)
    
    statistical_maps = {}
    
    for cluster_id in np.unique(cluster_labels):
        if cluster_id == -1:  # Skip noise points
            continue
            
        # Inside vs outside cluster indices
        inside_idx = np.where(cluster_labels == cluster_id)[0]
        outside_idx = np.where(cluster_labels != cluster_id)[0]
        
        # Apply threshold filtering
        inside_idx = inside_idx[threshold_mask[inside_idx]]
        outside_idx = outside_idx[threshold_mask[outside_idx]]
        
        if len(inside_idx) < 5 or len(outside_idx) < 5:  # Skip small clusters
            continue
        
        # Compute effect sizes in original feature space
        inside_features = input_features[inside_idx]
        outside_features = input_features[outside_idx]
        
        effect_size_map = input_matrix_stat_map(
            inside_features, outside_features, 
            test_type='cohen_d'  # or from config
        )
        
        statistical_maps[f'cluster_{cluster_id}'] = {
            'effect_size_map': effect_size_map,
            'inside_count': len(inside_idx),
            'outside_count': len(outside_idx)
        }
    
    return {'statistical_maps': statistical_maps}

def _apply_prediction_threshold(self, grid_predictions, embeddings):
    """
    Apply threshold: (prediction_value + confidence) / 2 to determine significant points.
    """
    predictions = grid_predictions['ensemble_predictions'][0]  # First target
    confidence = grid_predictions['confidence_scores'][0]
    
    threshold_values = (predictions + confidence) / 2
    # Apply threshold logic (implementation depends on specific criteria)
    threshold_mask = threshold_values > np.median(threshold_values)  # Example
    
    return threshold_mask

def _get_cluster_labels(self, context, embeddings):
    """
    Get cluster labels from context or compute them if needed.
    """
    # Try to get existing cluster labels
    cluster_labels = context.get("embedding_train_cluster_labels")
    
    if cluster_labels is None:
        # Compute clustering if not available
        clusterer = context.get("embedding_train_clusterer")
        if clusterer is not None:
            cluster_labels = clusterer.fit_predict(embeddings)
        else:
            # Fallback: create simple clustering
            import hdbscan
            clusterer = hdbscan.HDBSCAN(min_cluster_size=5)
            cluster_labels = clusterer.fit_predict(embeddings)
    
    return cluster_labels
```

### Phase 3: Interactive Visualizations  
```python
def _generate_interactive_visualizations(self, embeddings, labels, context, task):
    """
    Generate interactive HTML visualizations using existing EMUSES functions.
    Restore the commented-out visualization code.
    """
    if not getattr(self.config, 'interactive_plot', False):
        return {'interactive_visualizations_generated': False}
    
    from emuses.tools.visualisation import plot_clustering_interactive_with_hover
    
    interactive_folder = Path(self.config.output_folder) / "interactive_plots"
    interactive_folder.mkdir(exist_ok=True)
    
    # Simple scores vector preparation
    scores_vectors_dict = self._prepare_scores_vectors(labels, task)
    
    visualization_results = {'interactive_plots': {}}
    
    # Generate plots for each score vector
    for score_name, score_vector in scores_vectors_dict.items():
        interactive_path = interactive_folder / f"interactive_embeddings_{score_name}.html"
        
        fig = plot_clustering_interactive_with_hover(
            embeddings,
            score_vector,
            output_path=interactive_path,
            show_plot=False,
            return_plot=True,
            title=f"Embeddings colored by {score_name}"
        )
        
        visualization_results['interactive_plots'][score_name] = {
            'path': str(interactive_path),
            'figure': fig
        }
    
    return {
        'interactive_visualizations': visualization_results,
        'interactive_visualizations_generated': True
    }

def _prepare_scores_vectors(self, labels, task):
    """Simple conversion of labels to scores vectors dictionary."""
    if task == "clf":
        if labels.ndim == 1:
            unique_labels = np.unique(labels)
            return {str(label): (labels == label).astype(int) for label in unique_labels}
        else:
            return {f"class_{i}": labels[:, i] for i in range(labels.shape[1])}
    else:
        if labels.ndim == 1:
            return {"score": labels}
        else:
            return {f"score_{i}": labels[:, i] for i in range(labels.shape[1])}
```

## Integration Points

### Configuration Options
```python
# Add to pipeline config
statistical_map_grid_size: int = 100           # Grid size for predictions
generate_statistical_maps: bool = True         # Enable statistical maps
generate_grid_predictions: bool = True         # Enable grid predictions
prediction_threshold_method: str = "median"    # Thresholding method
effect_size_test: str = "cohen_d"             # Effect size calculation
```

### Helper Methods
```python
def _get_input_features_for_stats(self, context):
    """Get original high-dimensional features for statistical calculations."""
    return (context.get("prediction_train_features") or 
            context.get("embedding_train_features"))

def _should_generate_grid_predictions(self, context):
    """Check if grid predictions should be generated."""
    return (getattr(self.config, 'generate_grid_predictions', True) and 
            len(context.get("prediction_models", [])) > 0)

def _should_generate_statistical_maps(self, context):
    """Check if statistical maps should be generated.""" 
    return (getattr(self.config, 'generate_statistical_maps', True) and
            context.get("prediction_train_coords") is not None and
            self._get_input_features_for_stats(context) is not None)

def _should_generate_visualizations(self, context):
    """Check if interactive visualizations should be generated."""
    return getattr(self.config, 'interactive_plot', False)
```

## Benefits of This Corrected Approach

1. **Minimal Code Changes**: Uses existing EMUSES infrastructure without complex modifications
2. **No Optuna CV Changes**: Avoids complexity of modifying `nested_optuna_cv` 
3. **Existing Validation**: CV scores already provide out-of-sample validation
4. **Consistent API**: Uses InferenceStage approach for ensemble predictions
5. **Real Statistical Maps**: Implements proper cluster-based effect size comparisons
6. **Configurable**: Grid size, thresholds, and effect size methods are configurable

## Implementation Checklist

- [ ] Add grid prediction generation after Optuna CV
- [ ] Implement cluster-based statistical map generation
- [ ] Restore interactive visualizations from commented code
- [ ] Add configuration options for grid size and thresholds
- [ ] Test with existing EMUSES data pipeline
- [ ] Validate statistical map outputs match legacy behavior
- [ ] Document new analysis capabilities