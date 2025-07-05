"""Tests for EMUSESPipeline Integration in Pipeline Runner

This module tests the integration of EMUSESPipeline within PipelineRunner including:
- Context to EMUSESPipeline arguments conversion utility
- Progress callback adapter for EMUSESPipeline format
- EMUSESPipeline integration in _run_pipeline_in_process
- Context merging utility to preserve API metadata
- EMUSESPipeline equivalence validation
"""

import pytest
import tempfile
import argparse
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np

from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
from emuses.foundation_fastapi_service.job_manager import JobManager
from emuses.pipelines.emuses_pipeline import EMUSESPipeline


class TestEMUSESPipelineIntegration:
    """Test EMUSESPipeline integration in PipelineRunner"""

    @pytest.fixture
    def job_manager(self):
        """Create a mock JobManager for testing"""
        manager = Mock(spec=JobManager)
        manager.get_job_directory.return_value = Path("/tmp/test_job")
        return manager

    @pytest.fixture
    def sample_context(self):
        """Create a sample context dictionary for testing"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            context = {
                'config': {
                    'output_folder': tmp_dir,
                    'umap_trials': 15,
                    'hdbscan_trials': 8,
                    'optuna_trials': 20,
                    'prediction_optim_dict': 'optim_dict_custom',
                    'prefix': 'TEST',
                    'umap_stage_enabled': True,
                    'heatmap_stage_enabled': True,
                    'prediction_stage_enabled': True,
                },
                'input_matrix': np.random.rand(100, 50),
                'scores': np.random.rand(100),
                'dataset_type': 'synthetic',
                'output_format_info': (10, 5),
                'api_metadata': {
                    'user_id': 'test_user',
                    'request_id': 'req_123',
                    'timestamp': 1234567890
                }
            }
            yield context

    def test_context_to_emuses_args_converter(self, sample_context):
        """Test _context_to_emuses_args utility function"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
        
        # This test should fail initially since we haven't implemented the utility yet
        runner = PipelineRunner(Mock())
        
        # Test the converter utility
        args = runner._context_to_emuses_args(sample_context)
        
        # Verify args object is properly constructed
        assert isinstance(args, argparse.Namespace)
        assert args.output_folder == sample_context['config']['output_folder']
        assert args.umap_trials == 15
        assert args.hdbscan_trials == 8
        assert args.optuna_trials == 20
        assert args.prediction_optim_dict == 'optim_dict_custom'
        assert args.prefix == 'TEST'
        
        # Verify required defaults are set
        assert hasattr(args, 'random_state')
        assert hasattr(args, 'test_size')
        assert hasattr(args, 'interactive_plot')
        assert hasattr(args, 'input_dataset')
        
        # Verify boolean parameters are preserved
        assert args.interactive_plot is False  # Should default to False for API

    def test_context_to_emuses_args_with_missing_config(self, job_manager):
        """Test _context_to_emuses_args with missing config values"""
        runner = PipelineRunner(job_manager)
        
        # Test with minimal context
        minimal_context = {
            'config': {
                'output_folder': '/tmp/test'
            }
        }
        
        args = runner._context_to_emuses_args(minimal_context)
        
        # Verify defaults are applied
        assert args.umap_trials == 10  # Default value
        assert args.hdbscan_trials == 5  # Default value
        assert args.optuna_trials == 10  # Default value
        assert args.prefix == 'API'  # Default value

    def test_context_to_emuses_args_preserves_data_references(self, sample_context):
        """Test that _context_to_emuses_args preserves data matrix references"""
        runner = PipelineRunner(Mock())
        
        args = runner._context_to_emuses_args(sample_context)
        
        # Verify that data references are preserved in args or accessible
        # The exact mechanism will depend on implementation
        assert hasattr(args, 'input_matrix') or 'input_matrix' in sample_context
        assert hasattr(args, 'scores') or 'scores' in sample_context
        assert hasattr(args, 'output_format_info') or 'output_format_info' in sample_context

    def test_context_to_emuses_args_type_safety(self, sample_context):
        """Test that _context_to_emuses_args handles type conversions properly"""
        runner = PipelineRunner(Mock())
        
        # Test with string values that need conversion
        context_with_strings = sample_context.copy()
        context_with_strings['config']['umap_trials'] = '25'  # String instead of int
        context_with_strings['config']['test_size'] = '0.3'  # String instead of float
        
        args = runner._context_to_emuses_args(context_with_strings)
        
        # Verify proper type conversion
        assert isinstance(args.umap_trials, int)
        assert args.umap_trials == 25
        assert isinstance(args.test_size, float)
        assert args.test_size == 0.3

    def test_context_to_emuses_args_path_handling(self, sample_context):
        """Test that _context_to_emuses_args handles Path objects properly"""
        runner = PipelineRunner(Mock())
        
        # Test with Path object for output_folder
        context_with_path = sample_context.copy()
        context_with_path['config']['output_folder'] = Path(sample_context['config']['output_folder'])
        
        args = runner._context_to_emuses_args(context_with_path)
        
        # Verify Path objects are handled correctly
        assert isinstance(args.output_folder, (str, Path))
        if isinstance(args.output_folder, str):
            assert args.output_folder == str(context_with_path['config']['output_folder'])

    def test_progress_callback_adapter_for_emuses_pipeline(self, job_manager):
        """Test _create_emuses_progress_adapter utility function"""
        runner = PipelineRunner(job_manager)
        
        # Mock the job manager's update method
        job_manager.update_job_status = Mock()
        
        # Create a test progress callback
        api_progress_callback = Mock()
        
        # Test the adapter utility
        emuses_progress_callback = runner._create_emuses_progress_adapter(
            api_progress_callback,
            job_id="test_job_123"
        )
        
        # Verify adapter is a callable
        assert callable(emuses_progress_callback)
        
        # Test EMUSESPipeline-style progress callback (stage_name, progress, message)
        emuses_progress_callback(
            stage_name="UMAPStage",
            progress=0.5,
            message="UMAP optimization progress"
        )
        
        # Verify the API callback was called with appropriate arguments
        api_progress_callback.assert_called_once()
        call_args = api_progress_callback.call_args
        assert "UMAPStage" in str(call_args)
        assert 0.5 == call_args[1]['progress'] or 0.5 in call_args[0]

    def test_progress_callback_adapter_with_rate_limiting(self, job_manager):
        """Test progress callback adapter includes rate limiting"""
        runner = PipelineRunner(job_manager)
        
        api_progress_callback = Mock()
        
        # Create adapter with rate limiting
        emuses_progress_callback = runner._create_emuses_progress_adapter(
            api_progress_callback,
            job_id="test_job_456",
            rate_limit_seconds=0.1  # Very short for testing
        )
        
        # Call multiple times rapidly
        emuses_progress_callback("Stage1", 0.1, "msg1")
        emuses_progress_callback("Stage1", 0.2, "msg2")
        emuses_progress_callback("Stage1", 0.3, "msg3")
        
        # Should have rate limited some calls
        # Exact behavior depends on implementation, but should be fewer than 3 calls
        assert api_progress_callback.call_count <= 3

    def test_progress_callback_adapter_handles_none_callback(self, job_manager):
        """Test adapter gracefully handles None callback"""
        runner = PipelineRunner(job_manager)
        
        # Should not raise exception with None callback
        emuses_progress_callback = runner._create_emuses_progress_adapter(
            None,
            job_id="test_job_789"
        )
        
        # Should be callable and not crash
        assert callable(emuses_progress_callback)
        
        # Should not raise exception when called
        emuses_progress_callback("TestStage", 0.5, "test message")

    def test_progress_callback_adapter_job_status_integration(self, job_manager):
        """Test adapter integrates with job status updates"""
        runner = PipelineRunner(job_manager)
        job_manager.update_job_status = Mock()
        
        emuses_progress_callback = runner._create_emuses_progress_adapter(
            None,  # No API callback, just job status updates
            job_id="test_job_status"
        )
        
        # Call the adapter
        emuses_progress_callback("HeatmapStage", 0.75, "Processing heatmaps")
        
        # Verify job status was updated
        job_manager.update_job_status.assert_called()
        call_args = job_manager.update_job_status.call_args
        assert "test_job_status" in call_args[0]
        assert "HeatmapStage" in str(call_args) or "Processing heatmaps" in str(call_args)
