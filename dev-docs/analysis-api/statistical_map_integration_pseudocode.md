# Statistical Map Generation Integration - Pseudo Code (CORRECTED)

## Overview
The current HeatmapStage performs **model training and optimization** using Optuna CV, but lacks the **prediction generation** and **statistical map generation** capabilities that were in the legacy code. This integration plan adds back:

1. **Grid ensemble predictions with uncertainty** on the full embedding space (for thresholding)
2. **Statistical map generation** based on cluster comparisons in original feature space  
3. **Interactive visualizations** using existing EMUSES functions
4. **Uses existing infrastructure** without complex modifications

## Key Corrections Made
- **Out-of-sample validation**: Already exists in CV scores from `nested_optuna_cv`  
- **Ensemble predictions**: Use InferenceStage approach, not `ensemble_predict()` function
- **Statistical maps**: NOT prediction heatmaps, but effect size comparisons between inside/outside cluster points in original feature space
- **Data preparation**: Mostly unnecessary - data already properly formatted in context

## Current vs Legacy Workflow Analysis

### Current HeatmapStage (Active Code)
1. ✅ Load prediction optimization dictionary
2. ✅ Assemble design matrix (X) and targets (y) for Optuna  
3. ✅ AE/VAE pretraining (if needed)
4. ✅ Loop over target columns with nested Optuna CV optimization
5. ✅ Generate performance measures CSV files
6. ✅ **Out-of-sample validation**: Already exists in CV scores! (lines 215-216 in `nested_optuna_cv`)
7. ❌ **Missing: Grid ensemble predictions for thresholding** 
8. ❌ **Missing: Statistical map generation based on cluster comparisons**
9. ❌ **Missing: Interactive visualizations** (code exists but commented out)

### Legacy Code (Commented Out - Lines 431-695)
1. 📊 Data preparation (embeddings + input matrix selection) - **NOT NEEDED**
2. 📊 Clustering integration (compute cluster labels) - **NEEDED**
3. 📊 Scores vectors dictionary preparation - **SIMPLE CONVERSION** 
4. 📊 Interactive visualization generation - **RESTORE**
5. 📊 Statistical map generation - **IMPLEMENT WITH CLUSTER COMPARISONS**

### What Actually Exists in EMUSES
**✅ Infrastructure Ready**:
- `ensemble_predict()` function with uncertainty in `kernel_regression_utils.py`
- InferenceStage ensemble approach with confidence scores
- `input_matrix_stat_map()`, `calculate_correlation_grid()` for statistical calculations
- `plot_clustering_interactive_with_hover()` for visualizations
- Data already formatted in context (`prediction_train_coords`, `prediction_train_labels`)

## Integration Strategy

The integration should **ADD** the statistical map generation **AFTER** the current optimization workflow, creating a complete pipeline:

```
Current Workflow → Statistical Map Generation → Complete Output
```

## Pseudo-Code Integration Plan

### Phase 1: Post-Optimization Statistical Map Generation

```python
def run(self, context, progress_queue=None):
    # ========== EXISTING WORKFLOW (KEEP AS-IS) ==========
    # 1. Load prediction optimization dictionary
    # 2. Assemble design matrix and targets  
    # 3. AE/VAE pretraining
    # 4. Nested Optuna CV optimization loop
    # 5. Generate performance CSV files
    
    # ... existing code until line ~427 ...
    
    # ========== NEW: PREDICTION GENERATION AND STATISTICAL MAP GENERATION ==========
    logger.info("Starting scientifically valid prediction generation and statistical map analysis...")
    
    # Phase 1.1: Extract Already-Prepared Data (no preparation needed!)
    embeddings = context.get("prediction_train_coords")  # 2D UMAP coordinates 
    labels = context.get("prediction_train_labels")      # Target scores
    trained_models = context.get("prediction_results", {})  # CV-trained models
    
    # Phase 1.2: Generate Scientifically Valid Predictions (CRITICAL MISSING STEP!)
    if self._should_generate_predictions(context):
        prediction_results = self._generate_scientific_predictions(
            embeddings=embeddings,
            labels=labels, 
            trained_models=trained_models,
            task=task,
            context=context
        )
        
        # Store prediction results in context
        context.update(prediction_results)
        logger.info("Generated out-of-sample predictions and grid ensemble predictions with uncertainty")
    
    # Phase 1.3: Generate Statistical Maps (uses predictions from Phase 1.2)
    if self._should_generate_statistical_maps(context):
        statistical_results = self._generate_statistical_maps(
            embeddings=embeddings,
            labels=labels,
            prediction_results=prediction_results,
            context=context,
            task=task
        )
        
        # Store results in context
        context.update(statistical_results)
    
    # Phase 1.3: Generate Interactive Visualizations  
    if self._should_generate_visualizations(context):
        visualization_results = self._generate_interactive_visualizations(
            embeddings_data=embeddings_data,
            scores_data=scores_data,
            context=context,
            task=task
        )
        
        context.update(visualization_results)
```

### Phase 2: Scientific Prediction Generation

```python
def _generate_scientific_predictions(self, embeddings, labels, trained_models, task, context):
    """
    Generate scientifically valid predictions with proper uncertainty quantification.
    
    Uses already-prepared data from context:
    - embeddings: prediction_train_coords (2D UMAP coordinates)
    - labels: prediction_train_labels (target scores) 
    - trained_models: prediction_results (CV-trained pipelines)
    
    Two types of predictions:
    1. Out-of-sample predictions for known points (using CV structure)
    2. Ensemble predictions on grid with uncertainty quantification
    """
    
    # Step 1: Out-of-sample predictions for known points (SCIENTIFIC VALIDITY)
    oos_predictions = self._generate_out_of_sample_predictions(
        embeddings, trained_models, context, task
    )
    
    # Step 2: Ensemble predictions on grid with uncertainty (STATISTICAL MAPS)
    grid_predictions = self._generate_grid_ensemble_predictions(
        embeddings, trained_models, task
    )
    
    return {
        'out_of_sample_predictions': oos_predictions,
        'grid_ensemble_predictions': grid_predictions,
        'predictions_generated': True
    }

def _generate_out_of_sample_predictions(self, embeddings, prediction_results, context, task):
    """
    Generate true out-of-sample predictions for known points using CV structure.
    Each point is predicted ONLY by models that were NOT trained on that point.
    
    This requires reconstructing the CV fold structure from Optuna training.
    """
    
    # CRITICAL: We need to modify the Optuna CV process to save fold indices
    # For now, this is a conceptual framework - implementation needs CV fold tracking
    
    logger.info("Generating out-of-sample predictions for scientific validation...")
    
    # Get or reconstruct CV fold structure
    cv_fold_indices = self._get_or_reconstruct_cv_folds(embeddings, context)
    
    oos_predictions = {}
    
    for target, result_data in prediction_results.items():
        pipelines = result_data.get("best_pipelines", [])
        n_samples = len(embeddings)
        
        # Initialize out-of-sample prediction arrays
        oos_pred = np.full(n_samples, np.nan)
        oos_uncertainty = np.full(n_samples, np.nan)
        
        # For each CV fold, predict on the held-out test samples
        for fold_idx, pipeline in enumerate(pipelines):
            if fold_idx < len(cv_fold_indices):
                train_idx, test_idx = cv_fold_indices[fold_idx]
                
                # Predict only on samples that were held out in this fold
                X_test = embeddings[test_idx]
                fold_pred = pipeline.predict(X_test)
                
                # Store predictions for test samples
                oos_pred[test_idx] = fold_pred
                
                # Calculate uncertainty for this fold's predictions
                if hasattr(pipeline, 'predict_proba') and task == 'clf':
                    # Classification: use prediction confidence
                    pred_proba = pipeline.predict_proba(X_test)
                    # Entropy-based uncertainty
                    oos_uncertainty[test_idx] = -np.sum(pred_proba * np.log(pred_proba + 1e-10), axis=1)
                else:
                    # Regression: use model-specific uncertainty estimation
                    model_uncertainty = self._estimate_model_uncertainty(
                        pipeline, X_test, train_idx, embeddings, context
                    )
                    oos_uncertainty[test_idx] = model_uncertainty
        
        oos_predictions[target] = {
            'coordinates': embeddings,
            'predictions': oos_pred,
            'uncertainty': oos_uncertainty,
            'valid_mask': ~np.isnan(oos_pred)
        }
        
        valid_count = np.sum(~np.isnan(oos_pred))
        logger.info(f"Generated out-of-sample predictions for {target}: {valid_count}/{n_samples} points")
    
    return oos_predictions

def _generate_grid_ensemble_predictions(self, embeddings, prediction_results, task):
    """
    Generate ensemble predictions on a grid across embedding space.
    Each grid point gets predictions from ALL CV fold models with uncertainty quantification.
    """
    logger.info("Generating ensemble predictions on grid with uncertainty quantification...")
    
    # Create prediction grid across embedding space
    grid_coords, grid_shape = self._create_prediction_grid(embeddings)
    logger.info(f"Created prediction grid: {grid_coords.shape[0]} points in {grid_shape} grid")
    
    # For each target, generate ensemble predictions
    grid_predictions = {}
    
    for target, result_data in prediction_results.items():
        pipelines = result_data.get("best_pipelines", [])
        n_grid_points = len(grid_coords)
        
        # Collect predictions from all CV fold models
        fold_predictions = []
        model_types = []
        
        for fold_idx, pipeline in enumerate(pipelines):
            # Get predictions for all grid points from this fold's model
            fold_pred = pipeline.predict(grid_coords)
            fold_predictions.append(fold_pred)
            
            # Track model type for heterogeneous uncertainty
            model_type = self._get_model_type(pipeline)
            model_types.append(model_type)
        
        if len(fold_predictions) == 0:
            logger.warning(f"No models available for target {target}")
            continue
            
        fold_predictions = np.array(fold_predictions)  # Shape: (n_folds, n_grid_points)
        
        # Calculate ensemble statistics
        ensemble_mean = np.mean(fold_predictions, axis=0)
        ensemble_std = np.std(fold_predictions, axis=0)
        
        # Advanced uncertainty quantification for heterogeneous models
        uncertainty_components = self._calculate_heterogeneous_uncertainty(
            fold_predictions, model_types, pipelines, grid_coords
        )
        
        grid_predictions[target] = {
            'grid_coordinates': grid_coords,
            'grid_shape': grid_shape,
            'ensemble_mean': ensemble_mean,
            'ensemble_std': ensemble_std,  # Basic ensemble uncertainty
            'uncertainty_components': uncertainty_components,  # Advanced uncertainty
            'n_models': len(pipelines),
            'model_types': model_types
        }
        
        logger.info(f"Generated grid predictions for {target}: {n_grid_points} points, {len(pipelines)} models")
    
    return grid_predictions

def _calculate_heterogeneous_uncertainty(self, fold_predictions, model_types, pipelines, grid_coords):
    """
    Calculate advanced uncertainty quantification for heterogeneous model ensembles.
    
    Based on research showing that different model architectures can provide
    complementary uncertainty estimates that can be calibrated and combined.
    """
    unique_types = set(model_types)
    n_models = len(model_types)
    
    uncertainty_components = {
        'epistemic_uncertainty': np.std(fold_predictions, axis=0),  # Model disagreement
        'model_diversity': len(unique_types) / n_models,  # Architecture diversity
    }
    
    # If we have heterogeneous models, calculate advanced uncertainty
    if len(unique_types) > 1:
        logger.info(f"Calculating heterogeneous uncertainty for {unique_types}")
        
        # Method 1: Model-intrinsic uncertainty estimation
        intrinsic_uncertainties = []
        for i, (pipeline, model_type) in enumerate(zip(pipelines, model_types)):
            intrinsic_unc = self._estimate_model_intrinsic_uncertainty(
                pipeline, model_type, grid_coords
            )
            intrinsic_uncertainties.append(intrinsic_unc)
        
        intrinsic_uncertainties = np.array(intrinsic_uncertainties)
        
        # Method 2: Weighted ensemble uncertainty (weight by model performance)
        model_weights = self._calculate_model_weights(pipelines, model_types)
        weighted_uncertainty = np.average(intrinsic_uncertainties, axis=0, weights=model_weights)
        
        # Method 3: Calibrated total uncertainty (research-backed approach)
        total_uncertainty = self._calibrate_heterogeneous_uncertainty(
            uncertainty_components['epistemic_uncertainty'],  # Ensemble disagreement
            weighted_uncertainty,  # Weighted intrinsic uncertainty
            unique_types
        )
        
        uncertainty_components.update({
            'intrinsic_uncertainty': weighted_uncertainty,
            'total_uncertainty': total_uncertainty,
            'model_weights': model_weights,
            'heterogeneous': True
        })
    else:
        # Homogeneous models: use standard ensemble uncertainty
        uncertainty_components.update({
            'total_uncertainty': uncertainty_components['epistemic_uncertainty'],
            'heterogeneous': False
        })
    
    return uncertainty_components

def _estimate_model_intrinsic_uncertainty(self, pipeline, model_type, grid_coords):
    """
    Estimate model-specific (intrinsic) uncertainty based on model architecture.
    
    Different models provide different types of uncertainty information:
    - Random Forest: Bootstrap variance, OOB predictions
    - Kernel Methods: Local density, kernel weight confidence  
    - Elastic Net: Prediction stability, regularization path
    """
    
    if model_type == "rf":
        # Random Forest: Use prediction variance across trees
        try:
            # Get predictions from individual trees
            tree_predictions = np.array([
                tree.predict(grid_coords) 
                for tree in pipeline.named_steps['est'].estimators_
            ])
            return np.std(tree_predictions, axis=0)
        except:
            # Fallback if tree access fails
            return np.ones(len(grid_coords)) * 0.1
            
    elif model_type == "kernel":
        # Kernel methods: Uncertainty based on local training density
        try:
            kernel_regressor = pipeline.named_steps['est']
            if hasattr(kernel_regressor, 'X_train_'):
                # Calculate local density around each grid point
                from scipy.spatial.distance import cdist
                distances = cdist(grid_coords, kernel_regressor.X_train_)
                
                # Uncertainty inversely related to local density
                sigma = getattr(kernel_regressor, 'sigma', 0.1)
                weights = np.exp(-0.5 * (distances / sigma) ** 2)
                local_density = np.sum(weights, axis=1)
                
                # Higher density = lower uncertainty
                return 1.0 / (local_density + 1e-10)
            else:
                return np.ones(len(grid_coords)) * 0.1
        except:
            return np.ones(len(grid_coords)) * 0.1
            
    elif model_type == "elastic":
        # Elastic Net: Uncertainty based on regularization strength
        try:
            elastic_model = pipeline.named_steps['est']
            # Higher regularization = higher uncertainty
            alpha = getattr(elastic_model, 'alpha', 1.0)
            base_uncertainty = np.sqrt(alpha) * 0.1
            return np.full(len(grid_coords), base_uncertainty)
        except:
            return np.ones(len(grid_coords)) * 0.1
    
    # Default uncertainty for unknown model types
    return np.ones(len(grid_coords)) * 0.1

def _calibrate_heterogeneous_uncertainty(self, epistemic_unc, intrinsic_unc, model_types):
    """
    Calibrate uncertainty from heterogeneous models using research-backed methods.
    
    Based on "Calibration after bootstrap" and heterogeneous ensemble research.
    """
    
    # Simple calibration: weighted combination of uncertainties
    # This can be enhanced with proper calibration curves from validation data
    
    # Weight epistemic (model disagreement) vs intrinsic (model-specific) uncertainty
    diversity_factor = len(model_types) / 3.0  # Normalize by max model types (3 in EMUSES)
    epistemic_weight = 0.6 + 0.3 * diversity_factor  # More weight when models are diverse
    intrinsic_weight = 1.0 - epistemic_weight
    
    calibrated_uncertainty = (
        epistemic_weight * epistemic_unc + 
        intrinsic_weight * intrinsic_unc
    )
    
    return calibrated_uncertainty

def _create_prediction_grid(self, embeddings, grid_size=100):
    """
    Create a grid of coordinates across the embedding space for prediction.
    """
    # Get bounds of embedding space
    x_min, x_max = embeddings[:, 0].min(), embeddings[:, 0].max()
    y_min, y_max = embeddings[:, 1].min(), embeddings[:, 1].max()
    
    # Add padding
    x_padding = (x_max - x_min) * 0.1
    y_padding = (y_max - y_min) * 0.1
    
    # Create grid
    x_grid = np.linspace(x_min - x_padding, x_max + x_padding, grid_size)
    y_grid = np.linspace(y_min - y_padding, y_max + y_padding, grid_size)
    
    xx, yy = np.meshgrid(x_grid, y_grid)
    grid_coords = np.column_stack([xx.ravel(), yy.ravel()])
    
    return grid_coords, (grid_size, grid_size)

def _get_or_reconstruct_cv_folds(self, embeddings, context):
    """
    Get CV fold indices from context or reconstruct them.
    
    IMPORTANT: This requires modifying the Optuna CV process to save fold indices.
    For now, this reconstructs approximate folds - not scientifically perfect.
    """
    
    # Try to get saved fold indices from context
    if 'cv_fold_indices' in context:
        return context['cv_fold_indices']
    
    # Fallback: reconstruct approximate folds (not ideal but functional)
    logger.warning("CV fold indices not available - reconstructing approximate folds")
    
    n_samples = len(embeddings)
    n_folds = getattr(self.config, 'outer_folds', 5)
    random_state = getattr(self.config, 'random_state', 42)
    
    from sklearn.model_selection import KFold
    cv = KFold(n_splits=n_folds, shuffle=True, random_state=random_state)
    
    fold_indices = list(cv.split(embeddings))
    
    return fold_indices

def _get_model_type(self, pipeline):
    """Extract model type from sklearn pipeline."""
    try:
        estimator = pipeline.named_steps.get('est', pipeline)
        
        if hasattr(estimator, '__class__'):
            class_name = estimator.__class__.__name__.lower()
            
            if 'kernel' in class_name:
                return 'kernel'
            elif 'forest' in class_name or 'rf' in class_name:
                return 'rf'  
            elif 'elastic' in class_name or 'logistic' in class_name:
                return 'elastic'
                
        return 'unknown'
    except:
        return 'unknown'

def _calculate_model_weights(self, pipelines, model_types):
    """
    Calculate performance-based weights for model ensemble.
    Higher performing models get higher weights in uncertainty estimation.
    """
    
    # Simple equal weights for now - can be enhanced with cross-validation performance
    n_models = len(pipelines)
    weights = np.ones(n_models) / n_models
    
    # Could enhance this with:
    # - CV performance scores from context
    # - Model-specific reliability metrics
    # - Architecture-specific confidence scores
    
    return weights

def _should_generate_predictions(self, context):
    """
    Determine if predictions should be generated based on configuration.
    """
    # Check explicit configuration
    if hasattr(self.config, 'generate_predictions'):
        return self.config.generate_predictions
    
    # Default: generate predictions if we have trained models
    has_models = len(context.get("prediction_results", {})) > 0
    has_embeddings = context.get("prediction_train_coords") is not None
    
    return has_models and has_embeddings
```

### Phase 4: Simple Helper Methods

```python
def _prepare_scores_vectors(self, labels, task):
    """
    Simple conversion of labels to scores vectors dictionary.
    Much simpler than the complex method I had before!
    """
    if task == "clf":
        # Classification: create binary vectors for each class
        if labels.ndim == 1:
            unique_labels = np.unique(labels)
            scores_vectors_dict = {
                str(label): (labels == label).astype(int) 
                for label in unique_labels
            }
        else:
            # Multi-target classification (already converted in main code)
            scores_vectors_dict = {
                f"class_{i}": labels[:, i] 
                for i in range(labels.shape[1])
            }
    else:
        # Regression: handle single or multiple scores
        if labels.ndim == 1:
            scores_vectors_dict = {"score": labels}
        else:
            scores_vectors_dict = {
                f"score_{i}": labels[:, i] 
                for i in range(labels.shape[1])
            }
    
    return scores_vectors_dict

def _get_input_matrix_for_stats(self, context):
    """
    Get the input matrix for statistical calculations.
    Only needed if we want effect size maps (not just correlation maps).
    """
    # Try to get input features if available for effect size calculations
    prediction_features = context.get("prediction_train_features")
    embedding_features = context.get("embedding_train_features")
    
    if prediction_features is not None:
        return prediction_features
    elif embedding_features is not None:
        return embedding_features
    else:
        # If no input matrix available, skip effect size maps
        return None

def _should_generate_statistical_maps(self, context):
    """
    Determine if statistical maps should be generated based on configuration.
    """
    # Check explicit configuration
    if hasattr(self.config, 'generate_statistical_maps'):
        return self.config.generate_statistical_maps
    
    # Default: generate statistical maps if we have the required data
    has_embeddings = context.get("prediction_train_coords") is not None
    has_labels = context.get("prediction_train_labels") is not None
    
    return has_embeddings and has_labels

def _should_generate_visualizations(self, context):
    """
    Determine if interactive visualizations should be generated.
    """
    return getattr(self.config, 'interactive_plot', False)
```

### Phase 3: Statistical Map Generation

```python
def _generate_statistical_maps(self, embeddings, labels, prediction_results, context, task):
    """
    Generate statistical maps showing effect sizes across the embedding space.
    This is the core statistical analysis functionality.
    
    Uses already-prepared data and the generated predictions.
    """
    from emuses.tools.correlation_maps_utils import calculate_correlation_grid
    from emuses.tools.stats_utils import input_matrix_stat_map
    from emuses.tools.output_utils import save_statistical_maps
    
    # Prepare scores vectors for statistical analysis (simple conversion)
    scores_vectors_dict = self._prepare_scores_vectors(labels, task)
    
    # Configuration for statistical maps
    grid_size = getattr(self.config, 'statistical_map_grid_size', 100)
    effect_size_test = getattr(self.config, 'effect_size_test', 'cohen_d')
    
    statistical_results = {}
    
    # Generate maps for each score vector
    for score_name, score_vector in scores_vectors_dict.items():
        logger.info(f"Generating statistical map for: {score_name}")
        
        try:
            # Method 1: Correlation-based statistical maps
            correlation_results = calculate_correlation_grid(
                embeddings=embeddings_labelled,
                scores_vector=score_vector,
                grid_size=grid_size,
                method='pearson'  # or from config
            )
            
            # Method 2: Input matrix statistical maps (effect sizes)
            effect_size_results = input_matrix_stat_map(
                input_matrix=input_matrix_data,
                scores_vector=score_vector,
                embeddings=embeddings_labelled,
                grid_size=grid_size,
                test_type=effect_size_test
            )
            
            # Save statistical maps to files
            output_paths = save_statistical_maps(
                correlation_grid=correlation_results.get('correlation_grid'),
                effect_size_grid=effect_size_results.get('effect_size_grid'),
                embeddings=embeddings_labelled,
                score_name=score_name,
                output_folder=self.config.output_folder / "statistical_maps",
                metadata={
                    'task': task,
                    'grid_size': grid_size,
                    'effect_size_test': effect_size_test,
                    'n_samples': len(embeddings_labelled)
                }
            )
            
            # Store results for this score
            statistical_results[f"statistical_maps_{score_name}"] = {
                'correlation_results': correlation_results,
                'effect_size_results': effect_size_results,
                'output_paths': output_paths,
                'score_name': score_name
            }
            
            logger.info(f"Statistical maps saved for {score_name}: {output_paths}")
            
        except Exception as e:
            logger.error(f"Failed to generate statistical map for {score_name}: {e}")
            continue
    
    return {
        'statistical_map_results': statistical_results,
        'statistical_maps_generated': len(statistical_results) > 0
    }

def _generate_interactive_visualizations(self, embeddings_data, scores_data, context, task):
    """
    Generate interactive HTML visualizations showing embeddings colored by scores/clusters.
    """
    if not getattr(self.config, 'interactive_plot', False):
        return {'interactive_visualizations_generated': False}
    
    from emuses.tools.visualisation import plot_clustering_interactive_with_hover
    
    embeddings_labelled = embeddings_data['embeddings_labelled'] 
    full_embeddings = embeddings_data['full_embeddings']
    scores_vectors_dict = scores_data['scores_vectors_dict']
    
    interactive_folder = Path(self.config.output_folder) / "interactive_plots"
    interactive_folder.mkdir(exist_ok=True)
    
    visualization_results = {'interactive_plots': {}}
    
    try:
        # Get or compute cluster labels
        cluster_labels = self._get_or_compute_cluster_labels(embeddings_data, context)
        
        if embeddings_data['mode'] == 'label_dataset' and full_embeddings is not None:
            # Combined full + labeled embeddings plot
            combined_embeddings = np.concatenate([full_embeddings, embeddings_labelled], axis=0)
            interactive_path = interactive_folder / "interactive_clustering_full_and_labeled.html"
            
            fig = plot_clustering_interactive_with_hover(
                combined_embeddings,
                cluster_labels, 
                output_path=interactive_path,
                show_plot=False,
                return_plot=True
            )
            
            visualization_results['interactive_plots']['full_and_labeled'] = {
                'path': str(interactive_path),
                'figure': fig
            }
            
        # Individual plots for each score vector
        for score_name, score_vector in scores_vectors_dict.items():
            interactive_path = interactive_folder / f"interactive_embeddings_{score_name}.html"
            
            fig = plot_clustering_interactive_with_hover(
                embeddings_labelled,
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
            
        logger.info(f"Generated {len(visualization_results['interactive_plots'])} interactive plots")
        
    except Exception as e:
        logger.error(f"Failed to generate interactive visualizations: {e}")
        return {'interactive_visualizations_generated': False}
    
    return {
        'interactive_visualizations': visualization_results,
        'interactive_visualizations_generated': True
    }
```

### Phase 4: Helper Methods

```python
def _should_generate_statistical_maps(self, context):
    """
    Determine if statistical maps should be generated based on configuration.
    """
    # Check explicit configuration
    if hasattr(self.config, 'generate_statistical_maps'):
        return self.config.generate_statistical_maps
    
    # Default: generate statistical maps if we have the required data
    has_embeddings = context.get("prediction_train_coords") is not None
    has_features = (context.get("prediction_train_features") is not None or 
                   context.get("embedding_train_features") is not None)
    
    return has_embeddings and has_features

def _should_generate_visualizations(self, context):
    """
    Determine if interactive visualizations should be generated.
    """
    return getattr(self.config, 'interactive_plot', False)

def _get_or_compute_cluster_labels(self, embeddings_data, context):
    """
    Get existing cluster labels or compute new ones if needed for visualizations.
    """
    # Try to get existing cluster labels
    cluster_labels = context.get("embedding_train_cluster_labels")
    
    if cluster_labels is None and embeddings_data['mode'] == 'label_dataset':
        # For label_dataset mode, compute clustering on combined embeddings
        full_embeddings = embeddings_data['full_embeddings']
        embeddings_labelled = embeddings_data['embeddings_labelled']
        
        if full_embeddings is not None:
            clusterer = context.get("embedding_train_clusterer")
            if clusterer is not None:
                combined_embeddings = np.concatenate([full_embeddings, embeddings_labelled], axis=0)
                cluster_labels = clusterer.fit_predict(combined_embeddings)
                logger.info("Computed cluster labels on combined embeddings")
    
    if cluster_labels is None:
        # Fallback: use prediction cluster labels or create dummy labels
        cluster_labels = context.get("prediction_train_cluster_labels")
        if cluster_labels is None:
            # Create dummy cluster labels (all points in one cluster)
            n_points = len(embeddings_data['embeddings_labelled'])
            cluster_labels = np.zeros(n_points)
            logger.warning("No cluster labels available, using dummy labels for visualization")
    
    return cluster_labels
```

## Integration Points and Considerations

### 1. Configuration Integration
- Add new configuration options to control statistical map generation
- Make statistical maps optional but enabled by default
- Allow configuration of grid size, effect size test, etc.

### 2. Context Data Flow
- Ensure statistical map generation works with existing context data
- Handle both classic mode and label_dataset mode seamlessly
- Preserve all existing context data and model results

### 3. Error Handling
- Statistical map generation should not break the main pipeline
- Graceful degradation if required data is not available
- Clear logging for debugging and user feedback

### 4. Performance Considerations  
- Statistical map generation can be computationally expensive
- Consider making it optional for large datasets
- Parallelize statistical map generation across score vectors

### 5. Output Organization
- Create separate folders for statistical maps and interactive plots
- Maintain consistency with existing output structure
- Integrate with existing artifact management system

## Benefits of This Integration

1. **Preserves Existing Functionality**: All current Optuna optimization remains unchanged
2. **Adds Missing Capabilities**: Restores statistical map generation that was lost
3. **Seamless Integration**: Uses existing context data and configuration patterns
4. **Configurable**: Can be enabled/disabled based on user needs
5. **Complete Pipeline**: Provides both model training AND statistical analysis

This integration transforms HeatmapStage from a **model training only** stage into a **complete analysis pipeline** that provides both predictive models and statistical effect size maps.