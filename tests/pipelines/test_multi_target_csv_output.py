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
    
    @classmethod
    def setup_class(cls):
        """Load real test data for CSV output validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
        cls.train_coords = cls.features[:30, :2]  # First 2 features as coordinates
        cls.test_coords = cls.features[30:, :2]   # Last 20 samples for testing
        cls.train_targets = cls.targets[:30]       # Training targets
        cls.test_targets = cls.targets[30:]        # Test targets

    def test_single_target_csv_consistent_format(self):
        """Test that single-target CSV output uses consistent target_0_ format."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create realistic predictions using real test data
        from sklearn.ensemble import RandomForestRegressor
        model1 = RandomForestRegressor(n_estimators=3, random_state=42)
        model2 = RandomForestRegressor(n_estimators=3, random_state=43)
        
        # Train on single target
        model1.fit(self.train_coords, self.train_targets[:, 0])
        model2.fit(self.train_coords, self.train_targets[:, 0])
        
        # Generate predictions for test set (20 samples)
        pred1 = model1.predict(self.test_coords)
        pred2 = model2.predict(self.test_coords)
        ensemble_pred = (pred1 + pred2) / 2
        confidence = np.ones(len(ensemble_pred)) * 0.8  # Mock confidence
        
        # Single-target results in new consistent target_results format
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': ensemble_pred,
                    'confidence_scores': confidence,
                    'individual_predictions': {
                        'model_1': pred1,
                        'model_2': pred2
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
            
            # Check data with real test predictions (20 samples)
            assert len(df) == 20
            # Verify that predictions exist and are finite
            assert all(np.isfinite(df['target_0_ensemble_prediction']))
            assert all(df['target_0_confidence_score'] == 0.8)  # Mock confidence is constant
            assert all(np.isfinite(df['target_0_model_1']))

    def test_multi_target_predictions_csv_structure(self):
        """Test multi-target predictions CSV has correct structure."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create realistic multi-target predictions using real test data
        from sklearn.ensemble import RandomForestRegressor
        
        # Train models for both targets
        model_t0_1 = RandomForestRegressor(n_estimators=3, random_state=42)
        model_t0_2 = RandomForestRegressor(n_estimators=3, random_state=43)
        model_t1_1 = RandomForestRegressor(n_estimators=3, random_state=44)
        
        model_t0_1.fit(self.train_coords, self.train_targets[:, 0])
        model_t0_2.fit(self.train_coords, self.train_targets[:, 0])
        model_t1_1.fit(self.train_coords, self.train_targets[:, 1])
        
        # Generate predictions for test set (20 samples)
        pred_t0_1 = model_t0_1.predict(self.test_coords)
        pred_t0_2 = model_t0_2.predict(self.test_coords)
        pred_t1_1 = model_t1_1.predict(self.test_coords)
        
        ensemble_t0 = (pred_t0_1 + pred_t0_2) / 2
        ensemble_t1 = pred_t1_1
        
        # Multi-target results
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': ensemble_t0,
                    'confidence_scores': np.ones(len(ensemble_t0)) * 0.8,
                    'individual_predictions': {
                        'model_1': pred_t0_1,
                        'model_2': pred_t0_2
                    }
                },
                'target_1': {
                    'ensemble_predictions': ensemble_t1,
                    'confidence_scores': np.ones(len(ensemble_t1)) * 0.75,
                    'individual_predictions': {
                        'model_3': pred_t1_1
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
            
            # Check data with real test predictions (20 samples)
            assert len(df) == 20
            # Verify that predictions exist and are finite
            assert all(np.isfinite(df['target_0_ensemble_prediction']))
            assert all(np.isfinite(df['target_1_ensemble_prediction']))
            assert all(np.isfinite(df['target_0_model_1']))

    def test_multi_target_confidence_csv_structure(self):
        """Test multi-target confidence CSV has correct structure."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create realistic multi-target results with confidence scores using real data
        from sklearn.ensemble import RandomForestRegressor
        
        model_t0 = RandomForestRegressor(n_estimators=3, random_state=42)
        model_t1 = RandomForestRegressor(n_estimators=3, random_state=43)
        
        model_t0.fit(self.train_coords, self.train_targets[:, 0])
        model_t1.fit(self.train_coords, self.train_targets[:, 1])
        
        pred_t0 = model_t0.predict(self.test_coords)
        pred_t1 = model_t1.predict(self.test_coords)
        
        # Multi-target results with confidence
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': pred_t0,
                    'confidence_scores': np.ones(len(pred_t0)) * 0.8
                },
                'target_1': {
                    'ensemble_predictions': pred_t1,
                    'confidence_scores': np.ones(len(pred_t1)) * 0.9
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
            
            # Check data with real test predictions (20 samples)
            assert len(df) == 20
            assert all(df['target_0_confidence_score'] == 0.8)  # Mock confidence is constant
            assert all(df['target_1_confidence_score'] == 0.9)  # Mock confidence is constant

    def test_single_target_confidence_csv_consistent_format(self):
        """Test that single-target confidence CSV output uses consistent target_0_ format."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create realistic single-target predictions using real data
        from sklearn.ensemble import RandomForestRegressor
        model = RandomForestRegressor(n_estimators=3, random_state=42)
        model.fit(self.train_coords, self.train_targets[:, 0])
        predictions = model.predict(self.test_coords)
        
        # Single-target results in target_results format
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': predictions,
                    'confidence_scores': np.ones(len(predictions)) * 0.8
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
            assert len(df) == 20
            assert all(df['target_0_confidence_score'] == 0.8)  # Mock confidence is constant

    def test_multi_target_csv_with_prefixed_model_names(self):
        """Test multi-target CSV handles model names that already have target prefixes."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create realistic predictions using real data
        from sklearn.ensemble import RandomForestRegressor
        model1 = RandomForestRegressor(n_estimators=3, random_state=42)
        model2 = RandomForestRegressor(n_estimators=3, random_state=43)
        
        model1.fit(self.train_coords, self.train_targets[:, 0])
        model2.fit(self.train_coords, self.train_targets[:, 0])
        
        pred1 = model1.predict(self.test_coords)
        pred2 = model2.predict(self.test_coords)
        ensemble_pred = (pred1 + pred2) / 2
        
        # Multi-target results with pre-prefixed model names
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': ensemble_pred,
                    'confidence_scores': np.ones(len(ensemble_pred)) * 0.8,
                    'individual_predictions': {
                        'target_0_model_1': pred1,  # Already prefixed
                        'raw_model': pred2          # Not prefixed
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
        
        # Create realistic predictions using real data
        from sklearn.ensemble import RandomForestRegressor
        model_t0 = RandomForestRegressor(n_estimators=3, random_state=42)
        model_t1 = RandomForestRegressor(n_estimators=3, random_state=43)
        
        model_t0.fit(self.train_coords, self.train_targets[:, 0])
        model_t1.fit(self.train_coords, self.train_targets[:, 1])
        
        pred_t0 = model_t0.predict(self.test_coords)
        pred_t1 = model_t1.predict(self.test_coords)
        
        # Multi-target results without confidence scores
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': pred_t0,
                    # No confidence_scores key
                },
                'target_1': {
                    'ensemble_predictions': pred_t1,
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
        
        # Create realistic predictions using real data
        from sklearn.ensemble import RandomForestRegressor
        model_t0 = RandomForestRegressor(n_estimators=3, random_state=42)
        model_t1 = RandomForestRegressor(n_estimators=3, random_state=43)
        
        model_t0.fit(self.train_coords, self.train_targets[:, 0])
        model_t1.fit(self.train_coords, self.train_targets[:, 1])
        
        pred_t0 = model_t0.predict(self.test_coords)
        pred_t1 = model_t1.predict(self.test_coords)
        
        # Multi-target results with only ensemble predictions
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': pred_t0,
                    'confidence_scores': np.ones(len(pred_t0)) * 0.8,
                    'individual_predictions': {}  # Empty
                },
                'target_1': {
                    'ensemble_predictions': pred_t1,
                    'confidence_scores': np.ones(len(pred_t1)) * 0.75,
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
        
        # Create realistic multi-target predictions using real data
        from sklearn.ensemble import RandomForestRegressor
        model_t2 = RandomForestRegressor(n_estimators=3, random_state=40)
        model_t0 = RandomForestRegressor(n_estimators=3, random_state=41)
        model_t1 = RandomForestRegressor(n_estimators=3, random_state=42)
        
        model_t2.fit(self.train_coords, self.train_targets[:, 0])  # Use target 0 data for all
        model_t0.fit(self.train_coords, self.train_targets[:, 1])  
        model_t1.fit(self.train_coords, self.train_targets[:, 0])
        
        pred_t2 = model_t2.predict(self.test_coords)
        pred_t0 = model_t0.predict(self.test_coords)
        pred_t1 = model_t1.predict(self.test_coords)
        
        # Multi-target results with targets in non-alphabetical order
        results = {
            'target_results': {
                'target_2': {
                    'ensemble_predictions': pred_t2,
                    'confidence_scores': np.ones(len(pred_t2)) * 0.8,
                    'individual_predictions': {'model_z': pred_t2 * 0.98}
                },
                'target_0': {
                    'ensemble_predictions': pred_t0,
                    'confidence_scores': np.ones(len(pred_t0)) * 0.9,
                    'individual_predictions': {'model_a': pred_t0 * 1.02}
                },
                'target_1': {
                    'ensemble_predictions': pred_t1,
                    'confidence_scores': np.ones(len(pred_t1)) * 0.7,
                    'individual_predictions': {'model_m': pred_t1 * 0.99}
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
        
        # Create realistic predictions using real data with controlled precision
        from sklearn.ensemble import RandomForestRegressor
        model = RandomForestRegressor(n_estimators=3, random_state=42)
        model.fit(self.train_coords, self.train_targets[:, 0])
        
        pred = model.predict(self.test_coords)
        # Add known precise values to test precision preservation
        precise_pred = pred.copy()
        precise_pred[0] = 1.123456  # Known precision value
        
        # Multi-target results with known precision values
        results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': pred,
                    'confidence_scores': np.ones(len(pred)) * 0.888,
                    'individual_predictions': {
                        'precise_model': precise_pred
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
            
            # Check precision is preserved and data integrity
            assert len(df) == 20  # Real test data has 20 samples
            assert all(df['target_0_confidence_score'] == 0.888)  # Mock confidence is constant
            assert abs(df['target_0_precise_model'][0] - 1.123456) < 1e-6  # Precision preserved
            # Verify predictions exist and are finite
            assert all(np.isfinite(df['target_0_ensemble_prediction']))