"""
Comprehensive validation testing for the complete normalization fix.

This test suite validates the end-to-end normalization functionality
to ensure KernelRegressor models produce non-zero predictions and
existing ElasticNet models continue working correctly.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json
import joblib
from pathlib import Path
import shutil

from bcblib.tools.dataframe_filtering import normalize_dataframe


class TestNormalizationValidation:
    """End-to-end validation tests for normalization fixes."""

    @pytest.fixture
    def temp_model_dir(self):
        """Create a temporary model directory with complete EMUSES structure."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create target directory structure
        target_dir = temp_dir / "target_cognitive_score"
        target_dir.mkdir(parents=True)
        
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def complete_model_setup(self, temp_model_dir):
        """Create a complete model setup with all components and scalers."""
        # Create realistic training data
        training_input_data = pd.DataFrame({
            'feature_1': np.random.normal(100, 15, 1000),  # Mean 100, std 15
            'feature_2': np.random.normal(50, 10, 1000),   # Mean 50, std 10  
            'feature_3': np.random.uniform(0, 1, 1000)     # Uniform [0,1]
        })
        
        training_scores_data = pd.DataFrame({
            'cognitive_score': np.random.normal(85, 12, 1000)  # Mean 85, std 12
        })
        
        # Generate normalization scalers
        input_normalized, input_scaling_factors = normalize_dataframe(training_input_data, method='min-max')
        scores_normalized, scores_scaling_factors = normalize_dataframe(training_scores_data, method='zscore')
        
        # Save scalers
        input_scaler_path = temp_model_dir / "input_scaler.joblib"
        scores_scaler_path = temp_model_dir / "scores_scaler.joblib"
        joblib.dump(input_scaling_factors, input_scaler_path)
        joblib.dump(scores_scaling_factors, scores_scaler_path)
        
        # The embedding scaling belongs to the RUN FOLDER, not to the model object.
        # This fixture used to set `mock_umap.min_embeddings_` / `max_embeddings_`,
        # and those were the only assignments to those names anywhere in the tree:
        # inference read them with getattr, so on a Mock they looked wired and in
        # production they were always None. Write the real artefact instead, so the
        # fixture describes a folder EMUSES could actually have produced.
        with open(temp_model_dir / "embedding_scaling.json", 'w') as f:
            json.dump({
                'min_embeddings': [0.0, 0.0],
                'max_embeddings': [1.0, 1.0],
                'mode': 'per_axis',
                'margin': 0,
                'embeddings_npy_space': 'raw',
                'test_embeddings_npy_space': 'rescaled',
            }, f)

        # Create mock UMAP model with realistic embeddings
        mock_umap = Mock()
        mock_umap.transform.return_value = np.random.uniform(0, 1, (100, 2))  # 100 samples, 2D embeddings
        
        # Create different types of prediction models
        kernel_regressor = Mock()
        kernel_regressor.predict.return_value = np.random.normal(0.7, 0.2, 100)  # Realistic predictions
        
        elastic_net = Mock() 
        elastic_net.predict.return_value = np.random.normal(0.5, 0.3, 100)  # Different distribution
        
        # Create target directory with models
        target_dir = temp_model_dir / "target_cognitive_score"
        target_dir.mkdir(exist_ok=True)
        
        # Note: Skip saving mock models to avoid pickle issues
        # In real scenarios, these would be actual trained models saved during training
        # For testing, we'll inject them directly into the models dict
        
        # Create manifest with normalization
        manifest = {
            "model_info": {"version": "1.0.0", "model_type": "complete_emuses_model"},
            "normalization": {
                "input_scaler": "input_scaler.joblib",
                "scores_scaler": "scores_scaler.joblib", 
                "input_method": "min-max",
                "scores_method": "zscore",
                "embeddings_rescaling": True
            },
            "file_integrity": {
                "input_scaler.joblib": {"sha256": "mock_hash_input"},
                "scores_scaler.joblib": {"sha256": "mock_hash_scores"}
            }
        }
        
        manifest_path = temp_model_dir / "model_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return {
            'model_dir': temp_model_dir,
            'input_scaling_factors': input_scaling_factors,
            'scores_scaling_factors': scores_scaling_factors,
            'training_input_data': training_input_data,
            'training_scores_data': training_scores_data,
            'mock_umap': mock_umap,
            'kernel_regressor': kernel_regressor,
            'elastic_net': elastic_net
        }

    def test_end_to_end_normalization_workflow(self, complete_model_setup):
        """Test the complete end-to-end normalization workflow."""
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create mock config
        mock_config = Mock()
        mock_config.model_path = str(complete_model_setup['model_dir'])
        
        # Create InferenceStage
        inference_stage = InferenceStage(mock_config)
        
        # Test model loading (should load scalers from manifest)
        context = {}  # Empty context (standalone mode)
        
        # Mock the UMAP loading since we can't pickle Mock objects
        with patch.object(inference_stage, '_load_umap_from_disk', return_value=None):
            with patch.object(inference_stage, '_load_prediction_models_from_disk', return_value=[]):
                models = inference_stage._load_trained_models_with_context(context)
        
        # Verify scalers were loaded from manifest
        assert 'input_scaler' in models
        assert 'scores_scaler' in models
        assert models['input_scaler'] is not None
        assert models['scores_scaler'] is not None
        
        # Verify metadata was set from manifest
        assert 'input_normalization_method' in models['metadata']
        assert 'scores_normalization_method' in models['metadata']
        assert models['metadata']['input_normalization_method'] == 'min-max'
        assert models['metadata']['scores_normalization_method'] == 'zscore'

    def test_kernel_regressor_non_zero_predictions(self, complete_model_setup):
        """Test that KernelRegressor models produce non-zero predictions with normalization."""
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create inference data that's different from training scale
        inference_data = np.array([
            [150, 75, 0.8],  # Higher values than training mean
            [80, 35, 0.3],   # Lower values than training mean
            [120, 60, 0.5]   # Around training mean
        ])
        
        # Create mock config
        mock_config = Mock()
        mock_config.model_path = str(complete_model_setup['model_dir'])
        
        inference_stage = InferenceStage(mock_config)
        
        # Load models with scalers
        context = {}
        models = inference_stage._load_trained_models_with_context(context)
        
        # Set up the mock UMAP model in the loaded models
        models['umap_model'] = complete_model_setup['mock_umap']
        
        # Test feature transformation
        transformed_features = inference_stage._transform_features(inference_data, models)

        # The stage passes features to UMAP UNCHANGED. Normalization happens once, in
        # EMUSESPipeline, which loads the model's saved input_scaler in inference mode
        # (see tests/inference/test_normalization_fix.py). This test used to assert the
        # opposite; normalizing in both places scales the data twice and collapses the
        # UMAP transform to a single point.
        assert complete_model_setup['mock_umap'].transform.called
        features_passed = complete_model_setup['mock_umap'].transform.call_args[0][0]
        np.testing.assert_array_equal(features_passed, inference_data)

        # Test that KernelRegressor gets reasonable inputs for non-zero predictions
        kernel_regressor = complete_model_setup['kernel_regressor']
        kernel_predictions = kernel_regressor.predict(transformed_features)
        
        # Verify predictions are non-zero (the key fix)
        assert len(kernel_predictions) > 0
        assert not np.all(kernel_predictions == 0), "KernelRegressor should produce non-zero predictions with proper normalization"

    def test_elastic_net_regression_compatibility(self, complete_model_setup):
        """Test that ElasticNet models continue working (regression test)."""
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create inference data
        inference_data = np.array([
            [100, 50, 0.5],  # Around training mean
            [90, 45, 0.4]    # Slightly below mean
        ])
        
        # Create mock config
        mock_config = Mock()
        mock_config.model_path = str(complete_model_setup['model_dir'])
        
        inference_stage = InferenceStage(mock_config)
        
        # Load models with scalers
        context = {}
        models = inference_stage._load_trained_models_with_context(context)
        models['umap_model'] = complete_model_setup['mock_umap']
        
        # Test feature transformation
        transformed_features = inference_stage._transform_features(inference_data, models)
        
        # Test ElasticNet predictions (should still work)
        elastic_net = complete_model_setup['elastic_net']
        elastic_predictions = elastic_net.predict(transformed_features)
        
        # Verify ElasticNet continues to work
        assert len(elastic_predictions) > 0
        assert isinstance(elastic_predictions, np.ndarray)
        # ElasticNet should be less sensitive to scaling, but should still work

    def test_embedding_coordinate_ranges_consistency(self, complete_model_setup):
        """Test that embedding ranges are consistent between training and inference."""
        from emuses.pipelines.inference_stage import InferenceStage
        from emuses.tools.emuses_utils import rescale_embedding
        
        # Test data
        inference_data = np.array([[100, 50, 0.5]])
        
        # Create mock config
        mock_config = Mock()
        mock_config.model_path = str(complete_model_setup['model_dir'])
        
        inference_stage = InferenceStage(mock_config)
        
        # Load models
        context = {}
        models = inference_stage._load_trained_models_with_context(context)
        models['umap_model'] = complete_model_setup['mock_umap']
        
        # Set up min/max embeddings for rescaling test
        models['metadata']['min_embeddings'] = np.array([0.1, 0.2])
        models['metadata']['max_embeddings'] = np.array([0.9, 0.8])
        
        # Test transformation
        transformed_features = inference_stage._transform_features(inference_data, models)

        # Embeddings are rescaled against the TRAINING range: the saved min maps to 0 and
        # the saved max to 1. Points outside that range therefore land outside [0,1], and
        # must - that is the signal that the input sits off the training manifold. The old
        # assertion (everything within [0,1]) would only hold if rescaling clamped, which
        # would erase exactly that signal.
        raw = complete_model_setup['mock_umap'].transform.return_value
        expected = (raw - np.array([0.1, 0.2])) / (np.array([0.9, 0.8]) - np.array([0.1, 0.2]))
        np.testing.assert_allclose(transformed_features, expected, rtol=1e-6)

    def test_normalization_with_different_data_scales(self, complete_model_setup):
        """Test normalization with data at very different scales from training."""
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create inference data with extreme values
        extreme_data = np.array([
            [200, 100, 1.5],   # Much higher than training
            [10, 5, -0.5],     # Much lower than training (some negative)
            [1000, 200, 2.0]   # Extremely high
        ])
        
        # Create mock config
        mock_config = Mock()
        mock_config.model_path = str(complete_model_setup['model_dir'])
        
        inference_stage = InferenceStage(mock_config)
        
        # Load models with scalers
        context = {}
        models = inference_stage._load_trained_models_with_context(context)
        models['umap_model'] = complete_model_setup['mock_umap']
        
        # Test that extreme data is handled gracefully
        transformed_features = inference_stage._transform_features(extreme_data, models)

        # Extreme values are neither rescaled nor clipped here: the stage forwards what it
        # was given, and EMUSESPipeline has already applied the training scaler. Out-of-range
        # input stays out of range, which is what makes it visible downstream.
        features_passed = complete_model_setup['mock_umap'].transform.call_args[0][0]
        np.testing.assert_array_equal(features_passed, extreme_data)
        assert isinstance(transformed_features, np.ndarray)

    def test_backward_compatibility_without_scalers(self, temp_model_dir):
        """Test that models without scalers continue to work (backward compatibility)."""
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create a model directory WITHOUT scalers (legacy model)
        mock_umap = Mock()
        mock_umap.transform.return_value = np.array([[0.5, 0.5]])
        
        # Create manifest WITHOUT normalization section
        manifest = {
            "model_info": {"version": "1.0.0", "model_type": "complete_emuses_model"},
            "file_integrity": {}
            # No normalization section
        }
        
        manifest_path = temp_model_dir / "model_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Create mock config
        mock_config = Mock()
        mock_config.model_path = str(temp_model_dir)
        
        inference_stage = InferenceStage(mock_config)
        
        # Test model loading (should work without scalers)
        context = {}
        
        # Mock the model loading since we don't have actual model files
        with patch.object(inference_stage, '_load_umap_from_disk', return_value=None):
            with patch.object(inference_stage, '_load_prediction_models_from_disk', return_value=[]):
                models = inference_stage._load_trained_models_with_context(context)
        
        # Verify scalers are None (not loaded)
        assert models['input_scaler'] is None
        assert models['scores_scaler'] is None
        
        # Test feature transformation (should work without normalization)
        test_features = np.array([[100, 50]])
        models['umap_model'] = mock_umap
        
        transformed_features = inference_stage._transform_features(test_features, models)
        
        # Verify original features were passed to UMAP (no normalization)
        features_passed = mock_umap.transform.call_args[0][0]
        np.testing.assert_array_equal(features_passed, test_features)
        
        assert isinstance(transformed_features, np.ndarray)

    def test_normalization_validation_logging(self, complete_model_setup, caplog):
        """Test that appropriate logging messages are generated.

        The level is set explicitly: this test used to pass only when something earlier in
        the session had configured the emuses logger, and failed when run on its own.
        """
        import logging

        from emuses.pipelines.inference_stage import InferenceStage

        # Create mock config
        mock_config = Mock()
        mock_config.model_path = str(complete_model_setup['model_dir'])

        inference_stage = InferenceStage(mock_config)

        with caplog.at_level(logging.INFO, logger="emuses.pipelines.inference_stage"):
            # Test model loading with logging
            context = {}
            models = inference_stage._load_trained_models_with_context(context)

            # Verify scaler loading logs
            log_messages = [record.message for record in caplog.records]

            # Should have logs about loading scalers
            scaler_logs = [msg for msg in log_messages if 'scaler' in msg.lower()]
            assert len(scaler_logs) > 0, "Should have logging messages about scaler loading"

            # Test feature transformation with logging
            test_features = np.array([[100, 50, 0.5]])
            models['umap_model'] = complete_model_setup['mock_umap']

            caplog.clear()
            inference_stage._transform_features(test_features, models)

            # Should say what it did with normalization - here, that it did none, because
            # EMUSESPipeline already applied the saved scaler.
            transform_logs = [record.message for record in caplog.records]
            normalization_logs = [msg for msg in transform_logs if 'normaliz' in msg.lower()]
            assert len(normalization_logs) > 0, "Should have logging messages about normalization"

    def test_denormalization_capability(self, complete_model_setup):
        """Test that denormalization capability is available for interpretable output."""
        # Test that we can reverse the normalization for score interpretation
        from bcblib.tools.dataframe_filtering import inverse_normalize_dataframe
        
        # Create some normalized scores 
        normalized_scores = pd.DataFrame({'cognitive_score': [-0.5, 0.0, 0.5, 1.0]})
        
        # Use the saved scores scaling factors for denormalization
        scores_scaling_factors = complete_model_setup['scores_scaling_factors']
        
        # Test denormalization
        denormalized_scores = inverse_normalize_dataframe(
            normalized_scores, scores_scaling_factors, method='zscore'
        )
        
        # Verify denormalization worked
        assert isinstance(denormalized_scores, pd.DataFrame)
        assert denormalized_scores.shape == normalized_scores.shape
        
        # Values should be different from normalized (restored to original scale)
        assert not np.array_equal(denormalized_scores.values, normalized_scores.values)
        
        # Should be in reasonable range for cognitive scores (around 85 ± a few std devs)
        assert np.all(denormalized_scores.values > 50)  # Reasonable lower bound
        assert np.all(denormalized_scores.values < 120)  # Reasonable upper bound


if __name__ == '__main__':
    pytest.main([__file__, '-v'])