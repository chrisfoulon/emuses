"""
Tests for Rich UI real-time progress updates with graceful degradation (Task 5.4).

This module tests the real-time progress update functionality that provides
live feedback during pipeline execution with graceful degradation for
environments that don't support rich terminal features.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time
from rich.console import Console
from rich.progress import Progress, TaskID
from io import StringIO

from emuses.cli.rich_features import RealTimeProgressUpdater, ProgressStage


class TestRealTimeProgressUpdater:
    """Test real-time progress updates with graceful degradation."""

    @pytest.fixture
    def mock_console(self):
        """Create a mock console for testing."""
        console = Mock(spec=Console)
        console.is_terminal = True
        console.options.legacy_windows = False
        console.get_time = Mock(return_value=time.time())
        console.print = Mock()
        return console

    @pytest.fixture
    def progress_updater(self, mock_console):
        """Create a progress updater instance."""
        return RealTimeProgressUpdater(console=mock_console)

    def test_real_time_progress_creation(self, progress_updater):
        """Test that real-time progress updater initializes correctly."""
        assert progress_updater is not None
        assert hasattr(progress_updater, 'console')
        assert hasattr(progress_updater, 'progress')
        assert hasattr(progress_updater, 'active_tasks')

    def test_progress_update_with_live_refresh(self, progress_updater):
        """Test real-time progress updates with live refresh enabled."""
        # Create a progress task
        task_id = progress_updater.add_task("Test Task", total=100)
        
        # Update progress in real-time
        progress_updater.update_progress(task_id, advance=10)
        progress_updater.update_progress(task_id, advance=20)
        
        # Verify progress state
        assert progress_updater.get_task_progress(task_id) == 30
        assert not progress_updater.is_task_complete(task_id)

    def test_progress_graceful_degradation_no_terminal(self):
        """Test graceful degradation when terminal doesn't support rich features."""
        # Create console that doesn't support rich features
        fallback_console = Mock(spec=Console)
        fallback_console.is_terminal = False
        
        progress_updater = RealTimeProgressUpdater(console=fallback_console)
        
        # Should fall back to simple text output
        task_id = progress_updater.add_task("Fallback Task", total=100)
        progress_updater.update_progress(task_id, advance=50)
        
        # Should still track progress internally
        assert progress_updater.get_task_progress(task_id) == 50

    def test_progress_rate_limiting(self, progress_updater):
        """Test that progress updates are rate-limited to prevent performance issues."""
        task_id = progress_updater.add_task("Rate Limited Task", total=1000)
        
        # Rapid updates should be rate-limited
        start_time = time.time()
        for i in range(100):
            progress_updater.update_progress(task_id, advance=1)
        
        # Should not cause excessive console updates
        assert progress_updater.console.print.call_count < 100

    def test_multiple_concurrent_tasks(self, progress_updater):
        """Test handling multiple concurrent progress tasks."""
        task1 = progress_updater.add_task("Task 1", total=100)
        task2 = progress_updater.add_task("Task 2", total=200)
        task3 = progress_updater.add_task("Task 3", total=50)
        
        # Update different tasks
        progress_updater.update_progress(task1, advance=25)
        progress_updater.update_progress(task2, advance=100)
        progress_updater.update_progress(task3, advance=50)
        
        # Verify individual progress
        assert progress_updater.get_task_progress(task1) == 25
        assert progress_updater.get_task_progress(task2) == 100
        assert progress_updater.get_task_progress(task3) == 50
        assert progress_updater.is_task_complete(task3)

    def test_progress_stage_transitions(self, progress_updater):
        """Test smooth transitions between pipeline stages."""
        # Start with data loading stage
        load_task = progress_updater.add_task("Loading Data", total=100)
        progress_updater.update_progress(load_task, advance=100)
        progress_updater.complete_task(load_task)
        
        # Transition to processing stage
        process_task = progress_updater.add_task("Processing", total=200)
        progress_updater.update_progress(process_task, advance=50)
        
        # Verify stage transition
        assert progress_updater.is_task_complete(load_task)
        assert progress_updater.get_task_progress(process_task) == 50

    def test_progress_error_handling(self, progress_updater):
        """Test error handling during progress updates."""
        task_id = progress_updater.add_task("Error Task", total=100)
        
        # Test invalid task ID
        with pytest.raises(ValueError, match="Invalid task ID"):
            progress_updater.update_progress("invalid_id", advance=10)
        
        # Test negative progress
        with pytest.raises(ValueError, match="Progress cannot be negative"):
            progress_updater.update_progress(task_id, advance=-10)

    def test_progress_cleanup_on_completion(self, progress_updater):
        """Test that progress resources are cleaned up on completion."""
        task_id = progress_updater.add_task("Cleanup Task", total=100)
        progress_updater.update_progress(task_id, advance=100)
        progress_updater.complete_task(task_id)
        
        # Should clean up resources
        assert task_id not in progress_updater.active_tasks

    def test_progress_memory_efficiency(self, progress_updater):
        """Test that progress updates don't cause memory leaks."""
        # Create many short-lived tasks
        for i in range(100):
            task_id = progress_updater.add_task(f"Task {i}", total=10)
            progress_updater.update_progress(task_id, advance=10)
            progress_updater.complete_task(task_id)
        
        # Should not accumulate completed tasks
        assert len(progress_updater.active_tasks) == 0