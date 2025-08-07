# tests/pipelines/test_inference_progress_simple.py

"""
Simple test for Rich progress indicators in InferenceStage.
"""

import unittest
from unittest.mock import patch, MagicMock

from emuses.pipelines.inference_stage import InferenceStage


class TestInferenceProgressSimple(unittest.TestCase):
    """Simple test for progress indicators."""

    @patch('emuses.pipelines.inference_stage.Progress')
    @patch('emuses.pipelines.inference_stage.Console')
    def test_progress_imports_and_initialization(self, mock_console, mock_progress):
        """Test that Progress and Console are imported and can be instantiated."""
        # Create a mock config
        config = MagicMock()
        config.model_path = "/fake/path"
        config.data_path = "/fake/data" 
        config.output_folder = "/fake/output"
        
        # Create InferenceStage (should not fail)
        stage = InferenceStage(config)
        
        # Verify stage was created successfully
        self.assertIsNotNone(stage)
        self.assertEqual(stage.model_path, "/fake/path")

    @patch('emuses.pipelines.inference_stage.Progress')
    def test_progress_context_manager_called(self, mock_progress):
        """Test that Progress context manager is used when run() is called."""
        # Setup mock to track context manager usage
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        mock_progress.return_value.__exit__.return_value = None
        
        config = MagicMock()
        config.model_path = "/fake/path"
        config.data_path = "/fake/data"
        config.output_folder = "/fake/output"
        
        stage = InferenceStage(config)
        
        # Mock all the methods that would be called to prevent actual execution
        with patch.object(stage, '_load_trained_models', side_effect=Exception("Test complete")):
            try:
                # Provide a minimal context with features to avoid context validation error
                context = {"prediction_test_features": [[1, 2], [3, 4]]}
                stage.run(context)
            except Exception as e:
                if "Test complete" in str(e):
                    pass  # Expected - we want to stop early
                else:
                    raise
        
        # Verify Progress context manager was used
        mock_progress.assert_called_once()
        mock_progress.return_value.__enter__.assert_called_once()


if __name__ == '__main__':
    unittest.main()