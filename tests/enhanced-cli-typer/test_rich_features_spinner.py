"""
Tests for Rich UI spinner animations and memory usage monitoring (Task 5.5).

This module tests spinner animations for long-running operations and
memory usage monitoring to ensure efficient resource utilization.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time
import threading
from rich.console import Console
from rich.spinner import Spinner

from emuses.cli.rich_features import SpinnerManager, MemoryMonitor


class TestSpinnerManager:
    """Test spinner animations with memory monitoring."""

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
    def spinner_manager(self, mock_console):
        """Create a spinner manager instance."""
        return SpinnerManager(console=mock_console)

    def test_spinner_creation(self, spinner_manager):
        """Test that spinner manager initializes correctly."""
        assert spinner_manager is not None
        assert hasattr(spinner_manager, 'console')
        assert hasattr(spinner_manager, 'active_spinners')
        assert hasattr(spinner_manager, 'memory_monitor')

    def test_spinner_start_stop(self, spinner_manager):
        """Test starting and stopping spinners."""
        spinner_id = spinner_manager.start_spinner("Processing data...")
        assert spinner_id is not None
        assert spinner_id in spinner_manager.active_spinners
        
        spinner_manager.stop_spinner(spinner_id)
        assert spinner_id not in spinner_manager.active_spinners

    def test_spinner_update_text(self, spinner_manager):
        """Test updating spinner text."""
        spinner_id = spinner_manager.start_spinner("Initial text")
        
        spinner_manager.update_spinner_text(spinner_id, "Updated text")
        
        # Verify text was updated
        assert spinner_manager.active_spinners[spinner_id]['text'] == "Updated text"
        
        spinner_manager.stop_spinner(spinner_id)

    def test_multiple_concurrent_spinners(self, spinner_manager):
        """Test multiple concurrent spinners."""
        spinner1 = spinner_manager.start_spinner("Task 1")
        spinner2 = spinner_manager.start_spinner("Task 2")
        spinner3 = spinner_manager.start_spinner("Task 3")
        
        assert len(spinner_manager.active_spinners) == 3
        
        spinner_manager.stop_spinner(spinner2)
        assert len(spinner_manager.active_spinners) == 2
        assert spinner2 not in spinner_manager.active_spinners
        
        spinner_manager.stop_all_spinners()
        assert len(spinner_manager.active_spinners) == 0

    def test_spinner_graceful_degradation(self):
        """Test spinner graceful degradation for non-terminal environments."""
        # Create console that doesn't support rich features
        fallback_console = Mock(spec=Console)
        fallback_console.is_terminal = False
        fallback_console.print = Mock()
        
        spinner_manager = SpinnerManager(console=fallback_console)
        
        # Should fall back to simple text output
        spinner_id = spinner_manager.start_spinner("Fallback task")
        assert spinner_id is not None
        
        spinner_manager.stop_spinner(spinner_id)
        # Should have called print for fallback mode
        fallback_console.print.assert_called()

    def test_spinner_memory_monitoring(self, spinner_manager):
        """Test that spinners include memory monitoring."""
        spinner_id = spinner_manager.start_spinner("Memory test", monitor_memory=True)
        
        # Allow some time for memory monitoring
        time.sleep(0.1)
        
        # Check that memory data is being tracked
        assert spinner_id in spinner_manager.active_spinners
        spinner_data = spinner_manager.active_spinners[spinner_id]
        assert 'memory_monitor' in spinner_data
        
        spinner_manager.stop_spinner(spinner_id)

    def test_spinner_different_styles(self, spinner_manager):
        """Test different spinner styles."""
        spinner1 = spinner_manager.start_spinner("Task 1", style="dots")
        spinner2 = spinner_manager.start_spinner("Task 2", style="line")
        spinner3 = spinner_manager.start_spinner("Task 3", style="bouncingBar")
        
        # Verify different styles are applied
        assert spinner_manager.active_spinners[spinner1]['style'] == "dots"
        assert spinner_manager.active_spinners[spinner2]['style'] == "line"
        assert spinner_manager.active_spinners[spinner3]['style'] == "bouncingBar"
        
        spinner_manager.stop_all_spinners()

    def test_spinner_error_handling(self, spinner_manager):
        """Test error handling in spinner operations."""
        # Test invalid spinner ID
        with pytest.raises(ValueError, match="Invalid spinner ID"):
            spinner_manager.stop_spinner("invalid_id")
        
        # Test double stop
        spinner_id = spinner_manager.start_spinner("Test")
        spinner_manager.stop_spinner(spinner_id)
        
        # Should not raise error on double stop
        spinner_manager.stop_spinner(spinner_id)


class TestMemoryMonitor:
    """Test memory usage monitoring."""

    @pytest.fixture
    def memory_monitor(self):
        """Create a memory monitor instance."""
        return MemoryMonitor()

    def test_memory_monitor_creation(self, memory_monitor):
        """Test that memory monitor initializes correctly."""
        assert memory_monitor is not None
        assert hasattr(memory_monitor, 'current_memory')
        assert hasattr(memory_monitor, 'peak_memory')
        assert hasattr(memory_monitor, 'monitoring_active')

    def test_memory_tracking_start_stop(self, memory_monitor):
        """Test starting and stopping memory tracking."""
        memory_monitor.start_monitoring()
        assert memory_monitor.monitoring_active
        
        memory_monitor.stop_monitoring()
        assert not memory_monitor.monitoring_active

    def test_memory_current_usage(self, memory_monitor):
        """Test getting current memory usage."""
        memory_monitor.start_monitoring()
        
        current_mem = memory_monitor.get_current_memory()
        assert isinstance(current_mem, (int, float))
        assert current_mem > 0
        
        memory_monitor.stop_monitoring()

    def test_memory_peak_tracking(self, memory_monitor):
        """Test peak memory tracking."""
        memory_monitor.start_monitoring()
        
        # Allow some time for monitoring
        time.sleep(0.1)
        
        peak_mem = memory_monitor.get_peak_memory()
        assert isinstance(peak_mem, (int, float))
        assert peak_mem > 0
        
        memory_monitor.stop_monitoring()

    def test_memory_threshold_alerts(self, memory_monitor):
        """Test memory threshold alerts."""
        memory_monitor.start_monitoring()
        
        # Set a low threshold to trigger alert
        memory_monitor.set_threshold(1)  # 1 MB
        
        # Should trigger threshold alert
        alerts = memory_monitor.get_alerts()
        assert len(alerts) > 0
        
        memory_monitor.stop_monitoring()

    def test_memory_monitoring_thread_safety(self, memory_monitor):
        """Test that memory monitoring is thread-safe."""
        memory_monitor.start_monitoring()
        
        def access_memory():
            for _ in range(10):
                memory_monitor.get_current_memory()
                time.sleep(0.01)
        
        # Run multiple threads accessing memory monitor
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=access_memory)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        memory_monitor.stop_monitoring()

    def test_memory_statistics(self, memory_monitor):
        """Test memory statistics calculation."""
        memory_monitor.start_monitoring()
        
        # Allow some time for data collection
        time.sleep(0.2)
        
        stats = memory_monitor.get_statistics()
        assert 'current' in stats
        assert 'peak' in stats
        assert 'average' in stats
        assert 'samples' in stats
        
        memory_monitor.stop_monitoring()

    def test_memory_cleanup_on_stop(self, memory_monitor):
        """Test that memory monitor cleans up resources on stop."""
        memory_monitor.start_monitoring()
        
        # Allow some monitoring
        time.sleep(0.1)
        
        memory_monitor.stop_monitoring()
        
        # Should clean up monitoring thread
        assert not memory_monitor.monitoring_active