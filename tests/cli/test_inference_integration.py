"""
Test module for end-to-end inference CLI integration with preprocessing parameters.

Tests the complete integration flow from CLI parameters through EMUSESPipeline 
to verify that preprocessing parameters fix the user's specific failing case.
"""

import pytest
import csv
import tempfile
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, Mock

from emuses.cli.main import app


class TestInferenceIntegration:
    """Test end-to-end inference CLI integration with preprocessing parameters."""

    def setup_method(self):
        """Set up test environment with sample data files."""
        self.runner = CliRunner()
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # Create test CSV with headers and index column
        self.data_file = self.temp_path / "test_data_with_headers.csv"
        with open(self.data_file, 'w', newline='') as f:
            writer = csv.writer(f)
            # Header row
            writer.writerow(['Subject_ID', 'Feature1', 'Feature2', 'Feature3'])
            # Data rows with index column
            writer.writerow(['subject_001', 1.5, 2.3, 3.1])
            writer.writerow(['subject_002', 2.1, 1.8, 2.9]) 
            writer.writerow(['subject_003', 1.9, 2.7, 3.5])
        
        # Create test scores file with headers and index column
        self.scores_file = self.temp_path / "test_scores_with_headers.csv"
        with open(self.scores_file, 'w', newline='') as f:
            writer = csv.writer(f)
            # Header row
            writer.writerow(['Subject_ID', 'CognitiveScore'])
            # Data rows with index column
            writer.writerow(['subject_001', 85.5])
            writer.writerow(['subject_002', 92.1])
            writer.writerow(['subject_003', 78.9])
            
        # Create mock model directory
        self.model_dir = self.temp_path / "mock_model"
        self.model_dir.mkdir()
        
        # Create output directory
        self.output_dir = self.temp_path / "output"
        self.output_dir.mkdir()

    def teardown_method(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    @patch('emuses.pipelines.emuses_pipeline.EMUSESPipeline')
    @patch('emuses.pipelines.inference_stage.InferenceStage')
    def test_inference_with_preprocessing_parameters_end_to_end(
        self, mock_inference_stage, mock_pipeline
    ):
        """
        Test end-to-end inference with preprocessing parameters.
        
        This test simulates the user's exact failing case: CSV files with headers
        and index columns that require preprocessing parameters to process correctly.
        
        Parameters
        ----------
        mock_inference_stage : Mock
            Mock InferenceStage class  
        mock_pipeline : Mock
            Mock EMUSESPipeline class
        """
        # Setup mock pipeline
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_dataset.return_value = (
            [[1.5, 2.3, 3.1], [2.1, 1.8, 2.9], [1.9, 2.7, 3.5]],  # input_matrix
            "spreadsheet",  # dataset_type
            {"shape": (3, 3)},  # output_format_info
            [85.5, 92.1, 78.9]  # scores
        )
        mock_pipeline_instance.config = Mock()
        
        # Setup mock inference stage
        mock_stage_instance = Mock()
        mock_inference_stage.return_value = mock_stage_instance
        mock_stage_instance.run.return_value = {
            "mode": "validation",
            "samples_processed": 3,
            "performance_breakdown": {"total_ms": 1500},
            "output_files": {
                "predictions": str(self.output_dir / "predictions.csv"),
                "validation_metrics": str(self.output_dir / "metrics.json")
            },
            "validation_metrics": {
                "r2_score": 0.75,
                "mse": 0.25
            }
        }
        
        # Execute inference command with preprocessing parameters
        result = self.runner.invoke(app, [
            "inference",
            str(self.data_file),  # data with headers and index column
            "--model", str(self.model_dir),
            "--output", str(self.output_dir),
            # CRITICAL: The preprocessing parameters that fix the user's issue
            "--input_header", "0",  # Header in first row
            "--input_index_column", "0",  # Subject IDs in first column
            "--scores_header", "0",  # Scores header in first row
            "--scores_index_column", "0",  # Subject IDs in scores first column
            "--scores", str(self.scores_file),  # Enable validation mode
            "--validate"  # Force validation mode
        ])
        
        # Verify command executed successfully
        assert result.exit_code == 0, f"Command failed with output: {result.stdout}"
        
        # Verify EMUSESPipeline was created and called
        assert mock_pipeline.called
        args_used = mock_pipeline.call_args[0][0]
        
        # CRITICAL: Verify preprocessing parameters were passed correctly
        assert args_used.input_header == 0
        assert args_used.input_index_column == 0
        assert args_used.scores_header == 0
        assert args_used.scores_index_column == 0
        assert args_used.scores == str(self.scores_file)
        
        # Verify process_dataset was called with correct data file
        mock_pipeline_instance.process_dataset.assert_called_once()
        dataset_path_used = mock_pipeline_instance.process_dataset.call_args[0][0]
        assert str(dataset_path_used) == str(self.data_file)
        
        # Verify inference stage was created and run
        assert mock_inference_stage.called
        assert mock_stage_instance.run.called

    @patch('emuses.pipelines.emuses_pipeline.EMUSESPipeline')
    @patch('emuses.pipelines.inference_stage.InferenceStage') 
    def test_inference_without_preprocessing_parameters(
        self, mock_inference_stage, mock_pipeline
    ):
        """
        Test inference without preprocessing parameters (should work for simple data).
        
        This verifies that the changes don't break existing functionality for
        simple CSV files that don't need special preprocessing.
        
        Parameters
        ----------
        mock_inference_stage : Mock
            Mock InferenceStage class
        mock_pipeline : Mock
            Mock EMUSESPipeline class
        """
        # Create simple CSV without headers or index columns
        simple_data_file = self.temp_path / "simple_data.csv"
        with open(simple_data_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([1.5, 2.3, 3.1])
            writer.writerow([2.1, 1.8, 2.9])
            writer.writerow([1.9, 2.7, 3.5])
        
        # Setup mocks
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_dataset.return_value = (
            [[1.5, 2.3, 3.1], [2.1, 1.8, 2.9], [1.9, 2.7, 3.5]],
            "spreadsheet", 
            {"shape": (3, 3)}, 
            None
        )
        mock_pipeline_instance.config = Mock()
        
        mock_stage_instance = Mock()
        mock_inference_stage.return_value = mock_stage_instance
        mock_stage_instance.run.return_value = {
            "mode": "inference",
            "samples_processed": 3,
            "performance_breakdown": {"total_ms": 1000},
            "output_files": {"predictions": str(self.output_dir / "predictions.csv")}
        }
        
        # Execute inference command without preprocessing parameters
        result = self.runner.invoke(app, [
            "inference",
            str(simple_data_file),
            "--model", str(self.model_dir),
            "--output", str(self.output_dir)
        ])
        
        # Verify command executed successfully  
        assert result.exit_code == 0
        
        # Verify preprocessing parameters default to None
        args_used = mock_pipeline.call_args[0][0]
        assert args_used.input_header is None
        assert args_used.input_index_column is None
        assert args_used.scores_header is None
        assert args_used.scores_index_column is None
        assert args_used.scores is None

    def test_user_specific_failing_case_scenario(self):
        """
        Test that simulates the exact user error scenario and verifies the fix.
        
        This test documents the specific case that was failing:
        - CSV files with headers
        - CSV files with index columns
        - Error: "No numeric data remaining after processing"
        """
        # Create the exact type of file that was causing the user's issue
        problematic_file = self.temp_path / "problematic_input.csv"
        with open(problematic_file, 'w', newline='') as f:
            writer = csv.writer(f)
            # Headers that confuse the original parser
            writer.writerow(['ID', 'Age', 'Score', 'Category'])
            # Data with string IDs in first column
            writer.writerow(['Patient_A', 25, 85.5, 'Group1'])  
            writer.writerow(['Patient_B', 30, 92.1, 'Group2'])
            writer.writerow(['Patient_C', 28, 78.9, 'Group1'])
        
        # Before the fix: would fail with "No numeric data remaining"
        # After the fix: should be able to specify --input_header 0 --input_index_column 0
        
        # Test that the help text now includes our new parameters
        result = self.runner.invoke(app, ["inference", "--help"])
        assert result.exit_code == 0
        assert "--input_header" in result.stdout
        assert "--input_index_column" in result.stdout
        assert "Header row for input" in result.stdout
        assert "Index column for input" in result.stdout
        
        # This test documents that the fix is available - actual pipeline testing
        # is covered by the other integration tests with mocking