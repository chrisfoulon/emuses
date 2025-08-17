"""
Pytest configuration and fixtures for EMUSES testing.

This module provides shared fixtures and configuration for all tests,
ensuring proper isolation and cleanup.
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import logging


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables for all tests."""
    # Set environment variables for testing
    os.environ['TESTING_MODE'] = 'true'
    os.environ['RATE_LIMITING_ENABLED'] = 'false'
    
    yield
    
    # Clean up after test
    # Note: We don't unset these as they should persist for the test session


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    temp_dir = tempfile.mkdtemp(prefix="emuses_test_")
    yield Path(temp_dir)
    # Clean up after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_pipeline_config():
    """Mock PipelineConfig to avoid heavy initialization during testing."""
    
    class MockPipelineConfig:
        def __init__(self, *args, **kwargs):
            # Extract basic attributes without heavy processing
            if args and hasattr(args[0], '__dict__'):
                for key, value in vars(args[0]).items():
                    setattr(self, key, value)
            
            for key, value in kwargs.items():
                setattr(self, key, value)
            
            # Set required attributes - use temporary directory for tests
            if not hasattr(self, 'output_folder'):
                import tempfile
                self.output_folder = Path(tempfile.mkdtemp(prefix="emuses_test_"))
            
            self.output_path = Path(self.output_folder)
            self.output_path.mkdir(parents=True, exist_ok=True)
            
            # Mock other required attributes
            self.sigma = getattr(self, 'sigma', None)
            self.fwhm = getattr(self, 'fwhm', None)
            self.outer_folds = getattr(self, 'outer_folds', 5)
            self.optuna_trials = getattr(self, 'optuna_trials', 60)
            self.model_version = getattr(self, 'model_version', "1.0.0")
            self.prefix = getattr(self, 'prefix', "")
            self.umap_jobs = getattr(self, 'umap_jobs', None)
            self.hdbscan_jobs = getattr(self, 'hdbscan_jobs', None)
            self.umap_trials = getattr(self, 'umap_trials', 50)
            self.hdbscan_trials = getattr(self, 'hdbscan_trials', 20)
            
            # Mock computed fields
            self.umap_params = {}
            self.heatmap_params = {}
            self.prediction_params = {}
            
            # Mock required methods that tests might call
            self.load_embeddings = getattr(self, 'load_embeddings', False)
            
        def get_model_io_manager(self):
            """Mock model IO manager."""
            class MockModelIOManager:
                def __init__(self, base_path, version):
                    self.base_path = base_path
                    self.version = version
            return MockModelIOManager(self.output_path / "models", self.model_version)
    
    return MockPipelineConfig


@pytest.fixture
def disable_logging():
    """Disable logging during tests to reduce noise."""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture(scope="session", autouse=True)
def setup_test_session():
    """Set up the entire test session."""
    # Ensure test mode is set at session level
    os.environ['TESTING_MODE'] = 'true'
    os.environ['RATE_LIMITING_ENABLED'] = 'false'
    
    yield
    
    # Session cleanup
    pass


@pytest.fixture(autouse=True)
def mock_atexit_register():
    """Mock atexit.register to prevent pytest hanging issues.
    
    This fixture automatically mocks atexit.register calls during tests
    to prevent multiprocessing logging listeners from preventing clean
    pytest exit. This is a cleaner approach than adding TESTING_MODE
    checks in production code.
    """
    with patch('atexit.register') as mock_register:
        yield mock_register
