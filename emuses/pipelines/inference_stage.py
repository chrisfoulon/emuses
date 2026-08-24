# pipelines/inference_stage.py

"""
InferenceStage implementation for EMUSES pipeline inference capabilities.

This stage enables inference on trained models with automatic detection of
validation vs pure inference modes, leveraging the observability infrastructure
for performance tracking and research insights.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TimeElapsedColumn
)

from emuses.pipelines.pipeline_stage import PipelineStage
from emuses.tools.emuses_utils import rescale_embedding
from emuses.tools.model_io import ModelIOManager
from emuses.tools.UMAP_utils import load_umap_model

logger = logging.getLogger(__name__)


def _as_path_str(value):
    """Return ``value`` as a string path, preserving None."""
    return None if value is None else str(value)


class InferenceStage(PipelineStage):
    """
    Stage for running inference on trained EMUSES models.

    This stage handles:
    - Loading trained models from manifest-based storage
    - Automatic detection of validation vs inference modes
    - Feature transformation through trained UMAP
    - Ensemble prediction with confidence scoring
    - Performance tracking and research metrics
    """

    def __init__(self, config):
        """
        Initialize inference stage with model loading and metrics setup.

        Parameters
        ----------
        config : PipelineConfig
            Pipeline configuration containing model paths and settings
        """
        super().__init__(config)

        # Extract inference-specific configuration. Paths are kept as strings: they end up
        # in the results metadata, which is written as JSON and served over HTTP, and a
        # PosixPath there raises "Object of type PosixPath is not JSON serializable".
        # Every use here wraps them in Path() anyway.
        self.model_path = _as_path_str(getattr(config, 'model_path', None))
        self.data_path = _as_path_str(getattr(config, 'data_path', None))
        self.output_path = _as_path_str(getattr(config, 'output_path', None))
        self.validate_mode = getattr(config, 'validate_mode', False)

        # Initialize model storage
        self.trained_models = None

    def run(self, context, progress_queue=None):
        """
        Run inference with comprehensive performance tracking and research insights.

        Parameters
        ----------
        context : dict
            Execution context from pipeline
        progress_queue : queue.Queue, optional
            Queue for progress updates

        Returns
        -------
        dict
            Inference results with predictions, metrics, and performance data
        """
        # Only log if not called from CLI (avoid duplicate messages)
        if not context.get("cli_inference_mode", False):
            logger.info("Starting inference pipeline execution")
        start_time = time.time()
        console = Console()

        # Create Rich progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:

            try:
                # Task 1: Load trained models (context-first for performance)
                model_task = progress.add_task("Loading models...", total=1)
                self.trained_models = self._load_trained_models_with_context(context)
                progress.advance(model_task, 1)

                # Task 2: Load data from context (standard stage pattern)
                data_task = progress.add_task("Loading data from context...", total=1)
                data_start = time.time()
                new_features = self._load_features_from_context(context)
                data_duration = time.time() - data_start
                progress.advance(data_task, 1)

                # Auto-detect validation vs inference mode
                has_labels = self._detect_labels()
                mode = "validation" if (has_labels or self.validate_mode) else "inference"

                # Task 3: Transform features
                sample_count = len(new_features)
                transform_task = progress.add_task(
                    f"Transforming features ({sample_count} samples)...", 
                    total=sample_count
                )
                transform_start = time.time()
                
                # Check if prediction_test_coords already exists in context (internal pipeline mode)
                if 'prediction_test_coords' in context:
                    transformed_features = context.get('prediction_test_coords')
                    logger.info("Using pre-computed prediction_test_coords from context (internal pipeline mode)")
                    progress.advance(transform_task, sample_count)
                else:
                    # External standalone mode: do UMAP transform + rescale
                    transformed_features = self._transform_features_with_progress(
                        new_features, self.trained_models, progress, transform_task
                    )
                
                transform_duration = time.time() - transform_start

                # Task 4: Run predictions
                predict_task = progress.add_task(
                    f"Running predictions ({sample_count} samples)...", 
                    total=sample_count
                )
                predict_start = time.time()
                prediction_results = self._predict_with_progress(
                    transformed_features, self.trained_models, progress, predict_task
                )
                predict_duration = time.time() - predict_start

                # Task 5: Save results
                save_task = progress.add_task("Saving results...", total=1)
                
                # Calculate performance breakdown with actual measurements
                total_duration = time.time() - start_time
                performance_data = {
                    'data_load_duration_ms': data_duration * 1000,
                    'transform_duration_ms': transform_duration * 1000,
                    'prediction_duration_ms': predict_duration * 1000,
                    'total_duration_ms': total_duration * 1000,
                    'throughput_samples_per_sec': sample_count / total_duration if total_duration > 0 else 0.0
                }

                # Calculate validation metrics if in validation mode
                validation_metrics = None
                if mode == "validation" and hasattr(self, '_detected_labels') and self._detected_labels is not None:
                    # One shape: _predict always returns target_results, single-target included.
                    validation_metrics = self._calculate_multi_target_validation_metrics(
                        prediction_results['target_results'],
                        self._detected_labels
                    )
                    if validation_metrics:
                        logger.info("Validation metrics calculated successfully")

                # Format results for output
                formatted_results = self._format_results(prediction_results, mode, performance_data, validation_metrics)

                # Save results to output files with format from context
                output_format = context.get("output_format", "csv")
                output_paths = self._save_results(formatted_results, output_format=output_format)
                progress.advance(save_task, 1)

                # Display summary
                console.print(f"✅ [bold green]Inference completed successfully![/bold green]")
                console.print(f"   • Processed {sample_count} samples in {total_duration:.2f}s")
                console.print(f"   • Throughput: {performance_data['throughput_samples_per_sec']:.1f} samples/sec")
                console.print(f"   • Mode: {mode}")

            except Exception as e:
                console.print(f"❌ [bold red]Inference failed:[/bold red] {e}")
                logger.error(f"Inference pipeline execution failed: {e}")
                raise

        # Return results using consistent target_results structure
        results = {
            'mode': mode,
            'status': 'completed',
            'samples_processed': sample_count,
            'embeddings_shape': transformed_features.shape,
            'target_results': prediction_results['target_results'],
            'target_count': prediction_results.get('target_count', 1),
            'model_count': prediction_results['model_count'],
            'model_names': prediction_results['model_names'],
            'individual_predictions': prediction_results['individual_predictions'],
            'performance_breakdown': performance_data,
            'output_files': output_paths,
            'model_info': self._get_model_info()
        }

        logger.info(f"Inference pipeline completed in {mode} mode - processed {sample_count} samples")
        return results

    def _load_trained_models_with_context(self, context):
        """
        Load models with context-first priority for performance optimization.

        Parameters
        ----------
        context : dict
            Pipeline context that may contain in-memory models

        Returns
        -------
        dict
            Dictionary containing loaded models from context or disk
        """
        logger.info("Loading models with context-first optimization")

        models = {
            'umap_model': None,
            'prediction_models': [],
            'metadata': {},
            'input_scaler': None,
            'scores_scaler': None
        }

        # 1. Check context for in-memory models first (pipeline-integrated mode)
        umap_model = context.get("embedding_train_umap_model")
        prediction_models = context.get("prediction_models")
        
        if umap_model is not None:
            models['umap_model'] = umap_model
            logger.info("Using UMAP model from pipeline context (fast)")
            
            # Get scaling parameters from context or model attributes
            models['metadata']['min_embeddings'] = getattr(umap_model, 'min_embeddings_', None)
            models['metadata']['max_embeddings'] = getattr(umap_model, 'max_embeddings_', None)
        else:
            # 2. Load UMAP model from disk only if not in context (standalone mode)
            umap_model = self._load_umap_from_disk()
            if umap_model is not None:
                models['umap_model'] = umap_model
                logger.info("Loaded UMAP model from disk (slower)")
                
                # Load scaling parameters needed for rescaling
                embedding_scaling_file = Path(self.model_path) / "embedding_scaling.json"
                if embedding_scaling_file.exists():
                    with open(embedding_scaling_file, 'r') as f:
                        scaling_params = json.load(f)
                    models['metadata']['min_embeddings'] = np.array(scaling_params['min_embeddings'])
                    models['metadata']['max_embeddings'] = np.array(scaling_params['max_embeddings'])
                    logger.info(f"Loaded embedding scaling parameters from {embedding_scaling_file}")
                else:
                    models['metadata']['min_embeddings'] = None
                    models['metadata']['max_embeddings'] = None
                    logger.warning("No embedding scaling parameters found - raw embeddings will be used")
            else:
                logger.warning("UMAP model not available - inference will be limited")
            
        if prediction_models is not None and len(prediction_models) > 0:
            models['prediction_models'] = prediction_models
            logger.info(f"Using {len(prediction_models)} prediction models from pipeline context (fast)")
        else:
            # 3. Load prediction models from disk only if not in context
            models['prediction_models'] = self._load_prediction_models_from_disk()

        # 4. Load normalization scalers (context-first, then disk)
        self._load_normalization_scalers(models, context)
            
        return models

    def _load_umap_from_disk(self):
        """
        Load UMAP model from disk with metadata.

        Returns
        -------
        object
            Trained UMAP model with scaling parameters
        """
        if not self.model_path:
            logger.warning("No model_path specified - cannot load UMAP from disk")
            return None
            
        model_dir = Path(self.model_path)
        if not model_dir.exists():
            logger.warning(f"Model directory not found: {model_dir}")
            return None

        try:
            umap_model, umap_path = load_umap_model(model_dir, model_name="best_umap_model")
            if umap_model is not None:
                logger.info(f"Successfully loaded UMAP model from disk: {umap_path}")
                return umap_model
            else:
                logger.warning("UMAP model not found on disk")
                return None
        except Exception as e:
            logger.error(f"Failed to load UMAP model from disk: {str(e)}")
            return None

    def _load_prediction_models_from_disk(self):
        """
        Load prediction models from disk (HeatmapStage outputs).

        Returns
        -------
        list
            List of prediction model dictionaries
        """
        if not self.model_path:
            logger.warning("No model_path specified - cannot load prediction models from disk")
            return []
            
        model_dir = Path(self.model_path)
        if not model_dir.exists():
            logger.warning(f"Model directory not found: {model_dir}")
            return []

        prediction_models = []
        
        # Search for prediction model files (patterns: target_*/best_pipeline_fold*_*.joblib or target_*/best_pipeline_target_*_fold*.joblib)
        target_dirs = list(model_dir.glob('target_*'))
        logger.info(f"Found {len(target_dirs)} target directories for model loading")
        
        for target_dir in target_dirs:
            if target_dir.is_dir():
                # Find best pipeline models (support both old and new naming patterns)
                model_files = list(target_dir.glob('best_pipeline_fold*_*.joblib')) + \
                             list(target_dir.glob('best_pipeline_target_*_fold*.joblib'))
                logger.info(f"Found {len(model_files)} model files in {target_dir.name}")
                
                for model_file in model_files:
                    try:
                        import joblib
                        model = joblib.load(model_file)
                        prediction_models.append({
                            'model': model,
                            'path': model_file,
                            'target': target_dir.name,
                            'fold_info': model_file.stem  # Contains fold and metric info
                        })
                        logger.info(f"Successfully loaded prediction model: {model_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to load model {model_file}: {e}")
        
        logger.info(f"Successfully loaded {len(prediction_models)} prediction models from disk")
        return prediction_models

    def _load_normalization_scalers(self, models, context):
        """
        Load normalization scalers from context or disk using manifest detection.
        
        Loads scalers in priority order:
        1. From pipeline context (fast, pipeline-integrated mode)
        2. From disk using manifest auto-detection (standalone mode)
        
        Parameters
        ----------
        models : dict
            Models dictionary to update with scalers
        context : dict
            Pipeline context that may contain scaler info
        """
        logger.debug("Loading normalization scalers")
        
        # 1. Try loading from context first (pipeline-integrated mode)
        input_scaler_info = context.get("input_scaler_info", {})
        scores_scaler_info = context.get("scores_scaler_info", {})
        
        if input_scaler_info and "scaling_factors" in input_scaler_info:
            models['input_scaler'] = input_scaler_info["scaling_factors"]
            models['metadata']['input_normalization_method'] = input_scaler_info.get("method", "unknown")
            logger.info(f"Using input scaler from pipeline context ({input_scaler_info.get('method', 'unknown')})")
        
        if scores_scaler_info and "scaling_factors" in scores_scaler_info:
            models['scores_scaler'] = scores_scaler_info["scaling_factors"] 
            models['metadata']['scores_normalization_method'] = scores_scaler_info.get("method", "unknown")
            logger.info(f"Using scores scaler from pipeline context ({scores_scaler_info.get('method', 'unknown')})")
        
        # 2. If not in context, try loading from disk using manifest (standalone mode)
        if models['input_scaler'] is None or models['scores_scaler'] is None:
            self._load_scalers_from_disk(models)
    
    def _load_scalers_from_disk(self, models):
        """
        Load normalization scalers from disk using manifest auto-detection.
        
        Parameters
        ----------
        models : dict
            Models dictionary to update with scalers
        """
        if not self.model_path:
            logger.debug("No model_path specified - cannot load scalers from disk")
            return
            
        model_dir = Path(self.model_path)
        if not model_dir.exists():
            logger.debug(f"Model directory not found: {model_dir}")
            return
        
        try:
            # Try to load manifest to get scaler information
            from emuses.tools.model_io import ModelIOManager
            model_manager = ModelIOManager(base_path=model_dir)
            manifest = model_manager._load_or_generate_manifest(model_dir)
            
            normalization_info = manifest.get("normalization", {})
            
            # Load input scaler if present and not already loaded
            if models['input_scaler'] is None:
                input_scaler_path = normalization_info.get("input_scaler")
                if input_scaler_path:
                    scaler_file = model_dir / input_scaler_path
                    if scaler_file.exists():
                        try:
                            import joblib
                            models['input_scaler'] = joblib.load(scaler_file)
                            models['metadata']['input_normalization_method'] = normalization_info.get("input_method", "unknown")
                            logger.info(f"Loaded input scaler ({normalization_info.get('input_method', 'unknown')}) from {scaler_file}")
                        except Exception as e:
                            logger.warning(f"Failed to load input scaler from {scaler_file}: {e}")
            
            # Load scores scaler if present and not already loaded  
            if models['scores_scaler'] is None:
                scores_scaler_path = normalization_info.get("scores_scaler")
                if scores_scaler_path:
                    scaler_file = model_dir / scores_scaler_path
                    if scaler_file.exists():
                        try:
                            import joblib
                            models['scores_scaler'] = joblib.load(scaler_file)
                            models['metadata']['scores_normalization_method'] = normalization_info.get("scores_method", "unknown")
                            logger.info(f"Loaded scores scaler ({normalization_info.get('scores_method', 'unknown')}) from {scaler_file}")
                        except Exception as e:
                            logger.warning(f"Failed to load scores scaler from {scaler_file}: {e}")
                            
        except Exception as e:
            logger.debug(f"Could not load manifest or scalers from disk: {e}")

    def _load_trained_models(self):
        """
        Load all models from trained model folder with integrity verification.

        Returns
        -------
        dict
            Dictionary containing loaded UMAP, HDBSCAN, and prediction models

        Raises
        ------
        FileNotFoundError
            If model directory doesn't exist
        """
        if not self.model_path:
            raise ValueError("model_path not specified in configuration")

        model_dir = Path(self.model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"Model directory not found: {model_dir}")

        logger.info(f"Loading models from {model_dir}")

        # Initialize ModelIOManager for loading models with manifest verification
        ModelIOManager(base_path=model_dir)  # Will be used in future iterations

        models = {
            'umap_model': None,
            'prediction_models': [],
            'metadata': {}
        }

        try:
            # Load UMAP model using existing utilities
            umap_model, umap_path = load_umap_model(model_dir, model_name="best_umap_model")
            if umap_model is not None:
                models['umap_model'] = umap_model
                logger.info(f"Successfully loaded UMAP model from {umap_path}")

                # Load scaling parameters needed for rescaling
                embedding_scaling_file = model_dir / "embedding_scaling.json"
                if embedding_scaling_file.exists():
                    with open(embedding_scaling_file, 'r') as f:
                        scaling_params = json.load(f)
                    models['metadata']['min_embeddings'] = np.array(scaling_params['min_embeddings'])
                    models['metadata']['max_embeddings'] = np.array(scaling_params['max_embeddings'])
                    logger.info(f"Loaded embedding scaling parameters from {embedding_scaling_file}")
                else:
                    models['metadata']['min_embeddings'] = None
                    models['metadata']['max_embeddings'] = None
                    logger.warning("No embedding scaling parameters found - raw embeddings will be used")
            else:
                logger.warning("UMAP model not found - inference will be limited")

        except Exception as e:
            logger.error(f"Failed to load UMAP model: {str(e)}")

        # Load prediction models from HeatmapStage outputs
        prediction_models = []
        
        # Search for prediction model files (patterns: target_*/best_pipeline_fold*_*.joblib or target_*/best_pipeline_target_*_fold*.joblib)
        target_dirs = list(model_dir.glob('target_*'))
        logger.info(f"Found {len(target_dirs)} target directories for model loading")
        
        for target_dir in target_dirs:
            if target_dir.is_dir():
                # Find best pipeline models (support both old and new naming patterns)
                model_files = list(target_dir.glob('best_pipeline_fold*_*.joblib')) + \
                             list(target_dir.glob('best_pipeline_target_*_fold*.joblib'))
                logger.info(f"Found {len(model_files)} model files in {target_dir.name}")
                
                for model_file in model_files:
                    try:
                        import joblib
                        model = joblib.load(model_file)
                        prediction_models.append({
                            'model': model,
                            'path': model_file,
                            'target': target_dir.name,
                            'fold_info': model_file.stem  # Contains fold and metric info
                        })
                        logger.info(f"Successfully loaded prediction model: {model_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to load model {model_file}: {e}")
        
        models['prediction_models'] = prediction_models
        logger.info(f"Successfully loaded {len(prediction_models)} prediction models")
        
        # If no prediction models found, log warning but continue
        if len(prediction_models) == 0:
            logger.warning("No prediction models found - inference will be limited to UMAP transformation")
            
        return models

    def _detect_labels(self):
        """
        Detect if input data contains labels for validation mode.

        Returns
        -------
        bool
            True if labels detected, False otherwise
        """
        # Check if labels were detected during data loading
        if hasattr(self, '_detected_labels') and self._detected_labels is not None:
            logger.info(f"Labels detected during data loading: shape {self._detected_labels.shape}")
            return True
            
        # Check for explicit validation mode flag
        if self.validate_mode:
            logger.info("Validation mode explicitly enabled")
            return True
            
        # Check data path for label indicators
        if self.data_path:
            data_path_str = str(self.data_path).lower()
            label_indicators = ['label', 'target', 'ground_truth', 'gt', 'test_with_labels']
            has_indicators = any(indicator in data_path_str for indicator in label_indicators)
            if has_indicators:
                logger.info(f"Label indicators found in data path: {self.data_path}")
                return True
                
        logger.info("No labels detected - running in inference-only mode")
        return False

    def _get_model_info(self):
        """
        Get model metadata information.

        Returns
        -------
        dict
            Model metadata including version, creation date, etc.
        """
        return {
            'model_path': self.model_path,
            'loaded_models': len(self.trained_models.get('prediction_models', [])) if self.trained_models else 0
        }

    def _load_features_from_context(self, context):
        """
        Get inference features from context following standard stage pattern.

        Parameters
        ----------
        context : dict
            Pipeline context containing processed data

        Returns
        -------
        np.ndarray
            Feature matrix for inference from context
        """
        # Get inference features from context (standard stage pattern).
        # `inference_features` is what hands data over in every wired path: EMUSESPipeline sets it
        # in inference mode, and HeatmapStage sets it from prediction_test/train_features when the
        # stage runs inside a full pipeline (heatmap_stage.py). `prediction_test_features` is
        # deliberately NOT read here: HeatmapStage, not this method, decides whether validation
        # runs against the test or the train split, and a context that never went through it is a
        # wiring mistake worth refusing loudly - see
        # tests/pipelines/test_inference_stage_context_integration.py.
        features = context.get("inference_features")
        if features is None:
            # Fallback: check for other common feature keys in context
            features = context.get("features")
            if features is None:
                features = context.get("input_matrix")
            
        if features is None:
            raise ValueError("No inference features found in context. InferenceStage must receive data from EMUSESPipeline.")
            
        logger.info(f"Retrieved features from context: shape {features.shape}")
        
        # Check for labels in context for validation mode
        labels = context.get("inference_labels") 
        if labels is None:
            labels = context.get("labels")
        if labels is None:
            labels = context.get("scores")
            
        if labels is not None:
            logger.info(f"Labels found in context: shape {labels.shape}")
            self._detected_labels = labels
        else:
            self._detected_labels = None
            
        return features

    def _transform_features(self, features, models):
        """
        Transform new data through trained UMAP with performance tracking.

        Parameters
        ----------
        features : np.ndarray
            Input features to transform
        models : dict
            Dictionary containing loaded models

        Returns
        -------
        np.ndarray
            Transformed embeddings
        """
        umap_model = models.get('umap_model')
        if umap_model is None:
            raise ValueError("UMAP model not available for transformation")

        logger.info(f"Transforming {features.shape[0]} samples through trained UMAP")

        # Use features as-is - EMUSESPipeline already handles normalization consistently
        # during both training and inference when inference_mode=True
        logger.info("Using pre-normalized features from EMUSESPipeline (no duplicate normalization)")
        normalized_features = features

        # Apply UMAP transformation
        logger.info(f"Input to UMAP transform: shape={normalized_features.shape}")
        
        # Check UMAP model state
        umap_fitted = hasattr(umap_model, 'embedding_') and umap_model.embedding_ is not None
        umap_components = getattr(umap_model, 'n_components', 'unknown')
        logger.debug(f"UMAP model state: fitted={umap_fitted}, n_components={umap_components}")
        
        embeddings = umap_model.transform(normalized_features)
        
        logger.info(f"UMAP transform completed: shape={embeddings.shape}, range=[{np.min(embeddings):.6f}, {np.max(embeddings):.6f}]")

        # Rescale embeddings using saved parameters
        min_embeddings = models.get('metadata', {}).get('min_embeddings')
        max_embeddings = models.get('metadata', {}).get('max_embeddings')

        if min_embeddings is not None and max_embeddings is not None:
            logger.debug(f"Rescaling embeddings with parameters: min={min_embeddings}, max={max_embeddings}")
            # embeddings_before_rescale = embeddings.copy()
            embeddings = rescale_embedding(
                embeddings,
                preset_min=min_embeddings,
                preset_max=max_embeddings
            )
            logger.info(f"Embeddings rescaled: range=[{np.min(embeddings):.6f}, {np.max(embeddings):.6f}]")
            logger.info("Applied rescaling to transformed embeddings")
        else:
            logger.warning("No embedding scaling parameters found - using raw embeddings")

        return embeddings

    def _predict(self, embeddings, models):
        """
        Run ensemble predictions using unified multi-target processing.

        Uses a single unified workflow where single-target is treated as 
        multi-target with n=1 targets. All models are grouped by target
        (assigning 'target_0' for models without explicit target) and
        processed consistently.

        Parameters
        ----------
        embeddings : np.ndarray
            Transformed embeddings from UMAP
        models : dict
            Dictionary containing loaded models

        Returns
        -------
        dict
            Prediction results with target_results structure containing:
            - target_results: Dict[str, dict] with per-target predictions
            - target_count: int number of targets
            - model_count: int total number of models
            - individual_predictions: dict aggregated individual predictions
            - model_names: list aggregated model names
        """
        prediction_models = models.get('prediction_models', [])
        if not prediction_models:
            logger.warning("No prediction models available - returning zero predictions")
            # Same target_results shape as a real run: everything downstream
            # (_format_results, run(), the service endpoints) indexes 'target_results',
            # so a flat result here dies with KeyError instead of returning this.
            n_samples = len(embeddings)
            return {
                'target_results': {
                    'target_0': {
                        'ensemble_predictions': np.zeros(n_samples),
                        'normalized_ensemble_predictions': None,
                        'individual_predictions': {},
                        'confidence_scores': np.zeros(n_samples),
                        'model_count': 0,
                        'model_names': [],
                        'denormalization_applied': False,
                    }
                },
                'target_count': 1,
                'individual_predictions': {},
                'model_count': 0,
                'model_names': []
            }

        # Group models by target (assigns 'target_0' if no target specified)
        models_by_target = self._group_models_by_target(prediction_models)
        n_targets = len(models_by_target)
        
        logger.info(f"Processing {len(prediction_models)} models across {n_targets} target(s)")

        # Process predictions with target-specific ensembles (handles single-target as n=1 case)
        target_results = self._predict_multi_target(embeddings, models_by_target, models)
        
        # Format results in consistent target_results structure
        return self._format_multi_target_results(target_results)

    def _format_results(self, predictions, mode, performance_data, validation_metrics=None):
        """
        Format inference results with performance breakdown and metadata.
        
        Processes predictions from the unified multi-target workflow and
        adds performance metrics and metadata. Always expects target_results
        structure from _predict method.

        Parameters
        ----------
        predictions : dict
            Prediction results from _predict method with target_results structure
        mode : str
            Inference mode ("inference" or "validation")
        performance_data : dict
            Performance timing and throughput data
        validation_metrics : dict, optional
            Validation metrics if in validation mode

        Returns
        -------
        dict
            Formatted results with target_results, performance, and metadata
        """
        logger.info(f"Formatting {mode} results for output")

        # Extract predictions from target_results structure (always present now)
        target_results = predictions['target_results']
        individual_predictions = predictions.get('individual_predictions', {})
        
        # For metadata, calculate total samples from first target
        if target_results:
            first_target = list(target_results.keys())[0]
            ensemble_predictions = target_results[first_target]['ensemble_predictions']
            confidence_scores = target_results[first_target].get('confidence_scores', [])
        else:
            ensemble_predictions = []
            confidence_scores = []

        # Format performance breakdown
        performance_breakdown = {
            'data_load_ms': performance_data.get('data_load_duration_ms', 0.0),
            'transform_ms': performance_data.get('transform_duration_ms', 0.0),
            'prediction_ms': performance_data.get('prediction_duration_ms', 0.0),
            'total_ms': performance_data.get('total_duration_ms', 0.0),
            'throughput_samples_per_sec': performance_data.get('throughput_samples_per_sec', 0.0)
        }

        # Create metadata
        metadata = {
            'mode': mode,
            'timestamp': time.time(),
            'samples_processed': len(ensemble_predictions),
            'model_count': predictions.get('model_count', 0),
            'model_names': predictions.get('model_names', [])
        }

        # Assemble formatted results
        formatted_results = {
            'predictions': ensemble_predictions,
            'confidence_scores': confidence_scores,
            'individual_predictions': individual_predictions,
            'performance_breakdown': performance_breakdown,
            'metadata': metadata
        }
        
        # Always preserve target_results structure
        formatted_results['target_results'] = predictions['target_results']
        formatted_results['target_count'] = predictions.get('target_count', len(predictions['target_results']))

        # Add validation metrics if available
        if validation_metrics:
            formatted_results['validation_metrics'] = validation_metrics

        logger.info(f"Results formatted: {len(ensemble_predictions)} predictions with {mode} mode")
        return formatted_results

    def _save_results(self, results, output_format='csv'):
        """
        Save formatted results to output files.

        Parameters
        ----------
        results : dict
            Formatted results from _format_results method
        output_format : str, optional
            Output format ('csv' or 'npy'), defaults to 'csv'

        Returns
        -------
        dict
            Dictionary containing paths to saved files
        """
        if not self.output_path:
            # Use model path parent directory if no output path specified
            output_dir = Path(self.model_path).parent / "inference_results"
        else:
            output_dir = Path(self.output_path)

        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = results['metadata']['mode']

        # Save complete metadata and performance data as JSON (always created)
        metadata_file = output_dir / f"{mode}_metadata_{timestamp}.json"
        metadata_content = {
            'metadata': results['metadata'],
            'performance_breakdown': results['performance_breakdown']
        }

        # Add validation metrics if present
        if 'validation_metrics' in results:
            metadata_content['validation_metrics'] = results['validation_metrics']

        # Use bcblib save_json for consistency
        from bcblib.tools.general_utils import save_json
        save_json(metadata_file, metadata_content)

        output_paths = {'metadata_file': str(metadata_file)}

        if output_format == 'csv':
            # Save predictions in CSV format (default, user-friendly)
            predictions_csv = output_dir / f"{mode}_predictions_{timestamp}.csv"
            self._save_predictions_csv(results, predictions_csv)
            output_paths['predictions_csv'] = str(predictions_csv)
            
            # Save normalized predictions CSV if denormalization was applied
            if self._check_denormalization_applied(results):
                normalized_predictions_csv = output_dir / f"{mode}_predictions_normalized_{timestamp}.csv"
                self._save_normalized_predictions_csv(results, normalized_predictions_csv)
                output_paths['normalized_predictions_csv'] = str(normalized_predictions_csv)
                logger.info(f"Saved normalized predictions for comparison: {normalized_predictions_csv}")

            # Save confidence scores in CSV format if available
            if len(results.get('confidence_scores', [])) > 0:
                confidence_csv = output_dir / f"{mode}_confidence_{timestamp}.csv"
                self._save_confidence_csv(results, confidence_csv)
                output_paths['confidence_csv'] = str(confidence_csv)

        else:  # output_format == 'npy'
            # Save predictions as numpy array (for programmatic access)
            predictions_file = output_dir / f"{mode}_predictions_{timestamp}.npy"
            np.save(predictions_file, results['predictions'])
            output_paths['predictions_file'] = str(predictions_file)

            # Save confidence scores as numpy array if available
            if len(results.get('confidence_scores', [])) > 0:
                confidence_file = output_dir / f"{mode}_confidence_{timestamp}.npy"
                np.save(confidence_file, results['confidence_scores'])
                output_paths['confidence_file'] = str(confidence_file)

        logger.info(f"Results saved to {output_dir} in {output_format.upper()} format: {len(output_paths)} files created")
        return output_paths

    def _save_predictions_csv(self, results, output_file):
        """
        Save predictions in CSV format with target-specific columns.
        Handles both single-target (n=1) and multi-target (n>1) scenarios consistently.

        Parameters
        ----------
        results : dict
            Formatted results containing target_results structure
        output_file : Path
            Path to output CSV file
        """
        import pandas as pd

        # Always expect target_results structure now
        target_results = results['target_results']
        
        # Determine sample count from first target
        first_target = list(target_results.keys())[0]
        n_samples = len(target_results[first_target]['ensemble_predictions'])
        
        # Start with sample IDs
        data = {
            'sample_id': [f"sample_{i:04d}" for i in range(n_samples)]
        }
        
        # Add ensemble predictions per target
        for target in sorted(target_results.keys()):
            target_result = target_results[target]
            data[f'{target}_ensemble_prediction'] = target_result['ensemble_predictions']
            data[f'{target}_confidence_score'] = target_result.get('confidence_scores', [0.0] * n_samples)
        
        # Add individual model predictions with target prefixes
        for target in sorted(target_results.keys()):
            target_result = target_results[target]
            individual_preds = target_result.get('individual_predictions', {})
            for model_name, predictions in individual_preds.items():
                # Ensure model names are prefixed with target for clarity
                if not model_name.startswith(f"{target}_"):
                    column_name = f"{target}_{model_name}"
                else:
                    column_name = model_name
                data[column_name] = predictions
        
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        logger.info(f"Predictions saved to CSV: {output_file} ({len(target_results)} target(s))")

    def _save_confidence_csv(self, results, output_file):
        """
        Save confidence scores in CSV format with target-specific columns.
        Handles both single-target (n=1) and multi-target (n>1) scenarios consistently.

        Parameters
        ----------
        results : dict
            Formatted results containing target_results structure
        output_file : Path
            Path to output CSV file
        """
        import pandas as pd

        # Always expect target_results structure now
        target_results = results['target_results']
        
        # Check if any target has confidence scores
        has_confidence = False
        for target_result in target_results.values():
            if len(target_result.get('confidence_scores', [])) > 0:
                has_confidence = True
                break
        
        if not has_confidence:
            logger.info("No confidence scores available for any target")
            return
        
        # Determine sample count from first target
        first_target = list(target_results.keys())[0]
        n_samples = len(target_results[first_target]['ensemble_predictions'])
        
        # Start with sample IDs
        data = {
            'sample_id': [f"sample_{i:04d}" for i in range(n_samples)]
        }
        
        # Add confidence scores per target
        for target in sorted(target_results.keys()):
            target_result = target_results[target]
            confidence_scores = target_result.get('confidence_scores', [0.0] * n_samples)
            data[f'{target}_confidence_score'] = confidence_scores
        
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        logger.info(f"Confidence scores saved to CSV: {output_file} ({len(target_results)} target(s))")

    def _check_denormalization_applied(self, results):
        """
        Check if denormalization was applied to any target in the results.
        
        Parameters
        ----------
        results : dict
            Formatted results containing target_results structure
            
        Returns
        -------
        bool
            True if denormalization was applied to any target
        """
        target_results = results.get('target_results', {})
        return any(
            target_result.get('denormalization_applied', False) 
            for target_result in target_results.values()
        )
    
    def _save_normalized_predictions_csv(self, results, output_file):
        """
        Save normalized predictions in CSV format (before denormalization).
        Only includes targets where denormalization was applied.
        
        Parameters
        ----------
        results : dict
            Formatted results containing target_results structure
        output_file : Path
            Path to output CSV file
        """
        import pandas as pd
        
        target_results = results['target_results']
        
        # Filter to only targets with denormalization applied
        denormalized_targets = {
            target: target_result for target, target_result in target_results.items()
            if target_result.get('denormalization_applied', False)
        }
        
        if not denormalized_targets:
            logger.warning("No denormalized targets found - skipping normalized predictions CSV")
            return
            
        # Determine sample count from first denormalized target
        first_target = list(denormalized_targets.keys())[0]
        n_samples = len(denormalized_targets[first_target]['normalized_ensemble_predictions'])
        
        # Start with sample IDs
        data = {
            'sample_id': [f"sample_{i:04d}" for i in range(n_samples)]
        }
        
        # Add normalized ensemble predictions per target
        for target in sorted(denormalized_targets.keys()):
            target_result = denormalized_targets[target]
            normalized_preds = target_result.get('normalized_ensemble_predictions')
            if normalized_preds is not None:
                data[f'{target}_ensemble_prediction'] = normalized_preds
        
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        logger.info(f"Normalized predictions saved to CSV: {output_file} ({len(denormalized_targets)} target(s))")

    def _transform_features_with_progress(self, features, models, progress, task_id):
        """
        Transform features through trained UMAP with progress tracking.

        Parameters
        ----------
        features : np.ndarray
            Input features to transform
        models : dict
            Trained models including UMAP
        progress : Progress
            Rich progress instance
        task_id : TaskID
            Progress task identifier

        Returns
        -------
        np.ndarray
            Transformed features
        """
        # For now, use the existing transform method and update progress
        # In a real implementation, this could track batch-wise progress
        transformed_features = self._transform_features(features, models)
        
        # Update progress based on feature count
        progress.advance(task_id, len(features))
        
        return transformed_features

    def _predict_with_progress(self, embeddings, models, progress, task_id):
        """
        Run ensemble predictions with progress tracking.

        Parameters
        ----------
        embeddings : np.ndarray
            Transformed feature embeddings
        models : dict
            Trained prediction models
        progress : Progress
            Rich progress instance
        task_id : TaskID
            Progress task identifier

        Returns
        -------
        dict
            Prediction results with confidence scores and model breakdown
        """
        # Use existing predict method and update progress
        prediction_results = self._predict(embeddings, models)
        
        # Update progress based on sample count
        progress.advance(task_id, len(embeddings))
        
        return prediction_results

    def _calculate_validation_metrics(self, predictions, ground_truth):
        """
        Calculate comprehensive validation metrics for model performance evaluation.

        Parameters
        ----------
        predictions : list or np.ndarray
            Model predictions
        ground_truth : list or np.ndarray
            Ground truth labels

        Returns
        -------
        dict
            Dictionary containing validation metrics (MSE, MAE, R², etc.)
        """
        import numpy as np
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, accuracy_score, classification_report

        predictions = np.array(predictions)
        ground_truth = np.array(ground_truth)
        
        # Ensure consistent shapes (flatten if needed)
        if predictions.ndim > 1:
            predictions = predictions.flatten()
        if ground_truth.ndim > 1:
            ground_truth = ground_truth.flatten()
            
        # Ensure same length
        if len(predictions) != len(ground_truth):
            min_len = min(len(predictions), len(ground_truth))
            if min_len == 0:
                # Truncating to nothing and carrying on produced
                # "zero-size array to reduction operation minimum" from np.min a few lines
                # below - an opaque numpy error for what is really an empty ensemble.
                raise ValueError(
                    "Cannot calculate validation metrics: "
                    f"{len(predictions)} predictions against {len(ground_truth)} ground truth "
                    "values leaves no samples to compare. An empty prediction array means the "
                    "ensemble produced nothing - check that the loaded models predict on the "
                    "transformed embeddings."
                )
            predictions = predictions[:min_len]
            ground_truth = ground_truth[:min_len]
            logger.warning(f"Prediction and ground truth length mismatch - using first {min_len} samples")

        metrics = {
            'sample_count': len(predictions),
            'prediction_range': {
                'min': float(np.min(predictions)),
                'max': float(np.max(predictions)),
                'mean': float(np.mean(predictions)),
                'std': float(np.std(predictions))
            },
            'ground_truth_range': {
                'min': float(np.min(ground_truth)),
                'max': float(np.max(ground_truth)), 
                'mean': float(np.mean(ground_truth)),
                'std': float(np.std(ground_truth))
            }
        }

        try:
            # Regression metrics (always calculated)
            metrics['mse'] = float(mean_squared_error(ground_truth, predictions))
            metrics['mae'] = float(mean_absolute_error(ground_truth, predictions))
            metrics['rmse'] = float(np.sqrt(metrics['mse']))
            metrics['r2_score'] = float(r2_score(ground_truth, predictions))
            
            # Correlation coefficient
            correlation = np.corrcoef(ground_truth, predictions)[0, 1]
            metrics['correlation'] = float(correlation) if not np.isnan(correlation) else 0.0

            # Check if data appears to be classification (integer values in small range)
            unique_gt = np.unique(ground_truth)
            unique_pred = np.unique(predictions)
            
            if len(unique_gt) <= 10 and np.all(unique_gt == unique_gt.astype(int)):
                # Classification-like data
                # Round predictions to nearest integers for classification metrics
                pred_rounded = np.round(predictions).astype(int)
                
                try:
                    metrics['accuracy'] = float(accuracy_score(ground_truth.astype(int), pred_rounded))
                    logger.info("Added classification metrics (accuracy) for discrete target values")
                except Exception as e:
                    logger.warning(f"Could not calculate classification metrics: {e}")
                    
            logger.info(f"Calculated validation metrics: R² = {metrics['r2_score']:.3f}, RMSE = {metrics['rmse']:.3f}")
            
        except Exception as e:
            logger.error(f"Error calculating validation metrics: {e}")
            metrics['error'] = str(e)
            
        return metrics

    def _is_sklearn_pipeline(self, model):
        """
        Detect if a model is an sklearn Pipeline.
        
        Parameters
        ----------
        model : object
            Model object to check
            
        Returns
        -------
        bool
            True if model is an sklearn Pipeline, False otherwise
        """
        if model is None:
            return False
        
        # Check if it's an sklearn Pipeline by checking for expected attributes
        return (
            hasattr(model, 'named_steps') and 
            hasattr(model, 'steps') and
            hasattr(model, 'predict')
        )

    def _detect_multi_target_scenario(self, prediction_models):
        """
        Detect if this is a multi-target scenario and extract target information.
        
        Parameters
        ----------
        prediction_models : list
            List of model dictionaries with target information
            
        Returns
        -------
        tuple
            (is_multi_target: bool, targets: list) - detection result and sorted target list
        """
        if not prediction_models:
            return False, []
            
        targets_found = set()
        
        for model_info in prediction_models:
            target = model_info.get('target', 'target_0')  # Default for legacy models
            targets_found.add(target)
        
        sorted_targets = sorted(targets_found)
        is_multi_target = len(targets_found) > 1
        
        logger.info(f"Detected {'multi-target' if is_multi_target else 'single-target'} scenario: {sorted_targets}")
        return is_multi_target, sorted_targets

    def _group_models_by_target(self, prediction_models):
        """
        Group prediction models by target for target-specific processing.
        
        Parameters
        ----------
        prediction_models : list
            List of model dictionaries with target information
            
        Returns
        -------
        dict
            Dictionary mapping target names to lists of model dictionaries
        """
        models_by_target = {}
        
        for model_info in prediction_models:
            target = model_info.get('target', 'target_0')  # Default for legacy models
            
            if target not in models_by_target:
                models_by_target[target] = []
            models_by_target[target].append(model_info)
        
        # Log target distribution
        for target, models in models_by_target.items():
            logger.info(f"Target {target}: {len(models)} models loaded")
        
        return models_by_target

    def _get_enhanced_model_name(self, model_info):
        """
        Get enhanced model name with better fallback logic for multi-target scenarios.
        
        Parameters
        ----------
        model_info : dict
            Model information dictionary
            
        Returns
        -------
        str
            Enhanced model name with target and fold information
        """
        # Enhanced model name generation from available information
        model_name = (
            model_info.get('name') or                     # Direct name (test/manual usage)
            model_info.get('model_name') or               # Alternate name field 
            model_info.get('fold_info') or                # From disk loading (fold info)
            f"{model_info.get('target', 'model')}"        # Target-based fallback
        )
        
        # Add target prefix only if we don't have a direct name and target info is available
        target = model_info.get('target')
        if (target and 
            not model_info.get('name') and               # Don't prefix if direct name provided
            not model_name.startswith(target) and        # Don't prefix if already has target
            model_name != target):                        # Don't prefix if model_name is just target
            model_name = f"{target}_{model_name}"
        
        return model_name if model_name != 'model' else 'unknown'

    def _predict_multi_target(self, embeddings, models_by_target, models):
        """
        Process predictions with target-specific ensembles.
        
        Parameters
        ----------
        embeddings : np.ndarray
            Transformed feature embeddings
        models_by_target : dict
            Models grouped by target
        models : dict
            Full models dictionary including scalers and metadata
            
        Returns
        -------
        dict
            Target-specific prediction results
        """
        target_results = {}
        
        for target, target_models in models_by_target.items():
            logger.info(f"Processing ensemble for {target} with {len(target_models)} models")
            
            target_predictions = []
            target_individual = {}
            target_model_names = []
            
            for model_info in target_models:
                model = model_info['model']
                model_name = self._get_enhanced_model_name(model_info)
                
                # Use existing pipeline component extraction (reuse from recent enhancement)
                if self._is_sklearn_pipeline(model):
                    feature_transformer, estimator = self._extract_pipeline_components(model)
                    if feature_transformer is not None and estimator is not None:
                        # Apply model-specific feature transformations
                        transformed_features = feature_transformer.transform(embeddings)
                        predictions = estimator.predict(transformed_features)
                        
                        # Check for zero predictions (diagnostic for model health)
                        if "KernelRegressor" in str(type(estimator)):
                            zero_count = np.count_nonzero(predictions == 0)
                            if zero_count == len(predictions):
                                # All predictions are zero - this indicates a problem
                                emb_stats = f"emb_mean={np.mean(embeddings):.6f}, emb_std={np.std(embeddings):.6f}, emb_range=[{np.min(embeddings):.6f}, {np.max(embeddings):.6f}]"
                                feat_stats = f"feat_mean={np.mean(transformed_features):.6f}, feat_std={np.std(transformed_features):.6f}, feat_range=[{np.min(transformed_features):.6f}, {np.max(transformed_features):.6f}]"
                                kernel_params = f"kernel={getattr(estimator, 'kernel', 'unknown')}, alpha={getattr(estimator, 'alpha', 'unknown')}, gamma={getattr(estimator, 'gamma', 'unknown')}"
                                logger.error(f"KERNEL_ZERO_ISSUE {model_name}: ALL PREDICTIONS ARE ZERO! {emb_stats}, {feat_stats}, {kernel_params}")
                            elif zero_count > 0:
                                logger.debug(f"Model {model_name}: {zero_count}/{len(predictions)} zero predictions detected")
                            # No message when zero_count == 0 (this is the healthy, expected case)
                        
                        logger.debug(f"Pipeline prediction completed for {model_name}: {predictions.shape[0]} samples")
                    else:
                        # Fallback: use whole pipeline if component extraction failed
                        logger.warning(f"Pipeline component extraction failed for {model_name}, using whole pipeline")
                        predictions = model.predict(embeddings)
                else:
                    # Non-pipeline model: use directly (backward compatibility)
                    logger.debug(f"Non-pipeline model {model_name}, using directly")
                    predictions = model.predict(embeddings)
                
                target_predictions.append(predictions)
                target_individual[model_name] = predictions
                target_model_names.append(model_name)
            
            # Target-specific ensemble calculation
            # Initialize denormalization variables for all code paths
            denormalized_ensemble_predictions = None
            denormalization_applied = False
            actual_scaler = None
            target_column_name = None
            
            if len(target_predictions) > 0:
                normalized_ensemble_predictions = np.mean(target_predictions, axis=0)
                
                # Apply prediction denormalization if scores scaler is available
                scores_scaler_dict = models.get('scores_scaler')
                if scores_scaler_dict is not None:
                    try:
                        import pandas as pd
                        from bcblib.tools.dataframe_filtering import inverse_normalize_dataframe
                        
                        # Get the normalization method from metadata
                        scores_method = models.get('metadata', {}).get('scores_normalization_method', 'robust')
                        
                        # Extract the specific scaler for this target from the dictionary
                        # The scores_scaler is stored as {column_name: scaler_object}
                        target_column_name = None
                        actual_scaler = None
                        
                        if isinstance(scores_scaler_dict, dict):
                            # Find the scaler for this target (usually there's only one)
                            if len(scores_scaler_dict) == 1:
                                target_column_name = list(scores_scaler_dict.keys())[0]
                                actual_scaler = scores_scaler_dict[target_column_name]
                            else:
                                # Multiple scalers - try to match by target name
                                actual_scaler = scores_scaler_dict.get(target)
                                if actual_scaler is None:
                                    # Fallback to first available scaler
                                    target_column_name = list(scores_scaler_dict.keys())[0]
                                    actual_scaler = scores_scaler_dict[target_column_name]
                        else:
                            # Single scaler object (backward compatibility)
                            actual_scaler = scores_scaler_dict
                            target_column_name = 'score'
                        
                        if actual_scaler is not None:
                            # Convert predictions to DataFrame for denormalization
                            # Use original column name if available, otherwise 'score'
                            column_name = target_column_name or 'score'
                            pred_df = pd.DataFrame(normalized_ensemble_predictions, columns=[column_name])
                            denorm_df = inverse_normalize_dataframe(pred_df, {column_name: actual_scaler}, method=scores_method)
                            denormalized_ensemble_predictions = denorm_df[column_name].values
                            denormalization_applied = True
                            
                            logger.info(f"Applied prediction denormalization ({scores_method}) for target {target}: range [{denormalized_ensemble_predictions.min():.3f}, {denormalized_ensemble_predictions.max():.3f}]")
                        else:
                            logger.warning(f"Could not extract scaler for target {target} from scores_scaler")
                    except Exception as e:
                        logger.warning(f"Failed to denormalize predictions for target {target}: {e}")
                else:
                    logger.debug("No scores scaler available, predictions remain normalized")
                
                # Use denormalized predictions as the primary output (original scale for user interpretation)
                ensemble_predictions = denormalized_ensemble_predictions if denormalization_applied else normalized_ensemble_predictions
                
                # Target-specific confidence calculation
                if len(target_predictions) > 1:
                    pred_matrix = np.array(target_predictions)
                    confidence_scores = 1.0 - np.std(pred_matrix, axis=0)  # Higher std = lower confidence
                else:
                    # Single model - use uniform confidence
                    confidence_scores = np.ones(len(ensemble_predictions)) * 0.8
            else:
                # No models for this target - create empty results
                logger.warning(f"No models found for {target}")
                ensemble_predictions = np.zeros(len(embeddings))
                confidence_scores = np.zeros(len(embeddings))
            
            # Also denormalize individual predictions if scaler was applied to ensemble
            if denormalization_applied and len(target_predictions) > 0 and actual_scaler is not None:
                try:
                    import pandas as pd
                    from bcblib.tools.dataframe_filtering import inverse_normalize_dataframe
                    
                    scores_method = models.get('metadata', {}).get('scores_normalization_method', 'robust')
                    column_name = target_column_name or 'score'
                    
                    # Denormalize each individual prediction
                    denormalized_individual = {}
                    for model_name, individual_pred in target_individual.items():
                        pred_df = pd.DataFrame(individual_pred, columns=[column_name])
                        denorm_df = inverse_normalize_dataframe(pred_df, {column_name: actual_scaler}, method=scores_method)
                        denormalized_individual[model_name] = denorm_df[column_name].values
                    
                    target_individual = denormalized_individual
                    logger.debug(f"Denormalized individual predictions for target {target}")
                except Exception as e:
                    logger.warning(f"Failed to denormalize individual predictions for target {target}: {e}")
            
            target_results[target] = {
                'ensemble_predictions': ensemble_predictions,
                'normalized_ensemble_predictions': normalized_ensemble_predictions if denormalization_applied else None,
                'individual_predictions': target_individual,
                'confidence_scores': confidence_scores,
                'model_count': len(target_models),
                'model_names': target_model_names,
                'denormalization_applied': denormalization_applied
            }
            
            # Report what the ensemble actually produced, not the input count: this line read
            # "5 predictions generated" while ensemble_predictions was empty.
            logger.info(
                f"Target {target} ensemble complete: {len(ensemble_predictions)} predictions "
                f"generated from {len(embeddings)} samples"
            )
        
        return target_results

    def _format_multi_target_results(self, target_results):
        """
        Format target-specific results using unified structure.
        
        Processes results from the unified prediction workflow, where
        single-target is treated as multi-target with n=1. Always
        returns target_results structure for consistency.
        
        Parameters
        ----------
        target_results : dict
            Target-specific prediction results from _predict_multi_target
            
        Returns
        -------
        dict
            Consistent results structure containing:
            - target_results: dict with per-target predictions
            - target_count: int number of targets  
            - model_count: int total models across all targets
            - individual_predictions: dict aggregated individual predictions
            - model_names: list aggregated model names
        """
        if not target_results:
            # Keep the target_results shape even when empty - callers index it unconditionally.
            return {
                'target_results': {},
                'target_count': 0,
                'individual_predictions': {},
                'model_count': 0,
                'model_names': []
            }
        
        # Always return target_results format (single-target is just n=1 case)
        all_individual_predictions = {}
        all_model_names = []
        
        # Aggregate individual predictions and model names across all targets
        for target, results in target_results.items():
            all_individual_predictions.update(results['individual_predictions'])
            all_model_names.extend(results['model_names'])
        
        # Create consistent result structure (works for single-target n=1 and multi-target n>1)
        result = {
            'target_results': target_results,              # Full target-specific results
            'individual_predictions': all_individual_predictions,  # For CSV compatibility
            'model_names': all_model_names,
            'model_count': sum(results['model_count'] for results in target_results.values()),
            'target_count': len(target_results)
        }
        
        return result

    def _calculate_multi_target_validation_metrics(self, target_results, ground_truth_labels):
        """
        Calculate validation metrics per target with summary statistics.
        
        Parameters
        ----------
        target_results : dict
            Target-specific prediction results from _predict_multi_target
        ground_truth_labels : np.ndarray or None
            Ground truth labels for validation
            
        Returns
        -------
        dict or None
            Validation metrics per target with summary, or None if no labels available
        """
        if ground_truth_labels is None:
            logger.warning("No ground truth labels available for validation")
            return None
        
        if not target_results:
            logger.warning("No target results available for validation")
            return {}
        
        ground_truth_labels = np.array(ground_truth_labels)
        validation_metrics = {}
        
        # Handle single vs multi-target ground truth
        if ground_truth_labels.ndim == 1:
            # Single target case
            if len(target_results) == 1:
                target = list(target_results.keys())[0]
                metrics = self._calculate_validation_metrics(
                    target_results[target]['ensemble_predictions'], 
                    ground_truth_labels
                )
                validation_metrics[target] = metrics
                logger.info(f"Single-target validation metrics calculated for {target}")
            else:
                logger.warning("Single-dimensional ground truth with multi-target predictions - validation skipped")
                return None
        else:
            # Multi-target case
            if ground_truth_labels.shape[1] != len(target_results):
                logger.warning(f"Ground truth dimensions ({ground_truth_labels.shape[1]}) don't match target count ({len(target_results)})")
                return None
                
            for target_idx, target in enumerate(sorted(target_results.keys())):
                target_predictions = target_results[target]['ensemble_predictions']
                target_ground_truth = ground_truth_labels[:, target_idx]
                
                metrics = self._calculate_validation_metrics(target_predictions, target_ground_truth)
                validation_metrics[target] = metrics
                
                logger.info(f"Validation metrics calculated for {target}: R² = {metrics.get('r2_score', 'N/A'):.3f}")
        
        # Add summary statistics for multi-target scenarios
        if len(validation_metrics) > 1:
            validation_metrics['_summary'] = self._calculate_validation_summary(validation_metrics)
            logger.info(f"Multi-target validation summary calculated across {len(validation_metrics)-1} targets")
        
        return validation_metrics

    def _calculate_validation_summary(self, target_metrics):
        """
        Calculate summary statistics across all targets.
        
        Parameters
        ----------
        target_metrics : dict
            Validation metrics per target
            
        Returns
        -------
        dict
            Summary statistics across targets
        """
        metrics_keys = ['r2_score', 'mse', 'mae', 'rmse', 'correlation']
        summary = {}
        
        for key in metrics_keys:
            values = [metrics.get(key, 0) for target, metrics in target_metrics.items() 
                     if not target.startswith('_')]  # Skip summary entries
            if values:
                summary[f'mean_{key}'] = float(np.mean(values))
                summary[f'std_{key}'] = float(np.std(values))
                summary[f'min_{key}'] = float(np.min(values))
                summary[f'max_{key}'] = float(np.max(values))
        
        # Add target count
        summary['target_count'] = len([t for t in target_metrics.keys() if not t.startswith('_')])
        
        return summary

    def _extract_pipeline_components(self, pipeline):
        """
        Extract feature transformer and estimator from sklearn Pipeline.
        
        Parameters
        ----------
        pipeline : sklearn.pipeline.Pipeline
            Fitted pipeline with 'feat' and 'est' components
            
        Returns
        -------
        tuple
            (feature_transformer, estimator) or (None, None) if extraction fails
        """
        try:
            feature_transformer = pipeline.named_steps.get('feat')
            estimator = pipeline.named_steps.get('est')
            
            if feature_transformer is None:
                logger.warning("Pipeline missing 'feat' component - cannot extract feature transformer")
            if estimator is None:
                logger.warning("Pipeline missing 'est' component - cannot extract estimator")
                
            return feature_transformer, estimator
            
        except Exception as e:
            logger.error(f"Failed to extract pipeline components: {e}")
            return None, None
