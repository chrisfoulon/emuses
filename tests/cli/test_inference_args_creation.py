"""
Test module for inference CLI args object creation with preprocessing parameters.

Tests that the new preprocessing parameters are properly passed through to the
EMUSESPipeline args object creation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from emuses.cli.main import _execute_inference_locally
import asyncio


class TestInferenceArgsCreation:
    """Test args object creation for inference with preprocessing parameters."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_status_renderer = Mock()

    @patch('emuses.pipelines.emuses_pipeline.EMUSESPipeline')
    @patch('emuses.pipelines.inference_stage.InferenceStage')
    def test_args_object_receives_preprocessing_parameters(self, mock_inference_stage, mock_pipeline):
        """
        Test that args object creation includes preprocessing parameters from config.
        
        This test ensures that the new preprocessing parameters are properly
        set in the args object that's passed to EMUSESPipeline.
        
        Parameters
        ----------
        mock_inference_stage : Mock
            Mock InferenceStage class
        mock_pipeline : Mock
            Mock EMUSESPipeline class
        """
        # Setup mock pipeline and stage
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_dataset.return_value = (
            "input_matrix", "dataset_type", "output_format_info", "scores"
        )
        mock_pipeline_instance.config = Mock()
        
        mock_stage_instance = Mock()
        mock_inference_stage.return_value = mock_stage_instance
        mock_stage_instance.run.return_value = {
            "mode": "inference",
            "samples_processed": 100,
            "performance_breakdown": {"total_ms": 1000},
            "output_files": {"predictions": "/path/to/predictions.csv"}
        }
        
        # Create config with preprocessing parameters
        config = {
            "data": "/path/to/data.csv",
            "output": "/path/to/output",
            "model": "/path/to/model",
            "validate": False,
            "verify": True,
            "output_format": "csv",
            # NEW: Preprocessing parameters
            "input_header": 0,
            "input_index_column": 0,
            "scores_header": 0,
            "scores_index_column": 0,
            "scores": "/path/to/scores.csv"
        }
        
        # Execute local inference
        asyncio.run(_execute_inference_locally(config, self.mock_status_renderer))
        
        # Verify EMUSESPipeline was called
        assert mock_pipeline.called
        
        # Get the args object passed to EMUSESPipeline
        args_used = mock_pipeline.call_args[0][0]
        
        # Verify basic parameters are set (existing functionality)
        assert hasattr(args_used, 'input_dataset')
        assert args_used.input_dataset == str(config["data"])
        assert hasattr(args_used, 'output_folder')
        assert args_used.output_folder == str(config["output"])
        
        # CRITICAL: Verify new preprocessing parameters are set
        # This will fail initially until we enhance args object creation
        assert hasattr(args_used, 'input_header')
        assert args_used.input_header == config["input_header"]
        
        assert hasattr(args_used, 'input_index_column')
        assert args_used.input_index_column == config["input_index_column"]
        
        assert hasattr(args_used, 'scores_header')
        assert args_used.scores_header == config["scores_header"]
        
        assert hasattr(args_used, 'scores_index_column')
        assert args_used.scores_index_column == config["scores_index_column"]
        
        assert hasattr(args_used, 'scores')
        assert args_used.scores == str(config["scores"])

    @patch('emuses.pipelines.emuses_pipeline.EMUSESPipeline')
    @patch('emuses.pipelines.inference_stage.InferenceStage')
    def test_args_object_handles_none_preprocessing_parameters(self, mock_inference_stage, mock_pipeline):
        """
        Test that args object properly handles None values for preprocessing parameters.
        
        Parameters
        ----------
        mock_inference_stage : Mock
            Mock InferenceStage class
        mock_pipeline : Mock
            Mock EMUSESPipeline class
        """
        # Setup mocks
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_dataset.return_value = (
            "input_matrix", "dataset_type", "output_format_info", "scores"
        )
        mock_pipeline_instance.config = Mock()
        
        mock_stage_instance = Mock()
        mock_inference_stage.return_value = mock_stage_instance
        mock_stage_instance.run.return_value = {
            "mode": "inference",
            "samples_processed": 100,
            "performance_breakdown": {"total_ms": 1000},
            "output_files": {"predictions": "/path/to/predictions.csv"}
        }
        
        # Create config without preprocessing parameters (all None/missing)
        config = {
            "data": "/path/to/data.csv",
            "output": "/path/to/output",
            "model": "/path/to/model",
            "validate": False,
            "verify": True,
            "output_format": "csv"
            # No preprocessing parameters - should default to None
        }
        
        # Execute local inference
        asyncio.run(_execute_inference_locally(config, self.mock_status_renderer))
        
        # Get the args object passed to EMUSESPipeline
        args_used = mock_pipeline.call_args[0][0]
        
        # Verify preprocessing parameters default to None when not provided
        assert hasattr(args_used, 'input_header')
        assert args_used.input_header is None
        
        assert hasattr(args_used, 'input_index_column')
        assert args_used.input_index_column is None
        
        assert hasattr(args_used, 'scores_header')
        assert args_used.scores_header is None
        
        assert hasattr(args_used, 'scores_index_column')
        assert args_used.scores_index_column is None
        
        assert hasattr(args_used, 'scores')
        assert args_used.scores is None

    def test_args_object_parameter_validation(self):
        """
        Test validation of preprocessing parameters in args object creation.
        
        This test ensures that invalid parameter values are handled appropriately.
        """
        # This test will be implemented as part of parameter validation in task 1.2.3
        # For now, it's a placeholder to ensure we consider validation
        pass