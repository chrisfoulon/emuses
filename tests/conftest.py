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
import time
import numpy as np
# NOTE: EMUSESPipeline is deliberately NOT imported here. It pulls in nibabel and the rest
# of the scientific stack, and conftest.py is loaded for *every* pytest invocation — including
# the `fast-tests` CI job, which installs a minimal dependency set on purpose
# (`pip install -e . --no-deps`, see .github/workflows/emuses_tests.yml). A module-level import
# made that job fail at collection with ModuleNotFoundError: nibabel, so no test ran at all.
# It is imported lazily inside the one fixture that needs it.

# Repo root, derived from this file's location (tests/conftest.py -> repo root).
# Never hardcode absolute paths: they break on every machine but the author's.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Root of the large external research datasets (HCP and similar) that a few
# integration tests use. These are not in the repo; point EMUSES_TEST_DATA_ROOT at
# them to enable those tests, otherwise they skip.
EXTERNAL_DATA_ROOT = (
    Path(os.environ["EMUSES_TEST_DATA_ROOT"]).expanduser()
    if os.environ.get("EMUSES_TEST_DATA_ROOT")
    else None
)


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


@pytest.fixture(scope="session")
def emuses_pipeline_results():
    """
    Run EMUSES pipeline with all test_data modes once per session using Python API.
    
    This fixture runs the complete EMUSES pipeline for each test data mode:
    - Single-target regression
    - Multi-target regression  
    - Binary classification
    - Multi-class classification
    
    Results are cached and reused across all tests in the session to avoid
    redundant pipeline execution while enabling realistic integration testing.
    
    Returns:
        dict: Pipeline results with structure:
            {
                'regression': Path,
                'multi_target_regression': Path, 
                'binary_classification': Path,
                'multi_class_classification': Path,
                'session_temp_dir': Path
            }
    """
    # Create session-wide temporary directory
    session_temp_dir = Path(tempfile.mkdtemp(prefix="emuses_session_test_"))
    print(f"📁 Session temp directory: {session_temp_dir}")
    
    # Resolve the repo root from this file's location so the fixture works on any machine
    project_root = PROJECT_ROOT
    test_configs = {
        'regression': {
            'features': str(project_root / 'test_data/features.csv'),
            'scores': str(project_root / 'test_data/regression_scores.csv'),
            'output': session_temp_dir / 'regression_output'
        },
        'multi_target_regression': {
            'features': str(project_root / 'test_data/features.csv'), 
            'scores': str(project_root / 'test_data/regression_scores_multitarget.csv'),
            'output': session_temp_dir / 'multi_target_regression_output'
        }
    }
    
    results = {'session_temp_dir': session_temp_dir}
    
    # Run pipeline for each configuration using Python API
    for mode, config in test_configs.items():
        print(f"\n🔧 Setting up session fixture: Running EMUSES pipeline for {mode}...")
        start_time = time.time()
        
        try:
            # Create pipeline args object
            args = type('Args', (), {})()
            args.input_dataset = config['features']
            args.output_folder = str(config['output'])
            args.scores_dataset = config['scores']
            args.columns_are_features = True
            args.input_normalization = 'robust'
            args.scores_header = None
            args.scores_index_column = None
            args.input_header = None 
            args.input_index_column = None
            args.umap_trials = 1
            args.hdbscan_trials = 1
            args.optim_dict = 'optim_dict_hcp'
            args.prediction_optim_dict = 'quick_train_dict'
            args.optuna_trials = 2  # Minimal for speed
            args.n_jobs = 4
            args.random_state = 42
            args.inference_mode = False
            args.prefix = f"SessionTest_{mode}"
            
            # Additional required attributes based on PipelineConfig
            args.interactive_plot = False
            args.load_embeddings = False
            args.hdbscan_jobs = 4
            args.umap_jobs = 4
            args.test_size = 0.2  # Required for dataset splitting
            args.outer_folds = 5   # Required for cross-validation
            
            # Imported here rather than at module scope — see the note by the imports.
            from emuses.pipelines.emuses_pipeline import EMUSESPipeline

            # Create and run pipeline
            pipeline = EMUSESPipeline(args)
            
            # Run the full pipeline - this is the key method
            pipeline.run()
            
            duration = time.time() - start_time
            print(f"✅ Pipeline completed for {mode} in {duration:.1f}s")
            results[mode] = config['output']
                
        except Exception as e:
            print(f"💥 Pipeline error for {mode}: {e}")
            import traceback
            print(f"Full traceback:\n{traceback.format_exc()}")
            results[mode] = None
    
    print(f"🎯 Session fixture setup complete. Results: {list(results.keys())}")
    
    yield results
    
    # Cleanup session temporary directory
    try:
        shutil.rmtree(session_temp_dir, ignore_errors=True)
        print("🧹 Session fixture cleanup completed")
    except Exception as e:
        print(f"⚠️ Session cleanup warning: {e}")
