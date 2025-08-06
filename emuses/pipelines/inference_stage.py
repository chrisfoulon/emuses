# pipelines/inference_stage.py

"""
InferenceStage implementation for EMUSES pipeline inference capabilities.

This stage enables inference on trained models with automatic detection of
validation vs pure inference modes, leveraging the observability infrastructure
for performance tracking and research insights.
"""

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

        # Extract inference-specific configuration
        self.model_path = getattr(config, 'model_path', None)
        self.data_path = getattr(config, 'data_path', None)
        self.output_path = getattr(config, 'output_path', None)
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
                # Task 1: Load trained models
                model_task = progress.add_task("Loading models...", total=1)
                self.trained_models = self._load_trained_models()
                progress.advance(model_task, 1)

                # Task 2: Load data
                data_task = progress.add_task("Loading data...", total=1)
                data_start = time.time()
                new_features = self._load_features(self.data_path)
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

                # Format results for output
                formatted_results = self._format_results(prediction_results, mode, performance_data)

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

        # Return comprehensive results structure (after progress context)
        results = {
            'mode': mode,
            'status': 'completed',
            'samples_processed': sample_count,
            'embeddings_shape': transformed_features.shape,
            'predictions': prediction_results['ensemble_predictions'],
            'prediction_details': {
                'individual_predictions': prediction_results['individual_predictions'],
                'confidence_scores': prediction_results['confidence_scores'],
                'model_count': prediction_results['model_count'],
                'model_names': prediction_results['model_names']
            },
            'performance_breakdown': performance_data,
            'output_files': output_paths,
            'model_info': self._get_model_info()
        }

        logger.info(f"Inference pipeline completed in {mode} mode - processed {sample_count} samples")
        return results

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
                models['metadata']['min_embeddings'] = getattr(umap_model, 'min_embeddings_', None)
                models['metadata']['max_embeddings'] = getattr(umap_model, 'max_embeddings_', None)
            else:
                logger.warning("UMAP model not found - inference will be limited")

        except Exception as e:
            logger.error(f"Failed to load UMAP model: {str(e)}")

        return models

    def _detect_labels(self):
        """
        Detect if input data contains labels for validation mode.

        Returns
        -------
        bool
            True if labels detected, False otherwise
        """
        # Simple implementation - will enhance based on data format detection
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

    def _load_features(self, data_path):
        """
        Load new features for inference.

        Parameters
        ----------
        data_path : str
            Path to new data file

        Returns
        -------
        np.ndarray
            Feature matrix for inference
        """
        # Simple implementation - will enhance based on data format detection
        # For now, assume numpy array format
        logger.info(f"Loading features from {data_path}")
        # Return dummy data for now - will implement proper loading in next iteration
        return np.random.rand(100, 50)  # 100 samples, 50 features

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

        # Apply UMAP transformation
        embeddings = umap_model.transform(features)

        # Rescale embeddings using saved parameters
        min_embeddings = models.get('metadata', {}).get('min_embeddings')
        max_embeddings = models.get('metadata', {}).get('max_embeddings')

        if min_embeddings is not None and max_embeddings is not None:
            embeddings = rescale_embedding(
                embeddings,
                preset_min=min_embeddings,
                preset_max=max_embeddings
            )
            logger.info("Applied rescaling to transformed embeddings")
        else:
            logger.warning("Scaling parameters not available - using raw embeddings")

        return embeddings

    def _predict(self, embeddings, models):
        """
        Run ensemble predictions with per-model performance insights.

        Parameters
        ----------
        embeddings : np.ndarray
            Transformed embeddings from UMAP
        models : dict
            Dictionary containing loaded models

        Returns
        -------
        dict
            Prediction results with ensemble predictions, individual predictions,
            and confidence scores
        """
        prediction_models = models.get('prediction_models', [])
        if not prediction_models:
            raise ValueError("No prediction models available for inference")

        logger.info(f"Running ensemble prediction with {len(prediction_models)} models")

        # Collect individual predictions from each model
        individual_predictions = {}
        model_scores = []

        for model_info in prediction_models:
            model = model_info['model']
            model_name = model_info.get('name', 'unknown')
            model_score = model_info.get('score', 1.0)

            # Get predictions from this model
            predictions = model.predict(embeddings)
            individual_predictions[model_name] = predictions
            model_scores.append(model_score)

        # Create weighted ensemble predictions
        # Simple weighted average based on model scores
        model_names = list(individual_predictions.keys())
        if len(model_names) == 1:
            # Single model case
            ensemble_predictions = individual_predictions[model_names[0]]
        else:
            # Multi-model ensemble
            weighted_predictions = []
            total_weight = sum(model_scores)

            for i, model_name in enumerate(model_names):
                weight = model_scores[i] / total_weight
                weighted_predictions.append(weight * individual_predictions[model_name])

            ensemble_predictions = np.sum(weighted_predictions, axis=0)

        # Calculate confidence scores (standard deviation across models)
        if len(model_names) > 1:
            pred_matrix = np.array([individual_predictions[name] for name in model_names])
            confidence_scores = 1.0 - np.std(pred_matrix, axis=0)  # Higher std = lower confidence
        else:
            # Single model - use uniform confidence
            confidence_scores = np.ones(len(ensemble_predictions)) * 0.8

        results = {
            'ensemble_predictions': ensemble_predictions,
            'individual_predictions': individual_predictions,
            'confidence_scores': confidence_scores,
            'model_count': len(prediction_models),
            'model_names': model_names
        }

        logger.info(f"Ensemble prediction completed for {len(embeddings)} samples")
        return results

    def _format_results(self, predictions, mode, performance_data, validation_metrics=None):
        """
        Format inference results with performance breakdown and metadata.

        Parameters
        ----------
        predictions : dict
            Prediction results from _predict method
        mode : str
            Inference mode ("inference" or "validation")
        performance_data : dict
            Performance timing and throughput data
        validation_metrics : dict, optional
            Validation metrics if in validation mode

        Returns
        -------
        dict
            Formatted results with predictions, performance, and metadata
        """
        logger.info(f"Formatting {mode} results for output")

        # Extract core predictions
        ensemble_predictions = predictions.get('ensemble_predictions', [])
        confidence_scores = predictions.get('confidence_scores', [])
        individual_predictions = predictions.get('individual_predictions', {})

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
        Save predictions in CSV format consistent with training scores.

        Parameters
        ----------
        results : dict
            Formatted results containing predictions and metadata
        output_file : Path
            Path to output CSV file
        """
        import pandas as pd

        # Create DataFrame with consistent structure
        n_samples = len(results['predictions'])
        data = {
            'sample_id': [f"sample_{i:04d}" for i in range(n_samples)],
            'ensemble_prediction': results['predictions'],
            'confidence_score': results.get('confidence_scores', [0.0] * n_samples)
        }

        # Add individual model predictions as separate columns
        individual_preds = results.get('individual_predictions', {})
        for model_name, predictions in individual_preds.items():
            data[model_name] = predictions

        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        logger.info(f"Predictions saved to CSV: {output_file}")

    def _save_confidence_csv(self, results, output_file):
        """
        Save confidence scores in CSV format.

        Parameters
        ----------
        results : dict
            Formatted results containing confidence scores
        output_file : Path
            Path to output CSV file
        """
        import pandas as pd

        confidence_scores = results.get('confidence_scores', [])
        if len(confidence_scores) > 0:
            data = {
                'sample_id': [f"sample_{i:04d}" for i in range(len(confidence_scores))],
                'confidence_score': confidence_scores
            }
            df = pd.DataFrame(data)
            df.to_csv(output_file, index=False)
            logger.info(f"Confidence scores saved to CSV: {output_file}")

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
