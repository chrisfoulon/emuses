"""
Integration tests for CLI and API parallelism configuration.

Tests the end-to-end parallelism behavior across CLI and service execution modes,
ensuring proper backend selection and context detection in different subprocess
architectures.
"""

import asyncio
import multiprocessing as mp
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emuses.tools.parallelism_utils import (
    get_safe_parallel_backend,
    get_safe_n_jobs,
    configure_parallelism_backend,
)


class TestCLIParallelismIntegration:
    """Test CLI parallelism configuration and execution."""

    def test_cli_configures_main_process_context(self):
        """Test that CLI properly configures main process parallelism context."""
        # Import the CLI function
        from emuses.cli.main import _full_async
        
        # Mock the actual pipeline execution to isolate parallelism config
        with patch('emuses.cli.main._execute_via_unified_service') as mock_execute:
            mock_execute.return_value = None
            
            # Mock the components to avoid initialization overhead
            with patch('emuses.cli.main.StatusRenderer'), \
                 patch('emuses.cli.main.ProgressTracker'):
                
                # Test that parallelism is configured correctly in CLI context
                original_backend = get_safe_parallel_backend()
                
                # Run the CLI function
                asyncio.run(_full_async(
                    output_folder=Path(tempfile.mkdtemp()),
                    input_dataset=Path("test.csv"),
                    use_service=False
                ))
                
                # Verify parallelism backend selection
                # In main process context, should prefer loky backend
                backend = get_safe_parallel_backend()
                
                # Since we're in main process with good environment, should get loky
                assert backend in ['loky', 'threading'], f"Expected loky or threading, got {backend}"

    def test_cli_passes_n_jobs_correctly(self):
        """Test that CLI properly passes n_jobs parameter through configuration."""
        from emuses.cli.main import _convert_typer_args_to_service_config
        
        # Test conversion of CLI args to service config
        config = _convert_typer_args_to_service_config(
            n_jobs=4,
            hdbscan_jobs=2,
            umap_jobs=6,
            output_folder=Path("/tmp/test")
        )
        
        assert config['n_jobs'] == 4
        assert config['hdbscan_jobs'] == 2
        assert config['umap_jobs'] == 6
        assert config['output_folder'] == "/tmp/test"

    def test_cli_service_execution_flow(self):
        """Test the CLI to service execution flow for parallelism."""
        from emuses.cli.main import _execute_via_unified_service
        
        # Mock service components
        with patch('emuses.cli.service_manager.ServiceManager') as mock_manager, \
             patch('emuses.cli.main._start_local_service') as mock_start, \
             patch('emuses.cli.main._wait_for_service_ready') as mock_wait, \
             patch('emuses.cli.main._execute_via_remote_service') as mock_execute, \
             patch('emuses.cli.main._stop_local_service') as mock_stop:
            
            # Configure mocks
            mock_manager.return_value.find_available_port.return_value = 8001
            mock_start.return_value = Mock()
            mock_wait.return_value = True
            mock_execute.return_value = None
            
            # Mock components
            status_renderer = Mock()
            progress_tracker = Mock()
            
            config = {'n_jobs': 4, 'output_folder': '/tmp/test'}
            
            # Test unified service execution
            asyncio.run(_execute_via_unified_service(
                config, status_renderer, progress_tracker
            ))
            
            # Verify service lifecycle
            mock_start.assert_called_once()
            mock_wait.assert_called_once()
            mock_execute.assert_called_once()
            mock_stop.assert_called_once()


class TestServiceParallelismIntegration:
    """Test service parallelism configuration and execution."""

    def test_pipeline_runner_configures_worker_context(self):
        """Test that PipelineRunner configures worker process parallelism context."""
        import contextlib

        from emuses.foundation_fastapi_service import pipeline_runner as pipeline_runner_module
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

        # Mock dependencies
        job_manager = Mock()

        runner = PipelineRunner(job_manager)

        # Mock the EMUSESPipeline to avoid actual execution
        with patch('emuses.foundation_fastapi_service.pipeline_runner.EMUSESPipeline') as mock_pipeline:
            mock_pipeline_instance = Mock()
            mock_pipeline_instance.context = {}
            mock_pipeline.return_value = mock_pipeline_instance

            # Record what the *pipeline body* sees, not just what the scope was asked for.
            # Asserting that `parallelism_backend("threading")` was entered says nothing about
            # whether the value is visible where `create_safe_parallel` is actually called; a
            # per-thread or per-task mechanism could be in force at the scope and invisible one
            # frame deeper. This is the positive control for that.
            observed_in_body = []

            def _record_and_finish(*_args, **_kwargs):
                from emuses.tools.parallelism_utils import (
                    get_safe_parallel_backend,
                )

                observed_in_body.append(get_safe_parallel_backend())
                return {'status': 'completed'}

            mock_pipeline_instance.run.side_effect = _record_and_finish
            
            # Phase 1B1 replaced the process-wide
            # `configure_parallelism_backend(force_backend="threading")` call with a
            # scoped `parallelism_backend("threading")` context manager, because the
            # old one wrote global state that production never restored. This test
            # still asserted the old call and was invisible: a stale import in this
            # module broke its collection entirely. It now checks both halves of that
            # change -- the backend chosen, and that it is put back afterwards.
            from emuses.tools import parallelism_utils

            real_backend = parallelism_utils.parallelism_backend
            requested = []
            inside = []

            @contextlib.contextmanager
            def spy(backend):
                requested.append(backend)
                with real_backend(backend):
                    inside.append(parallelism_utils._FORCED_BACKEND.get())
                    yield

            before = parallelism_utils._FORCED_BACKEND.get()
            with patch.object(pipeline_runner_module, 'parallelism_backend', spy):
                context = {
                    'config': {
                        'output_folder': '/tmp/test',
                        'n_jobs': 4
                    }
                }

                runner._run_pipeline_in_process(context, 0.75)

            assert requested == ["threading"]
            assert inside == ["threading"], "the backend was not in force inside the scope"
            assert observed_in_body == ["threading"], (
                f"the scope was entered, but the pipeline body saw "
                f"{observed_in_body!r} - the override is not reaching the depth where "
                f"create_safe_parallel is called"
            )
            assert parallelism_utils._FORCED_BACKEND.get() == before, (
                "parallelism_backend leaked its override past the scope, which is exactly "
                "what the context manager exists to prevent"
            )
            mock_pipeline.assert_called_once()

    def test_context_to_emuses_args_preserves_n_jobs(self):
        """Test that context conversion preserves n_jobs parameters."""
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
        
        job_manager = Mock()
        runner = PipelineRunner(job_manager)
        
        context = {
            'config': {
                'output_folder': '/tmp/test',
                'n_jobs': 8,
                'hdbscan_jobs': 4,
                'umap_jobs': 2
            }
        }
        
        args = runner._context_to_emuses_args(context)
        
        assert args.n_jobs == 8
        assert args.hdbscan_jobs == 4
        assert args.umap_jobs == 2
        assert str(args.output_folder) == '/tmp/test'

    # test_process_hierarchy_detection_in_service was removed (2026-08-23), not
    # skipped. It called get_process_hierarchy_depth(), which Phase 1B1 deleted
    # because it walked `multiprocessing.current_process().parent` -- an
    # attribute multiprocessing.Process does not have, so it always returned 0
    # and backend detection never worked. The test could not have caught that:
    # it mocked current_process with a Mock, which fabricates the missing
    # attribute, so it asserted against an object model that does not exist.
    # Its stale import was breaking collection of the whole suite.
    # Replaced by tests/tools/test_parallelism_utils.py, which calls
    # is_subprocess_context() in a real subprocess.


class TestEndToEndParallelism:
    """End-to-end parallelism integration tests."""

    def test_full_pipeline_n_jobs_flow(self):
        """Test that n_jobs flows correctly through CLI -> Service -> Pipeline."""
        # This is a comprehensive integration test
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Mock input dataset
            input_csv = output_folder / "test_input.csv"
            input_csv.write_text("col1,col2\n1,2\n3,4\n")
            
            # Test configuration flow
            from emuses.cli.main import _convert_typer_args_to_service_config
            
            config = _convert_typer_args_to_service_config(
                output_folder=output_folder,
                input_dataset=input_csv,
                n_jobs=4,
                hdbscan_jobs=2
            )
            
            assert config['n_jobs'] == 4
            assert config['hdbscan_jobs'] == 2
            
            # Test service context conversion
            from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
            
            job_manager = Mock()
            runner = PipelineRunner(job_manager)
            
            service_context = {
                'config': config,
                'input_dataset': str(input_csv)
            }
            
            args = runner._context_to_emuses_args(service_context)
            
            # Verify n_jobs preservation
            assert args.n_jobs == 4
            assert args.hdbscan_jobs == 2

    def test_parallelism_backend_selection_in_different_contexts(self):
        """Test parallelism backend selection in different execution contexts."""
        # Test main process context (CLI)
        configure_parallelism_backend(force_backend=None)
        main_backend = get_safe_parallel_backend()
        
        # Test forced threading context (service worker)
        configure_parallelism_backend(force_backend="threading")
        worker_backend = get_safe_parallel_backend()
        
        assert worker_backend == "threading"
        
        # Reset to default
        configure_parallelism_backend(force_backend=None)

    def test_safe_n_jobs_calculation_in_contexts(self):
        """Test safe n_jobs calculation in different subprocess contexts."""
        # Test with various n_jobs values
        test_cases = [-1, 1, 4, 8]
        
        for n_jobs in test_cases:
            safe_n_jobs = get_safe_n_jobs(n_jobs)
            
            # Should always return valid n_jobs >= 1 or -1 (which means use all cores)
            assert safe_n_jobs >= 1 or safe_n_jobs == -1, f"Invalid n_jobs {safe_n_jobs} for input {n_jobs}"
            
            # Should not exceed system CPU count (unless -1 which means use all cores)
            if safe_n_jobs != -1:
                assert safe_n_jobs <= mp.cpu_count(), f"n_jobs {safe_n_jobs} exceeds CPU count"


@pytest.mark.integration
class TestRealWorldIntegration:
    """Real-world integration scenarios."""

    @pytest.mark.skipif(not sys.platform.startswith('linux'), reason="Linux-specific test")  
    def test_no_n_jobs_warnings_in_integration(self, capfd):
        """Integration test to verify no 'setting n_jobs=1' warnings appear."""
        # This test would require a minimal pipeline run
        # For now, test the parallelism utilities don't generate warnings
        
        # Configure different contexts and verify no warnings
        configure_parallelism_backend(force_backend="threading")
        backend = get_safe_parallel_backend()
        safe_n_jobs = get_safe_n_jobs(-1)
        
        # Capture any warnings/output
        captured = capfd.readouterr()
        
        # Should not contain the problematic warning
        assert "setting n_jobs=1" not in captured.out
        assert "setting n_jobs=1" not in captured.err
        
        # Reset
        configure_parallelism_backend(force_backend=None)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])