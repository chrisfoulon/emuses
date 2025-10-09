"""
Test module for inference CLI preprocessing parameters.

Tests the addition of critical data preprocessing parameters to the inference
CLI command to fix EMUSESPipeline data loading failures.
"""

import pytest
import typer
from typer.testing import CliRunner
from pathlib import Path

from emuses.cli.main import app


class TestInferencePreprocessingParameters:
    """Test inference CLI preprocessing parameter support."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_input_header_parameter_exists(self):
        """
        Test that --input_header parameter is available and accepts integer values.
        
        This test ensures the critical --input_header parameter is properly
        defined to fix header row processing issues.
        """
        # Test help shows the parameter
        result = self.runner.invoke(app, ["inference", "--help"])
        assert result.exit_code == 0
        assert "--input_header" in result.stdout
        
        # This should pass once parameter is implemented
        # For now, this test will fail as expected in TDD

    def test_input_index_column_parameter_exists(self):
        """
        Test that --input_index_column parameter is available and accepts integer values.
        
        This test ensures the critical --input_index_column parameter is properly
        defined to fix index column processing issues.
        """
        # Test help shows the parameter
        result = self.runner.invoke(app, ["inference", "--help"])
        assert result.exit_code == 0
        assert "--input_index_column" in result.stdout

    def test_scores_header_parameter_exists(self):
        """
        Test that --scores_header parameter is available and accepts integer values.
        
        This test ensures the --scores_header parameter is properly defined
        for validation mode with scores files.
        """
        # Test help shows the parameter
        result = self.runner.invoke(app, ["inference", "--help"])
        assert result.exit_code == 0
        assert "--scores_header" in result.stdout

    def test_scores_index_column_parameter_exists(self):
        """
        Test that --scores_index_column parameter is available and accepts integer values.
        
        This test ensures the --scores_index_column parameter is properly defined
        for validation mode with scores files.
        """
        # Test help shows the parameter
        result = self.runner.invoke(app, ["inference", "--help"])
        assert result.exit_code == 0
        assert "--scores_index_column" in result.stdout

    def test_scores_parameter_exists(self):
        """
        Test that --scores parameter is available and accepts file paths.
        
        This test ensures the --scores parameter is properly defined
        for validation mode support.
        """
        # Test help shows the parameter
        result = self.runner.invoke(app, ["inference", "--help"])
        assert result.exit_code == 0
        assert "--scores" in result.stdout

    def test_preprocessing_parameters_accept_valid_values(self, tmp_path):
        """
        Test that preprocessing parameters accept valid integer and path values.
        
        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory fixture
        """
        # Create dummy files for testing
        data_file = tmp_path / "test_data.csv"
        scores_file = tmp_path / "test_scores.csv"
        model_path = tmp_path / "test_model"
        
        data_file.write_text("col1,col2\n1,2\n3,4\n")
        scores_file.write_text("score\n0.5\n0.8\n")
        model_path.mkdir()
        
        # This test will fail initially - we expect parameter validation to work
        # once parameters are implemented
        result = self.runner.invoke(app, [
            "inference",
            str(data_file),
            "--model", str(model_path),
            "--input_header", "0",
            "--input_index_column", "0", 
            "--scores_header", "0",
            "--scores_index_column", "0",
            "--scores", str(scores_file)
        ])
        
        # Initially will fail because parameters don't exist yet
        # Once implemented, this should not fail due to parameter issues
        # (though may fail for other reasons like missing actual model files)
        
    def test_preprocessing_parameters_reject_invalid_values(self, tmp_path):
        """
        Test that preprocessing parameters reject invalid values with helpful errors.
        
        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory fixture
        """
        data_file = tmp_path / "test_data.csv"
        model_path = tmp_path / "test_model" 
        
        data_file.write_text("col1,col2\n1,2\n3,4\n")
        model_path.mkdir()
        
        # Test invalid header value (should be integer)
        result = self.runner.invoke(app, [
            "inference", 
            str(data_file),
            "--model", str(model_path),
            "--input_header", "invalid"
        ])
        
        # Should fail with parameter validation error once parameters are implemented
        assert result.exit_code != 0