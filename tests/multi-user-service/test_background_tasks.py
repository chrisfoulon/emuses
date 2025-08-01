"""Tests for background task management system.

Comprehensive test suite for ProcessPoolExecutor integration, user context isolation,
task lifecycle management, and process monitoring in the EMUSES multi-user service.
"""

import asyncio
import os
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timedelta

from emuses.multi_user_service.background_tasks import (
    BackgroundTaskManager,
    BackgroundTask,
    TaskStatus,
    _execute_pipeline_task
)
from emuses.multi_user_service.job_manager import MultiUserJobManager
from emuses.multi_user_service.task_integration import (
    initialize_task_manager,
    shutdown_task_manager,
    get_task_manager_health
)


class TestBackgroundTaskManager:
    """Test ProcessPoolExecutor configuration and task management."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def job_manager(self, temp_directory):
        """Create job manager for testing."""
        return MultiUserJobManager(temp_directory)

    @pytest.fixture
    def task_manager(self, job_manager):
        """Create task manager for testing."""
        manager = BackgroundTaskManager(
            job_manager=job_manager,
            max_workers=2,
            task_timeout=30.0,
            process_memory_limit_gb=1.0
        )
        yield manager
        manager.shutdown(wait=False, timeout=5.0)

    def test_process_pool_configuration(self, task_manager):
        """Test ProcessPoolExecutor configuration with appropriate worker count."""
        assert task_manager.max_workers == 2
        assert task_manager.task_timeout == 30.0
        assert task_manager.process_memory_limit_gb == 1.0
        
        # Configure process pool
        task_manager.configure_process_pool()
        assert task_manager._executor is not None
        assert task_manager._cleanup_thread is not None
        assert task_manager._monitor_thread is not None

    def test_task_creation_with_quota_validation(self, task_manager, temp_directory):
        """Test background task creation with quota validation."""
        user_id = uuid4()
        job_id = uuid4()
        
        # Create job directory structure
        user_storage = temp_directory / "users" / str(user_id) / "jobs"
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True)
        
        # Create job metadata
        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
        
        config = {"test": "config"}
        
        # Test task creation
        task_id = task_manager.create_task(
            job_id=job_id,
            user_id=user_id,
            config=config,
            expected_compute_hours=1.0,
            expected_storage_gb=0.5
        )
        
        assert isinstance(task_id, UUID)
        task = task_manager.get_task(task_id)
        assert task is not None
        assert task.job_id == job_id
        assert task.user_id == user_id
        assert task.config == config
        assert task.expected_compute_hours == 1.0
        assert task.expected_storage_gb == 0.5
        assert task.status == TaskStatus.PENDING

    def test_task_submission_and_execution(self, task_manager, temp_directory):
        """Test task submission to ProcessPoolExecutor."""
        user_id = uuid4()
        job_id = uuid4()
        
        # Set up job directory
        user_storage = temp_directory / "users" / str(user_id) / "jobs"
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True)
        (job_dir / "input").mkdir()
        (job_dir / "output").mkdir()
        (job_dir / "logs").mkdir()
        
        # Create job metadata
        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
        
        config = {"test": "simple_config"}
        
        # Create and submit task
        task_id = task_manager.create_task(job_id, user_id, config)
        
        # Mock the pipeline executor to avoid actual execution
        with patch('emuses.multi_user_service.background_tasks.PipelineExecutor') as mock_executor:
            mock_executor.return_value.execute.return_value = {"success": True}
            
            success = task_manager.submit_task(task_id)
            assert success is True
            
            task = task_manager.get_task(task_id)
            assert task.status == TaskStatus.QUEUED

    def test_task_cancellation(self, task_manager, temp_directory):
        """Test task cancellation with user authorization."""
        user_id = uuid4()
        job_id = uuid4()
        
        # Set up job directory
        user_storage = temp_directory / "users" / str(user_id) / "jobs"
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True)
        
        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
        
        config = {"test": "config"}
        
        # Create task
        task_id = task_manager.create_task(job_id, user_id, config)
        
        # Test cancellation
        cancelled = task_manager.cancel_task(task_id, user_id)
        assert cancelled is True
        
        task = task_manager.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED
        assert task.completed_at is not None

    def test_user_authorization_validation(self, task_manager, temp_directory):
        """Test user authorization for task operations."""
        user1_id = uuid4()
        user2_id = uuid4()
        job_id = uuid4()
        
        # Set up job directory for user1
        user_storage = temp_directory / "users" / str(user1_id) / "jobs"
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True)
        
        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text('{"user_id": "' + str(user1_id) + '"}')
        
        config = {"test": "config"}
        
        # Create task as user1
        task_id = task_manager.create_task(job_id, user1_id, config)
        
        # Try to cancel as user2 (should fail)
        with pytest.raises(ValueError, match="not authorized"):
            task_manager.cancel_task(task_id, user2_id)

    def test_task_listing_and_filtering(self, task_manager, temp_directory):
        """Test task listing with user filtering and pagination."""
        user_id = uuid4()
        
        # Create multiple tasks
        task_ids = []
        for i in range(5):
            job_id = uuid4()
            
            # Set up job directory
            user_storage = temp_directory / "users" / str(user_id) / "jobs"
            job_dir = user_storage / str(job_id)
            job_dir.mkdir(parents=True)
            
            metadata_file = job_dir / "metadata.json"
            metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
            
            task_id = task_manager.create_task(job_id, user_id, {"test": f"config_{i}"})
            task_ids.append(task_id)
        
        # Test listing all user tasks
        tasks = task_manager.list_user_tasks(user_id)
        assert len(tasks) == 5
        
        # Test filtering by status
        tasks = task_manager.list_user_tasks(user_id, status=TaskStatus.PENDING)
        assert len(tasks) == 5
        
        # Test pagination
        tasks = task_manager.list_user_tasks(user_id, limit=3)
        assert len(tasks) == 3
        
        tasks = task_manager.list_user_tasks(user_id, limit=3, offset=3)
        assert len(tasks) == 2

    def test_process_monitoring_and_cleanup(self, task_manager):
        """Test process monitoring and resource limit enforcement."""
        # Test system status
        status = task_manager.get_system_status()
        
        assert "max_workers" in status
        assert "active_workers" in status
        assert "task_counts" in status
        assert "total_tasks" in status
        assert "process_memory_limit_gb" in status
        assert "executor_active" in status
        
        assert status["max_workers"] == 2
        assert status["process_memory_limit_gb"] == 1.0

    def test_task_cleanup_old_completed(self, task_manager, temp_directory):
        """Test cleanup of old completed tasks."""
        user_id = uuid4()
        job_id = uuid4()
        
        # Set up job directory
        user_storage = temp_directory / "users" / str(user_id) / "jobs"
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True)
        
        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
        
        # Create task and mark as completed with old timestamp
        task_id = task_manager.create_task(job_id, user_id, {"test": "config"})
        task = task_manager.get_task(task_id)
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow() - timedelta(hours=25)  # Older than 24 hours
        
        # Trigger cleanup
        task_manager._cleanup_completed_tasks()
        
        # Task should be removed
        cleaned_task = task_manager.get_task(task_id)
        assert cleaned_task is None


class TestPipelineExecution:
    """Test pipeline execution in separate processes with user context isolation."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_pipeline_execution_with_user_context(self, temp_directory):
        """Test pipeline execution with user workspace isolation."""
        user_id = uuid4()
        job_id = uuid4()
        
        # Set up job directory structure
        user_storage = temp_directory / "users" / str(user_id) / "jobs"
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True)
        (job_dir / "input").mkdir()
        (job_dir / "output").mkdir()
        (job_dir / "logs").mkdir()
        
        # Create job metadata
        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
        
        config = {"test": "execution_config"}
        
        # Mock pipeline executor
        with patch('emuses.multi_user_service.background_tasks.PipelineExecutor') as mock_executor:
            mock_executor.return_value.execute.return_value = {"result": "success"}
            
            # Execute pipeline task
            result = _execute_pipeline_task(
                job_id=job_id,
                user_id=user_id,
                config=config,
                base_directory=str(temp_directory),
                memory_limit_gb=1.0
            )
            
            assert result["success"] is True
            assert result["job_id"] == str(job_id)
            assert result["user_id"] == str(user_id)
            assert "execution_time_hours" in result
            assert "storage_bytes" in result

    def test_pipeline_execution_with_resource_tracking(self, temp_directory):
        """Test resource usage tracking during pipeline execution."""
        user_id = uuid4()
        job_id = uuid4()
        
        # Set up job directory
        user_storage = temp_directory / "users" / str(user_id) / "jobs"
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True)
        (job_dir / "input").mkdir()
        (job_dir / "output").mkdir()
        (job_dir / "logs").mkdir()
        
        # Create some output files to measure storage
        (job_dir / "output" / "result.txt").write_text("test result data")
        
        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
        
        config = {"test": "resource_tracking"}
        
        with patch('emuses.multi_user_service.background_tasks.PipelineExecutor') as mock_executor:
            mock_executor.return_value.execute.return_value = {"tracked": True}
            
            result = _execute_pipeline_task(
                job_id=job_id,
                user_id=user_id,
                config=config,
                base_directory=str(temp_directory),
                memory_limit_gb=1.0
            )
            
            assert result["storage_bytes"] > 0  # Should measure the output file
            assert result["execution_time_hours"] >= 0
            assert "usage_summary" in result

    def test_pipeline_execution_failure_handling(self, temp_directory):
        """Test error handling during pipeline execution."""
        user_id = uuid4()
        job_id = uuid4()
        
        # Set up job directory
        user_storage = temp_directory / "users" / str(user_id) / "jobs"
        job_dir = user_storage / str(job_id)
        job_dir.mkdir(parents=True)
        (job_dir / "input").mkdir()
        (job_dir / "output").mkdir()
        (job_dir / "logs").mkdir()
        
        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
        
        config = {"test": "failure_config"}
        
        # Mock pipeline executor to raise exception
        with patch('emuses.multi_user_service.background_tasks.PipelineExecutor') as mock_executor:
            mock_executor.return_value.execute.side_effect = Exception("Pipeline failed")
            
            with pytest.raises(Exception, match="Pipeline failed"):
                _execute_pipeline_task(
                    job_id=job_id,
                    user_id=user_id,
                    config=config,
                    base_directory=str(temp_directory),
                    memory_limit_gb=1.0
                )


class TestTaskIntegration:
    """Test task manager integration and health monitoring."""

    @pytest.fixture
    def temp_directory(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_task_manager_initialization(self, temp_directory):
        """Test task manager initialization and configuration."""
        job_manager = MultiUserJobManager(temp_directory)
        
        task_manager = initialize_task_manager(
            job_manager=job_manager,
            max_workers=3,
            task_timeout=60.0,
            process_memory_limit_gb=2.0
        )
        
        assert task_manager is not None
        assert task_manager.max_workers == 3
        assert task_manager.task_timeout == 60.0
        assert task_manager.process_memory_limit_gb == 2.0
        
        # Clean up
        shutdown_task_manager(timeout=5.0)

    def test_task_manager_health_monitoring(self, temp_directory):
        """Test task manager health status reporting."""
        job_manager = MultiUserJobManager(temp_directory)
        
        # Test health when not initialized
        health = get_task_manager_health()
        assert health["status"] == "not_initialized"
        assert health["healthy"] is False
        
        # Initialize and test health
        task_manager = initialize_task_manager(job_manager=job_manager, max_workers=2)
        
        health = get_task_manager_health()
        assert health["status"] in ["active", "degraded"]
        assert "max_workers" in health
        assert "active_workers" in health
        assert "total_tasks" in health
        
        # Clean up
        shutdown_task_manager(timeout=5.0)

    def test_concurrent_task_execution(self, temp_directory):
        """Test concurrent task execution and worker management."""
        job_manager = MultiUserJobManager(temp_directory)
        task_manager = BackgroundTaskManager(
            job_manager=job_manager,
            max_workers=2,
            task_timeout=30.0
        )
        
        user_id = uuid4()
        
        # Create multiple tasks
        task_ids = []
        for i in range(3):
            job_id = uuid4()
            
            # Set up job directory
            user_storage = temp_directory / "users" / str(user_id) / "jobs"
            job_dir = user_storage / str(job_id)
            job_dir.mkdir(parents=True)
            (job_dir / "input").mkdir()
            (job_dir / "output").mkdir()
            (job_dir / "logs").mkdir()
            
            metadata_file = job_dir / "metadata.json"
            metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
            
            task_id = task_manager.create_task(job_id, user_id, {"test": f"concurrent_{i}"})
            task_ids.append(task_id)
        
        # Submit tasks
        with patch('emuses.multi_user_service.background_tasks.PipelineExecutor') as mock_executor:
            mock_executor.return_value.execute.return_value = {"concurrent": True}
            
            for task_id in task_ids:
                task_manager.submit_task(task_id)
        
        # Verify tasks are queued
        for task_id in task_ids:
            task = task_manager.get_task(task_id)
            assert task.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]
        
        # Clean up
        task_manager.shutdown(wait=False, timeout=5.0)

    def test_task_count_and_metrics(self, temp_directory):
        """Test task counting and system metrics."""
        job_manager = MultiUserJobManager(temp_directory)
        task_manager = BackgroundTaskManager(job_manager=job_manager, max_workers=2)
        
        user_id = uuid4()
        
        # Initially no tasks
        assert task_manager.get_task_count() == 0
        assert task_manager.get_task_count(TaskStatus.PENDING) == 0
        
        # Create tasks
        for i in range(3):
            job_id = uuid4()
            
            user_storage = temp_directory / "users" / str(user_id) / "jobs"
            job_dir = user_storage / str(job_id)
            job_dir.mkdir(parents=True)
            
            metadata_file = job_dir / "metadata.json"
            metadata_file.write_text('{"user_id": "' + str(user_id) + '"}')
            
            task_manager.create_task(job_id, user_id, {"test": f"metrics_{i}"})
        
        # Check counts
        assert task_manager.get_task_count() == 3
        assert task_manager.get_task_count(TaskStatus.PENDING) == 3
        
        # Clean up
        task_manager.shutdown(wait=False, timeout=5.0)