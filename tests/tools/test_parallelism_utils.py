"""
Test suite for enhanced parallelism utilities.

Tests context detection, backend selection, and n_jobs handling
for complex subprocess hierarchies.
"""
import multiprocessing as mp
import pytest
import logging
from unittest.mock import patch, MagicMock
from emuses.tools.parallelism_utils import (
    get_safe_parallel_backend,
    get_safe_n_jobs,
    create_safe_parallel,
    get_process_hierarchy_depth,
    is_subprocess_context,
    configure_parallelism_backend,
)


class TestEnhancedContextDetection:
    """Test enhanced context detection for subprocess hierarchies."""

    def test_get_process_hierarchy_depth_main_process(self):
        """Test process hierarchy depth detection in main process."""
        with patch('multiprocessing.current_process') as mock_process:
            # Mock main process
            mock_process.return_value.name = "MainProcess"
            mock_process.return_value.parent = None

            depth = get_process_hierarchy_depth()
            assert depth == 0

    def test_get_process_hierarchy_depth_single_subprocess(self):
        """Test process hierarchy depth detection in single subprocess."""
        with patch('multiprocessing.current_process') as mock_process:
            # Mock single subprocess
            main_process = MagicMock()
            main_process.name = "MainProcess"
            main_process.parent = None

            current_process = MagicMock()
            current_process.name = "Process-1"
            current_process.parent = main_process

            mock_process.return_value = current_process

            depth = get_process_hierarchy_depth()
            assert depth == 1

    def test_get_process_hierarchy_depth_nested_subprocess(self):
        """Test process hierarchy depth detection in nested subprocesses."""
        with patch('multiprocessing.current_process') as mock_process:
            # Mock nested subprocess hierarchy: Main -> Worker -> SubWorker
            main_process = MagicMock()
            main_process.name = "MainProcess"
            main_process.parent = None

            worker_process = MagicMock()
            worker_process.name = "Worker-1"
            worker_process.parent = main_process

            current_process = MagicMock()
            current_process.name = "SubWorker-1"
            current_process.parent = worker_process

            mock_process.return_value = current_process

            depth = get_process_hierarchy_depth()
            assert depth == 2

    def test_is_subprocess_context_detection(self):
        """Test subprocess context detection utility."""
        with patch('multiprocessing.current_process') as mock_process:
            # Test main process
            mock_process.return_value.name = "MainProcess"
            assert not is_subprocess_context()

            # Test subprocess
            mock_process.return_value.name = "Process-1"
            assert is_subprocess_context()

    def test_enhanced_backend_selection_by_depth(self):
        """Test backend selection considers process hierarchy depth."""
        with patch('emuses.tools.parallelism_utils.get_process_hierarchy_depth') as mock_depth:
            # Test main process (depth 0)
            mock_depth.return_value = 0
            backend = get_safe_parallel_backend()
            assert backend == "loky"

            # Test single subprocess (depth 1)
            mock_depth.return_value = 1
            backend = get_safe_parallel_backend()
            assert backend == "threading"

            # Test nested subprocess (depth 2+)
            mock_depth.return_value = 2
            backend = get_safe_parallel_backend()
            assert backend == "threading"


class TestBackendConfiguration:
    """Test parallelism backend configuration options."""

    def test_configure_parallelism_backend_override(self):
        """Test backend configuration override functionality."""
        # Test setting backend override
        configure_parallelism_backend(force_backend="threading")

        # Should use override regardless of context
        with patch('emuses.tools.parallelism_utils.get_process_hierarchy_depth') as mock_depth:
            mock_depth.return_value = 0  # Main process would normally use loky
            backend = get_safe_parallel_backend()
            assert backend == "threading"

    def test_configure_parallelism_backend_reset(self):
        """Test resetting backend configuration to auto-detection."""
        # Set override first
        configure_parallelism_backend(force_backend="threading")

        # Reset to auto-detection
        configure_parallelism_backend(force_backend=None)

        # Should use normal context detection
        with patch('emuses.tools.parallelism_utils.get_process_hierarchy_depth') as mock_depth:
            mock_depth.return_value = 0
            backend = get_safe_parallel_backend()
            assert backend == "loky"

    def test_configure_parallelism_backend_invalid_backend(self):
        """Test configuration with invalid backend raises error."""
        with pytest.raises(ValueError, match="Invalid backend"):
            configure_parallelism_backend(force_backend="invalid_backend")


class TestEnhancedLogging:
    """Test enhanced logging for debugging multiprocessing issues."""

    def test_context_detection_logging(self, caplog):
        """Test that context detection includes detailed logging."""
        with caplog.at_level(logging.DEBUG):
            with patch('emuses.tools.parallelism_utils.get_process_hierarchy_depth') as mock_depth:
                mock_depth.return_value = 1
                get_safe_parallel_backend()

                # Check that log includes process hierarchy info
                assert "Process hierarchy depth: 1" in caplog.text
                assert "Selected backend: threading" in caplog.text

    def test_n_jobs_adjustment_logging(self, caplog):
        """Test that n_jobs adjustment includes detailed logging."""
        with caplog.at_level(logging.DEBUG):
            with patch('emuses.tools.parallelism_utils.is_subprocess_context') as mock_subprocess:
                mock_subprocess.return_value = True
                safe_n_jobs = get_safe_n_jobs(4)

                # Check that log includes n_jobs adjustment details
                assert "Subprocess detected" in caplog.text
                assert "limiting n_jobs from 4 to 1" in caplog.text
                assert safe_n_jobs == 1


class TestExistingFunctionality:
    """Test that existing functionality is preserved."""

    def test_get_safe_n_jobs_main_process(self):
        """Test n_jobs handling in main process (existing behavior)."""
        with patch('multiprocessing.current_process') as mock_process:
            mock_process.return_value.name = "MainProcess"
            assert get_safe_n_jobs(4) == 4
            assert get_safe_n_jobs(-1) == -1

    def test_get_safe_n_jobs_subprocess(self):
        """Test n_jobs handling in subprocess (existing behavior)."""
        with patch('multiprocessing.current_process') as mock_process:
            mock_process.return_value.name = "Process-1"
            assert get_safe_n_jobs(4) == 1
            assert get_safe_n_jobs(-1) == 1
            assert get_safe_n_jobs(1) == 1  # Already 1, no change

    def test_create_safe_parallel_integration(self):
        """Test create_safe_parallel function integration."""
        from joblib import Parallel

        with patch('emuses.tools.parallelism_utils.get_process_hierarchy_depth') as mock_depth:
            mock_depth.return_value = 0  # Main process

            parallel = create_safe_parallel(n_jobs=4)

            # Should create Parallel object with correct configuration
            assert isinstance(parallel, Parallel)
            assert parallel.n_jobs == 4
            # Backend is configured properly (tested through actual usage)
