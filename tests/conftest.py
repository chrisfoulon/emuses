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
def _isolate_cwd(tmp_path, monkeypatch):
    """
    Run every test in a throwaway directory instead of the repo root.

    Tests that invoke the CLI create whatever output folder they are given, relative to
    the current working directory. Run from the repo root, that litters the tree — and on
    2026-07-31 nine such directories were committed by accident, with names like
    ``$(whoami)_output`` and ``` `cat /etc/passwd` ``` because the security tests pass
    shell-injection payloads as output paths.

    Safe to apply globally: no test refers to ``test_data/`` by bare relative path (they
    all derive from PROJECT_ROOT or __file__), and the handful that touch the cwd either
    save and restore it themselves or patch ``Path.cwd``.

    A test that genuinely needs the real repo root can opt out with
    ``@pytest.mark.usefixtures("repo_cwd")``.
    """
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def repo_cwd(monkeypatch):
    """Opt back in to running from the repo root, for tests that require it."""
    monkeypatch.chdir(PROJECT_ROOT)
    return PROJECT_ROOT


# Entries that legitimately appear in the repo root during a test run.
_POLLUTION_ALLOWLIST = {
    ".pytest_cache",
    ".coverage",
    "htmlcov",
    ".hypothesis",
    "__pycache__",
}


@pytest.fixture(scope="session", autouse=True)
def _no_repo_pollution():
    """
    Fail the session if tests leave new files in the repo root.

    The backstop behind _isolate_cwd. Silent litter is how nine injection-named
    directories ended up tracked in git without anyone noticing; this makes the next
    occurrence a visible test failure instead.
    """
    before = set(os.listdir(PROJECT_ROOT))

    yield

    new = {
        name for name in os.listdir(PROJECT_ROOT)
        if name not in before
        and name not in _POLLUTION_ALLOWLIST
        and not name.startswith(".coverage")
    }
    if new:
        pytest.fail(
            "Tests polluted the repo root with: "
            + ", ".join(sorted(repr(n) for n in new))
            + ". Write to tmp_path instead of the working directory.",
            pytrace=False,
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
            # `scores`, not `scores_dataset`. The latter is the FastAPI service-layer name,
            # translated to args.scores in pipeline_runner.py before the pipeline sees it
            # (see pipeline_runner.py:133). Setting the service name here left
            # PipelineConfig.scores at its default of None, so no scores were ever loaded and
            # split_dataset() raised TypeError on a None. PipelineConfig copies unknown
            # attributes verbatim, so the wrong name failed silently rather than erroring.
            args.scores = config['scores']
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
            # Deliberately empty. UMAPStage writes f"{prefix}embeddings.npy" and UMAP_utils
            # writes f"{pref}_input_matrix.npy", while the registry's completeness check
            # (ModelIOManager._validate_emuses_folder_structure) looks for exactly
            # "embeddings.npy" and "input_matrix.npy". A prefix therefore produces a folder
            # the registry rejects. The two modes already write to separate output folders,
            # so the prefix bought nothing here.
            args.prefix = ""
            
            # Additional required attributes based on PipelineConfig
            args.interactive_plot = False
            args.load_embeddings = False
            args.hdbscan_jobs = 4
            args.umap_jobs = 4
            args.test_size = 0.2  # Required for dataset splitting
            args.outer_folds = 5   # Required for cross-validation
            
            # Imported here rather than at module scope — see the note by the imports.
            from emuses.pipelines.emuses_pipeline import EMUSESPipeline
            from emuses.pipelines.heatmap_stage import HeatmapStage
            from emuses.pipelines.umap_stage import UMAPStage

            # Create and run pipeline
            pipeline = EMUSESPipeline(args)

            # Stages are the caller's responsibility: EMUSESPipeline.run() iterates
            # self.stages, which add_stage() populates and nothing else does. Without this
            # the fixture ran an empty stage list and produced no model. Wiring mirrors
            # PipelineRunner._run_pipeline_in_process (pipeline_runner.py:~424), which is
            # what the service uses to produce a complete training folder.
            pipeline.add_stage(UMAPStage(pipeline.config))
            pipeline.add_stage(
                HeatmapStage(
                    pipeline.config, pipeline.context.get("output_format_info")
                )
            )

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


@pytest.fixture(scope="session")
def real_emuses_model_source(emuses_pipeline_results):
    """Path to a genuine complete EMUSES output folder, produced by a real run.

    Registry fixtures used to hand-build a directory holding a bare sklearn
    ``Pipeline`` and call it a model. ADR 2.1 is explicit that an EMUSES model is
    an *entire output folder* - UMAP, HDBSCAN, prediction pipelines, scalers and
    metadata, trained together - and that components are not separable. The
    registry was right to reject those directories; the fixtures were wrong.

    Guardrail G009 says not to invent what real data looks like, so this does not
    assemble a folder by hand to satisfy the validator. It takes the folder a
    real pipeline run produced and asserts it validates, which means the check
    and the pipeline are held to each other rather than to a fixture author's
    guess about the format.

    Session-scoped: the pipeline runs once. Use ``real_emuses_model`` for a
    writable per-test copy.
    """
    folder = emuses_pipeline_results.get("regression")
    if folder is None:
        pytest.fail(
            "The session pipeline fixture did not produce a regression model. It "
            "logs the pipeline traceback to stdout and stores None on failure, so "
            "run with -s to see why.",
            pytrace=False,
        )

    folder = Path(folder)
    if not folder.is_dir():
        pytest.fail(f"Pipeline reported success but {folder} is not a directory.",
                    pytrace=False)

    from emuses.tools.model_io import ModelIOManager

    # base_path is where the manager keeps its own metadata, not the model under
    # test; give it a scratch dir so validation does not write into the fixture.
    manager = ModelIOManager(base_path=folder.parent / "_io_manager_scratch")
    validation = manager.validate_model(folder)
    if not validation.is_complete_model:
        pytest.fail(
            f"A real pipeline run produced {folder}, but the registry does not "
            f"accept it as a complete EMUSES model: {validation.validation_errors}. "
            "That is a genuine disagreement between what the pipeline writes and "
            "what the registry requires - fix that, do not relax the validator.",
            pytrace=False,
        )
    return folder


@pytest.fixture
def real_emuses_model(real_emuses_model_source, tmp_path):
    """A writable per-test copy of a genuine complete EMUSES model folder.

    Tests install, mutate and delete these, so each gets its own copy rather
    than sharing the session's folder.
    """
    destination = tmp_path / "emuses_model"
    shutil.copytree(real_emuses_model_source, destination)
    return destination


@pytest.fixture(scope="session")
def real_emuses_model_alt_source(emuses_pipeline_results):
    """A second, genuinely different complete EMUSES model.

    The session fixture trains a single-target and a multi-target run. Using the
    multi-target one here means tests needing two models get two that really
    differ, rather than two copies of one folder - which the registry would
    correctly identify as duplicates and refuse.
    """
    folder = emuses_pipeline_results.get("multi_target_regression")
    if folder is None or not Path(folder).is_dir():
        pytest.fail(
            "The session pipeline fixture did not produce a multi_target_regression "
            "model. Run with -s to see the pipeline traceback.",
            pytrace=False,
        )
    return Path(folder)


@pytest.fixture
def real_emuses_model_alt(real_emuses_model_alt_source, tmp_path):
    """A writable per-test copy of the second complete EMUSES model."""
    destination = tmp_path / "emuses_model_alt"
    shutil.copytree(real_emuses_model_alt_source, destination)
    return destination
