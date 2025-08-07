"""
Test semantic aliasing pattern for context keys in InferenceStage.
"""
import tempfile
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from emuses.pipelines.inference_stage import InferenceStage
from emuses.pipelines.pipeline_config import PipelineConfig


class TestSemanticAliasing(unittest.TestCase):
    """Test semantic aliasing for multiple context key names"""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "test_model"
        self.model_path.mkdir(exist_ok=True)
        
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv",
            validate_mode=False
        )

    def tearDown(self):
        """Clean up test environment.""" 
        self.temp_dir.cleanup()

    def test_pipeline_context_keys_priority(self):
        """Test that pipeline context keys (prediction_test_features) have highest priority"""
        stage = InferenceStage(self.config)
        
        # Mock model loading to avoid file system dependencies
        stage._load_trained_models_with_context = MagicMock(return_value={
            'umap_model': None,
            'prediction_models': [],
            'metadata': {}
        })
        
        # Create context with multiple key options - pipeline context should win
        pipeline_features = np.random.rand(10, 5)
        standalone_features = np.random.rand(8, 4)
        generic_features = np.random.rand(6, 3)
        
        context = {
            "prediction_test_features": pipeline_features,    # Pipeline context (should win)
            "inference_features": standalone_features,        # Standalone context
            "features": generic_features                      # Generic fallback
        }
        
        # Extract features using the method
        features = stage._load_features_from_context(context)
        
        # Should get pipeline features (highest priority)
        np.testing.assert_array_equal(features, pipeline_features)
        self.assertEqual(features.shape, (10, 5))

    def test_standalone_context_keys_fallback(self):
        """Test that standalone context keys (inference_features) are used when pipeline keys missing"""
        stage = InferenceStage(self.config)
        
        # Create context with only standalone and generic keys
        standalone_features = np.random.rand(8, 4)
        generic_features = np.random.rand(6, 3)
        
        context = {
            "inference_features": standalone_features,        # Standalone context (should win)
            "features": generic_features                      # Generic fallback
        }
        
        features = stage._load_features_from_context(context)
        
        # Should get standalone features (second priority)
        np.testing.assert_array_equal(features, standalone_features)
        self.assertEqual(features.shape, (8, 4))

    def test_generic_fallback_keys(self):
        """Test that generic fallback keys (features, input_matrix) work when specific keys missing"""
        stage = InferenceStage(self.config)
        
        # Create context with only generic keys
        generic_features = np.random.rand(6, 3)
        
        context = {
            "features": generic_features                      # Generic fallback
        }
        
        features = stage._load_features_from_context(context)
        
        # Should get generic features (fallback)
        np.testing.assert_array_equal(features, generic_features)
        self.assertEqual(features.shape, (6, 3))

    def test_labels_semantic_aliasing(self):
        """Test that label semantic aliasing works correctly"""
        stage = InferenceStage(self.config)
        
        # Test pipeline context labels priority
        pipeline_labels = np.array([1, 2, 3, 4, 5])
        standalone_labels = np.array([6, 7, 8])
        
        pipeline_features = np.random.rand(5, 3)
        context = {
            "prediction_test_features": pipeline_features,
            "prediction_test_labels": pipeline_labels,     # Pipeline context (should win)
            "inference_labels": standalone_labels          # Standalone context
        }
        
        features = stage._load_features_from_context(context)
        
        # Verify pipeline labels are detected and stored
        self.assertIsNotNone(stage._detected_labels)
        np.testing.assert_array_equal(stage._detected_labels, pipeline_labels)

    def test_missing_context_raises_error(self):
        """Test that missing all context keys raises appropriate error"""
        stage = InferenceStage(self.config)
        
        # Context with no feature keys
        context = {
            "some_other_data": "irrelevant"
        }
        
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            stage._load_features_from_context(context)
            
        self.assertIn("No inference features found in context", str(cm.exception))
        self.assertIn("InferenceStage must receive data from EMUSESPipeline", str(cm.exception))