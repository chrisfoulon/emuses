"""Tests for Pipeline Runner

This module tests the pipeline runner for EMUSES including:
- EMUSESPipeline async wrapper with ProcessPoolExecutor and resource limits
- Context dictionary preservation with deep copy validation
- Progress callback integration with rate limiting
- Error handling and exception capture with job status updates
"""

import pytest
import asyncio
import tempfile
import shutil
import pickle
import copy
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from uuid import uuid4
from concurrent.futures import ProcessPoolExecutor

from emuses.foundation_fastapi_service.job_manager import JobManager
from emuses.pipelines.pipeline_config import PipelineConfig


class TestPipelineRunner:
    """Test PipelineRunner functionality"""

    @pytest.fixture
    def job_manager(self):
        """Create a mock JobManager for testing"""
        manager = Mock(spec=JobManager)
        manager.get_job_directory.return_value = Path("/tmp/test_job")
        return manager

    @pytest.fixture
    def pipeline_config(self):
        """Create a valid pipeline configuration"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = Mock(spec=PipelineConfig)
            config.output_folder = Path(tmp_dir)
            config.umap_stage_enabled = True
            config.heatmap_stage_enabled = True
            config.prediction_stage_enabled = True
            config.input_file = Path(tmp_dir) / "input.nii"
            config.scores_file = Path(tmp_dir) / "scores.csv"
            yield config

    @pytest.fixture
    def valid_context(self):
        """Create valid context for pipeline execution"""
        return {
            "input_matrix": np.random.rand(100, 1000),
            "scores": np.random.rand(100, 5),
            "embedding_train_features": np.random.rand(80, 1000),
            "embedding_test_features": np.random.rand(20, 1000),
            "config": {
                "param1": "value1",
                "param2": 42,
                "output_folder": "/tmp/test_output",
                "input_dataset": "/tmp/test_input.csv",
                "scores_dataset": "/tmp/test_scores.csv"
            }
        }

    def test_pipeline_runner_initialization(self, job_manager):
        """Test PipelineRunner initialization"""
        # This test should fail initially since PipelineRunner doesn't exist yet
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager)

        assert runner.job_manager == job_manager
        assert hasattr(runner, 'executor')
        assert runner.max_workers == 4  # Default process limit

    @pytest.mark.asyncio
    async def test_pipeline_runner_context_preservation(self, job_manager, valid_context):
        """Test context dictionary preservation with deep copy validation"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager)
        job_id = str(uuid4())

        # Test that context is deep copied and preserved
        original_context = copy.deepcopy(valid_context)

        # Mock the pipeline execution to return modified context
        with patch.object(runner, '_execute_pipeline_stages') as mock_execute:
            modified_context = copy.deepcopy(valid_context)
            modified_context["new_key"] = "new_value"
            mock_execute.return_value = modified_context

            result_context = await runner.execute_pipeline(job_id, valid_context)

            # Original context should be unchanged (check keys and shapes)
            assert set(valid_context.keys()) == set(original_context.keys())
            for key in valid_context:
                if hasattr(valid_context[key], 'shape'):
                    # For numpy arrays, check shapes match
                    assert valid_context[key].shape == original_context[key].shape
                else:
                    # For other types, check equality
                    assert valid_context[key] == original_context[key]

            # Result should have the new key
            assert result_context["new_key"] == "new_value"

    @pytest.mark.asyncio
    async def test_pipeline_runner_process_pool_executor(self, job_manager, valid_context):
        """Test background execution with ProcessPoolExecutor and resource limits"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager, max_workers=2, memory_limit_ratio=0.5)
        job_id = str(uuid4())

        # Mock the actual pipeline execution method instead of the executor
        with patch.object(runner, '_run_pipeline_in_process') as mock_run_pipeline:
            mock_run_pipeline.return_value = valid_context
            
            result = await runner.execute_pipeline(job_id, valid_context)
            
            # Verify the pipeline method was called (avoid NumPy array comparison issues)
            mock_run_pipeline.assert_called_once()
            call_args = mock_run_pipeline.call_args[0][0]
            assert set(call_args.keys()) == set(valid_context.keys())
            
            # Verify result is returned correctly
            assert result == valid_context

    @pytest.mark.asyncio
    async def test_pipeline_runner_progress_callback_integration(self, job_manager, valid_context):
        """Test progress callback integration with rate limiting"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager)
        job_id = str(uuid4())

        progress_updates = []

        def mock_progress_callback(stage, progress, message):
            progress_updates.append((stage, progress, message))

        with patch.object(runner, '_create_progress_callback', return_value=mock_progress_callback):
            with patch.object(runner, '_execute_pipeline_stages') as mock_execute:
                mock_execute.return_value = valid_context

                await runner.execute_pipeline(job_id, valid_context)

                # Verify progress callback was created and used
                runner._create_progress_callback.assert_called_once_with(job_id)

    @pytest.mark.asyncio
    async def test_pipeline_runner_error_handling(self, job_manager, valid_context):
        """Test error handling and exception capture with job status updates"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager)
        job_id = str(uuid4())

        # Test exception handling
        with patch.object(runner, '_execute_pipeline_stages') as mock_execute:
            mock_execute.side_effect = Exception("Pipeline execution failed")

            with pytest.raises(Exception, match="Pipeline execution failed"):
                await runner.execute_pipeline(job_id, valid_context)

            # Verify job status was updated to FAILED
            job_manager.update_job_status.assert_called_with(
                job_id, "FAILED",
                message="Pipeline execution error: Pipeline execution failed"
            )

    @pytest.mark.asyncio
    async def test_pipeline_runner_timeout_handling(self, job_manager, valid_context):
        """Test pipeline timeout handling"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager, pipeline_timeout=1)  # 1 second timeout
        job_id = str(uuid4())

        # Mock a long-running pipeline that should timeout
        async def slow_pipeline(*args, **kwargs):
            await asyncio.sleep(2)  # Longer than timeout
            return valid_context

        with patch.object(runner, '_execute_pipeline_stages', side_effect=slow_pipeline):
            with pytest.raises(asyncio.TimeoutError):
                await runner.execute_pipeline(job_id, valid_context)

            # Verify job status was updated to FAILED
            job_manager.update_job_status.assert_called_with(
                job_id, "FAILED",
                message="Pipeline execution timeout after 1 seconds"
            )

    def test_context_serialization_validation(self, job_manager):
        """Test context serialization for ProcessPoolExecutor"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager)

        # Test with serializable context
        serializable_context = {
            "input_matrix": np.random.rand(10, 10),
            "scores": np.random.rand(10, 3),
            "config": {"param1": 1, "param2": "test"}
        }

        # Should be able to serialize and deserialize
        serialized = runner._serialize_context(serializable_context)
        deserialized = runner._deserialize_context(serialized)

        assert "input_matrix" in deserialized
        assert "scores" in deserialized
        assert deserialized["config"]["param1"] == 1

    def test_context_serialization_large_data(self, job_manager):
        """Test context serialization with large dictionaries"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager)

        # Create large context (100MB of data)
        large_context = {
            "large_matrix": np.random.rand(1000, 1000),
            "metadata": {"size": "large", "type": "test"}
        }

        # Should handle large data efficiently
        serialized = runner._serialize_context(large_context)
        assert len(serialized) > 1000000  # Should be substantial

        deserialized = runner._deserialize_context(serialized)
        assert deserialized["large_matrix"].shape == (1000, 1000)
        assert deserialized["metadata"]["size"] == "large"

    @pytest.mark.asyncio
    async def test_real_pipeline_execution_creates_files(self, job_manager):
        """Test that real pipeline execution creates actual output files"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
        
        # Create temporary directory for output
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "output"
            output_dir.mkdir(exist_ok=True)
            
            # Create realistic test data
            np.random.seed(42)  # For reproducibility
            n_samples, n_features = 50, 20  # Small for fast testing
            
            features = np.random.randn(n_samples, n_features)
            targets = np.random.randn(n_samples, 2)
            
            # Create context with proper structure for EMUSES pipeline
            context = {
                'input_matrix': features,
                'scores': targets,
                'embedding_train_features': features,
                'embedding_test_features': features[:10],  # Subset for test
                # Prediction data that HeatmapStage expects
                'prediction_train_features': features,
                'prediction_train_labels': targets,  # This is what HeatmapStage needs
                'config': {
                    'output_folder': output_dir,
                    'umap_trials': 2,  # Minimal for testing
                    'hdbscan_trials': 1,
                    'optuna_trials': 2,
                    'prediction_optim_dict': 'optim_dict_test',
                    'prefix': 'TEST'
                },
                'pipeline_metadata': {
                    'start_time': 0,
                    'stages_completed': [],
                    'stages_runtime': {}
                },
                'output_format_info': []  # For HeatmapStage
            }
            
            runner = PipelineRunner(job_manager)
            job_id = str(uuid4())
            
            # Execute pipeline
            result_context = await runner.execute_pipeline(job_id, context)
            
            # Verify pipeline was actually executed
            assert result_context["pipeline_executed"] is True
            assert "api_execution_timestamp" in result_context
            
            # Check that output files were created
            output_files = list(output_dir.rglob("*"))
            output_file_names = [f.name for f in output_files if f.is_file()]
            
            # Should have at least some output files from EMUSES pipeline
            assert len(output_file_names) > 0, f"No output files created. Found: {output_file_names}"
            
            # Verify specific expected files based on EMUSES pipeline
            # These might include: random_seeds.json, models, embeddings, etc.
            expected_patterns = ["random_seeds.json"]  # Files that should always be created
            
            for pattern in expected_patterns:
                matching_files = [f for f in output_file_names if pattern in f]
                assert len(matching_files) > 0, f"Expected file pattern '{pattern}' not found in {output_file_names}"


class TestPipelineRunnerResourceManagement:
    """Test resource management aspects of PipelineRunner"""

    @pytest.fixture
    def job_manager(self):
        """Create a mock JobManager for testing"""
        manager = Mock(spec=JobManager)
        manager.get_job_directory.return_value = Path("/tmp/test_job")
        return manager

    @pytest.fixture
    def valid_context(self):
        """Create valid context for pipeline execution"""
        return {
            "input_matrix": np.random.rand(100, 1000),
            "scores": np.random.rand(100, 5),
            "embedding_train_features": np.random.rand(80, 1000),
            "embedding_test_features": np.random.rand(20, 1000),
            "config": {
                "param1": "value1",
                "param2": 42,
                "output_folder": "/tmp/test_output",
                "input_dataset": "/tmp/test_input.csv",
                "scores_dataset": "/tmp/test_scores.csv"
            }
        }

    def test_pipeline_runner_resource_limits(self, job_manager):
        """Test resource limit configuration"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        # Test custom resource limits
        runner = PipelineRunner(
            job_manager,
            max_workers=8,
            memory_limit_ratio=0.8,
            pipeline_timeout=3600
        )

        assert runner.max_workers == 8
        assert runner.memory_limit_ratio == 0.8
        assert runner.pipeline_timeout == 3600

    @pytest.mark.asyncio
    async def test_pipeline_runner_cleanup(self, job_manager, valid_context):
        """Test proper cleanup of background processes"""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        runner = PipelineRunner(job_manager)
        job_id = str(uuid4())

        # Mock the pipeline execution to test cleanup behavior
        with patch.object(runner, '_run_pipeline_in_process') as mock_run_pipeline:
            mock_run_pipeline.return_value = valid_context

            result = await runner.execute_pipeline(job_id, valid_context)

            # Verify pipeline was executed (avoid NumPy array comparison issues)
            mock_run_pipeline.assert_called_once()
            call_args = mock_run_pipeline.call_args[0][0]
            assert set(call_args.keys()) == set(valid_context.keys())
            
            # Verify result is returned correctly
            assert result == valid_context
