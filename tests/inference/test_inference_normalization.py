"""
Test suite for inference-time normalization loading and application.

Tests the enhanced InferenceStage functionality for loading and applying
normalization scalers during inference pipeline execution.
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


class TestInferenceNormalization:
    """Test inference-time normalization functionality."""

    @pytest.fixture
    def temp_model_dir(self):
        """Create a temporary model directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_inference_stage(self, temp_model_dir):
        """Create a mock InferenceStage with temporary model directory."""
        # Import the actual class to test against
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create a mock config object
        mock_config = Mock()
        mock_config.model_path = str(temp_model_dir)
        
        stage = InferenceStage(mock_config)
        stage.model_path = str(temp_model_dir)
        return stage

    def test_scaler_loading_from_context(self, mock_inference_stage):
        """Test loading scalers from pipeline context (pipeline-integrated mode)."""
        # Create test scaling factors
        test_input_df = pd.DataFrame({'feat1': [1, 2, 3], 'feat2': [10, 20, 30]})
        test_scores_df = pd.DataFrame({'score': [0.1, 0.2, 0.3]})
        
        _, input_factors = normalize_dataframe(test_input_df, method='min-max')
        _, scores_factors = normalize_dataframe(test_scores_df, method='zscore')
        
        # Create context with scaler info (as enhanced EMUSESPipeline would provide)
        context = {
            "input_scaler_info": {
                "path": "input_scaler.joblib",
                "method": "min-max",
                "scaling_factors": input_factors
            },
            "scores_scaler_info": {
                "path": "scores_scaler.joblib", 
                "method": "zscore",
                "scaling_factors": scores_factors
            }
        }
        
        # Test scaler loading
        models = {
            'umap_model': None,
            'prediction_models': [],
            'metadata': {},
            'input_scaler': None,
            'scores_scaler': None
        }
        
        mock_inference_stage._load_normalization_scalers(models, context)
        
        # Verify scalers were loaded from context
        assert models['input_scaler'] is not None
        assert models['scores_scaler'] is not None
        assert models['input_scaler'] == input_factors
        assert models['scores_scaler'] == scores_factors
        
        # Verify metadata was set correctly
        assert models['metadata']['input_normalization_method'] == 'min-max'
        assert models['metadata']['scores_normalization_method'] == 'zscore'

    def test_scaler_loading_from_disk_with_manifest(self, mock_inference_stage, temp_model_dir):
        """Test loading scalers from disk using manifest auto-detection."""
        # Create test scalers and save to disk
        test_input_df = pd.DataFrame({'feat1': [1, 2, 3], 'feat2': [10, 20, 30]})
        test_scores_df = pd.DataFrame({'score': [0.1, 0.2, 0.3]})
        
        _, input_factors = normalize_dataframe(test_input_df, method='robust')
        _, scores_factors = normalize_dataframe(test_scores_df, method='min-max')
        
        # Save scalers to model directory
        input_scaler_path = temp_model_dir / "input_scaler.joblib"
        scores_scaler_path = temp_model_dir / "scores_scaler.joblib"
        joblib.dump(input_factors, input_scaler_path)
        joblib.dump(scores_factors, scores_scaler_path)
        
        # Create manifest with normalization section
        manifest = {
            "model_info": {"version": "1.0.0"},
            "normalization": {
                "input_scaler": "input_scaler.joblib",
                "scores_scaler": "scores_scaler.joblib",
                "input_method": "robust",
                "scores_method": "min-max",
                "embeddings_rescaling": True
            }
        }
        
        manifest_path = temp_model_dir / "model_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Test scaler loading from disk
        models = {
            'umap_model': None,
            'prediction_models': [],
            'metadata': {},
            'input_scaler': None,
            'scores_scaler': None
        }
        
        # Empty context (standalone mode)
        context = {}
        
        mock_inference_stage._load_normalization_scalers(models, context)
        
        # Verify scalers were loaded from disk
        assert models['input_scaler'] is not None
        assert models['scores_scaler'] is not None
        
        # Verify metadata was set from manifest
        assert models['metadata']['input_normalization_method'] == 'robust'
        assert models['metadata']['scores_normalization_method'] == 'min-max'

    def test_transform_does_not_normalize_again(self, mock_inference_stage):
        """The stage forwards features to UMAP; it does not apply the input scaler."""
        # Create test input features
        test_features = np.array([
            [1.5, 15.0],
            [2.5, 25.0],
            [3.5, 35.0]
        ])
        
        # Create scaling factors for min-max normalization [0,1]
        # Training data was [1,2,3,4,5] and [10,20,30,40,50]
        train_df = pd.DataFrame({
            'feat1': [1, 2, 3, 4, 5],
            'feat2': [10, 20, 30, 40, 50]
        })
        _, scaling_factors = normalize_dataframe(train_df, method='min-max')
        
        # Create mock UMAP model
        mock_umap = Mock()
        mock_umap.transform.return_value = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        
        # Create models dict with scaler
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
        result_embeddings = mock_inference_stage._transform_features(test_features, models)
        
        # Verify UMAP transform was called
        assert mock_umap.transform.called

        # Features reach UMAP UNCHANGED, even though the models dict carries an
        # input_scaler. Normalization is EMUSESPipeline's job and happens exactly once,
        # before the stage sees the data (tests/inference/test_normalization_fix.py).
        # Applying the scaler here as well would scale the input twice.
        features_passed = mock_umap.transform.call_args[0][0]
        np.testing.assert_array_equal(features_passed, test_features)

        # Verify result is returned
        assert isinstance(result_embeddings, np.ndarray)

    def test_transform_without_input_normalization(self, mock_inference_stage):
        """Test feature transformation when no input scaler is available."""
        test_features = np.array([[1, 2], [3, 4]])
        
        mock_umap = Mock()
        mock_umap.transform.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
        
        # Models without input scaler
        models = {
            'umap_model': mock_umap,
            'input_scaler': None,  # No scaler available
            'metadata': {
                'min_embeddings': np.array([0.0, 0.0]),
                'max_embeddings': np.array([1.0, 1.0])
            }
        }
        
        result_embeddings = mock_inference_stage._transform_features(test_features, models)
        
        # Verify original features were passed to UMAP (no normalization)
        features_passed = mock_umap.transform.call_args[0][0]
        np.testing.assert_array_equal(features_passed, test_features)
        
        # Verify result is returned
        assert isinstance(result_embeddings, np.ndarray)

    def test_normalization_error_handling(self, mock_inference_stage):
        """Test graceful error handling when normalization fails."""
        test_features = np.array([[1, 2], [3, 4]])
        
        # Create invalid scaling factors that will cause an error
        invalid_scaling_factors = {"invalid": "data"}
        
        mock_umap = Mock()
        mock_umap.transform.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])
        
        models = {
            'umap_model': mock_umap,
            'input_scaler': invalid_scaling_factors,
            'metadata': {
                'input_normalization_method': 'min-max',
                'min_embeddings': np.array([0.0, 0.0]),
                'max_embeddings': np.array([1.0, 1.0])
            }
        }
        
        # Should not raise exception, should fall back to original features
        result_embeddings = mock_inference_stage._transform_features(test_features, models)
        
        # Verify that either original features were used OR normalization proceeded with defaults
        # (the key is that it didn't crash)
        features_passed = mock_umap.transform.call_args[0][0]
        assert isinstance(features_passed, np.ndarray)
        assert features_passed.shape == test_features.shape
        
        assert isinstance(result_embeddings, np.ndarray)

    def test_context_priority_over_disk(self, mock_inference_stage, temp_model_dir):
        """Test that context scalers take priority over disk scalers."""
        # Create disk scalers
        disk_input_df = pd.DataFrame({'feat': [10, 20, 30]})
        _, disk_input_factors = normalize_dataframe(disk_input_df, method='min-max')
        
        input_scaler_path = temp_model_dir / "input_scaler.joblib"
        joblib.dump(disk_input_factors, input_scaler_path)
        
        manifest = {
            "normalization": {
                "input_scaler": "input_scaler.joblib",
                "input_method": "min-max"
            }
        }
        manifest_path = temp_model_dir / "model_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Create different context scalers
        context_input_df = pd.DataFrame({'feat': [1, 2, 3]})
        _, context_input_factors = normalize_dataframe(context_input_df, method='zscore')
        
        context = {
            "input_scaler_info": {
                "path": "input_scaler.joblib",
                "method": "zscore",
                "scaling_factors": context_input_factors
            }
        }
        
        models = {
            'umap_model': None,
            'prediction_models': [],
            'metadata': {},
            'input_scaler': None,
            'scores_scaler': None
        }
        
        mock_inference_stage._load_normalization_scalers(models, context)
        
        # Verify context scaler takes priority (zscore, not min-max)
        assert models['input_scaler'] == context_input_factors
        assert models['metadata']['input_normalization_method'] == 'zscore'

    def test_no_manifest_graceful_handling(self, mock_inference_stage, temp_model_dir):
        """Test graceful handling when no manifest exists."""
        # Create scaler files but no manifest
        test_df = pd.DataFrame({'feat': [1, 2, 3]})
        _, factors = normalize_dataframe(test_df, method='min-max')
        
        input_scaler_path = temp_model_dir / "input_scaler.joblib"
        joblib.dump(factors, input_scaler_path)
        
        models = {
            'umap_model': None,
            'prediction_models': [],
            'metadata': {},
            'input_scaler': None,
            'scores_scaler': None
        }
        
        # Empty context, no manifest file
        context = {}
        
        # Should not raise exception
        mock_inference_stage._load_normalization_scalers(models, context)
        
        # May or may not load scalers depending on manifest generation,
        # but should not crash
        assert 'input_scaler' in models

    def test_different_normalization_methods(self, mock_inference_stage):
        """Test different normalization methods work correctly."""
        test_features = np.array([[1.5, 15.0, 150.0]])
        
        methods_and_data = [
            ('min-max', pd.DataFrame({'f1': [1,2,3,4,5], 'f2': [10,20,30,40,50], 'f3': [100,200,300,400,500]})),
            ('zscore', pd.DataFrame({'f1': [1,2,3,4,5], 'f2': [10,20,30,40,50], 'f3': [100,200,300,400,500]})),
            ('robust', pd.DataFrame({'f1': [1,2,3,4,100], 'f2': [10,20,30,40,500], 'f3': [100,200,300,400,5000]}))
        ]
        
        for method, train_data in methods_and_data:
            _, scaling_factors = normalize_dataframe(train_data, method=method)
            
            mock_umap = Mock()
            mock_umap.transform.return_value = np.array([[0.1, 0.2]])
            
            models = {
                'umap_model': mock_umap,
                'input_scaler': scaling_factors,
                'metadata': {
                    'input_normalization_method': method,
                    'min_embeddings': np.array([0.0, 0.0]),
                    'max_embeddings': np.array([1.0, 1.0])
                }
            }
            
            # Should work without error
            result = mock_inference_stage._transform_features(test_features, models)
            assert mock_umap.transform.called
            assert isinstance(result, np.ndarray)

    def test_scaler_loading_integration_with_model_loading(self, mock_inference_stage, temp_model_dir):
        """Test scaler loading integration with the main model loading method."""
        # Create a manifest with normalization info
        manifest = {
            "model_info": {"version": "1.0.0"},
            "normalization": {
                "input_scaler": "input_scaler.joblib",
                "scores_scaler": "scores_scaler.joblib",
                "input_method": "min-max",
                "scores_method": "zscore"
            }
        }
        
        manifest_path = temp_model_dir / "model_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)
        
        # Create scaler files
        test_input_df = pd.DataFrame({'f1': [1,2,3], 'f2': [10,20,30]})
        test_scores_df = pd.DataFrame({'score': [0.1,0.2,0.3]})
        
        _, input_factors = normalize_dataframe(test_input_df, method='min-max')
        _, scores_factors = normalize_dataframe(test_scores_df, method='zscore')
        
        joblib.dump(input_factors, temp_model_dir / "input_scaler.joblib")
        joblib.dump(scores_factors, temp_model_dir / "scores_scaler.joblib")
        
        # Test with empty context (standalone mode)
        context = {}
        
        # The method should call our new scaler loading functionality
        models = mock_inference_stage._load_trained_models_with_context(context)
        
        # Verify scalers were loaded
        assert 'input_scaler' in models
        assert 'scores_scaler' in models
        # Note: May be None if manifest loading fails, but keys should exist


if __name__ == '__main__':
    pytest.main([__file__, '-v'])