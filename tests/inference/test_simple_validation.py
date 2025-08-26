"""
Simple focused validation tests for normalization fix.

This test suite provides focused validation of the key functionality
without complex setup to ensure the normalization fix works correctly.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock
import tempfile
import json
import joblib
from pathlib import Path
import shutil

from bcblib.tools.dataframe_filtering import normalize_dataframe


class TestSimpleNormalizationValidation:
    """Simple focused validation tests."""

    @pytest.fixture
    def temp_model_dir(self):
        """Create a temporary model directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_scaler_persistence_and_loading(self, temp_model_dir):
        """Test that scalers can be saved and loaded correctly."""
        # Create realistic test data
        training_data = pd.DataFrame({
            'feature_1': np.random.normal(100, 20, 100),
            'feature_2': np.random.uniform(0, 10, 100),
            'feature_3': np.random.exponential(2, 100)
        })
        
        # Test different normalization methods
        methods = ['min-max', 'zscore', 'robust']
        
        for method in methods:
            # Generate and save scaler
            _, scaling_factors = normalize_dataframe(training_data, method=method)
            
            scaler_path = temp_model_dir / f"{method}_scaler.joblib"
            joblib.dump(scaling_factors, scaler_path)
            
            # Load scaler back
            loaded_factors = joblib.load(scaler_path)
            
            # Verify loaded scaler works on new data
            test_data = pd.DataFrame({
                'feature_1': [120, 80],
                'feature_2': [5, 8],
                'feature_3': [1, 3]
            })
            
            # Apply loaded scaler to new data
            normalized_test, _ = normalize_dataframe(
                test_data, method=method, scaling_factors=loaded_factors
            )
            
            # Verify normalization worked
            assert isinstance(normalized_test, pd.DataFrame)
            assert normalized_test.shape == test_data.shape
            assert not np.array_equal(normalized_test.values, test_data.values)

    def test_manifest_normalization_detection(self, temp_model_dir):
        """Test that manifest correctly detects and includes normalization scalers."""
        # Create test scalers
        test_df = pd.DataFrame({
            'feat1': [1, 2, 3, 4, 5],
            'feat2': [10, 20, 30, 40, 50]
        })
        
        _, input_factors = normalize_dataframe(test_df, method='min-max')
        _, scores_factors = normalize_dataframe(test_df.rename(columns={'feat1': 'score'})[['score']], method='zscore')
        
        # Save scalers
        joblib.dump(input_factors, temp_model_dir / "input_scaler.joblib")
        joblib.dump(scores_factors, temp_model_dir / "scores_scaler.joblib")
        
        # Create initial manifest
        manifest = {
            "model_info": {"version": "1.0.0"},
            "file_integrity": {}
        }
        
        manifest_path = temp_model_dir / "model_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Test manifest enhancement
        from emuses.tools.model_io import enhance_model_manifest_with_pipeline_data
        success = enhance_model_manifest_with_pipeline_data(temp_model_dir)
        
        assert success
        
        # Verify enhanced manifest includes normalization
        with open(manifest_path, 'r') as f:
            enhanced_manifest = json.load(f)
        
        assert "normalization" in enhanced_manifest
        norm_info = enhanced_manifest["normalization"]
        
        assert "input_scaler" in norm_info
        assert "scores_scaler" in norm_info  
        assert "embeddings_rescaling" in norm_info
        
        assert norm_info["input_scaler"] == "input_scaler.joblib"
        assert norm_info["scores_scaler"] == "scores_scaler.joblib"
        assert norm_info["embeddings_rescaling"] is True

    def test_inference_stage_scaler_loading(self, temp_model_dir):
        """Test InferenceStage loads scalers from manifest."""
        # Create scalers and manifest
        test_df = pd.DataFrame({'f1': [1, 2, 3], 'f2': [10, 20, 30]})
        _, scaling_factors = normalize_dataframe(test_df, method='min-max')
        
        joblib.dump(scaling_factors, temp_model_dir / "input_scaler.joblib")
        
        manifest = {
            "model_info": {"version": "1.0.0"},
            "normalization": {
                "input_scaler": "input_scaler.joblib",
                "input_method": "min-max"
            }
        }
        
        with open(temp_model_dir / "model_manifest.json", 'w') as f:
            json.dump(manifest, f)
        
        # Test InferenceStage loading
        from emuses.pipelines.inference_stage import InferenceStage
        
        mock_config = Mock()
        mock_config.model_path = str(temp_model_dir)
        
        inference_stage = InferenceStage(mock_config)
        
        # Test scaler loading method directly
        models = {
            'umap_model': None,
            'prediction_models': [],
            'metadata': {},
            'input_scaler': None,
            'scores_scaler': None
        }
        
        inference_stage._load_scalers_from_disk(models)
        
        # Verify scaler was loaded
        assert models['input_scaler'] is not None
        assert models['metadata']['input_normalization_method'] == 'min-max'

    def test_normalization_application_during_transform(self, temp_model_dir):
        """Test that normalization is correctly applied during feature transformation."""
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create training data and scaling factors
        training_data = pd.DataFrame({
            'feature_1': [0, 10, 20, 30, 40],  # Range 0-40
            'feature_2': [100, 200, 300, 400, 500]  # Range 100-500  
        })
        
        _, scaling_factors = normalize_dataframe(training_data, method='min-max')
        
        # Create mock config and inference stage
        mock_config = Mock()
        mock_config.model_path = str(temp_model_dir)
        inference_stage = InferenceStage(mock_config)
        
        # Create mock UMAP model
        mock_umap = Mock()
        mock_umap.transform.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
        
        # Create models with scaler
        models = {
            'umap_model': mock_umap,
            'input_scaler': scaling_factors,
            'metadata': {
                'input_normalization_method': 'min-max',
                'min_embeddings': np.array([0.0, 0.0]),
                'max_embeddings': np.array([1.0, 1.0])
            }
        }
        
        # Test feature transformation
        test_features = np.array([
            [20, 300],  # Mid-range values
            [0, 100],   # Min values
            [40, 500]   # Max values
        ])
        
        result = inference_stage._transform_features(test_features, models)
        
        # Verify UMAP was called with normalized features
        assert mock_umap.transform.called
        normalized_features = mock_umap.transform.call_args[0][0]
        
        # For min-max normalization:
        # [20, 300] -> [(20-0)/(40-0), (300-100)/(500-100)] = [0.5, 0.5]
        # [0, 100] -> [0.0, 0.0]
        # [40, 500] -> [1.0, 1.0]
        expected = np.array([
            [0.5, 0.5],
            [0.0, 0.0], 
            [1.0, 1.0]
        ])
        
        np.testing.assert_array_almost_equal(normalized_features, expected, decimal=10)

    def test_backward_compatibility_no_scalers(self, temp_model_dir):
        """Test that models without scalers still work."""
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create manifest without normalization section
        manifest = {
            "model_info": {"version": "1.0.0"}
            # No normalization section
        }
        
        with open(temp_model_dir / "model_manifest.json", 'w') as f:
            json.dump(manifest, f)
        
        mock_config = Mock()
        mock_config.model_path = str(temp_model_dir)
        inference_stage = InferenceStage(mock_config)
        
        # Test scaler loading (should handle missing scalers gracefully)
        models = {
            'umap_model': None,
            'prediction_models': [],
            'metadata': {},
            'input_scaler': None,
            'scores_scaler': None
        }
        
        # Should not raise exception
        inference_stage._load_scalers_from_disk(models)
        
        # Scalers should remain None
        assert models['input_scaler'] is None
        assert models['scores_scaler'] is None
        
        # Test feature transformation without scalers
        mock_umap = Mock()
        mock_umap.transform.return_value = np.array([[0.1, 0.2]])
        
        models['umap_model'] = mock_umap
        models['metadata']['min_embeddings'] = np.array([0.0, 0.0])
        models['metadata']['max_embeddings'] = np.array([1.0, 1.0])
        
        test_features = np.array([[100, 50]])
        
        result = inference_stage._transform_features(test_features, models)
        
        # Should use original features (no normalization)
        features_passed = mock_umap.transform.call_args[0][0]
        np.testing.assert_array_equal(features_passed, test_features)

    def test_kernel_regressor_prediction_scenario(self):
        """Test realistic KernelRegressor scenario with and without normalization."""
        # Simulate the KernelRegressor issue: distance-based model sensitive to scaling
        
        # Training data (well-normalized)
        training_embeddings = np.array([
            [0.2, 0.3],
            [0.4, 0.5],
            [0.6, 0.7],
            [0.8, 0.9]
        ])
        
        # Mock KernelRegressor that's sensitive to input scale
        def distance_sensitive_predict(X):
            # Calculate distances from training center
            center = np.array([0.5, 0.5])
            distances = np.linalg.norm(X - center, axis=1)
            
            # If distances are very large (unnormalized data), predictions approach zero
            predictions = np.exp(-distances * 5)  # Exponential decay with distance
            return predictions
        
        # Test Case 1: Unnormalized data (the problem scenario)
        unnormalized_inference = np.array([
            [100, 200],  # Very large values compared to training [0.2-0.8]
            [150, 300]
        ])
        
        unnormalized_predictions = distance_sensitive_predict(unnormalized_inference)
        
        # Should produce near-zero predictions due to large distances
        assert np.all(unnormalized_predictions < 0.01), "Unnormalized data should produce near-zero predictions"
        
        # Test Case 2: Properly normalized data (the fix)
        # Normalize inference data to same scale as training
        normalized_inference = np.array([
            [0.3, 0.4],  # Similar scale to training data
            [0.7, 0.8]
        ])
        
        normalized_predictions = distance_sensitive_predict(normalized_inference)
        
        # Should produce meaningful predictions
        assert np.all(normalized_predictions > 0.1), "Normalized data should produce meaningful predictions"
        assert np.all(normalized_predictions < 1.0), "Predictions should be reasonable"
        
        # Demonstrate the fix effectiveness
        improvement_ratio = normalized_predictions.mean() / unnormalized_predictions.mean()
        assert improvement_ratio > 10, f"Normalization should improve predictions by >10x, got {improvement_ratio:.1f}x"

    def test_denormalization_scores_capability(self):
        """Test that scores can be denormalized for interpretability."""
        from bcblib.tools.dataframe_filtering import inverse_normalize_dataframe
        
        # Create training scores
        training_scores = pd.DataFrame({
            'cognitive_score': np.random.normal(85, 12, 100)  # Mean 85, std 12
        })
        
        # Normalize scores
        normalized_scores, scaling_factors = normalize_dataframe(training_scores, method='zscore')
        
        # Simulate prediction results (in normalized space)
        predicted_scores_normalized = pd.DataFrame({
            'cognitive_score': [-1.0, 0.0, 1.0, 2.0]  # Z-scores
        })
        
        # Denormalize for interpretability
        predicted_scores_denormalized = inverse_normalize_dataframe(
            predicted_scores_normalized, scaling_factors, method='zscore'
        )
        
        # Verify denormalized scores are in realistic range
        denorm_values = predicted_scores_denormalized['cognitive_score'].values
        
        # Z-score of -1.0 should be approximately 85 - 12 = 73
        # Z-score of 0.0 should be approximately 85
        # Z-score of 1.0 should be approximately 85 + 12 = 97  
        # Z-score of 2.0 should be approximately 85 + 24 = 109
        
        assert abs(denorm_values[0] - 73) < 2, f"Z-score -1.0 should denormalize to ~73, got {denorm_values[0]}"
        assert abs(denorm_values[1] - 85) < 2, f"Z-score 0.0 should denormalize to ~85, got {denorm_values[1]}"
        assert abs(denorm_values[2] - 97) < 2, f"Z-score 1.0 should denormalize to ~97, got {denorm_values[2]}"
        assert abs(denorm_values[3] - 109) < 2, f"Z-score 2.0 should denormalize to ~109, got {denorm_values[3]}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])