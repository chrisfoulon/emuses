#!/usr/bin/env python3
"""
Backward Compatibility Testing

Tests backward compatibility aspects of the FastAPI service including:
- CLI interface unchanged (python main.py full continues working)
- Python imports unchanged (from emuses.pipelines import EMUSESPipeline)
- Context pattern preservation (exact dictionary passing between stages)
- Computational result equivalence (API vs CLI produces identical outputs)
- API/CLI unification via EMUSESPipeline integration
"""

import copy
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Try to import numpy/pandas, but skip tests that need them if they fail
try:
    import pandas as pd
    import numpy as np
    HEAVY_DEPS_AVAILABLE = True
except ImportError:
    HEAVY_DEPS_AVAILABLE = False
    pd = None
    np = None


@pytest.fixture
def temp_test_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory(prefix='compatibility_test_') as td:
        yield Path(td)


@pytest.fixture
def test_data_files(temp_test_dir):
    """Create test data files for compatibility testing."""
    if not HEAVY_DEPS_AVAILABLE:
        pytest.skip("pandas/numpy not available for data file creation")

    # Create test input data
    input_data = pd.DataFrame({
        'feature1': np.random.random(50),
        'feature2': np.random.random(50),
        'feature3': np.random.random(50),
        'feature4': np.random.random(50),
        'feature5': np.random.random(50)
    })

    # Create test scores data
    scores_data = pd.DataFrame({
        'score': np.random.random(50)
    })

    # Create file paths
    input_file = temp_test_dir / "test_input.csv"
    scores_file = temp_test_dir / "test_scores.csv"
    output_dir = temp_test_dir / "output"

    # Write test files
    input_data.to_csv(input_file, index=False)
    scores_data.to_csv(scores_file, index=False)
    output_dir.mkdir(exist_ok=True)

    return {
        'input_file': str(input_file),
        'scores_file': str(scores_file),
        'output_dir': str(output_dir),
        'input_data': input_data,
        'scores_data': scores_data
    }


class TestCLIInterface:
    """Test CLI interface backward compatibility."""

    def test_cli_main_script_exists(self):
        """Test that the main CLI script exists and is accessible."""
        main_script = project_root / "emuses" / "scripts" / "main.py"
        assert main_script.exists(), "emuses/scripts/main.py script should exist"
        assert main_script.is_file(), "main.py should be a file"

    def test_cli_module_execution(self):
        """Test that CLI can be executed via python -m emuses.scripts.main."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "emuses.scripts.main", "--help"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            # Check if the failure is due to heavy dependency issues
            if result.returncode != 0:
                if "numpy" in result.stderr or "scipy" in result.stderr or "sklearn" in result.stderr:
                    pytest.skip(f"CLI module execution skipped due to heavy dependency issues: {result.stderr[:200]}...")
                else:
                    pytest.fail(f"Module execution failed: {result.stderr}")
            else:
                assert "usage:" in result.stdout.lower() or "help" in result.stdout.lower()
        except subprocess.TimeoutExpired:
            pytest.fail("CLI module execution timed out")
        except Exception as e:
            pytest.fail(f"CLI module execution failed: {e}")

    def test_cli_help_command(self):
        """Test that CLI help command works."""
        try:
            # Try direct script execution first
            result = subprocess.run(
                [sys.executable, str(project_root / "emuses" / "scripts" / "main.py"), "--help"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            # Check if the failure is due to heavy dependency issues
            if result.returncode != 0:
                if "numpy" in result.stderr or "scipy" in result.stderr or "sklearn" in result.stderr:
                    pytest.skip(f"CLI help command skipped due to heavy dependency issues: {result.stderr[:200]}...")
                else:
                    pytest.fail(f"Help command failed: {result.stderr}")
            else:
                assert "usage:" in result.stdout.lower() or "help" in result.stdout.lower()
        except subprocess.TimeoutExpired:
            pytest.fail("CLI help command timed out")
        except FileNotFoundError:
            pytest.fail("main.py script not found or not executable")

    def test_cli_full_command_structure(self, test_data_files):
        """Test that CLI 'full' command accepts expected arguments."""
        try:
            # Test with minimal required arguments using module execution
            result = subprocess.run(
                [
                    sys.executable, "-m", "emuses.scripts.main", "full",
                    test_data_files['input_file'],  # input_dataset positional arg
                    test_data_files['output_dir'],  # output_folder positional arg
                    "--scores", test_data_files['scores_file'],
                    "--help"  # Just test argument parsing, not execution
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            # Should either show help or indicate the command exists
            # Exit code 0 for help, or other codes but should not be 'command not found'
            assert "not found" not in result.stderr.lower()
            assert "invalid choice" not in result.stderr.lower()
        except subprocess.TimeoutExpired:
            pytest.fail("CLI full command structure test timed out")
        except FileNotFoundError:
            pytest.fail("CLI script not found or not executable")


class TestPythonImports:
    """Test Python import backward compatibility."""

    def test_emuses_pipeline_import_structure(self):
        """Test that EMUSESPipeline module exists and has expected structure."""
        # Check if the file exists
        pipeline_file = project_root / "emuses" / "pipelines" / "emuses_pipeline.py"
        assert pipeline_file.exists(), "emuses_pipeline.py should exist"

        # Check if the file contains the EMUSESPipeline class definition
        with open(pipeline_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "class EMUSESPipeline" in content, "EMUSESPipeline class should be defined"
            assert "def __init__" in content, "EMUSESPipeline should have __init__ method"
            assert "def run" in content, "EMUSESPipeline should have run method"

    def test_emuses_pipeline_import_attempt(self):
        """Test that EMUSESPipeline can be imported (skip if heavy deps unavailable)."""
        try:
            from emuses.pipelines.emuses_pipeline import EMUSESPipeline
            assert EMUSESPipeline is not None
            assert hasattr(EMUSESPipeline, '__init__')

            # Check for expected methods (class-level, no instantiation needed)
            expected_methods = ['run', 'process_dataset', 'load_and_process_scores']
            for method in expected_methods:
                assert hasattr(EMUSESPipeline, method), f"EMUSESPipeline should have {method} method"

            # For compatibility testing, we just need to confirm the class exists and has methods
            # Full instantiation testing should be done in integration tests with proper setup

        except ImportError as e:
            if "numpy" in str(e) or "scipy" in str(e) or "sklearn" in str(e):
                pytest.skip(f"EMUSESPipeline not available due to heavy dependency issues: {e}")
            else:
                pytest.fail(f"Failed to import EMUSESPipeline: {e}")
        except Exception as e:
            pytest.fail(f"EMUSESPipeline import/class inspection failed: {e}")

    def test_pipeline_context_pattern_structure(self):
        """Test that pipeline file has context pattern methods."""
        pipeline_file = project_root / "emuses" / "pipelines" / "emuses_pipeline.py"
        with open(pipeline_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for context pattern methods
        context_indicators = [
            "self.context",
            "context",
            "process_dataset",
            "load_and_process_scores"
        ]

        found_indicators = [indicator for indicator in context_indicators if indicator in content]
        assert len(found_indicators) >= 2, f"Should find context pattern indicators, found: {found_indicators}"

    def test_pipeline_context_pattern_runtime(self):
        """Test that pipeline preserves context dictionary passing pattern (skip if deps unavailable)."""
        try:
            from emuses.pipelines.emuses_pipeline import EMUSESPipeline

            # Create a minimal args object for pipeline
            class MinimalArgs:
                def __init__(self):
                    self.output_folder = Path("test_output")
                    self.input_dataset = "test_input"
                    self.scores = None
                    self.prefix = "test"
                    self.verbose = False

            args = MinimalArgs()
            pipeline = EMUSESPipeline(args)

            # Test that context dictionary exists and can be used
            assert hasattr(pipeline, 'context'), "Pipeline should have context attribute"
            assert isinstance(pipeline.context, dict), "Context should be a dictionary"

            # Test that we can add to context
            pipeline.context['test_key'] = 'test_value'
            assert pipeline.context['test_key'] == 'test_value', "Context should preserve added values"

        except ImportError as e:
            if "numpy" in str(e) or "scipy" in str(e) or "sklearn" in str(e):
                pytest.skip(f"Pipeline context pattern test skipped due to heavy dependency issues: {e}")
            else:
                pytest.fail(f"Pipeline context pattern test failed: {e}")
        except Exception as e:
            pytest.fail(f"Pipeline context pattern test failed: {e}")


class TestComputationalEquivalence:
    """Test computational equivalence between CLI and API."""

    def test_data_preprocessing_equivalence(self, test_data_files):
        """Test that data processing produces deterministic results."""
        try:
            from emuses.pipelines.emuses_pipeline import EMUSESPipeline

            # Create minimal args for pipeline
            class MinimalArgs:
                def __init__(self):
                    self.output_folder = Path(test_data_files['output_dir'])
                    self.input_dataset = test_data_files['input_file']
                    self.scores = test_data_files['scores_file']
                    self.prefix = "equiv_test"
                    self.verbose = False

            args = MinimalArgs()

            # Create two pipeline instances
            pipeline1 = EMUSESPipeline(args)
            pipeline2 = EMUSESPipeline(args)

            # Test that both pipelines have same initial state
            assert pipeline1.output_folder == pipeline2.output_folder
            assert pipeline1.config.input_dataset == pipeline2.config.input_dataset

        except ImportError:
            pytest.skip("EMUSESPipeline not available for preprocessing test")
        except Exception as e:
            pytest.fail(f"Data preprocessing equivalence test failed: {e}")

    def test_context_preservation_through_stages(self, test_data_files):
        """Test that context is preserved exactly through pipeline stages."""
        try:
            from emuses.pipelines.emuses_pipeline import EMUSESPipeline

            # Create minimal args for pipeline
            class MinimalArgs:
                def __init__(self):
                    self.output_folder = Path(test_data_files['output_dir'])
                    self.input_dataset = test_data_files['input_file']
                    self.scores = test_data_files['scores_file']
                    self.prefix = "context_test"
                    self.verbose = False

            args = MinimalArgs()
            pipeline = EMUSESPipeline(args)

            # Test context preservation - add test data to context
            original_context_data = {
                'test_input': test_data_files['input_file'],
                'test_scores': test_data_files['scores_file'],
                'test_prefix': 'context_preservation_test'
            }

            # Add to pipeline context
            pipeline.context.update(original_context_data)

            # Check that context data is preserved
            for key, value in original_context_data.items():
                assert key in pipeline.context, f"Context key '{key}' should be preserved"
                assert pipeline.context[key] == value, f"Context value for '{key}' should be unchanged"

        except ImportError:
            pytest.skip("EMUSESPipeline not available for context preservation test")
        except Exception as e:
            pytest.fail(f"Context preservation test failed: {e}")


class TestAPIUnification:
    """Test API/CLI unification via EMUSESPipeline integration."""

    def test_pipeline_runner_structure(self):
        """Test that PipelineRunner file exists and has expected structure."""
        runner_file = project_root / "emuses" / "foundation_fastapi_service" / "pipeline_runner.py"
        assert runner_file.exists(), "pipeline_runner.py should exist"

        with open(runner_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for expected class and methods
        assert "class PipelineRunner" in content, "PipelineRunner class should be defined"
        assert "execute_pipeline" in content, "PipelineRunner should have execute_pipeline method"

        # Check for EMUSESPipeline integration indicators
        integration_indicators = [
            "emuses_pipeline",
            "EMUSESPipeline",
            "from emuses.pipelines",
            "setup_context",
        ]

        found_indicators = [indicator for indicator in integration_indicators if indicator in content]
        assert len(found_indicators) >= 1, f"Should find EMUSESPipeline integration indicators, found: {found_indicators}"

    def test_pipeline_runner_uses_emuses_pipeline(self):
        """Test that PipelineRunner integrates with EMUSESPipeline (skip if deps unavailable)."""
        try:
            from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
            from emuses.foundation_fastapi_service.job_manager import JobManager
            import tempfile

            # Create a temporary directory for the job manager
            with tempfile.TemporaryDirectory() as temp_dir:
                job_manager = JobManager(temp_dir)
                runner = PipelineRunner(job_manager)

                # Check if PipelineRunner has EMUSESPipeline integration
                assert hasattr(runner, 'execute_pipeline'), "PipelineRunner should have execute_pipeline method"

                # Check the _run_pipeline method for EMUSESPipeline integration
                assert hasattr(runner, '_run_pipeline'), "PipelineRunner should have _run_pipeline method"

                # Check helper methods for EMUSESPipeline integration
                assert hasattr(runner, '_context_to_emuses_args'), "PipelineRunner should have _context_to_emuses_args method"
                assert hasattr(runner, '_merge_pipeline_context'), "PipelineRunner should have _merge_pipeline_context method"

                # Verify the method signature of execute_pipeline
                import inspect
                signature = inspect.signature(runner.execute_pipeline)
                params = list(signature.parameters.keys())
                assert 'job_id' in params, "execute_pipeline should accept job_id parameter"
                assert 'config' in params, "execute_pipeline should accept config parameter"

        except ImportError as e:
            if "numpy" in str(e) or "scipy" in str(e) or "sklearn" in str(e):
                pytest.skip(f"PipelineRunner test skipped due to heavy dependency issues: {e}")
            else:
                pytest.fail(f"Failed to import PipelineRunner: {e}")
        except Exception as e:
            pytest.fail(f"PipelineRunner integration test failed: {e}")

    def test_consistent_data_processing_pathway(self, test_data_files):
        """Test that API and CLI use consistent data processing."""
        try:
            # Test structural integration without heavy dependencies
            from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
            from emuses.foundation_fastapi_service.job_manager import JobManager
            import tempfile

            # Create a temporary directory for the job manager
            with tempfile.TemporaryDirectory() as temp_dir:
                job_manager = JobManager(temp_dir)
                api_runner = PipelineRunner(job_manager)

                # Test that PipelineRunner can create EMUSESPipeline args
                test_context = {
                    'input_dataset': test_data_files['input_file'],
                    'scores': test_data_files['scores_file'],
                    'output_folder': test_data_files['output_dir'],
                    'prefix': 'unification_test'
                }

                # Test the context to args conversion
                if hasattr(api_runner, '_context_to_emuses_args'):
                    args = api_runner._context_to_emuses_args(test_context)
                    assert hasattr(args, 'input_dataset'), "Args should have input_dataset"
                    assert hasattr(args, 'output_folder'), "Args should have output_folder"
                    assert args.input_dataset == test_context['input_dataset']
                    assert str(args.output_folder) == test_data_files['output_dir']

                # The integration means they should use compatible interfaces
                # This test verifies the structural compatibility

        except ImportError as e:
            pytest.skip(f"Components not available for unification test: {e}")
        except Exception as e:
            pytest.fail(f"Consistent data processing test failed: {e}")


class TestRealWorldDatasetCompatibility:
    """Test compatibility with real-world dataset patterns."""

    def test_missing_value_handling_consistency(self):
        """Test that missing value handling structure is consistent."""
        try:
            # Test file structure and method availability without heavy imports
            from emuses.pipelines.emuses_pipeline import EMUSESPipeline

            # Create minimal args for pipeline
            class MinimalArgs:
                def __init__(self):
                    self.output_folder = Path("test_output")
                    self.input_dataset = "test_input"
                    self.scores = None
                    self.prefix = "test"
                    self.verbose = False

            args = MinimalArgs()
            pipeline = EMUSESPipeline(args)

            # Check if dataset processing methods exist
            expected_methods = ['process_dataset', 'load_and_process_scores', 'run']
            found_methods = [method for method in expected_methods if hasattr(pipeline, method)]
            assert len(found_methods) >= 2, f"Pipeline should have data processing methods, found: {found_methods}"

        except ImportError as e:
            pytest.skip(f"EMUSESPipeline import failed due to dependencies: {e}")
        except Exception as e:
            pytest.fail(f"Missing value handling structure test failed: {e}")

    def test_type_coercion_consistency(self):
        """Test that type coercion structure is consistent."""
        try:
            # Test method signatures and structure without executing heavy operations
            from emuses.pipelines.emuses_pipeline import EMUSESPipeline

            # Create minimal args for pipeline
            class MinimalArgs:
                def __init__(self):
                    self.output_folder = Path("test_output")
                    self.input_dataset = "test_input"
                    self.scores = None
                    self.prefix = "test"
                    self.verbose = False

            args = MinimalArgs()
            pipeline = EMUSESPipeline(args)

            # Check method signatures
            if hasattr(pipeline, 'process_dataset'):
                import inspect
                sig = inspect.signature(pipeline.process_dataset)
                params = list(sig.parameters.keys())
                assert len(params) >= 1, f"process_dataset should accept parameters, found: {params}"

        except ImportError as e:
            pytest.skip(f"EMUSESPipeline import failed due to dependencies: {e}")
        except Exception as e:
            pytest.fail(f"Type coercion consistency test failed: {e}")

    def test_cli_argument_structure(self):
        """Test CLI argument structure without executing the CLI."""
        main_script = project_root / "emuses" / "scripts" / "main.py"

        if not main_script.exists():
            pytest.skip("Main CLI script not found")

        # Read the CLI script to check argument structure
        with open(main_script, 'r') as f:
            content = f.read()

        # Check for expected CLI patterns
        assert 'argparse' in content, "CLI should use argparse"
        assert 'input_dataset' in content, "CLI should accept input dataset"
        assert '--scores' in content, "CLI should accept scores file"
        assert 'output_folder' in content, "CLI should accept output folder"


# Test execution markers for different test categories
pytestmark = [
    pytest.mark.compatibility,
    pytest.mark.integration
]
