"""Tests for Stage Runners

This module tests the stage runners for EMUSES pipeline including:
- UMAPStageRunner with parameter validation and resource limits
- HeatmapStageRunner with optimization progress tracking
- Stage-specific artifact organization with secure file handling
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from uuid import uuid4

from emuses.foundation_fastapi_service.stage_runners import (
    UMAPStageRunner,
    HeatmapStageRunner,
    ResourceMonitor,
    ProgressTracker,
    BaseStageRunner
)
from emuses.foundation_fastapi_service.job_manager import JobManager
from emuses.pipelines.pipeline_config import PipelineConfig


class TestResourceMonitor:
    """Test ResourceMonitor functionality"""

    def test_resource_monitor_initialization(self):
        """Test ResourceMonitor initialization with default values"""
        monitor = ResourceMonitor()
        # Should use 75% of system memory by default
        assert monitor.memory_limit_bytes > 0
        assert monitor.cpu_percent_limit == 90.0
        assert not monitor.monitoring
        assert not monitor.exceeded_limits

    def test_resource_monitor_custom_limits(self):
        """Test ResourceMonitor with custom limits"""
        monitor = ResourceMonitor(memory_limit_ratio=0.5, cpu_percent_limit=80.0)
        # Should use 50% of system memory
        assert monitor.memory_limit_bytes > 0
        assert monitor.cpu_percent_limit == 80.0

    def test_resource_monitor_start_stop(self):
        """Test ResourceMonitor start/stop monitoring"""
        monitor = ResourceMonitor()

        # Start monitoring
        monitor.start_monitoring()
        assert monitor.monitoring
        assert not monitor.exceeded_limits

        # Stop monitoring
        monitor.stop_monitoring()
        assert not monitor.monitoring

    @patch('emuses.foundation_fastapi_service.stage_runners.psutil.virtual_memory')
    @patch('emuses.foundation_fastapi_service.stage_runners.psutil.cpu_percent')
    def test_resource_monitor_check_resources_ok(self, mock_cpu, mock_memory):
        """Test ResourceMonitor when resources are within limits"""
        # Mock total memory as 16GB
        total_memory = 16 * 1024 * 1024 * 1024
        mock_memory.return_value = Mock(used=8 * 1024 * 1024 * 1024)  # 8GB used
        mock_cpu.return_value = 50.0  # 50% CPU usage

        # Create monitor with 75% limit (should be 12GB limit)
        with patch('emuses.foundation_fastapi_service.stage_runners.psutil.virtual_memory',
                   return_value=Mock(total=total_memory)):
            monitor = ResourceMonitor(memory_limit_ratio=0.75, cpu_percent_limit=90.0)

        monitor.start_monitoring()

        assert monitor.check_resources()  # Should pass because 8GB < 12GB limit
        assert not monitor.exceeded_limits

    @patch('emuses.foundation_fastapi_service.stage_runners.psutil.virtual_memory')
    @patch('emuses.foundation_fastapi_service.stage_runners.psutil.cpu_percent')
    def test_resource_monitor_check_resources_memory_exceeded(self, mock_cpu, mock_memory):
        """Test ResourceMonitor when memory limit is exceeded"""
        # Mock total memory as 16GB
        total_memory = 16 * 1024 * 1024 * 1024
        mock_memory.return_value = Mock(used=14 * 1024 * 1024 * 1024)  # 14GB used
        # Create monitor with 75% limit (should be 12GB limit)
        with patch('emuses.foundation_fastapi_service.stage_runners.psutil.virtual_memory',
                   return_value=Mock(total=total_memory)):
            monitor = ResourceMonitor(memory_limit_ratio=0.75, cpu_percent_limit=90.0)

        mock_cpu.return_value = 50.0  # 50% CPU usage

        monitor.start_monitoring()

        assert not monitor.check_resources()  # Should fail because 14GB > 12GB limit
        assert monitor.exceeded_limits

    @patch('emuses.foundation_fastapi_service.stage_runners.psutil.virtual_memory')
    @patch('emuses.foundation_fastapi_service.stage_runners.psutil.cpu_percent')
    def test_resource_monitor_check_resources_cpu_exceeded(self, mock_cpu, mock_memory):
        """Test ResourceMonitor when CPU limit is exceeded"""
        # Mock total memory as 16GB
        total_memory = 16 * 1024 * 1024 * 1024
        mock_memory.return_value = Mock(used=8 * 1024 * 1024 * 1024)  # 8GB used
        mock_cpu.return_value = 95.0  # 95% CPU usage (exceeds 90% limit)

        # Create monitor with 75% memory limit and 90% CPU limit
        with patch('emuses.foundation_fastapi_service.stage_runners.psutil.virtual_memory',
                   return_value=Mock(total=total_memory)):
            monitor = ResourceMonitor(memory_limit_ratio=0.75, cpu_percent_limit=90.0)

        monitor.start_monitoring()

        assert not monitor.check_resources()
        assert monitor.exceeded_limits

    @patch('emuses.foundation_fastapi_service.stage_runners.psutil.virtual_memory')
    def test_resource_monitor_check_resources_exception(self, mock_memory):
        """Test ResourceMonitor graceful handling of exceptions"""
        # Mock total memory for initialization
        total_memory = 16 * 1024 * 1024 * 1024
        with patch('emuses.foundation_fastapi_service.stage_runners.psutil.virtual_memory',
                   return_value=Mock(total=total_memory)):
            monitor = ResourceMonitor()

        # Now make virtual_memory fail during check_resources
        mock_memory.side_effect = Exception("Mock exception")

        monitor.start_monitoring()

        # Should return True when monitoring fails
        assert monitor.check_resources()
        assert not monitor.exceeded_limits


class TestProgressTracker:
    """Test ProgressTracker functionality"""

    def test_progress_tracker_initialization(self):
        """Test ProgressTracker initialization"""
        job_manager = Mock(spec=JobManager)
        job_id = str(uuid4())
        stage_name = "test_stage"

        tracker = ProgressTracker(job_manager, job_id, stage_name)

        assert tracker.job_manager == job_manager
        assert tracker.job_id == job_id
        assert tracker.stage_name == stage_name
        assert tracker.max_update_rate == 1.0
        assert tracker.last_update_time == 0.0

    def test_progress_tracker_update_progress(self):
        """Test ProgressTracker update_progress"""
        job_manager = Mock(spec=JobManager)
        job_id = str(uuid4())
        stage_name = "test_stage"

        tracker = ProgressTracker(job_manager, job_id, stage_name)

        # First update should always go through
        tracker.update_progress(0.5, "Test message")

        job_manager.update_job_status.assert_called_once_with(
            job_id,
            "RUNNING",
            progress=0.5,
            current_stage=stage_name,
            message="Test message"
        )

    def test_progress_tracker_rate_limiting(self):
        """Test ProgressTracker rate limiting functionality"""
        job_manager = Mock(spec=JobManager)
        job_id = str(uuid4())
        stage_name = "test_stage"

        tracker = ProgressTracker(job_manager, job_id, stage_name, max_update_rate=2.0)

        # First update
        tracker.update_progress(0.3, "First update")
        assert job_manager.update_job_status.call_count == 1

        # Second update immediately after (should be rate limited)
        tracker.update_progress(0.4, "Second update")
        # Should still be 1 call due to rate limiting
        assert job_manager.update_job_status.call_count == 1

        # Wait for rate limit to expire (mock time)
        import time
        with patch('time.time', return_value=tracker.last_update_time + 1.0):
            tracker.update_progress(0.5, "Third update")
            assert job_manager.update_job_status.call_count == 2


class TestBaseStageRunner:
    """Test BaseStageRunner functionality"""

    def test_base_stage_runner_initialization(self):
        """Test BaseStageRunner initialization"""
        job_manager = Mock(spec=JobManager)
        runner = BaseStageRunner(job_manager)

        assert runner.job_manager == job_manager
        assert runner.logger is not None

    def test_validate_context_success(self):
        """Test _validate_context with valid context"""
        job_manager = Mock(spec=JobManager)
        runner = BaseStageRunner(job_manager)

        context = {"key1": "value1", "key2": "value2"}
        required_keys = ["key1", "key2"]

        # Should not raise exception
        runner._validate_context(context, required_keys)

    def test_validate_context_missing_keys(self):
        """Test _validate_context with missing keys"""
        job_manager = Mock(spec=JobManager)
        runner = BaseStageRunner(job_manager)

        context = {"key1": "value1"}
        required_keys = ["key1", "key2", "key3"]

        with pytest.raises(ValueError, match="Missing required context keys"):
            runner._validate_context(context, required_keys)

    def test_validate_breaking_parameters_success(self):
        """Test _validate_breaking_parameters with valid parameters"""
        job_manager = Mock(spec=JobManager)
        runner = BaseStageRunner(job_manager)

        config = Mock()
        config.param1 = 5
        config.param2 = 0.5

        breaking_checks = {
            "param1": lambda x: isinstance(x, int) and x > 0,
            "param2": lambda x: isinstance(x, (int, float)) and x > 0.0
        }

        # Should not raise exception
        runner._validate_breaking_parameters(config, breaking_checks)

    def test_validate_breaking_parameters_failure(self):
        """Test _validate_breaking_parameters with breaking parameters"""
        job_manager = Mock(spec=JobManager)
        runner = BaseStageRunner(job_manager)

        config = Mock()
        config.param1 = -5  # Breaking value

        breaking_checks = {
            "param1": lambda x: isinstance(x, int) and x > 0
        }

        with pytest.raises(ValueError, match="Parameter param1=-5 would cause breaking behavior"):
            runner._validate_breaking_parameters(config, breaking_checks)

    def test_is_safe_path_valid(self):
        """Test _is_safe_path with valid path"""
        job_manager = Mock(spec=JobManager)
        runner = BaseStageRunner(job_manager)

        with tempfile.TemporaryDirectory() as tmp_dir:
            safe_path = Path(tmp_dir) / "safe_file.txt"
            safe_path.touch()

            # Should be safe
            assert runner._is_safe_path(safe_path)

    def test_is_safe_path_traversal_attempt(self):
        """Test _is_safe_path with directory traversal attempt"""
        job_manager = Mock(spec=JobManager)
        runner = BaseStageRunner(job_manager)

        # Path with .. should be detected (after resolution)
        unsafe_path = Path("../../../etc/passwd")

        # This should return False (unsafe)
        assert not runner._is_safe_path(unsafe_path)


class TestUMAPStageRunner:
    """Test UMAPStageRunner functionality"""

    @pytest.fixture
    def job_manager(self):
        """Create a mock JobManager for testing"""
        manager = Mock(spec=JobManager)
        manager.get_job_directory.return_value = Path("/tmp/test_job")
        return manager

    @pytest.fixture
    def umap_runner(self, job_manager):
        """Create UMAPStageRunner instance for testing"""
        return UMAPStageRunner(job_manager)

    @pytest.fixture
    def valid_context(self):
        """Create valid context for UMAP stage"""
        config = Mock()
        config.n_components = 2
        config.n_neighbors = 15
        config.min_dist = 0.1
        config.min_cluster_size = 10
        config.output_folder = Path("/tmp/test_output")

        return {
            "embedding_train_features": np.random.rand(100, 50),
            "config": config
        }

    def test_umap_stage_runner_initialization(self, job_manager):
        """Test UMAPStageRunner initialization"""
        runner = UMAPStageRunner(job_manager)

        assert runner.job_manager == job_manager
        assert isinstance(runner, BaseStageRunner)

    @pytest.mark.asyncio
    async def test_umap_stage_runner_missing_context(self, umap_runner):
        """Test UMAPStageRunner with missing context keys"""
        job_id = str(uuid4())
        invalid_context = {"config": Mock()}  # Missing embedding_train_features

        with pytest.raises(ValueError, match="Missing required context keys"):
            await umap_runner.run_stage(job_id, invalid_context)

    @pytest.mark.asyncio
    async def test_umap_stage_runner_invalid_parameters(self, umap_runner):
        """Test UMAPStageRunner with invalid parameters"""
        job_id = str(uuid4())

        config = Mock()
        config.n_components = -1  # Breaking: negative value
        config.n_neighbors = 15
        config.min_dist = 0.1
        config.min_cluster_size = 10

        context = {
            "embedding_train_features": np.random.rand(100, 50),
            "config": config
        }

        with pytest.raises(ValueError, match="Parameter n_components=-1 would cause breaking behavior"):
            await umap_runner.run_stage(job_id, context)

    @pytest.mark.asyncio
    @patch('emuses.foundation_fastapi_service.stage_runners.UMAPStage')
    async def test_umap_stage_runner_successful_execution(self, mock_umap_stage, umap_runner, valid_context):
        """Test successful UMAP stage execution"""
        job_id = str(uuid4())

        # Mock UMAP stage
        mock_stage_instance = Mock()
        mock_stage_instance.run.return_value = valid_context
        mock_umap_stage.return_value = mock_stage_instance

        # Mock job directory structure
        with tempfile.TemporaryDirectory() as tmp_dir:
            job_dir = Path(tmp_dir) / "test_job"
            umap_runner.job_manager.get_job_directory.return_value = job_dir

            # Execute stage
            result = await umap_runner.run_stage(job_id, valid_context)

            # Verify result
            assert result == valid_context
            mock_umap_stage.assert_called_once()
            mock_stage_instance.run.assert_called_once()

    @pytest.mark.asyncio
    @patch('emuses.foundation_fastapi_service.stage_runners.UMAPStage')
    async def test_umap_stage_runner_execution_failure(self, mock_umap_stage, umap_runner, valid_context):
        """Test UMAP stage execution failure handling"""
        job_id = str(uuid4())

        # Mock UMAP stage to raise exception
        mock_stage_instance = Mock()
        mock_stage_instance.run.side_effect = Exception("Mock UMAP error")
        mock_umap_stage.return_value = mock_stage_instance

        # Execute stage and expect exception
        with pytest.raises(Exception, match="Mock UMAP error"):
            await umap_runner.run_stage(job_id, valid_context)

        # Verify job status was updated to FAILED
        umap_runner.job_manager.update_job_status.assert_called_with(
            job_id, "FAILED",
            current_stage="umap_stage",
            message="UMAP stage error: Mock UMAP error"
        )

    @pytest.mark.asyncio
    async def test_umap_organize_artifacts(self, umap_runner):
        """Test UMAP artifact organization"""
        job_id = str(uuid4())

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Setup directories
            job_dir = Path(tmp_dir) / "test_job"
            source_dir = Path(tmp_dir) / "source"
            source_dir.mkdir(parents=True)

            # Create mock artifacts
            artifacts = [
                "best_umap_model.joblib",
                "embeddings.npy",
                "hdbscan_model.joblib",
                "cluster_labels.npy"
            ]

            for artifact in artifacts:
                (source_dir / artifact).write_text("mock content")

            # Mock context
            config = Mock()
            config.output_folder = source_dir
            context = {"config": config}

            # Mock job manager
            umap_runner.job_manager.get_job_directory.return_value = job_dir

            # Execute artifact organization
            await umap_runner._organize_umap_artifacts(job_id, context)

            # Verify artifacts were copied
            umap_output_dir = job_dir / "output" / "umap"
            assert umap_output_dir.exists()

            for artifact in artifacts:
                assert (umap_output_dir / artifact).exists()


class TestHeatmapStageRunner:
    """Test HeatmapStageRunner functionality"""

    @pytest.fixture
    def job_manager(self):
        """Create a mock JobManager for testing"""
        manager = Mock(spec=JobManager)
        manager.get_job_directory.return_value = Path("/tmp/test_job")
        return manager

    @pytest.fixture
    def heatmap_runner(self, job_manager):
        """Create HeatmapStageRunner instance for testing"""
        return HeatmapStageRunner(job_manager)

    @pytest.fixture
    def valid_context(self):
        """Create valid context for heatmap stage"""
        config = Mock()
        config.cv_folds = 5
        config.test_size = 0.2
        config.max_iter = 1000
        config.output_folder = Path("/tmp/test_output")

        return {
            "embeddings": np.random.rand(100, 10),
            "scores": np.random.rand(100, 5),
            "config": config
        }

    def test_heatmap_stage_runner_initialization(self, job_manager):
        """Test HeatmapStageRunner initialization"""
        runner = HeatmapStageRunner(job_manager)

        assert runner.job_manager == job_manager
        assert isinstance(runner, BaseStageRunner)

    @pytest.mark.asyncio
    async def test_heatmap_stage_runner_missing_context(self, heatmap_runner):
        """Test HeatmapStageRunner with missing context keys"""
        job_id = str(uuid4())
        invalid_context = {"config": Mock()}  # Missing embeddings and scores

        with pytest.raises(ValueError, match="Missing required context keys"):
            await heatmap_runner.run_stage(job_id, invalid_context)

    @pytest.mark.asyncio
    async def test_heatmap_stage_runner_invalid_parameters(self, heatmap_runner):
        """Test HeatmapStageRunner with invalid parameters"""
        job_id = str(uuid4())

        config = Mock()
        config.cv_folds = 1  # Breaking: must be >= 2 for cross-validation
        config.test_size = 0.2
        config.max_iter = 1000

        context = {
            "embeddings": np.random.rand(100, 10),
            "scores": np.random.rand(100, 5),
            "config": config
        }

        with pytest.raises(ValueError, match="Parameter cv_folds=1 would cause breaking behavior"):
            await heatmap_runner.run_stage(job_id, context)
