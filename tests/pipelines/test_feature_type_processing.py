"""
Test feature type processing for all supported feat_types.

Tests that InferenceStage correctly processes models trained with different
feature types (raw_only, gwd, pca_gwd, kpca_gwd) through pipeline component extraction.
"""
import numpy as np
import pytest
from unittest.mock import Mock
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.ensemble import RandomForestRegressor

from emuses.pipelines.inference_stage import InferenceStage
from emuses.tools.features_utils import RawCoords, GWD, PCAGWD, KernelPCAGWD


class TestFeatureTypeProcessing:
    """Test processing of all supported feature types."""

    def test_raw_only_feature_type(self):
        """
        Test feat_type="raw_only" processing.
        
        Validates that models trained on raw coordinates only receive
        the expected 2D input during inference.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Training data
        train_coords = np.random.rand(10, 2)
        labels = np.random.rand(10)
        
        # Create pipeline with raw_only features
        pipeline_raw = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords())  # Only raw coordinates, no augmentation
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline_raw.fit(train_coords, labels)
        
        # Test component extraction and processing
        feature_transformer, estimator = stage._extract_pipeline_components(pipeline_raw)
        
        # Test data
        test_coords = np.random.rand(5, 2)
        
        # Apply feature transformation
        transformed_features = feature_transformer.transform(test_coords)
        
        # Assert raw_only should produce 2D output (passthrough)
        assert transformed_features.shape == (5, 2)
        
        # Verify estimator can predict
        predictions = estimator.predict(transformed_features)
        assert predictions.shape == (5,)

    def test_gwd_feature_type(self):
        """
        Test feat_type="gwd" processing.
        
        Validates that models trained with Gaussian Weighted Distance features
        receive the expected augmented input during inference.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Training data  
        train_coords = np.random.rand(8, 2)
        labels = np.random.rand(8)
        
        # Create pipeline with GWD features
        pipeline_gwd = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("gwd", GWD(sigma=0.1))  # Adds ~N features where N=training samples
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline_gwd.fit(train_coords, labels)
        
        # Test component extraction
        feature_transformer, estimator = stage._extract_pipeline_components(pipeline_gwd)
        
        # Test data
        test_coords = np.random.rand(3, 2)
        
        # Apply feature transformation
        transformed_features = feature_transformer.transform(test_coords)
        
        # Assert GWD should produce 2 + N features (raw + GWD distances)
        # Where N is number of training samples
        expected_features = 2 + len(train_coords)  # 2 raw + 8 GWD features
        assert transformed_features.shape == (3, expected_features)
        
        # Verify estimator can predict
        predictions = estimator.predict(transformed_features)
        assert predictions.shape == (3,)

    def test_pca_gwd_feature_type(self):
        """
        Test feat_type="pca_gwd" processing.
        
        Validates that models trained with PCA-reduced GWD features
        receive the expected PCA-transformed input during inference.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Training data
        train_coords = np.random.rand(12, 2)  # Need enough samples for PCA
        labels = np.random.rand(12)
        
        # Create pipeline with PCA-GWD features
        n_pca_components = 5
        pipeline_pca = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("pca", PCAGWD(sigma=0.1, n_comp=n_pca_components))
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline_pca.fit(train_coords, labels)
        
        # Test component extraction
        feature_transformer, estimator = stage._extract_pipeline_components(pipeline_pca)
        
        # Test data
        test_coords = np.random.rand(4, 2)
        
        # Apply feature transformation
        transformed_features = feature_transformer.transform(test_coords)
        
        # Assert PCA-GWD should produce 2 + n_comp features (raw + PCA components)
        expected_features = 2 + n_pca_components
        assert transformed_features.shape == (4, expected_features)
        
        # Verify estimator can predict
        predictions = estimator.predict(transformed_features)
        assert predictions.shape == (4,)

    def test_kpca_gwd_feature_type(self):
        """
        Test feat_type="kpca_gwd" processing.
        
        Validates that models trained with Kernel PCA-reduced GWD features
        receive the expected KPCA-transformed input during inference.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Training data
        train_coords = np.random.rand(10, 2)
        labels = np.random.rand(10)
        
        # Create pipeline with Kernel PCA-GWD features
        n_kpca_components = 4
        pipeline_kpca = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("kpca", KernelPCAGWD(sigma=0.1, n_comp=n_kpca_components))
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline_kpca.fit(train_coords, labels)
        
        # Test component extraction
        feature_transformer, estimator = stage._extract_pipeline_components(pipeline_kpca)
        
        # Test data
        test_coords = np.random.rand(3, 2)
        
        # Apply feature transformation
        transformed_features = feature_transformer.transform(test_coords)
        
        # Assert KPCA-GWD should produce 2 + n_comp features (raw + KPCA components)
        expected_features = 2 + n_kpca_components
        assert transformed_features.shape == (3, expected_features)
        
        # Verify estimator can predict
        predictions = estimator.predict(transformed_features)
        assert predictions.shape == (3,)

    def test_mixed_feature_type_ensemble(self):
        """
        Test ensemble with mixed feature types.
        
        Validates that models with different feat_types can be combined
        in an ensemble without shape mismatch errors.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        stage = InferenceStage(config)
        
        # Training data
        train_coords = np.random.rand(8, 2)
        labels = np.random.rand(8)
        
        # Create models with different feature types
        models = []
        
        # Model 1: raw_only
        pipeline_raw = Pipeline([
            ("feat", FeatureUnion([("raw", RawCoords())])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=41))
        ])
        pipeline_raw.fit(train_coords, labels)
        models.append({"model": pipeline_raw, "model_name": "raw_model", "score": 0.8})
        
        # Model 2: GWD features
        pipeline_gwd = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("gwd", GWD(sigma=0.1))
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline_gwd.fit(train_coords, labels)
        models.append({"model": pipeline_gwd, "model_name": "gwd_model", "score": 0.9})
        
        # Model 3: PCA features
        pipeline_pca = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("pca", PCAGWD(sigma=0.1, n_comp=3))
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=43))
        ])
        pipeline_pca.fit(train_coords, labels)
        models.append({"model": pipeline_pca, "model_name": "pca_model", "score": 0.85})
        
        models_dict = {"prediction_models": models}
        
        # Test data
        test_coords = np.random.rand(5, 2)
        
        # Act - should work without shape mismatch errors
        results = stage._predict(test_coords, models_dict)
        
        # Assert
        assert results is not None
        assert "individual_predictions" in results
        assert "ensemble_predictions" in results
        
        # All models should produce predictions
        individual_preds = results["individual_predictions"]
        assert "raw_model" in individual_preds
        assert "gwd_model" in individual_preds 
        assert "pca_model" in individual_preds
        
        # All predictions should have consistent shape for ensemble
        for model_name, predictions in individual_preds.items():
            assert predictions.shape == (5,), f"Model {model_name} has wrong shape: {predictions.shape}"
        
        # Ensemble prediction should work
        ensemble_pred = results["ensemble_predictions"]
        assert ensemble_pred.shape == (5,)
        
        # Should have correct model count and names
        assert results["model_count"] == 3
        assert len(results["model_names"]) == 3

    def test_feature_consistency_across_inference_calls(self):
        """
        Test that the same model produces consistent features across multiple calls.
        
        Validates that fitted feature transformers produce deterministic results.
        """
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Training data
        train_coords = np.random.rand(6, 2)
        labels = np.random.rand(6)
        
        # Create pipeline with GWD features
        pipeline = Pipeline([
            ("feat", FeatureUnion([
                ("raw", RawCoords()),
                ("gwd", GWD(sigma=0.1))
            ])),
            ("est", RandomForestRegressor(n_estimators=5, random_state=42))
        ])
        pipeline.fit(train_coords, labels)
        
        # Extract components
        feature_transformer, estimator = stage._extract_pipeline_components(pipeline)
        
        # Test data
        test_coords = np.random.rand(3, 2)
        
        # Apply transformation multiple times
        features1 = feature_transformer.transform(test_coords)
        features2 = feature_transformer.transform(test_coords)
        
        # Assert results are identical (deterministic)
        np.testing.assert_array_equal(features1, features2)
        
        # Predictions should also be identical
        pred1 = estimator.predict(features1)
        pred2 = estimator.predict(features2)
        np.testing.assert_array_equal(pred1, pred2)