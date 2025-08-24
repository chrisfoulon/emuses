"""
Test pipeline component extraction for feature transformation reproducibility.

Tests that InferenceStage can correctly extract and use sklearn Pipeline components
to apply model-specific feature transformations during inference.
"""
import numpy as np
import pytest
from unittest.mock import Mock
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import FeatureUnion

from emuses.pipelines.inference_stage import InferenceStage
from emuses.tools.features_utils import RawCoords, GWD, PCAGWD


class TestPipelineComponentExtraction:
    """Test pipeline component extraction and feature processing."""

    def test_pipeline_detection_sklearn_pipeline(self):
        """
        Test detection of sklearn Pipeline vs other model types.
        
        This validates the _is_sklearn_pipeline() method can distinguish
        between Pipeline objects and other model formats.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create a mock sklearn Pipeline
        pipeline = Pipeline([
            ("feat", FeatureUnion([("raw", RawCoords())])),
            ("est", RandomForestRegressor())
        ])
        
        # Create non-pipeline objects
        simple_model = RandomForestRegressor()
        string_object = "not_a_pipeline"
        dict_object = {"model": "fake"}
        
        # Act & Assert
        assert stage._is_sklearn_pipeline(pipeline) is True
        assert stage._is_sklearn_pipeline(simple_model) is False
        assert stage._is_sklearn_pipeline(string_object) is False
        assert stage._is_sklearn_pipeline(dict_object) is False
        assert stage._is_sklearn_pipeline(None) is False

    def test_pipeline_component_extraction_success(self):
        """
        Test successful extraction of 'feat' and 'est' components from Pipeline.
        
        Validates the _extract_pipeline_components() method can safely extract
        the feature transformer and estimator from a well-formed pipeline.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create a complete sklearn Pipeline with fitted components
        raw_coords = np.random.rand(10, 2)
        labels = np.random.rand(10)
        
        feature_union = FeatureUnion([
            ("raw", RawCoords()),
            ("gwd", GWD(sigma=0.1))
        ])
        estimator = RandomForestRegressor(n_estimators=5, random_state=42)
        
        pipeline = Pipeline([
            ("feat", feature_union),
            ("est", estimator)
        ])
        pipeline.fit(raw_coords, labels)
        
        # Act
        feature_transformer, extracted_estimator = stage._extract_pipeline_components(pipeline)
        
        # Assert
        assert feature_transformer is not None
        assert extracted_estimator is not None
        assert feature_transformer is pipeline.named_steps["feat"]
        assert extracted_estimator is pipeline.named_steps["est"]

    def test_pipeline_component_extraction_missing_components(self):
        """
        Test graceful handling of malformed pipelines missing expected components.
        
        Should return None for missing components and log appropriate warnings.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create pipeline with non-standard component names
        pipeline_wrong_names = Pipeline([
            ("features", FeatureUnion([("raw", RawCoords())])),  # Wrong name
            ("model", RandomForestRegressor())                   # Wrong name
        ])
        
        # Create pipeline with missing estimator
        pipeline_missing_est = Pipeline([
            ("feat", FeatureUnion([("raw", RawCoords())]))
            # Missing "est" component
        ])
        
        # Act & Assert - should handle gracefully
        feat1, est1 = stage._extract_pipeline_components(pipeline_wrong_names)
        assert feat1 is None
        assert est1 is None
        
        feat2, est2 = stage._extract_pipeline_components(pipeline_missing_est)
        assert feat2 is not None  # "feat" exists
        assert est2 is None       # "est" missing

    def test_shape_mismatch_reproduction(self):
        """
        Test reproduction of the original shape mismatch error.
        
        Creates models with different feat_types that would cause
        concatenation errors in ensemble prediction.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        stage = InferenceStage(config)
        
        # Create models that produce different output shapes
        raw_coords = np.random.rand(5, 2)
        labels = np.random.rand(5)
        
        # Model A: raw_only (2D input → 1D output)  
        pipeline_raw = Pipeline([
            ("feat", FeatureUnion([("raw", RawCoords())])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline_raw.fit(raw_coords, labels)
        
        # Model B: GWD features (2D input → ~214D features → 1D output)
        pipeline_gwd = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("gwd", GWD(sigma=0.1))  # Creates ~N features where N=training samples
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline_gwd.fit(raw_coords, labels)
        
        # Create prediction models list (simulating loaded models)
        prediction_models = [
            {"model": pipeline_raw, "model_name": "raw_model", "model_score": 0.8},
            {"model": pipeline_gwd, "model_name": "gwd_model", "model_score": 0.9}
        ]
        
        models_dict = {"prediction_models": prediction_models}
        
        # Test data (different from training to simulate inference)
        test_coords = np.random.rand(3, 2)
        
        # This should reproduce the concatenation error with current implementation
        # but will be fixed by our pipeline component extraction approach
        try:
            results = stage._predict(test_coords, models_dict)
            # If this succeeds, our implementation is working
            assert results is not None
            assert "ensemble_predictions" in results
            # All predictions should have consistent shape for ensemble
            ensemble_pred = results["ensemble_predictions"]
            assert isinstance(ensemble_pred, np.ndarray)
            assert len(ensemble_pred) == 3  # Same as test samples
        except ValueError as e:
            if "concatenation axis" in str(e) or "dimensions except for" in str(e):
                pytest.fail("Pipeline component extraction should prevent shape mismatch errors")
            else:
                raise  # Re-raise if it's a different error

    def test_per_model_feature_processing(self):
        """
        Test that each model receives its expected feature representation.
        
        Validates that models trained on different feat_types get the correct
        transformed features during inference.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Training data
        train_coords = np.random.rand(8, 2)
        labels = np.random.rand(8)
        
        # Create pipeline with PCA features (different from raw)
        pipeline_pca = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("pca", PCAGWD(sigma=0.1, n_comp=3))  # 3 PCA components
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline_pca.fit(train_coords, labels)
        
        # Test the component extraction and feature processing
        feature_transformer, estimator = stage._extract_pipeline_components(pipeline_pca)
        
        # Test data
        test_coords = np.random.rand(3, 2)
        
        # Apply feature transformation
        transformed_features = feature_transformer.transform(test_coords)
        
        # Verify shape is as expected (raw coords + PCA components)
        expected_features = 2 + 3  # 2 raw coords + 3 PCA components
        assert transformed_features.shape == (3, expected_features)
        
        # Verify estimator can predict on transformed features
        predictions = estimator.predict(transformed_features)
        assert predictions.shape == (3,)  # One prediction per test sample

    def test_backward_compatibility_non_pipeline_models(self):
        """
        Test backward compatibility with non-pipeline model formats.
        
        Ensures that legacy models (non-sklearn Pipeline) are handled gracefully
        and still produce predictions correctly.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        stage = InferenceStage(config)
        
        # Create non-pipeline models (legacy format)
        train_coords = np.random.rand(8, 2)
        labels = np.random.rand(8)
        
        legacy_model = RandomForestRegressor(n_estimators=5, random_state=42)
        legacy_model.fit(train_coords, labels)
        
        # Create models list with mixed formats
        prediction_models = [
            # Legacy non-pipeline model
            {"model": legacy_model, "model_name": "legacy_model", "model_score": 0.7},
            # Modern pipeline model  
            {"model": Pipeline([
                ("feat", FeatureUnion([("raw", RawCoords())])),
                ("est", RandomForestRegressor(n_estimators=5, random_state=43))
            ]).fit(train_coords, labels), "model_name": "pipeline_model", "model_score": 0.8}
        ]
        
        models_dict = {"prediction_models": prediction_models}
        
        # Test data
        test_coords = np.random.rand(3, 2)
        
        # Act - should handle both model types gracefully
        results = stage._predict(test_coords, models_dict)
        
        # Assert
        assert results is not None
        assert "individual_predictions" in results
        assert "ensemble_predictions" in results
        
        # Both models should produce predictions
        individual_preds = results["individual_predictions"] 
        assert "legacy_model" in individual_preds
        assert "pipeline_model" in individual_preds
        
        # All predictions should have same shape for ensemble
        legacy_pred = individual_preds["legacy_model"]
        pipeline_pred = individual_preds["pipeline_model"]
        assert legacy_pred.shape == pipeline_pred.shape == (3,)
        
        # Ensemble prediction should work
        ensemble_pred = results["ensemble_predictions"]
        assert ensemble_pred.shape == (3,)