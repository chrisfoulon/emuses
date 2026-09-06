"""
Grid creation functionality for statistical analysis in HeatmapStage.

This module provides the GridCreator class that generates prediction heatmaps
using 100x100 coordinate grids and simplified inference.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from bcblib.tools.dataframe_filtering import inverse_normalize_dataframe

logger = logging.getLogger(__name__)


class GridCreator:
    """
    Creates prediction heatmaps using 100x100 coordinate grids and simplified inference.

    Executes AFTER nested CV training when models are available in pipeline context.

    Parameters
    ----------
    grid_size : int, default=100
        Grid resolution (creates grid_size x grid_size coordinate grid)
    confidence_method : str, default="cv_ensemble"
        Method for confidence aggregation. Options: "5_model", "cv_ensemble"
    """

    def __init__(self, grid_size: int = 100, confidence_method: str = "cv_ensemble"):
        self.grid_size = grid_size
        self.confidence_method = confidence_method

        if confidence_method not in ["5_model", "cv_ensemble"]:
            raise ValueError(f"confidence_method must be '5_model' or 'cv_ensemble', got: {confidence_method}")

        logger.info(f"GridCreator initialized with grid_size={grid_size}, confidence_method={confidence_method}")

    def generate_coordinate_grid(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Generate 100x100 linspace coordinate grid on rescaled embeddings (0-1).

        Creates a uniform grid of coordinates spanning the full range of the
        rescaled embedding space. The embeddings are assumed to be already
        rescaled to 0-1 range (prediction_train_coords from pipeline context).

        Parameters
        ----------
        embeddings : np.ndarray
            Rescaled UMAP embeddings with shape (n_samples, 2).
            Expected to be in 0-1 coordinate range.

        Returns
        -------
        np.ndarray
            Grid coordinates with shape (grid_size*grid_size, 2).
            For default grid_size=100, returns (10000, 2) array.

        Raises
        ------
        ValueError
            If embeddings don't have expected shape or aren't in 0-1 range.
        """
        if embeddings.ndim != 2 or embeddings.shape[1] != 2:
            raise ValueError(f"embeddings must have shape (n_samples, 2), got: {embeddings.shape}")

        # Verify embeddings are in expected 0-1 range (allow small tolerance)
        min_vals = np.min(embeddings, axis=0)
        max_vals = np.max(embeddings, axis=0)

        tolerance = 0.1  # Allow 10% tolerance outside 0-1 range
        if np.any(min_vals < -tolerance) or np.any(max_vals > 1 + tolerance):
            logger.warning(f"Embeddings may not be properly rescaled. Range: [{min_vals}, {max_vals}]. "
                           f"Expected approximately [0, 1].")

        # The grid spans exactly the data, with no padding.
        #
        # There used to be a +/-0.05 pad clamped to [0, 1]. Under the old per-axis
        # rescale the data spanned exactly [0, 1] on both axes, so the clamps cancelled
        # the pad exactly and it did nothing -- it was inert for as long as it existed.
        # Under the isotropic rescale (2026-09-06) the narrow axis no longer reaches 1,
        # so the pad would have woken up ASYMMETRICALLY: still 0 at the bottom, where
        # the clamp bites, and +0.05 at the top, where it does not. That is a grid
        # silently off-centre against the data it describes.
        #
        # Its stated purpose was display -- making sure points on the edge stay
        # visible. Matplotlib already does that: axes.xmargin/axes.ymargin default to
        # exactly 0.05. Padding the DATA grid to solve a rendering problem also changes
        # what gets predicted, thresholded and turned into regions.
        x_min, x_max = np.min(embeddings[:, 0]), np.max(embeddings[:, 0])
        y_min, y_max = np.min(embeddings[:, 1]), np.max(embeddings[:, 1])

        # Removing the pad exposed a case it had been hiding: with no extent at all,
        # linspace(v, v, n) returns n copies of v, so every grid point is the SAME
        # coordinate. Predictions, confidences and regions are then all computed on one
        # location and reported as a map. The pad made that look like a real grid.
        #
        # Refused rather than padded, matching isotropic_scaling_factors, which raises on
        # exactly this input for the same reason. One degenerate axis is allowed: an
        # embedding collapsed onto a line is pathological but still has structure to
        # place, and the rescale survives it.
        spans = np.array([x_max - x_min, y_max - y_min], dtype=float)
        if not np.isfinite(spans).all() or spans.max() <= 0:
            raise ValueError(
                f"The embedding has no extent to grid (axis ranges {spans.tolist()}). "
                f"Every sample sits at the same coordinate, so there is no morphospace "
                f"to lay a grid over: linspace would return {self.grid_size**2} copies "
                f"of one point and everything downstream would report a map of it."
            )
        if spans.min() <= 0:
            logger.warning(
                f"Embedding is degenerate on one axis (ranges {spans.tolist()}); the "
                f"grid is a line, and any region found on it has no width."
            )

        x_coords = np.linspace(x_min, x_max, self.grid_size)
        y_coords = np.linspace(y_min, y_max, self.grid_size)

        # Create meshgrid and flatten to coordinate pairs
        X, Y = np.meshgrid(x_coords, y_coords)
        grid_coords = np.column_stack([X.ravel(), Y.ravel()])

        logger.info(f"Generated {self.grid_size}x{self.grid_size} coordinate grid "
                    f"with shape {grid_coords.shape}. "
                    f"X range: [{x_min:.3f}, {x_max:.3f}], Y range: [{y_min:.3f}, {y_max:.3f}]")

        return grid_coords

    def _adapt_models_for_target(self, models, target_name):
        """
        Adapter method to handle both dict and sklearn Pipeline models.
        
        This method provides compatibility between:
        - Dictionary interface (existing tests): models with .get('target') method
        - sklearn Pipeline interface (production): Pipeline objects without .get()
        
        Parameters
        ----------
        models : list
            List of models, either dict objects or sklearn Pipeline objects
        target_name : str
            Target variable name for model selection
            
        Returns
        -------
        list
            Filtered models for the specified target
        """
        adapted_models = []
        for model in models:
            if hasattr(model, 'get'):  # Dictionary interface (existing tests)
                if str(target_name) in model.get('target', ''):
                    adapted_models.append(model)
            else:  # sklearn Pipeline interface (production case)
                # All models from HeatmapStage are already target-specific
                adapted_models.append(model)
        return adapted_models

    def simplified_inference(self,
                             grid_coords: np.ndarray,
                             trained_models: Dict,
                             target_name: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run inference on grid coordinates using trained models from context.

        Performs simplified inference by skipping input data transformation since we
        start with grid coordinates directly. Uses models from pipeline context
        available after nested CV training.

        Parameters
        ----------
        grid_coords : np.ndarray
            Grid coordinates with shape (n_points, 2) from generate_coordinate_grid
        trained_models : dict
            Dictionary containing prediction models from pipeline context.
            Expected format: {'prediction_models': [model_dicts, ...]}
        target_name : str
            Target variable name for model selection

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Tuple of (predictions, confidences) for grid points.
            Both arrays have shape (n_points,)

        Raises
        ------
        ValueError
            If no models found for target or models dict malformed
        """
        prediction_models = trained_models.get('prediction_models', [])
        if not prediction_models:
            raise ValueError("No prediction models found in trained_models")

        # Group models by target using adapter pattern
        target_models = self._adapt_models_for_target(prediction_models, target_name)

        if not target_models:
            # For error message, safely extract target info based on model type
            available_targets = set()
            for m in prediction_models:
                if hasattr(m, 'get'):
                    available_targets.add(m.get('target', 'target_0'))
                else:
                    available_targets.add('target_specific_pipeline')
            raise ValueError(f"No models found for target '{target_name}'. "
                             f"Available targets: {available_targets}")

        logger.info(f"Running simplified inference on {len(grid_coords)} grid points "
                    f"using {len(target_models)} models for target '{target_name}'")

        # Collect predictions from all models for the target
        all_predictions = []
        all_confidences = []

        for i, model_info in enumerate(target_models):
            model = model_info['model']

            try:
                # Run prediction on grid coordinates directly (skip input transformation)
                if hasattr(model, 'predict'):
                    pred = model.predict(grid_coords)
                    all_predictions.append(pred)

                    # Calculate confidence based on model type
                    if hasattr(model, 'predict_proba'):
                        # Classification model - use max probability as confidence
                        proba = model.predict_proba(grid_coords)
                        confidence = np.max(proba, axis=1)
                    elif hasattr(model, 'score') or hasattr(model, 'predict'):
                        # Regression model - use 1 - relative prediction variance as confidence proxy
                        # For now, use a constant confidence for regression models
                        confidence = np.ones(len(grid_coords)) * 0.8  # Default confidence
                    else:
                        confidence = np.ones(len(grid_coords)) * 0.5  # Fallback confidence

                    all_confidences.append(confidence)

                    logger.debug(f"Model {i+1}/{len(target_models)} prediction shape: {pred.shape}, "
                                 f"confidence shape: {confidence.shape}")

                else:
                    logger.warning(f"Model {i+1} doesn't have predict method - skipping")

            except Exception as e:
                logger.warning(f"Inference failed for model {i+1}: {e}")
                continue

        if not all_predictions:
            raise ValueError(f"All inference attempts failed for target '{target_name}'")

        # Convert to arrays for easier handling
        all_predictions = np.array(all_predictions)  # Shape: (n_models, n_points)
        all_confidences = np.array(all_confidences)  # Shape: (n_models, n_points)

        # Ensemble predictions (mean across models)
        ensemble_predictions = np.mean(all_predictions, axis=0)

        # Aggregate confidences using the specified method
        ensemble_confidences = self.aggregate_confidence(all_confidences)

        logger.info(f"Completed simplified inference. Prediction range: "
                    f"[{np.min(ensemble_predictions):.3f}, {np.max(ensemble_predictions):.3f}], "
                    f"Confidence range: [{np.min(ensemble_confidences):.3f}, {np.max(ensemble_confidences):.3f}]")

        return ensemble_predictions, ensemble_confidences

    def aggregate_confidence(self, model_confidences: np.ndarray) -> np.ndarray:
        """
        Aggregate confidence from multiple model predictions.

        Supports two methods for confidence aggregation:
        - "5_model": Average of model-specific confidences
        - "cv_ensemble": 1 - standard deviation of ensemble predictions (CV-style confidence)

        Parameters
        ----------
        model_confidences : np.ndarray
            Confidence values from each model with shape (n_models, n_points)

        Returns
        -------
        np.ndarray
            Aggregated confidence values with shape (n_points,)

        Raises
        ------
        ValueError
            If model_confidences array is empty or has wrong shape
        """
        if model_confidences.size == 0:
            raise ValueError("model_confidences array is empty")

        if model_confidences.ndim != 2:
            raise ValueError(f"model_confidences must be 2D array, got shape: {model_confidences.shape}")

        n_models, n_points = model_confidences.shape

        if self.confidence_method == "5_model":
            # Method 1: Simple average of model-specific confidences
            aggregated_confidence = np.mean(model_confidences, axis=0)

            logger.debug(f"Using 5_model confidence aggregation: "
                         f"averaged {n_models} model confidences")

        elif self.confidence_method == "cv_ensemble":
            # Method 2: 1 - std of predictions (CV ensemble style confidence)
            # Higher std = lower confidence, lower std = higher confidence
            # We use the confidences as a proxy for prediction variability

            # Calculate standard deviation across models
            confidence_std = np.std(model_confidences, axis=0)

            # Convert to confidence: 1 - normalized_std
            # Normalize std to 0-1 range based on max possible std
            max_possible_std = 0.5  # Conservative estimate for confidence std
            normalized_std = np.clip(confidence_std / max_possible_std, 0, 1)
            aggregated_confidence = 1 - normalized_std

            logger.debug(f"Using cv_ensemble confidence aggregation: "
                         f"std range [{np.min(confidence_std):.3f}, {np.max(confidence_std):.3f}], "
                         f"confidence range [{np.min(aggregated_confidence):.3f}, {np.max(aggregated_confidence):.3f}]")

        else:
            # This should never happen due to __init__ validation, but defensive programming
            raise ValueError(f"Unknown confidence_method: {self.confidence_method}")

        # Ensure confidence values are in valid range [0, 1]
        aggregated_confidence = np.clip(aggregated_confidence, 0.0, 1.0)

        logger.debug(f"Aggregated confidence stats - Mean: {np.mean(aggregated_confidence):.3f}, "
                     f"Std: {np.std(aggregated_confidence):.3f}, "
                     f"Range: [{np.min(aggregated_confidence):.3f}, {np.max(aggregated_confidence):.3f}]")

        return aggregated_confidence

    def create_prediction_heatmaps(self,
                                   embeddings: np.ndarray,
                                   trained_models: Dict,
                                   target_data: Dict,
                                   output_folder: Path,
                                   denormalize: bool = True) -> Dict:
        """
        Main interface: Create prediction*confidence heatmaps for all targets.

        Creates target_*/prediction-heatmaps/ folder structure with artifacts.

        Parameters
        ----------
        embeddings : np.ndarray
            Rescaled embeddings (0-1 coordinates) from pipeline context
        trained_models : dict
            Models from pipeline context with prediction models and scalers
        target_data : dict
            Target variable data and metadata {target_name: scores, ...}
        output_folder : Path
            Base output directory
        denormalize : bool, default=True
            Whether to denormalize predictions to original range using scores scalers

        Returns
        -------
        dict
            Results with artifact paths and metadata for all targets
        """
        output_folder = Path(output_folder)
        results = {
            'heatmap_results': {},
            'grid_metadata': {
                'grid_size': self.grid_size,
                'confidence_method': self.confidence_method,
                'denormalize': denormalize
            }
        }

        # Generate coordinate grid once for all targets
        grid_coords = self.generate_coordinate_grid(embeddings)

        logger.info(f"Creating prediction heatmaps for {len(target_data)} targets")

        # Process each target separately
        for target_name, target_scores in target_data.items():
            logger.info(f"Processing target: {target_name}")

            try:
                # Create target-specific output directory
                # Check if output_folder already contains target structure (e.g., .../target_0/)
                if output_folder.name.startswith(f"target_"):
                    # HeatmapStage already created target-specific folder
                    target_output = output_folder / "prediction-heatmaps"
                else:
                    # Create target structure ourselves
                    target_output = output_folder / f"target_{target_name}" / "prediction-heatmaps"
                target_output.mkdir(parents=True, exist_ok=True)

                # Run simplified inference for this target
                predictions, confidences = self.simplified_inference(
                    grid_coords, trained_models, target_name
                )

                # Apply denormalization if requested and scalers are available
                denormalized_predictions = None
                denormalization_applied = False

                if denormalize:
                    denormalized_predictions, denormalization_applied = self._denormalize_predictions(
                        predictions, target_name, trained_models
                    )

                # Use denormalized predictions if available, otherwise normalized
                final_predictions = denormalized_predictions if denormalization_applied else predictions

                # Create prediction*confidence heatmaps
                combined_heatmap = final_predictions * confidences

                # Save numerical results
                prediction_values_path = target_output / "prediction_values.npy"
                confidence_values_path = target_output / "confidence_values.npy"
                combined_values_path = target_output / "combined_values.npy"
                grid_coords_path = target_output / "grid_coordinates.npy"

                np.save(prediction_values_path, final_predictions)
                np.save(confidence_values_path, confidences)
                np.save(combined_values_path, combined_heatmap)
                np.save(grid_coords_path, grid_coords)

                # Save metadata
                metadata = {
                    'target_name': target_name,
                    'grid_size': self.grid_size,
                    'confidence_method': self.confidence_method,
                    'denormalization_applied': denormalization_applied,
                    'prediction_range': [float(np.min(final_predictions)), float(np.max(final_predictions))],
                    'confidence_range': [float(np.min(confidences)), float(np.max(confidences))],
                    'combined_range': [float(np.min(combined_heatmap)), float(np.max(combined_heatmap))],
                    'grid_points': len(grid_coords),
                    'artifacts': {
                        'prediction_values': str(prediction_values_path),
                        'confidence_values': str(confidence_values_path),
                        'combined_values': str(combined_values_path),
                        'grid_coordinates': str(grid_coords_path)
                    }
                }

                # Include normalized predictions if denormalization was applied
                if denormalization_applied:
                    normalized_values_path = target_output / "normalized_prediction_values.npy"
                    np.save(normalized_values_path, predictions)
                    metadata['normalized_prediction_range'] = [float(np.min(predictions)), float(np.max(predictions))]
                    metadata['artifacts']['normalized_prediction_values'] = str(normalized_values_path)

                # Save metadata as JSON
                metadata_path = target_output / "prediction_metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                metadata['artifacts']['metadata'] = str(metadata_path)

                results['heatmap_results'][target_name] = metadata

                logger.info(f"Created prediction heatmaps for target {target_name}: "
                            f"predictions [{metadata['prediction_range'][0]:.3f}, {metadata['prediction_range'][1]:.3f}], "
                            f"combined heatmap [{metadata['combined_range'][0]:.3f}, {metadata['combined_range'][1]:.3f}]")

            except Exception as e:
                logger.error(f"Failed to create heatmaps for target {target_name}: {e}")
                results['heatmap_results'][target_name] = {'error': str(e)}
                continue

        logger.info(f"Completed prediction heatmap generation for {len(results['heatmap_results'])} targets")
        return results

    def _denormalize_predictions(self, predictions: np.ndarray, target_name: str, trained_models: Dict) -> Tuple[Optional[np.ndarray], bool]:
        """
        Denormalize predictions using scores scalers from trained models.

        Follows the same denormalization pattern as InferenceStage.

        Parameters
        ----------
        predictions : np.ndarray
            Normalized predictions to denormalize
        target_name : str
            Target name for scaler lookup
        trained_models : dict
            Models dictionary containing scores scalers

        Returns
        -------
        tuple[Optional[np.ndarray], bool]
            Tuple of (denormalized_predictions, denormalization_applied)
        """
        scores_scaler_dict = trained_models.get('scores_scaler')
        if scores_scaler_dict is None:
            logger.debug("No scores scaler available, predictions remain normalized")
            return None, False

        try:
            # Get the normalization method from metadata
            scores_method = trained_models.get('metadata', {}).get('scores_normalization_method', 'robust')

            # Determine the correct scaler and column name for this target
            actual_scaler = None
            target_column_name = None

            # Try target-specific scaler first
            if target_name in scores_scaler_dict:
                actual_scaler = scores_scaler_dict[target_name]
                target_column_name = target_name
            # Try with score prefix
            elif f"score_{target_name.split('_')[-1]}" in scores_scaler_dict:
                score_key = f"score_{target_name.split('_')[-1]}"
                actual_scaler = scores_scaler_dict[score_key]
                target_column_name = score_key
            # Fallback to generic 'score' key
            elif 'score' in scores_scaler_dict:
                actual_scaler = scores_scaler_dict['score']
                target_column_name = 'score'

            if actual_scaler is not None:
                # Convert predictions to DataFrame for denormalization
                # Use original column name if available, otherwise 'score'
                column_name = target_column_name or 'score'
                pred_df = pd.DataFrame(predictions, columns=[column_name])
                denorm_df = inverse_normalize_dataframe(pred_df, {column_name: actual_scaler}, method=scores_method)
                denormalized_predictions = denorm_df[column_name].values

                logger.info(f"Applied prediction denormalization ({scores_method}) for target {target_name}: "
                            f"range [{denormalized_predictions.min():.3f}, {denormalized_predictions.max():.3f}]")
                return denormalized_predictions, True
            else:
                logger.warning(f"Could not extract scaler for target {target_name} from scores_scaler")
                return None, False

        except Exception as e:
            logger.warning(f"Failed to denormalize predictions for target {target_name}: {e}")
            return None, False
