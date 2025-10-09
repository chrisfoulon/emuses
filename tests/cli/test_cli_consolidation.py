"""
Tests for CLI inference consolidation with EMUSESPipeline.

This module tests the consolidated CLI inference approach that eliminates
duplication between CLI and EMUSESPipeline initialization.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from emuses.cli.main import _execute_inference_locally
from emuses.pipelines.emuses_pipeline import EMUSESPipeline
from emuses.pipelines.inference_stage import InferenceStage


class TestCLIInferenceConsolidation(unittest.TestCase):
    """Test CLI inference consolidation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test data files
        test_data = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
        test_scores = np.array([0.1, 0.2, 0.3])
        
        self.data_file = self.temp_path / "data.csv"
        self.scores_file = self.temp_path / "scores.csv"
        self.model_dir = self.temp_path / "model"
        self.output_dir = self.temp_path / "output"
        
        np.savetxt(self.data_file, test_data, delimiter=',')
        np.savetxt(self.scores_file, test_scores)
        self.model_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create config for CLI function
        self.config = {
            "data": str(self.data_file),
            "scores": str(self.scores_file),
            "model": str(self.model_dir),
            "output": str(self.output_dir),
            "validate": False,
            "verify": True,
            "output_format": "csv"
        }
        
        # Create mock status renderer
        self.status_renderer = Mock()
        self.status_renderer.render_status.return_value = "mock status"
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    @patch('emuses.pipelines.inference_stage.InferenceStage')
    @patch('emuses.pipelines.emuses_pipeline.EMUSESPipeline')
    def test_cli_uses_consolidated_pipeline(self, mock_pipeline_class, mock_inference_class):
        """Test that CLI uses consolidated EMUSESPipeline with inference_data."""
        # Set up mocks
        mock_pipeline = Mock()
        mock_pipeline.context = {
            "inference_features": np.array([[1, 2], [3, 4]]),
            "inference_labels": np.array([0.1, 0.2]),
            "dataset_type": "csv",
            "output_format_info": None
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        mock_inference_stage = Mock()
        mock_inference_stage.run.return_value = {"mode": "inference"}
        mock_inference_class.return_value = mock_inference_stage
        
        # Call the CLI function using asyncio
        asyncio.run(_execute_inference_locally(self.config, self.status_renderer))
        
        # Verify EMUSESPipeline was called with inference_data
        mock_pipeline_class.assert_called_once()
        call_args = mock_pipeline_class.call_args
        
        # Check that inference_data was passed
        self.assertEqual(len(call_args), 2)  # args, kwargs or two positional args
        args, inference_data = call_args[0]  # Two positional arguments
        
        self.assertIsNotNone(inference_data)
        self.assertIn("input_path", inference_data)
        self.assertIn("model_path", inference_data)
        self.assertEqual(inference_data["input_path"], str(self.data_file))
        self.assertEqual(inference_data["model_path"], str(self.model_dir))
        
        # Verify InferenceStage uses pipeline context directly
        mock_inference_stage.run.assert_called_once()
        context_arg = mock_inference_stage.run.call_args[0][0]
        self.assertIn("inference_features", context_arg)
        
    @patch('emuses.pipelines.inference_stage.InferenceStage')
    @patch('emuses.pipelines.emuses_pipeline.EMUSESPipeline')
    def test_cli_eliminates_duplicate_processing(self, mock_pipeline_class, mock_inference_class):
        """Test that CLI doesn't call process_dataset manually anymore."""
        # Set up mocks
        mock_pipeline = Mock()
        mock_pipeline.context = {"inference_features": np.array([[1, 2]])}
        mock_pipeline_class.return_value = mock_pipeline
        
        mock_inference_stage = Mock()
        mock_inference_stage.run.return_value = {"mode": "inference"}
        mock_inference_class.return_value = mock_inference_stage
        
        # Call the CLI function using asyncio
        asyncio.run(_execute_inference_locally(self.config, self.status_renderer))
        
        # Verify that process_dataset and load_and_process_scores are NOT called manually
        mock_pipeline.process_dataset.assert_not_called()
        mock_pipeline.load_and_process_scores.assert_not_called()
        
    @patch('emuses.pipelines.inference_stage.InferenceStage')
    @patch('emuses.pipelines.emuses_pipeline.EMUSESPipeline')  
    def test_cli_preserves_inference_features(self, mock_pipeline_class, mock_inference_class):
        """Test that CLI preserves all inference-specific features."""
        # Set up mocks
        mock_pipeline = Mock()
        mock_pipeline.context = {
            "inference_features": np.array([[1, 2]]),
            "cli_inference_mode": True,
            "model_path": str(self.model_dir)
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        mock_inference_stage = Mock()
        mock_inference_stage.run.return_value = {
            "mode": "validation",
            "validation_metrics": {"accuracy": 0.95, "f1": 0.93}
        }
        mock_inference_class.return_value = mock_inference_stage
        
        # Call the CLI function using asyncio
        asyncio.run(_execute_inference_locally(self.config, self.status_renderer))
        
        # Verify inference stage configuration
        mock_inference_class.assert_called_once()
        inference_init_call = mock_inference_class.call_args
        self.assertIsNotNone(inference_init_call)
        
        # Verify inference stage attributes are set
        self.assertEqual(mock_inference_stage.model_path, str(self.model_dir))
        self.assertEqual(mock_inference_stage.output_path, str(self.output_dir))
        self.assertFalse(mock_inference_stage.validate_mode)  # Based on config
        
        # Verify validation metrics are handled
        # This would be called when rendering validation results
        self.assertTrue(mock_inference_stage.run.called)


if __name__ == "__main__":
    unittest.main()