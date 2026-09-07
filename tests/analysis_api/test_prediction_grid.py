"""
Tests for prediction grid creation functionality.

Tests the GridCreator class for coordinate generation, inference, and heatmap creation.
"""

import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from emuses.tools.grid_creator import GridCreator, HeatmapIntegrityError


class TestGridCreator:
    """Test GridCreator coordinate generation and grid creation functionality."""
    
    def test_init_default_parameters(self):
        """Test GridCreator initialization with default parameters."""
        creator = GridCreator()
        assert creator.grid_size == 100
        assert creator.confidence_method == "cv_ensemble"
    
    def test_init_custom_parameters(self):
        """Test GridCreator initialization with custom parameters.""" 
        creator = GridCreator(grid_size=50, confidence_method="5_model")
        assert creator.grid_size == 50
        assert creator.confidence_method == "5_model"
    
    def test_init_invalid_confidence_method(self):
        """Test GridCreator raises error for invalid confidence method."""
        with pytest.raises(ValueError, match="confidence_method must be '5_model' or 'cv_ensemble'"):
            GridCreator(confidence_method="invalid_method")
    
    def test_generate_coordinate_grid_basic(self):
        """Test basic coordinate grid generation."""
        creator = GridCreator(grid_size=10)  # Smaller grid for testing
        
        # Create sample embeddings in 0-1 range
        embeddings = np.array([
            [0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8], [0.9, 1.0]
        ])
        
        grid_coords = creator.generate_coordinate_grid(embeddings)
        
        # Check output shape
        assert grid_coords.shape == (100, 2)  # 10x10 = 100 points, 2 coordinates
        
        # Check coordinate ranges are reasonable
        assert np.all(grid_coords >= -0.1)  # Allow small padding
        assert np.all(grid_coords <= 1.1)   # Allow small padding
        
        # Check grid spans the embedding space
        x_range = np.max(grid_coords[:, 0]) - np.min(grid_coords[:, 0])
        y_range = np.max(grid_coords[:, 1]) - np.min(grid_coords[:, 1])
        assert x_range > 0.5  # Should span significant portion
        assert y_range > 0.5  # Should span significant portion
    
    def test_generate_coordinate_grid_default_size(self):
        """Test coordinate grid generation with default 100x100 size."""
        creator = GridCreator()
        
        # Create sample embeddings
        np.random.seed(42)  # For reproducible tests
        embeddings = np.random.uniform(0, 1, (50, 2))
        
        grid_coords = creator.generate_coordinate_grid(embeddings)
        
        # Check default 100x100 grid
        assert grid_coords.shape == (10000, 2)  # 100*100 = 10000
        
        # Check coordinates are within reasonable bounds
        assert np.all(grid_coords >= -0.1)
        assert np.all(grid_coords <= 1.1)
    
    def test_generate_coordinate_grid_invalid_shape(self):
        """Test coordinate grid generation with invalid embedding shape."""
        creator = GridCreator()
        
        # Test wrong number of dimensions
        with pytest.raises(ValueError, match="embeddings must have shape"):
            creator.generate_coordinate_grid(np.array([1, 2, 3]))
        
        # Test wrong second dimension
        with pytest.raises(ValueError, match="embeddings must have shape"):
            creator.generate_coordinate_grid(np.array([[1, 2, 3], [4, 5, 6]]))
    
    def test_generate_coordinate_grid_out_of_range_embeddings(self, caplog):
        """Test coordinate grid generation with embeddings outside 0-1 range."""
        import logging
        caplog.set_level(logging.WARNING, logger="emuses.tools.grid_creator")
        
        creator = GridCreator()
        
        # Embeddings outside expected 0-1 range
        embeddings = np.array([
            [-0.5, 0.2], [0.3, 1.5], [2.0, -1.0]
        ])
        
        grid_coords = creator.generate_coordinate_grid(embeddings)
        
        # Should still work but log warning
        assert "may not be properly rescaled" in caplog.text
        assert grid_coords.shape == (10000, 2)
    
    def test_generate_coordinate_grid_refuses_a_collapsed_embedding(self):
        """An embedding with no extent has no grid, and saying so beats inventing one.

        CHANGED 2026-09-06, and the direction matters: this test previously asserted
        the grid still had spread here, which was true only because of a +/-0.05 pad.
        That pad was inert everywhere else (the old per-axis rescale made the data span
        exactly [0, 1], so the clamps cancelled it) and would have gone asymmetric under
        the isotropic rescale, so it was removed.

        Removing it exposed what the pad had been hiding: with every sample at one
        coordinate, ``linspace(v, v, n)`` returns n copies of v, so all 25 grid points
        are the same location and every prediction, confidence and region downstream
        describes that single point while being reported as a map. The old assertion
        called that "reasonable spread".

        So this is not the same assertion relaxed -- it is a stronger one. Refusing
        matches ``isotropic_scaling_factors``, which raises on exactly this input.
        """
        creator = GridCreator(grid_size=5)
        embeddings = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]])

        with pytest.raises(ValueError, match="no extent to grid"):
            creator.generate_coordinate_grid(embeddings)

    def test_generate_coordinate_grid_allows_a_collapsed_axis(self):
        """One flat axis is pathological but still has structure to place.

        The refusal above must not widen to this: an embedding on a line has a real
        extent to grid along x, and the rescale survives it. Warned, not refused.
        """
        creator = GridCreator(grid_size=5)
        embeddings = np.array([[0.0, 0.5], [0.5, 0.5], [1.0, 0.5]])

        grid_coords = creator.generate_coordinate_grid(embeddings)

        assert grid_coords.shape == (25, 2)
        assert np.ptp(grid_coords[:, 0]) == pytest.approx(1.0)
        assert np.ptp(grid_coords[:, 1]) == 0.0
    
    def test_generate_coordinate_grid_reproducible(self):
        """Test coordinate grid generation is reproducible."""
        creator1 = GridCreator(grid_size=20)
        creator2 = GridCreator(grid_size=20)
        
        embeddings = np.array([[0.1, 0.2], [0.8, 0.9]])
        
        grid1 = creator1.generate_coordinate_grid(embeddings)
        grid2 = creator2.generate_coordinate_grid(embeddings)
        
        # Should be identical
        np.testing.assert_array_equal(grid1, grid2)


class TestGridCreatorInference:
    """Test GridCreator inference and confidence aggregation functionality."""
    
    # The fixture below is shared by the two aggregation tests so they are comparing the
    # same thing. It is a matrix of PREDICTIONS from 3 CV folds at 4 grid points -- the
    # folds agree exactly everywhere except point 2, which is the only place any of this
    # has anything to measure.
    #
    #   spread = std(axis=0)             = [0, 0, 0.816496580927726, 0]
    #   ensemble = mean(axis=0)          = [1, 1, 2, 1]
    #   std(ensemble)                    = 0.4330127018922193
    #
    # against target_scale = 2.0 (the training target's SD).
    FOLD_PREDICTIONS = np.array([
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 1.0, 2.0, 1.0],
        [1.0, 1.0, 3.0, 1.0],
    ])
    TARGET_SCALE = 2.0

    def test_aggregate_confidence_5_model_method(self):
        """5_model is cross-model agreement alone, as a fraction of the target's SD."""
        creator = GridCreator(confidence_method="5_model")

        aggregated = creator.aggregate_confidence(self.FOLD_PREDICTIONS,
                                                  target_scale=self.TARGET_SCALE)

        # agreement = 1 - spread/target_scale
        #           = 1 - [0, 0, 0.816496580927726, 0] / 2
        expected = np.array([1.0, 1.0, 1.0 - 0.408248290463863, 1.0])
        np.testing.assert_array_almost_equal(aggregated, expected, decimal=12)

        assert aggregated.shape == (4,)
        assert np.all(aggregated >= 0.0) and np.all(aggregated <= 1.0)

    def test_aggregate_confidence_cv_ensemble_method(self):
        """cv_ensemble is that same agreement scaled by whether the surface varies."""
        creator = GridCreator(confidence_method="cv_ensemble")

        aggregated = creator.aggregate_confidence(self.FOLD_PREDICTIONS,
                                                  target_scale=self.TARGET_SCALE)

        # variability = std(ensemble)/target_scale = 0.4330127018922193 / 2
        variability = 0.21650635094610965
        agreement = np.array([1.0, 1.0, 1.0 - 0.408248290463863, 1.0])
        np.testing.assert_array_almost_equal(aggregated, agreement * variability,
                                             decimal=12)

        assert np.all(aggregated >= 0.0) and np.all(aggregated <= 1.0)
        # Where the folds disagree, confidence drops. This is the ordering the whole
        # method exists to produce, and the pre-2026-09-06 implementation could not
        # produce it at all: it was fed identical per-model constants.
        assert aggregated[2] < aggregated[0]
        assert aggregated[2] < aggregated[3]

    def test_aggregate_confidence_is_not_constant_when_folds_disagree(self):
        """The exact defect Step 3 removes: a confidence map with no variation.

        A percentile threshold is invariant to multiplication by a positive constant,
        so a constant confidence changes nothing about which regions are selected
        downstream -- it is not a weak signal, it is no signal. Asserting the map varies
        is therefore asserting that confidence participates in region selection at all.
        """
        creator = GridCreator(confidence_method="cv_ensemble")

        aggregated = creator.aggregate_confidence(self.FOLD_PREDICTIONS,
                                                  target_scale=self.TARGET_SCALE)

        assert np.std(aggregated) > 0.0, (
            "confidence is constant across the grid; every percentile threshold "
            "downstream will select exactly what it would have selected with no "
            "confidence at all"
        )

    def test_aggregate_confidence_collapses_on_constant_models(self):
        """Models that ignore the coordinates must not read as confident.

        Every fold returning the same number agrees with itself perfectly, so the
        agreement factor alone is 1.0 everywhere -- the most degenerate possible model
        scoring the maximum. The variability factor is what makes this report 0.
        """
        constant_folds = np.full((3, 4), 7.0)

        cv = GridCreator(confidence_method="cv_ensemble")
        np.testing.assert_array_almost_equal(
            cv.aggregate_confidence(constant_folds, target_scale=self.TARGET_SCALE),
            np.zeros(4), decimal=12
        )

        # And the demonstration that agreement alone cannot see it:
        five = GridCreator(confidence_method="5_model")
        np.testing.assert_array_almost_equal(
            five.aggregate_confidence(constant_folds, target_scale=self.TARGET_SCALE),
            np.ones(4), decimal=12
        )

    def test_aggregate_confidence_invalid_inputs(self):
        """Test confidence aggregation with invalid inputs."""
        creator = GridCreator()

        # Empty array
        with pytest.raises(ValueError, match="model_predictions array is empty"):
            creator.aggregate_confidence(np.array([]), target_scale=1.0)

        # Wrong dimensions
        with pytest.raises(ValueError, match="model_predictions must be 2D array"):
            creator.aggregate_confidence(np.array([0.5, 0.6, 0.7]), target_scale=1.0)

        # A scale of zero would make every ratio infinite; refuse rather than clip it
        # to 1 and report a confidence of 0 that looks like a measurement.
        for bad_scale in (0.0, -1.0, np.nan):
            with pytest.raises(ValueError, match="target_scale must be finite and positive"):
                creator.aggregate_confidence(self.FOLD_PREDICTIONS, target_scale=bad_scale)

    def test_target_scale_refuses_a_constant_target(self):
        """A constant target has no scale, so no confidence can be expressed against it."""
        with pytest.raises(ValueError, match="is constant"):
            GridCreator._target_scale(np.full(20, 3.5), "target_0")

        with pytest.raises(ValueError, match="is empty"):
            GridCreator._target_scale(np.array([]), "target_0")

        assert GridCreator._target_scale(np.array([0.0, 2.0]), "target_0") == 1.0


    def test_simplified_inference_basic(self):
        """Test basic simplified inference functionality."""
        creator = GridCreator()
        
        # Two folds for score_0 that DISAGREE, and by a different amount at each grid
        # point. Two identical mocks (what this test used before 2026-09-06) give a
        # cross-model spread of exactly zero everywhere, which is the degenerate input
        # the old implementation could not distinguish from a well determined surface.
        class MockModel:
            def __init__(self, slope=0.5):
                self.slope = slope

            def predict(self, X):
                return np.sum(X, axis=1) * self.slope

        class MockDivergingModel:
            """Agrees with MockModel(0.5) at the origin and diverges outward."""
            def predict(self, X):
                return np.sum(X, axis=1) * 0.5 + np.sum(X, axis=1) ** 2

        trained_models = {
            'prediction_models': [
                {'model': MockModel(), 'target': 'score_0'},
                {'model': MockDivergingModel(), 'target': 'score_0'},
                {'model': MockModel(), 'target': 'score_1'},  # Different target
            ]
        }

        # Test grid coordinates, ordered by increasing distance from the origin
        grid_coords = np.array([[0.1, 0.2], [0.5, 0.5], [0.8, 0.9]])
        target_scores = np.array([0.0, 0.5, 1.0, 1.5, 2.0])  # SD 0.7071...

        predictions, confidences = creator.simplified_inference(
            grid_coords, trained_models, 'score_0', target_scores
        )

        # Check output shapes
        assert predictions.shape == (3,)
        assert confidences.shape == (3,)

        # Check value ranges
        assert np.all(confidences >= 0.0)
        assert np.all(confidences <= 1.0)

        # Ensemble of the two score_0 models: mean of 0.5*s and 0.5*s + s**2
        s = np.sum(grid_coords, axis=1)
        np.testing.assert_array_almost_equal(predictions, 0.5 * s + 0.5 * s ** 2,
                                             decimal=10)

        # Confidence falls where the folds diverge. Both the ordering and the fact that
        # the map varies at all are new in Step 3; this previously returned 1.0 at every
        # point regardless of the models.
        assert np.std(confidences) > 0.0
        assert confidences[0] > confidences[1] > confidences[2]


    def test_simplified_inference_no_models(self):
        """Test simplified inference with no models."""
        creator = GridCreator()
        
        # Empty trained_models
        trained_models = {'prediction_models': []}
        grid_coords = np.array([[0.1, 0.2]])
        
        with pytest.raises(ValueError, match="No prediction models found"):
            creator.simplified_inference(grid_coords, trained_models, 'score_0',
                                         np.array([0.0, 1.0]))
    
    def test_simplified_inference_no_target_models(self):
        """Test simplified inference when no models match target."""
        creator = GridCreator()
        
        class MockModel:
            def predict(self, X):
                return np.zeros(len(X))
        
        trained_models = {
            'prediction_models': [
                {'model': MockModel(), 'target': 'different_target'}
            ]
        }
        
        grid_coords = np.array([[0.1, 0.2]])
        
        with pytest.raises(ValueError, match="No models found for target 'score_0'"):
            creator.simplified_inference(grid_coords, trained_models, 'score_0',
                                         np.array([0.0, 1.0]))

    def test_simplified_inference_regression_model(self):
        """A regression model with a single fold: predictions real, agreement vacuous.

        This test used to assert `confidences == 0.8` -- the literal constant the old
        implementation assigned to any model without `predict_proba`, which then flowed
        through `aggregate_confidence` unchanged. That number came from nowhere and
        measured nothing. With one fold there genuinely is no cross-model agreement to
        measure, so what is asserted now is that the code says so (agreement 1.0 by
        construction) rather than inventing a value.
        """
        creator = GridCreator(confidence_method="5_model")

        class MockRegressionModel:
            def predict(self, X):
                return np.sum(X, axis=1)  # Simple sum

            # Explicitly exclude predict_proba to ensure regression path
            def score(self, X, y):
                return 1.0

        trained_models = {
            'prediction_models': [
                {'model': MockRegressionModel(), 'target': 'score_0'}
            ]
        }

        grid_coords = np.array([[0.1, 0.2], [0.3, 0.4]])
        target_scores = np.array([0.0, 0.5, 1.0])

        predictions, confidences = creator.simplified_inference(
            grid_coords, trained_models, 'score_0', target_scores
        )

        # One model => spread 0 at every point => agreement 1.0. Vacuous, and logged as
        # such by aggregate_confidence, but not a fabricated constant.
        np.testing.assert_array_almost_equal(confidences, np.ones(2), decimal=12)

        # Check predictions
        expected = np.array([0.3, 0.7])  # sum of coordinates
        np.testing.assert_array_almost_equal(predictions, expected)


class TestGridCreatorHeatmaps:
    """Test GridCreator main heatmap creation functionality."""
    
    def test_create_prediction_heatmaps_basic(self):
        """Test basic prediction heatmap creation."""
        import tempfile
        
        creator = GridCreator(grid_size=10, confidence_method="5_model")  # Smaller grid for testing
        
        # Mock models and data
        class MockModel:
            def predict(self, X):
                return np.sum(X, axis=1) * 2.0  # Simple prediction
            
            def predict_proba(self, X):
                pred = self.predict(X)
                p1 = 1 / (1 + np.exp(-pred))
                return np.column_stack([1-p1, p1])
        
        trained_models = {
            'prediction_models': [
                {'model': MockModel(), 'target': 'score_0'},
                {'model': MockModel(), 'target': 'score_1'},
            ],
            'scores_scaler': None,  # No scaler for this test
            'metadata': {}
        }
        
        # Sample data
        embeddings = np.random.uniform(0, 1, (20, 2))
        target_data = {
            'score_0': np.random.uniform(10, 50, 20),
            'score_1': np.random.uniform(0, 1, 20)
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            results = creator.create_prediction_heatmaps(
                embeddings=embeddings,
                trained_models=trained_models,
                target_data=target_data,
                output_folder=temp_dir,
                denormalize=False  # No denormalization for this test
            )
            
            # Check results structure
            assert 'heatmap_results' in results
            assert 'grid_metadata' in results
            assert len(results['heatmap_results']) == 2
            
            # Check each target
            for target_name in ['score_0', 'score_1']:
                target_result = results['heatmap_results'][target_name]
                assert 'target_name' in target_result
                assert 'artifacts' in target_result
                assert 'prediction_range' in target_result
                assert 'confidence_range' in target_result
                assert 'corrected_range' in target_result
                assert target_result['combination'] == 'shrink_to_null'
                assert 'null_level' in target_result
                
                # Check artifacts exist
                artifacts = target_result['artifacts']
                for artifact_path in artifacts.values():
                    assert Path(artifact_path).exists()
    
    def test_create_prediction_heatmaps_with_denormalization(self):
        """Test prediction heatmap creation with denormalization."""
        import tempfile
        from unittest.mock import Mock
        
        creator = GridCreator(grid_size=5, confidence_method="cv_ensemble")
        
        # Mock model
        class MockModel:
            def predict(self, X):
                return np.sum(X, axis=1)  # Normalized predictions
        
        # Mock scaler
        mock_scaler = Mock()
        mock_scaler.inverse_transform.return_value = np.array([[10.0], [20.0], [30.0]])  # Denormalized values
        
        trained_models = {
            'prediction_models': [
                {'model': MockModel(), 'target': 'score_0'},
            ],
            'scores_scaler': {'score': mock_scaler},
            'metadata': {'scores_normalization_method': 'robust'}
        }
        
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        target_data = {'score_0': np.array([10.0, 20.0, 30.0])}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the pandas DataFrame operations for denormalization
            with pytest.MonkeyPatch.context() as m:
                # This test focuses on the structure, denormalization details tested separately
                results = creator.create_prediction_heatmaps(
                    embeddings=embeddings,
                    trained_models=trained_models,
                    target_data=target_data,
                    output_folder=temp_dir,
                    denormalize=True
                )
                
                # Check basic structure
                assert 'heatmap_results' in results
                assert 'score_0' in results['heatmap_results']
                target_result = results['heatmap_results']['score_0']
                
                # Should have all required artifacts
                assert 'artifacts' in target_result
                assert len(target_result['artifacts']) >= 4  # prediction, confidence, corrected, coords
    
    def test_create_prediction_heatmaps_no_models_for_target(self):
        """Test heatmap creation when no models exist for a target."""
        import tempfile
        
        creator = GridCreator(grid_size=5)
        
        trained_models = {
            'prediction_models': [
                {'model': Mock(), 'target': 'different_target'}
            ]
        }
        
        # Two distinct points, not one. This test is about the missing-model path, and
        # a single sample gives the grid no extent -- which is now refused up front, so
        # the run would fail before reaching the behaviour under test. The degeneracy
        # was incidental scaffolding, never the subject.
        embeddings = np.array([[0.1, 0.2], [0.8, 0.9]])
        target_data = {'score_0': np.array([1.0, 2.0])}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            results = creator.create_prediction_heatmaps(
                embeddings=embeddings,
                trained_models=trained_models,
                target_data=target_data,
                output_folder=temp_dir
            )
            
            # Should have error for the target
            assert 'score_0' in results['heatmap_results']
            assert 'error' in results['heatmap_results']['score_0']
    
    def test_create_prediction_heatmaps_file_structure(self):
        """Test that the correct file structure is created."""
        import tempfile
        
        creator = GridCreator(grid_size=3)
        
        class MockModel:
            def predict(self, X):
                return np.ones(len(X)) * 0.5
        
        trained_models = {
            'prediction_models': [
                {'model': MockModel(), 'target': 'cognitive_flexibility'}
            ]
        }
        
        embeddings = np.array([[0.2, 0.3], [0.7, 0.8]])
        target_data = {'cognitive_flexibility': np.array([100.0, 200.0])}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            results = creator.create_prediction_heatmaps(
                embeddings=embeddings,
                trained_models=trained_models,
                target_data=target_data,
                output_folder=temp_dir
            )
            
            # Check directory structure
            target_dir = Path(temp_dir) / "target_cognitive_flexibility" / "prediction-heatmaps"
            assert target_dir.exists()
            
            # Check expected files
            expected_files = [
                "prediction_values.npy",
                "confidence_values.npy", 
                "corrected_values.npy",
                "grid_coordinates.npy",
                "prediction_metadata.json"
            ]
            
            for filename in expected_files:
                assert (target_dir / filename).exists(), f"Missing file: {filename}"
            
            # Check metadata file content
            metadata_path = target_dir / "prediction_metadata.json"
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            assert metadata['target_name'] == 'cognitive_flexibility'
            assert metadata['grid_size'] == 3
            assert 'prediction_range' in metadata
            assert 'artifacts' in metadata

class TestShrinkageTowardTheNull:
    """How confidence enters the prediction map.

    The map used to be ``predictions * confidence``. That is shrinkage toward *zero*, and
    zero is the null only for a centred quantity. It is now
    ``null + confidence * (prediction - null)`` with the null set to the training target's
    mean. These tests pin the property that distinguishes the two, because the difference
    is invisible on any target that happens to straddle zero.

    Measured on swiss_roll (2026-09-07), for the record: under multiplication the bottom-5%
    grid cells were *entirely* replaced (500 added, 500 removed) and the cells pulled in had
    mean confidence 0.06 -- the "low prediction" region was the low-*confidence* region.
    Under shrinkage 377 of 500 cells stayed, and the 123 that entered had mean confidence
    0.79, above the 0.63 average.
    """

    GRID_SIZE = 10
    N_GRID = GRID_SIZE ** 2

    class _Ramp:
        """A model whose prediction increases across the grid, so tails exist to fall into."""

        def __init__(self, offset):
            self.offset = offset

        def predict(self, X):
            return self.offset + 5.0 * np.sum(X, axis=1)

    @staticmethod
    def _models(offset):
        return {
            'prediction_models': [{'model': TestShrinkageTowardTheNull._Ramp(offset),
                                   'target': 'score'}],
            'scores_scaler': None,
            'metadata': {},
        }

    @staticmethod
    def _run(tmp_path, offset, scores, confidence_pattern, monkeypatch):
        monkeypatch.setattr(
            GridCreator, "aggregate_confidence",
            lambda self, model_predictions, target_scale: confidence_pattern,
        )
        creator = GridCreator(grid_size=TestShrinkageTowardTheNull.GRID_SIZE,
                              confidence_method="5_model")
        creator.create_prediction_heatmaps(
            embeddings=np.linspace(0.0, 1.0, 21 * 2).reshape(21, 2),
            trained_models=TestShrinkageTowardTheNull._models(offset),
            target_data={'score': scores},
            output_folder=str(tmp_path),
            denormalize=False,
        )
        d = Path(tmp_path) / "target_score" / "prediction-heatmaps"
        return (np.load(d / "prediction_values.npy"),
                np.load(d / "corrected_values.npy"),
                json.loads((d / "prediction_metadata.json").read_text()))

    @pytest.mark.parametrize("offset,scores,null", [
        # A 0-1-style target read as "0 = worst": the sign case that motivated this. Under
        # multiplication an untrusted point lands at 0, i.e. maximally low.
        (5.0, np.linspace(5.0, 15.0, 21), 10.0),
        # The same shape reflected. Under multiplication the identical untrusted point lands
        # at 0, which here is maximally *high* -- the operation's answer depends on which
        # side of zero the target happens to sit, which is what makes it wrong rather than
        # merely noisy.
        (-15.0, np.linspace(-15.0, -5.0, 21), -10.0),
    ], ids=["positive_target", "negative_target"])
    def test_a_zero_confidence_point_lands_on_the_null_whatever_the_sign(
            self, tmp_path, monkeypatch, offset, scores, null):
        untrusted = np.zeros(self.N_GRID)
        untrusted[::2] = 1.0  # half trusted, half not, so both tails still have occupants

        predictions, corrected, metadata = self._run(
            tmp_path, offset, scores, untrusted, monkeypatch)

        assert metadata['null_level'] == pytest.approx(null)
        zero_conf = untrusted == 0.0
        np.testing.assert_allclose(corrected[zero_conf], null)

        # And the property that actually matters downstream: an untrusted point is in
        # neither tail of the corrected map, on either sign. Under `predictions * confidence`
        # every one of them would sit at 0.0 and therefore in one tail or the other.
        assert corrected[zero_conf].min() > np.percentile(corrected, 5)
        assert corrected[zero_conf].max() < np.percentile(corrected, 95)
        old_way = predictions * untrusted
        assert (old_way[zero_conf] <= np.percentile(old_way, 5)).all() or \
               (old_way[zero_conf] >= np.percentile(old_way, 95)).all()

    def test_full_confidence_leaves_the_map_exactly_alone(self, tmp_path, monkeypatch):
        """The control the swiss_roll measurement rested on, pinned so it stays true.

        With confidence 1 everywhere the correction must be the identity -- otherwise a
        before/after comparison is measuring the correction plus an unrelated shift.
        """
        predictions, corrected, _ = self._run(
            tmp_path, 5.0, np.linspace(5.0, 15.0, 21), np.ones(self.N_GRID), monkeypatch)

        np.testing.assert_array_equal(corrected, predictions)

    def test_null_is_pushed_through_the_same_transform_as_the_predictions(self):
        """A null in different units from the map it corrects is silent nonsense.

        ``target_scores`` lives in the space the models were fitted on; the map has been
        denormalized when a scores scaler exists. If the transform cannot be applied to the
        null too, the only honest move is to refuse -- returning the model-space mean would
        subtract one unit from another and produce a plausible-looking map.
        """
        creator = GridCreator(grid_size=5)
        creator._denormalize_predictions = lambda values, target, models: (None, False)

        with pytest.raises(RuntimeError, match="different units"):
            creator._null_level(np.linspace(0.0, 1.0, 10), 'score', {}, True)

    def test_a_unit_mismatch_stops_the_run_rather_than_the_target(self, tmp_path, monkeypatch):
        """The refusal has to escape the per-target handler, or it is only a log line.

        ``create_prediction_heatmaps`` catches Exception per target so one target with no
        usable models does not take the others down. That is right for "cannot compute" --
        the target gets no map and the absence is visible. It is wrong for "would compute
        the wrong thing": recorded as ``{'error': ...}`` the run reports success, and the
        next run writes the same wrong map. Hence HeatmapIntegrityError is re-raised.
        """
        creator = GridCreator(grid_size=self.GRID_SIZE, confidence_method="5_model")
        monkeypatch.setattr(
            GridCreator, "aggregate_confidence",
            lambda self, model_predictions, target_scale: np.ones(self.grid_size ** 2),
        )
        # Denormalization succeeds for the grid, fails for the single null value -- the
        # asymmetry that makes the two arrays end up in different units.
        monkeypatch.setattr(
            GridCreator, "_denormalize_predictions",
            lambda self, values, target, models: (
                (values, True) if np.size(values) > 1 else (None, False)
            ),
        )

        with pytest.raises(HeatmapIntegrityError, match="different units"):
            creator.create_prediction_heatmaps(
                embeddings=np.linspace(0.0, 1.0, 21 * 2).reshape(21, 2),
                trained_models=self._models(5.0),
                target_data={'score': np.linspace(5.0, 15.0, 21)},
                output_folder=str(tmp_path),
                denormalize=True,
            )

    def test_a_target_that_simply_cannot_be_mapped_is_still_skipped(self, tmp_path):
        """The counterpart, so the re-raise above does not quietly widen into everything.

        A constant target has no scale to measure confidence against. That is "cannot
        compute", not "would be wrong", and it must stay a per-target skip.
        """
        creator = GridCreator(grid_size=self.GRID_SIZE, confidence_method="5_model")

        results = creator.create_prediction_heatmaps(
            embeddings=np.linspace(0.0, 1.0, 21 * 2).reshape(21, 2),
            trained_models=self._models(5.0),
            target_data={'score': np.full(21, 7.0)},
            output_folder=str(tmp_path),
            denormalize=False,
        )

        assert 'error' in results['heatmap_results']['score']

    def test_null_level_refuses_an_empty_target(self):
        creator = GridCreator(grid_size=5)
        with pytest.raises(ValueError, match="is empty"):
            creator._null_level(np.array([]), 'score', {}, False)
