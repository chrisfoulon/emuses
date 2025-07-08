#!/usr/bin/env python3
"""
Test to verify that logging configuration doesn't cause pytest to hang during cleanup.
This test validates that the pytest fixture approach properly handles atexit registration
without polluting production code with testing checks.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from emuses.pipelines.pipeline_config import PipelineConfig


class TestLoggingCleanup:
    """Test that logging setup is compatible with pytest cleanup."""
    
    def test_logging_setup_with_mocked_atexit_register(self):
        """Test that logging configuration works with mocked atexit.register."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # The atexit.register should be mocked by conftest.py fixture
            config = PipelineConfig(
                output_folder=tmp_dir,
                umap_trials=2,
                hdbscan_trials=2,
                optuna_trials=2
            )
            
            # Verify logging was configured
            assert config.output_path.exists()
            log_dir = config.output_path / "log"
            assert log_dir.exists()
            
            # This test passes if we get here without pytest hanging
            # The atexit.register call should be mocked by the fixture
            assert True
    
    def test_production_logging_still_uses_atexit_registration(self):
        """Test that production code still uses atexit registration when not mocked."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Explicitly test without the conftest.py mock (by patching it away)
            with patch('emuses.pipelines.pipeline_config.atexit.register') as mock_atexit:
                config = PipelineConfig(
                    output_folder=tmp_dir,
                    umap_trials=2,
                    hdbscan_trials=2,
                    optuna_trials=2
                )
                
                # Verify atexit.register was called in production code
                mock_atexit.assert_called_once()
                
                # Verify logging was configured
                assert config.output_path.exists()
                log_dir = config.output_path / "log"
                assert log_dir.exists()
    
    def test_logging_cleanup_preserves_functionality(self):
        """Test that the logging approach preserves all expected functionality."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = PipelineConfig(
                output_folder=tmp_dir,
                umap_trials=2,
                hdbscan_trials=2,
                optuna_trials=2
            )
            
            # Check that logging directory and files are created
            log_dir = config.output_path / "log"
            assert log_dir.exists()
            
            # Check that arguments are saved
            import json
            args_files = list(log_dir.glob("arguments_*.json"))
            assert len(args_files) > 0, "Arguments file should be created"
            
            # Verify args file contains expected data
            with open(args_files[0], 'r') as f:
                args_data = json.load(f)
                assert args_data["umap_trials"] == 2
                assert "datetime" in args_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
