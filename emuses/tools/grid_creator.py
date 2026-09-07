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


class HeatmapIntegrityError(RuntimeError):
    """A map cannot be built *correctly*, as opposed to not at all.

    ``create_prediction_heatmaps`` wraps each target in a broad handler so that one target
    with no usable models does not take the others down with it. That is right for "cannot
    compute": the target ends up with no map, and its absence is visible downstream.

    It is wrong for "would compute the wrong thing". A map built from a null in different
    units from the predictions it corrects is arithmetic on incompatible quantities; it
    produces a plausible-looking array that someone will interpret. Raising this class
    instead means the broad handler re-raises rather than recording ``{'error': ...}`` and
    carrying on, so the run stops where the science broke rather than in the log.
    """


class GridCreator:
    """
    Creates prediction heatmaps using 100x100 coordinate grids and simplified inference.

    Executes AFTER nested CV training when models are available in pipeline context.

    Parameters
    ----------
    grid_size : int, default=100
        Grid resolution (creates grid_size x grid_size coordinate grid)
    confidence_method : str, default="cv_ensemble"
        How the CV ensemble's predictions become a confidence. See
        ``aggregate_confidence`` for what each one computes and, importantly, for which
        part of it can actually move region selection.
        - "cv_ensemble": cross-model agreement x whether the ensemble varies at all.
        - "5_model": cross-model agreement only.
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
                             target_name: str,
                             target_scores: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
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
        target_scores : np.ndarray
            The training targets these models were fitted on, and the yardstick the
            confidence is measured against.

            **Required to be in the same space the models predict in.** A yardstick in
            the wrong units rescales every confidence on the grid and reports nothing
            about it. In the pipeline both sides are whatever ``--scores_normalization``
            produced, because ``prediction_train_labels`` -- which is what reaches this
            as ``target_data`` -- is exactly the array the models were trained on. That
            is why the comparison here is against the raw model output, and NOT against
            the denormalized predictions ``create_prediction_heatmaps`` goes on to save.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Tuple of (predictions, confidences) for grid points.
            Both arrays have shape (n_points,)

        Raises
        ------
        ValueError
            If no models found for target, models dict malformed, or the target is
            constant (no scale to measure a confidence against).
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

        for i, model_info in enumerate(target_models):
            model = model_info['model']

            try:
                # Run prediction on grid coordinates directly (skip input transformation)
                if hasattr(model, 'predict'):
                    pred = model.predict(grid_coords)
                    all_predictions.append(pred)

                    logger.debug(f"Model {i+1}/{len(target_models)} prediction shape: {pred.shape}")

                else:
                    logger.warning(f"Model {i+1} doesn't have predict method - skipping")

            except Exception as e:
                logger.warning(f"Inference failed for model {i+1}: {e}")
                continue

        if not all_predictions:
            raise ValueError(f"All inference attempts failed for target '{target_name}'")

        # Convert to arrays for easier handling
        all_predictions = np.array(all_predictions)  # Shape: (n_models, n_points)

        # Ensemble predictions (mean across models)
        ensemble_predictions = np.mean(all_predictions, axis=0)

        # Confidence from the predictions themselves. Until 2026-09-06 this loop also
        # built an `all_confidences` array in which every regression model contributed
        # `np.ones(n_points) * 0.8`, and handed that to `aggregate_confidence`, whose
        # cv_ensemble branch took the standard deviation across models -- of identical
        # constants, so exactly 0, so confidence 1.0 at every grid point. The map was
        # a constant, and `combined_heatmap = predictions * confidences` was therefore
        # just the predictions scaled by 0.8. See `aggregate_confidence` for what
        # replaced it and for what a constant confidence costs downstream.
        ensemble_confidences = self.aggregate_confidence(
            all_predictions, target_scale=self._target_scale(target_scores, target_name)
        )

        logger.info(f"Completed simplified inference. Prediction range: "
                    f"[{np.min(ensemble_predictions):.3f}, {np.max(ensemble_predictions):.3f}], "
                    f"Confidence range: [{np.min(ensemble_confidences):.3f}, {np.max(ensemble_confidences):.3f}]")

        return ensemble_predictions, ensemble_confidences

    @staticmethod
    def _target_scale(target_scores: np.ndarray, target_name: str) -> float:
        """The yardstick a confidence is measured against: the training target's SD.

        Chosen over the alternatives (the prediction range on the grid, a fixed
        constant) because it is the only one that makes the number comparable across
        targets and across runs. A disagreement of 0.3 between folds means something
        different on a target with SD 0.1 than on one with SD 10, and a confidence that
        cannot distinguish those is not measuring agreement, it is measuring units.

        Raises rather than falling back if the target is constant. A constant target has
        no scale, every model fitted on it predicts the same number, and any confidence
        computed against it is a ratio of zero to zero dressed up as a fraction.
        """
        target_scores = np.asarray(target_scores, dtype=float).ravel()
        if target_scores.size == 0:
            raise ValueError(
                f"target_scores for '{target_name}' is empty; there is no scale to "
                f"measure a grid confidence against."
            )
        scale = float(np.std(target_scores))
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError(
                f"target '{target_name}' is constant (SD {scale}); there is nothing for "
                f"a model to predict and therefore no scale a confidence could be "
                f"expressed in. Refusing rather than returning a confidence that would "
                f"be a ratio of zero to zero."
            )
        return scale

    def aggregate_confidence(self, model_predictions: np.ndarray,
                             target_scale: float) -> np.ndarray:
        """
        Turn the cross-validation ensemble's predictions into a per-grid-point confidence.

        ``confidence = agreement x variability``:

        - **agreement** (per grid point) -- ``1 - std(model_predictions, axis=0) /
          target_scale``, clipped to [0, 1]. The folds were fitted on different subsets,
          so where they still agree the surface is pinned by data and where they diverge
          it is being extrapolated. This grows with sparsity at the edges *and* in
          interior holes, which is why it partly subsumes the boundary-bias work.
        - **variability** (one scalar for the whole grid) -- ``std(ensemble) /
          target_scale``, clipped to [0, 1]. Asks whether the ensemble surface varies at
          all. A model that returns the same number everywhere agrees with itself
          perfectly, so agreement alone would report 1.0 across the grid for the most
          degenerate model there is.

        **Only `agreement` moves region selection.** ``create_statistical_maps`` selects
        regions with a *percentile* threshold on ``predictions * confidence``, and a
        percentile is invariant to multiplication by a positive constant -- so the
        scalar ``variability`` factor cannot change which grid points are selected, by
        construction. Its job is different: it collapses the whole map toward zero when
        the ensemble is flat, so a degenerate run is visible in the saved
        ``confidence_values.npy`` and in ``confidence_range`` instead of looking like a
        confident one. Do not read it as a second discriminating signal.

        Confidence was previously a constant (see the note in ``simplified_inference``),
        and a constant confidence has *exactly zero* effect on a percentile threshold --
        it was not a weak signal, it was no signal.

        ``confidence_method`` selects between:
        - ``"cv_ensemble"`` (default): both factors, as above.
        - ``"5_model"``: ``agreement`` only. The absolute values are then not comparable
          with a cv_ensemble run, and a flat ensemble reads as fully confident.

        Parameters
        ----------
        model_predictions : np.ndarray
            Predictions from each model with shape (n_models, n_points). **Predictions,
            not confidences.** Until 2026-09-06 the caller passed per-model confidence
            values here while this docstring already described predictions; the code has
            been made to match the documented intent, per Step 3 of
            dev-docs/methodology/embedding_scaling_and_boundary_bias_plan.md.
        target_scale : float
            Positive scale the disagreement is expressed as a fraction of -- the training
            target's SD, from ``_target_scale``. Replaces the previous
            ``max_possible_std = 0.5``, which was calibrated against nothing.

        Returns
        -------
        np.ndarray
            Confidence values in [0, 1] with shape (n_points,)

        Raises
        ------
        ValueError
            If model_predictions is empty, not 2D, or target_scale is not positive
        """
        if model_predictions.size == 0:
            raise ValueError("model_predictions array is empty")

        if model_predictions.ndim != 2:
            raise ValueError(f"model_predictions must be 2D array, got shape: {model_predictions.shape}")

        if not np.isfinite(target_scale) or target_scale <= 0:
            raise ValueError(f"target_scale must be finite and positive, got: {target_scale}")

        n_models, n_points = model_predictions.shape

        spread = np.std(model_predictions, axis=0)
        agreement = 1.0 - np.clip(spread / target_scale, 0.0, 1.0)

        if n_models == 1:
            # std across one model is 0 at every point, so `agreement` is 1.0 everywhere
            # and carries no information. Not an error -- one fold is a legitimate, if
            # weak, configuration -- but the caller must not read the flat map as
            # meaning the surface is well determined.
            logger.warning(
                "Confidence computed from a single model: cross-model agreement is 1.0 "
                "at every grid point by construction and says nothing about how well "
                "the surface is determined. Only the variability factor carries signal."
            )

        if self.confidence_method == "5_model":
            aggregated_confidence = agreement
            variability = 1.0

        elif self.confidence_method == "cv_ensemble":
            ensemble = np.mean(model_predictions, axis=0)
            variability = float(np.clip(np.std(ensemble) / target_scale, 0.0, 1.0))
            aggregated_confidence = agreement * variability

        else:
            # This should never happen due to __init__ validation, but defensive programming
            raise ValueError(f"Unknown confidence_method: {self.confidence_method}")

        aggregated_confidence = np.clip(aggregated_confidence, 0.0, 1.0)

        if float(np.std(aggregated_confidence)) == 0.0:
            # The exact defect Step 3 exists to remove, so it is reported rather than
            # returned quietly. A constant confidence multiplied into the heatmap cannot
            # change any percentile threshold, so every downstream region is selected as
            # if no confidence had been computed at all.
            logger.warning(
                f"Confidence for this target is CONSTANT at {float(aggregated_confidence.flat[0]):.4f} "
                f"across all {n_points} grid points (ensemble spread {float(np.std(np.mean(model_predictions, axis=0))):.3e}, "
                f"cross-model spread {float(np.max(spread)):.3e}, target scale {target_scale:.3e}). "
                f"Region selection downstream uses a percentile threshold, which is "
                f"invariant to a constant factor, so this confidence has no effect on "
                f"which regions are reported. Usually it means the fitted models ignore "
                f"the embedding coordinates -- check whether the prediction stage found "
                f"any signal before reading the maps."
            )

        logger.info(
            f"Confidence ({self.confidence_method}) from {n_models} models: "
            f"agreement [{np.min(agreement):.3f}, {np.max(agreement):.3f}], "
            f"variability {variability:.3f}, "
            f"final [{np.min(aggregated_confidence):.3f}, {np.max(aggregated_confidence):.3f}]"
        )

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

                # Run simplified inference for this target.
                # `target_scores` is the yardstick the confidence is measured against,
                # and it must be in the space the models predict in -- which it is,
                # because it IS what they were trained on (heatmap_stage passes
                # `prediction_train_labels` straight through). Hence it is paired with
                # the pre-denormalization `predictions`, not with `final_predictions`.
                predictions, confidences = self.simplified_inference(
                    grid_coords, trained_models, target_name, target_scores
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

                # Shrink toward the null by confidence, rather than multiplying by it.
                null_level = self._null_level(
                    target_scores, target_name, trained_models, denormalization_applied
                )
                corrected_heatmap = null_level + confidences * (final_predictions - null_level)

                # Save numerical results
                prediction_values_path = target_output / "prediction_values.npy"
                confidence_values_path = target_output / "confidence_values.npy"
                corrected_values_path = target_output / "corrected_values.npy"
                grid_coords_path = target_output / "grid_coordinates.npy"

                np.save(prediction_values_path, final_predictions)
                np.save(confidence_values_path, confidences)
                np.save(corrected_values_path, corrected_heatmap)
                np.save(grid_coords_path, grid_coords)

                # Save metadata
                metadata = {
                    'target_name': target_name,
                    'grid_size': self.grid_size,
                    'confidence_method': self.confidence_method,
                    'denormalization_applied': denormalization_applied,
                    # What `corrected_values.npy` actually is, recorded so a saved map stays
                    # interpretable without this source file. `combined_values.npy` used to sit
                    # here holding `predictions * confidence`; it is deliberately NOT written
                    # any more rather than redefined, so an old folder cannot be misread as a
                    # new one.
                    'combination': 'shrink_to_null',
                    'null_level': float(null_level),
                    'prediction_range': [float(np.min(final_predictions)), float(np.max(final_predictions))],
                    'confidence_range': [float(np.min(confidences)), float(np.max(confidences))],
                    'corrected_range': [float(np.min(corrected_heatmap)), float(np.max(corrected_heatmap))],
                    'grid_points': len(grid_coords),
                    'artifacts': {
                        'prediction_values': str(prediction_values_path),
                        'confidence_values': str(confidence_values_path),
                        'corrected_values': str(corrected_values_path),
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
                            f"corrected heatmap [{metadata['corrected_range'][0]:.3f}, {metadata['corrected_range'][1]:.3f}] "
                            f"(shrunk toward null {null_level:.3f})")

            except HeatmapIntegrityError:
                # Deliberately not absorbed. The handler below is for "this target has no
                # map"; this is "this target's map would be wrong", and a wrong map recorded
                # as a per-target error is a wrong map that still gets written next run and
                # read by someone. Let it stop the run.
                raise
            except Exception as e:
                logger.error(f"Failed to create heatmaps for target {target_name}: {e}")
                results['heatmap_results'][target_name] = {'error': str(e)}
                continue

        logger.info(f"Completed prediction heatmap generation for {len(results['heatmap_results'])} targets")
        return results

    def _null_level(self, target_scores: np.ndarray, target_name: str,
                    trained_models: Dict, denormalization_applied: bool) -> float:
        """The value a grid point takes when there is no confidence in it.

        The training target's **mean**: the prediction you would make knowing nothing about
        position in the morphospace, which is literally what a constant model returns (the
        degenerate fixtures in ADR 3.1b return exactly this). Not a tuning parameter -- the
        alternative worth considering is the median, for robustness, and nothing else.

        WHY THIS EXISTS AT ALL. The map used to be ``predictions * confidence``. That is
        shrinkage toward zero, and zero is the null only for a centred quantity. On a 0-1
        target -- a depression score where 0 means "fully depressed" -- zero is a meaningful
        *extreme*, so multiplying pushed every low-confidence grid point toward "maximally
        depressed" and into the bottom tail. Measured on swiss_roll (2026-09-07): the low
        prediction region went from 29 to 77 training samples, the old set a strict subset,
        purely from confidence entering the wrong way. The defect is sign-dependent -- on a
        negative-valued target the same multiplication pushes untrusted points *out* of the
        low tail -- which is what shows the operation was wrong rather than the confidence.
        Note ``null_level = 0`` recovers the old behaviour exactly, so this generalises it.

        SPACE CONSISTENCY, which is the easy thing to get wrong here. ``target_scores`` is in
        the space the models were fitted on; ``final_predictions`` has been *denormalized* when
        a scores scaler exists. Taking the mean of the former and subtracting it from the latter
        would mix the two silently. So when denormalization was applied, the mean is pushed
        through the very same transform rather than an equivalent-looking one.
        """
        target_scores = np.asarray(target_scores, dtype=float).ravel()
        if target_scores.size == 0:
            raise ValueError(
                f"target_scores for '{target_name}' is empty; there is no null level to "
                f"shrink an untrusted grid point toward."
            )
        null_model_space = float(np.mean(target_scores))

        if not denormalization_applied:
            return null_model_space

        denormalized, applied = self._denormalize_predictions(
            np.array([null_model_space]), target_name, trained_models
        )
        if not applied or denormalized is None:
            # Deliberately not a fallback to the model-space value. The predictions this null
            # is about to be subtracted from HAVE been denormalized; returning the un-transformed
            # mean here would put the two in different units and the shrinkage would be
            # arithmetic on incompatible quantities, silently.
            raise HeatmapIntegrityError(
                f"predictions for '{target_name}' were denormalized but the same transform "
                f"could not be applied to the null level ({null_model_space}). Refusing to "
                f"shrink toward a null in different units from the map it corrects."
            )
        return float(denormalized[0])

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
