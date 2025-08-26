"""
Tests for inference normalization fix.

Verifies that EMUSESPipeline correctly applies normalization during inference mode
by loading saved scalers from training.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import joblib
from pathlib import Path
from unittest.mock import Mock, patch

from bcblib.tools.dataframe_filtering import normalize_dataframe
from emuses.pipelines.emuses_pipeline import EMUSESPipeline


class TestInferenceNormalizationFix:
    """Test that inference mode correctly applies saved normalization scalers."""
    
    def test_input_normalization_applies_during_inference(self):
        """
        Test that input normalization is applied during inference mode
        when a saved scaler is available.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            # Create mock args for inference mode
            args = Mock()
            args.output_folder = output_path
            args.input_normalization = 'robust'
            args.inference_mode = True
            args.dataset_source = 'spreadsheet'
            args.inputs_path = 'dummy_path.csv'
            args.input_header = 0
            args.input_index_column = None
            args.inputs_columns = None
            args.columns_are_features = True
            
            # Create a saved scaler file
            test_data = pd.DataFrame({
                'feature1': [1.0, 2.0, 3.0, 4.0],
                'feature2': [10.0, 20.0, 30.0, 40.0]
            })
            _, original_scaler = normalize_dataframe(test_data, method='robust')
            
            scaler_path = output_path / "input_scaler.joblib"
            scaler_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(original_scaler, scaler_path)
            
            # Create test input data (different from training data)
            inference_data = pd.DataFrame({
                'feature1': [5.0, 6.0],
                'feature2': [50.0, 60.0]
            })
            
            with patch('emuses.pipelines.emuses_pipeline.spreadsheet_to_input_df') as mock_load:
                mock_load.return_value = inference_data
                
                pipeline = EMUSESPipeline(args)
                result_matrix, result_format = pipeline.load_and_process_inputs()
                
                # Verify normalization was applied
                # The exact values depend on the scaler, but they should be transformed
                assert result_matrix is not None
                assert not np.allclose(result_matrix, inference_data.values)
                
                # Verify that the scaler was loaded and applied
                # Apply same normalization manually for comparison
                expected_normalized, _ = normalize_dataframe(
                    inference_data, method='robust', scaling_factors=original_scaler
                )
                np.testing.assert_array_almost_equal(
                    result_matrix, expected_normalized.values, decimal=6
                )
                
    def test_input_normalization_warns_when_scaler_missing(self):
        """
        Test that inference mode warns when scaler file is missing
        but doesn't crash.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            # Create mock args for inference mode
            args = Mock()
            args.output_folder = output_path
            args.input_normalization = 'robust'
            args.inference_mode = True
            args.dataset_source = 'spreadsheet'
            args.inputs_path = 'dummy_path.csv'
            args.input_header = 0
            args.input_index_column = None
            args.inputs_columns = None
            args.columns_are_features = True
            
            # Create test input data
            inference_data = pd.DataFrame({
                'feature1': [5.0, 6.0],
                'feature2': [50.0, 60.0]
            })
            
            with patch('emuses.pipelines.emuses_pipeline.spreadsheet_to_input_df') as mock_load:
                mock_load.return_value = inference_data
                
                pipeline = EMUSESPipeline(args)
                
                # This should not crash, but should issue warning
                with patch.object(pipeline.logger, 'warning') as mock_warning:
                    result_matrix, result_format = pipeline.load_and_process_inputs()
                    
                    # Verify warning was issued
                    mock_warning.assert_called_once()
                    warning_message = mock_warning.call_args[0][0]
                    assert "Input scaler not found" in warning_message
                    
                    # Without normalization, result should match input
                    np.testing.assert_array_equal(result_matrix, inference_data.values)