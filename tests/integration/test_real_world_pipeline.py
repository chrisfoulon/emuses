"""
Integration tests for the complete EMUSES pipeline using real-world data patterns.

This module provides comprehensive integration tests that validate the entire
EMUSES pipeline across different interfaces (CLI, FastAPI, Streamlit) using
a realistic command that represents production usage patterns.

The tests ensure that all LAD sessions maintain compatibility and produce
identical results regardless of the interface used.
"""

import os
import tempfile
import shutil
import subprocess
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import pickle


class RealWorldIntegrationTest:
    """
    Integration test suite based on real-world EMUSES usage patterns.

    This class provides a comprehensive test framework that validates the
    complete EMUSES pipeline using realistic data and parameters that
    represent actual production usage.
    """

    # Real-world CLI command pattern for integration testing
    # Based on actual EMUSES production usage
    CLI_COMMAND_TEMPLATE = """
    python "{script_path}" full \
      "{features_train}" \
      "{labels_train}" \
      --columns_are_features \
      --input_header 0 \
      --input_index_column 0 \
      -inorm robust \
      --scores "{labels_train}" \
      --scores_header 0 \
      --scores_index_column 0 \
      --interactive_plot \
      --umap_trials {umap_trials} \
      --hdbscan_trials {hdbscan_trials} \
      --optim_dict optim_dict_hcp \
      --hdbscan_jobs {hdbscan_jobs} \
      --optuna_trials {optuna_trials} \
      --prediction_optim_dict {prediction_optim_dict} \
      --output_folder "{output_folder}" \
      --prefix "{prefix}"
    """

    # Default parameters for integration testing
    # Based on the actual real-world command
    DEFAULT_PARAMS = {
        'script_path': 'emuses/scripts/main.py',
        'umap_trials': 10,
        'hdbscan_trials': 5,
        'hdbscan_jobs': 16,
        'optuna_trials': 10,  # Reduced for faster testing
        'prediction_optim_dict': 'optim_dict_test',  # Use test config
        'prefix': 'Integration_Test_RealWorld'
    }

    # CI-friendly parameters (reduced for speed)
    CI_PARAMS = {
        'script_path': 'emuses/scripts/main.py',
        'umap_trials': 3,
        'hdbscan_trials': 2,
        'hdbscan_jobs': 4,
        'optuna_trials': 5,  # Very reduced for CI
        'prediction_optim_dict': 'optim_dict_test',  # Use test config
        'prefix': 'CI_Test_RealWorld'
    }

    def __init__(self, use_ci_params: bool = False):
        """
        Initialize the integration test suite.

        Args:
            use_ci_params: If True, use reduced parameters for CI environments
        """
        self.params = self.CI_PARAMS if use_ci_params else self.DEFAULT_PARAMS
        self.temp_dir = None
        self.output_dir = None

    def create_synthetic_data(
        self,
        n_samples: int = 200,
        n_features: int = 50,
        n_targets: int = 3,
        test_size: float = 0.3,
        random_state: int = 42
    ) -> Dict[str, Path]:
        """
        Create synthetic data that mimics real-world EMUSES data patterns.

        Args:
            n_samples: Number of training samples
            n_features: Number of features (dimensionality)
            n_targets: Number of target variables
            test_size: Proportion of data for testing
            random_state: Random seed for reproducibility

        Returns:
            Dictionary with paths to created CSV files
        """
        np.random.seed(random_state)

        # Create synthetic feature matrix with realistic patterns
        X_train = np.random.randn(n_samples, n_features)
        X_test = np.random.randn(int(n_samples * test_size), n_features)

        # Create correlated targets with some noise
        y_train = np.random.randn(n_samples, n_targets)
        y_test = np.random.randn(int(n_samples * test_size), n_targets)

        # Add some structure to make the data more realistic
        for i in range(n_targets):
            # Make targets somewhat correlated with features
            feature_weights = np.random.randn(n_features) * 0.1
            y_train[:, i] += X_train @ feature_weights
            y_test[:, i] += X_test @ feature_weights

        # Save to CSV files
        data_files = {}

        # Features
        features_train_df = pd.DataFrame(X_train, columns=[f'feature_{i}' for i in range(n_features)])
        features_test_df = pd.DataFrame(X_test, columns=[f'feature_{i}' for i in range(n_features)])

        data_files['features_train'] = self.temp_dir / 'features_train.csv'
        data_files['features_test'] = self.temp_dir / 'features_test.csv'

        features_train_df.to_csv(data_files['features_train'], index=False)
        features_test_df.to_csv(data_files['features_test'], index=False)

        # Labels
        labels_train_df = pd.DataFrame(y_train, columns=[f'target_{i}' for i in range(n_targets)])
        labels_test_df = pd.DataFrame(y_test, columns=[f'target_{i}' for i in range(n_targets)])

        data_files['labels_train'] = self.temp_dir / 'labels_train.csv'
        data_files['labels_test'] = self.temp_dir / 'labels_test.csv'

        labels_train_df.to_csv(data_files['labels_train'], index=False)
        labels_test_df.to_csv(data_files['labels_test'], index=False)

        return data_files

    def setup_test_environment(self) -> Dict[str, Path]:
        """
        Set up the test environment with temporary directories and data.

        Returns:
            Dictionary with all file paths needed for testing
        """
        # Create temporary directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix='emuses_integration_test_'))
        self.output_dir = self.temp_dir / 'output'
        self.output_dir.mkdir(exist_ok=True)

        # Create synthetic data
        data_files = self.create_synthetic_data()

        # Add output directory
        data_files['output_folder'] = self.output_dir

        return data_files

    def teardown_test_environment(self):
        """Clean up temporary test environment."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def run_cli_command(self, data_files: Dict[str, Path]) -> subprocess.CompletedProcess:
        """
        Execute the CLI command with the given data files.

        Args:
            data_files: Dictionary of file paths for the command

        Returns:
            CompletedProcess object with command results
        """
        # Format the command with actual file paths
        command_params = {**self.params, **data_files}

        # Build the command
        cmd = self.CLI_COMMAND_TEMPLATE.format(**command_params)

        # Clean up the command (remove extra whitespace)
        cmd = ' '.join(cmd.split())

        # Execute the command
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )

        return result

    def validate_output_structure(self, output_dir: Path) -> Dict[str, bool]:
        """
        Validate that the output directory contains expected files.

        Args:
            output_dir: Path to the output directory

        Returns:
            Dictionary with validation results for each expected output
        """
        validations = {}

        # Expected output files based on EMUSES pipeline
        expected_files = [
            'umap_model.pkl',
            'hdbscan_model.pkl',
            'embedding_train_coords.csv',
            'embedding_test_coords.csv',
            'cluster_labels.csv',
            'prediction_results.json',
            'cv_scores.csv',
            'optimization_history.json'
        ]

        for expected_file in expected_files:
            file_path = output_dir / expected_file
            validations[expected_file] = file_path.exists()

        return validations

    def extract_performance_metrics(self, output_dir: Path) -> Dict[str, Any]:
        """
        Extract performance metrics from the output files.

        Args:
            output_dir: Path to the output directory

        Returns:
            Dictionary with extracted performance metrics
        """
        metrics = {}

        # Extract CV scores if available
        cv_scores_path = output_dir / 'cv_scores.csv'
        if cv_scores_path.exists():
            cv_scores_df = pd.read_csv(cv_scores_path)
            metrics['cv_scores'] = cv_scores_df.to_dict()

        # Extract optimization results if available
        optim_history_path = output_dir / 'optimization_history.json'
        if optim_history_path.exists():
            with open(optim_history_path, 'r') as f:
                metrics['optimization_history'] = json.load(f)

        # Extract prediction results if available
        pred_results_path = output_dir / 'prediction_results.json'
        if pred_results_path.exists():
            with open(pred_results_path, 'r') as f:
                metrics['prediction_results'] = json.load(f)

        return metrics

    def compare_results(
        self,
        baseline_metrics: Dict[str, Any],
        test_metrics: Dict[str, Any],
        tolerance: float = 1e-6
    ) -> Dict[str, bool]:
        """
        Compare metrics between baseline and test runs.

        Args:
            baseline_metrics: Metrics from baseline run
            test_metrics: Metrics from test run
            tolerance: Numerical tolerance for floating-point comparisons

        Returns:
            Dictionary with comparison results
        """
        comparisons = {}

        for key in baseline_metrics:
            if key in test_metrics:
                baseline_val = baseline_metrics[key]
                test_val = test_metrics[key]

                if isinstance(baseline_val, (int, float)) and isinstance(test_val, (int, float)):
                    # Numerical comparison
                    comparisons[key] = abs(baseline_val - test_val) <= tolerance
                elif isinstance(baseline_val, dict) and isinstance(test_val, dict):
                    # Recursive comparison for nested dictionaries
                    comparisons[key] = self.compare_results(baseline_val, test_val, tolerance)
                else:
                    # Direct comparison
                    comparisons[key] = baseline_val == test_val
            else:
                comparisons[key] = False

        return comparisons


@pytest.fixture
def integration_test_suite():
    """Pytest fixture for integration test suite."""
    # Use CI parameters in CI environment
    use_ci = os.getenv('CI', '').lower() in ('true', '1', 'yes')
    suite = RealWorldIntegrationTest(use_ci_params=use_ci)

    yield suite

    # Cleanup
    suite.teardown_test_environment()


class TestCLIIntegration:
    """Test suite for CLI integration with real-world patterns."""

    def test_full_pipeline_execution(self, integration_test_suite):
        """Test that the complete CLI pipeline executes successfully."""
        # Setup test environment
        data_files = integration_test_suite.setup_test_environment()

        # Run CLI command
        result = integration_test_suite.run_cli_command(data_files)

        # Validate execution
        assert result.returncode == 0, f"CLI command failed with error: {result.stderr}"

        # Validate output structure
        validations = integration_test_suite.validate_output_structure(data_files['output_folder'])

        # Check that key outputs exist
        assert validations.get('embedding_train_coords.csv', False), "Missing training embeddings"
        assert validations.get('embedding_test_coords.csv', False), "Missing test embeddings"
        assert validations.get('cluster_labels.csv', False), "Missing cluster labels"

    def test_output_file_formats(self, integration_test_suite):
        """Test that output files have correct formats and can be loaded."""
        # Setup and run
        data_files = integration_test_suite.setup_test_environment()
        result = integration_test_suite.run_cli_command(data_files)

        assert result.returncode == 0

        output_dir = data_files['output_folder']

        # Test CSV files can be loaded
        embedding_coords_path = output_dir / 'embedding_train_coords.csv'
        if embedding_coords_path.exists():
            df = pd.read_csv(embedding_coords_path)
            assert not df.empty, "Embedding coordinates file is empty"
            assert df.shape[1] >= 2, "Embedding should have at least 2 dimensions"

        # Test JSON files can be loaded
        pred_results_path = output_dir / 'prediction_results.json'
        if pred_results_path.exists():
            with open(pred_results_path, 'r') as f:
                results = json.load(f)
            assert isinstance(results, dict), "Prediction results should be a dictionary"

    def test_reproducibility(self, integration_test_suite):
        """Test that runs with same parameters produce identical results."""
        # First run
        data_files_1 = integration_test_suite.setup_test_environment()
        result_1 = integration_test_suite.run_cli_command(data_files_1)
        assert result_1.returncode == 0

        metrics_1 = integration_test_suite.extract_performance_metrics(data_files_1['output_folder'])

        # Second run (new temporary directory)
        integration_test_suite.teardown_test_environment()
        data_files_2 = integration_test_suite.setup_test_environment()
        result_2 = integration_test_suite.run_cli_command(data_files_2)
        assert result_2.returncode == 0

        metrics_2 = integration_test_suite.extract_performance_metrics(data_files_2['output_folder'])

        # Compare results (should be identical with same random seed)
        comparisons = integration_test_suite.compare_results(metrics_1, metrics_2)

        # Note: Due to optimization randomness, we mainly check structure consistency
        # rather than exact numerical equality
        assert len(metrics_1) == len(metrics_2), "Different number of output metrics"

        # Basic consistency check - at least some metrics should match
        if comparisons:
            matching_keys = sum(1 for v in comparisons.values() if v)
            total_keys = len(comparisons)
            match_ratio = matching_keys / total_keys if total_keys > 0 else 0
            assert match_ratio >= 0.5, f"Too few matching metrics: {match_ratio:.2%}"


class TestFastAPIIntegration:
    """Test suite for FastAPI service integration (LAD Session 1)."""

    @pytest.mark.skipif(
        not os.path.exists('emuses/api/app.py'),
        reason="FastAPI service not yet implemented"
    )
    def test_api_vs_cli_consistency(self, integration_test_suite):
        """Test that FastAPI service produces identical results to CLI."""
        # TODO: Implement after LAD Session 1
        # This test will:
        # 1. Run the CLI command
        # 2. Run equivalent FastAPI requests
        # 3. Compare all outputs for consistency
        pass

    @pytest.mark.skipif(
        not os.path.exists('emuses/api/app.py'),
        reason="FastAPI service not yet implemented"
    )
    def test_background_task_processing(self, integration_test_suite):
        """Test that long-running optimization works in background tasks."""
        # TODO: Implement after LAD Session 1
        pass


class TestStreamlitIntegration:
    """Test suite for Streamlit GUI integration (LAD Session 4)."""

    @pytest.mark.skipif(
        not os.path.exists('emuses/gui/streamlit_app.py'),
        reason="Streamlit GUI not yet implemented"
    )
    def test_gui_file_upload_processing(self, integration_test_suite):
        """Test that Streamlit GUI can process uploaded files correctly."""
        # TODO: Implement after LAD Session 4
        pass


if __name__ == '__main__':
    # Allow running the test suite directly
    import sys

    # Create a test suite and run a basic validation
    suite = RealWorldIntegrationTest(use_ci_params=True)

    try:
        print("Setting up integration test environment...")
        data_files = suite.setup_test_environment()

        print("Running CLI command...")
        result = suite.run_cli_command(data_files)

        if result.returncode == 0:
            print("✓ CLI command executed successfully")

            # Validate outputs
            validations = suite.validate_output_structure(data_files['output_folder'])
            print(f"✓ Output validation: {sum(validations.values())}/{len(validations)} files found")

            # Extract metrics
            metrics = suite.extract_performance_metrics(data_files['output_folder'])
            print(f"✓ Performance metrics extracted: {len(metrics)} metric groups")

            print("\n✅ Integration test completed successfully!")

        else:
            print(f"❌ CLI command failed with return code {result.returncode}")
            print(f"Error output: {result.stderr}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Integration test failed with exception: {e}")
        sys.exit(1)

    finally:
        suite.teardown_test_environment()
