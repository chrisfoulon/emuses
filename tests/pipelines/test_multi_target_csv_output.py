"""
Test multi-target CSV output functionality.

Tests the enhanced CSV generation system that handles both single-target 
and multi-target prediction results with proper column formatting.
"""
import numpy as np
import pytest
import pandas as pd
import tempfile
from pathlib import Path
from unittest.mock import Mock

from emuses.pipelines.inference_stage import InferenceStage


class TestMultiTargetCSVOutput:
    """Test multi-target CSV output formatting and generation."""

    def test_single_target_csv_consistent_format(self):
        """Test that single-target CSV output uses consistent target_0_ format."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Single-target results in new consistent target_results format
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.1, 2.2, 3.3, 4.4]),
                    'confidence_scores': np.array([0.8, 0.85, 0.9, 0.7]),
                    'individual_predictions': {
                        'model_1': np.array([1.0, 2.1, 3.2, 4.1]),
                        'model_2': np.array([1.2, 2.3, 3.4, 4.7])
                    }
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_predictions.csv"
            
            # Act
            stage._save_predictions_csv(results, output_file)
            
            # Assert
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Check structure with target_0_ prefixes
            expected_columns = ['sample_id', 'target_0_ensemble_prediction', 'target_0_confidence_score', 'target_0_model_1', 'target_0_model_2']
            assert list(df.columns) == expected_columns
            
            # Check data
            assert len(df) == 4
            assert list(df['target_0_ensemble_prediction']) == [1.1, 2.2, 3.3, 4.4]
            assert list(df['target_0_confidence_score']) == [0.8, 0.85, 0.9, 0.7]
            assert list(df['target_0_model_1']) == [1.0, 2.1, 3.2, 4.1]

    def test_multi_target_predictions_csv_structure(self):
        """Test multi-target predictions CSV has correct structure."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target results
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.1, 2.2, 3.3]),
                    'confidence_scores': np.array([0.8, 0.85, 0.9]),
                    'individual_predictions': {
                        'model_1': np.array([1.0, 2.1, 3.2]),
                        'model_2': np.array([1.2, 2.3, 3.4])
                    }
                },
                'target_1': {
                    'ensemble_predictions': np.array([10.1, 20.2, 30.3]),
                    'confidence_scores': np.array([0.7, 0.75, 0.8]),
                    'individual_predictions': {
                        'model_3': np.array([10.0, 20.1, 30.2])
                    }
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_multi_predictions.csv"
            
            # Act
            stage._save_predictions_csv(results, output_file)
            
            # Assert
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Check structure
            expected_columns = [
                'sample_id', 
                'target_0_ensemble_prediction', 'target_0_confidence_score',
                'target_1_ensemble_prediction', 'target_1_confidence_score',
                'target_0_model_1', 'target_0_model_2', 'target_1_model_3'
            ]
            assert list(df.columns) == expected_columns
            
            # Check data
            assert len(df) == 3
            assert list(df['target_0_ensemble_prediction']) == [1.1, 2.2, 3.3]
            assert list(df['target_1_ensemble_prediction']) == [10.1, 20.2, 30.3]
            assert list(df['target_0_model_1']) == [1.0, 2.1, 3.2]

    def test_multi_target_confidence_csv_structure(self):
        """Test multi-target confidence CSV has correct structure."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target results with confidence
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.1, 2.2]),
                    'confidence_scores': np.array([0.8, 0.85])
                },
                'target_1': {
                    'ensemble_predictions': np.array([10.1, 20.2]),
                    'confidence_scores': np.array([0.9, 0.95])
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_multi_confidence.csv"
            
            # Act
            stage._save_confidence_csv(results, output_file)
            
            # Assert
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Check structure
            expected_columns = ['sample_id', 'target_0_confidence_score', 'target_1_confidence_score']
            assert list(df.columns) == expected_columns
            
            # Check data
            assert len(df) == 2
            assert list(df['target_0_confidence_score']) == [0.8, 0.85]
            assert list(df['target_1_confidence_score']) == [0.9, 0.95]

    def test_single_target_confidence_csv_consistent_format(self):
        """Test that single-target confidence CSV output uses consistent target_0_ format."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Single-target results in target_results format
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.0, 2.0, 3.0]),
                    'confidence_scores': np.array([0.8, 0.85, 0.9])
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_confidence.csv"
            
            # Act
            stage._save_confidence_csv(results, output_file)
            
            # Assert
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Check structure with target_0_ prefix
            expected_columns = ['sample_id', 'target_0_confidence_score']
            assert list(df.columns) == expected_columns
            assert len(df) == 3
            assert list(df['target_0_confidence_score']) == [0.8, 0.85, 0.9]

    def test_multi_target_csv_with_prefixed_model_names(self):
        """Test multi-target CSV handles model names that already have target prefixes."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target results with pre-prefixed model names
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.1, 2.2]),
                    'confidence_scores': np.array([0.8, 0.85]),
                    'individual_predictions': {
                        'target_0_model_1': np.array([1.0, 2.1]),  # Already prefixed
                        'raw_model': np.array([1.2, 2.3])         # Not prefixed
                    }
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_prefixed.csv"
            
            # Act
            stage._save_predictions_csv(results, output_file)
            
            # Assert
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Check that prefixed names are preserved, non-prefixed get prefix
            columns = list(df.columns)
            assert 'target_0_model_1' in columns      # Already prefixed, preserved
            assert 'target_0_raw_model' in columns    # Got prefix added

    def test_multi_target_csv_no_confidence_scores(self):
        """Test multi-target confidence CSV when no confidence scores available."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target results without confidence scores
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.1, 2.2]),
                    # No confidence_scores key
                },
                'target_1': {
                    'ensemble_predictions': np.array([10.1, 20.2]),
                    'confidence_scores': []  # Empty confidence scores
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_no_confidence.csv"
            
            # Act
            stage._save_confidence_csv(results, output_file)
            
            # Assert - no file should be created when no confidence scores
            assert not output_file.exists()

    def test_multi_target_csv_empty_individual_predictions(self):
        """Test multi-target CSV with no individual model predictions."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target results with only ensemble predictions
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.1, 2.2, 3.3]),
                    'confidence_scores': np.array([0.8, 0.85, 0.9]),
                    'individual_predictions': {}  # Empty
                },
                'target_1': {
                    'ensemble_predictions': np.array([10.1, 20.2, 30.3]),
                    'confidence_scores': np.array([0.7, 0.75, 0.8]),
                    # No individual_predictions key
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_no_individual.csv"
            
            # Act
            stage._save_predictions_csv(results, output_file)
            
            # Assert
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Should only have ensemble and confidence columns
            expected_columns = [
                'sample_id',
                'target_0_ensemble_prediction', 'target_0_confidence_score',
                'target_1_ensemble_prediction', 'target_1_confidence_score'
            ]
            assert list(df.columns) == expected_columns

    def test_multi_target_csv_column_ordering(self):
        """Test that multi-target CSV columns are properly ordered."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target results with targets in non-alphabetical order
        results = {
            'target_results': {
                'target_2': {
                    'ensemble_predictions': np.array([1.1, 2.2]),
                    'confidence_scores': np.array([0.8, 0.85]),
                    'individual_predictions': {'model_z': np.array([1.0, 2.1])}
                },
                'target_0': {
                    'ensemble_predictions': np.array([10.1, 20.2]),
                    'confidence_scores': np.array([0.9, 0.95]),
                    'individual_predictions': {'model_a': np.array([10.0, 20.1])}
                },
                'target_1': {
                    'ensemble_predictions': np.array([100.1, 200.2]),
                    'confidence_scores': np.array([0.7, 0.75]),
                    'individual_predictions': {'model_m': np.array([100.0, 200.1])}
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_ordering.csv"
            
            # Act
            stage._save_predictions_csv(results, output_file)
            
            # Assert
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            columns = list(df.columns)
            
            # Should be ordered: sample_id, then targets in sorted order
            assert columns[0] == 'sample_id'
            assert 'target_0_ensemble_prediction' in columns
            assert 'target_1_ensemble_prediction' in columns 
            assert 'target_2_ensemble_prediction' in columns
            
            # Ensemble predictions should appear before individual model columns
            ensemble_indices = [i for i, col in enumerate(columns) if 'ensemble_prediction' in col]
            model_indices = [i for i, col in enumerate(columns) if col.startswith('target_') and '_model_' in col]
            
            if model_indices:  # Only check if there are model columns
                assert max(ensemble_indices) < min(model_indices)

    def test_multi_target_csv_data_integrity(self):
        """Test that multi-target CSV preserves data integrity."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target results with known values
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.111, 2.222]),
                    'confidence_scores': np.array([0.888, 0.999]),
                    'individual_predictions': {
                        'precise_model': np.array([1.123456, 2.234567])
                    }
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_precision.csv"
            
            # Act
            stage._save_predictions_csv(results, output_file)
            
            # Assert
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Check precision is preserved
            assert abs(df['target_0_ensemble_prediction'][0] - 1.111) < 1e-6
            assert abs(df['target_0_confidence_score'][1] - 0.999) < 1e-6
            assert abs(df['target_0_precise_model'][0] - 1.123456) < 1e-6