"""
Test to verify that InferenceStage integration tests can be fixed with proper context data.
"""
import tempfile
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from emuses.pipelines.inference_stage import InferenceStage
from emuses.pipelines.pipeline_config import PipelineConfig


class TestContextDataFix(unittest.TestCase):
    """Test that integration tests work with proper context data"""

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

    def test_integration_with_proper_context_data(self):
        """Test that integration works when proper context data is provided"""
        stage = InferenceStage(self.config)
        
        # Mock model loading to avoid file system dependencies
        mock_umap_model = MagicMock()
        mock_prediction_model = MagicMock()
        mock_prediction_model.predict.return_value = np.array([1.0, 2.0, 3.0])
        
        stage._load_trained_models_with_context = MagicMock(return_value={
            'umap_model': mock_umap_model,
            'prediction_models': [
                {'model': mock_prediction_model, 'name': 'test_model', 'score': 0.90}
            ],
            'metadata': {}
        })
        
        # Create proper context with inference_features (standalone context)
        test_features = np.random.rand(3, 5)
        test_labels = np.array([1.1, 2.2, 3.3])  # For validation mode
        
        context = {
            "inference_features": test_features,    # Standalone context format
            "inference_labels": test_labels         # For validation mode
        }
        
        # This should work now without ValueError
        results = stage.run(context)
        
        # Verify results
        self.assertIsNotNone(results)
        self.assertIn('predictions', results)
        self.assertEqual(results['mode'], 'validation')  # Should detect validation mode
        self.assertEqual(results['samples_processed'], 3)
        
    def test_integration_with_pipeline_context_data(self):
        """Test that integration works with pipeline context data (prediction_test_features)"""
        stage = InferenceStage(self.config)
        
        # Mock model loading
        mock_umap_model = MagicMock()
        mock_prediction_model = MagicMock()
        mock_prediction_model.predict.return_value = np.array([4.0, 5.0])
        
        stage._load_trained_models_with_context = MagicMock(return_value={
            'umap_model': mock_umap_model,
            'prediction_models': [
                {'model': mock_prediction_model, 'name': 'test_model', 'score': 0.85}
            ],
            'metadata': {}
        })
        
        # Create proper context with prediction_test_features (pipeline context)
        test_features = np.random.rand(2, 4) 
        test_labels = np.array([4.4, 5.5])
        
        context = {
            "prediction_test_features": test_features,  # Pipeline context format (should have priority)
            "prediction_test_labels": test_labels,
            "inference_features": np.random.rand(1, 2)  # Should be ignored due to lower priority
        }
        
        # This should work and use pipeline context data
        results = stage.run(context)
        
        # Verify results
        self.assertIsNotNone(results)
        self.assertIn('predictions', results)
        self.assertEqual(results['mode'], 'validation')  # Should detect validation mode
        self.assertEqual(results['samples_processed'], 2)  # Should use pipeline context features (2 samples)