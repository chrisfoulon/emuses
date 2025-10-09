"""
Test end-to-end multi-target functionality using real test_data.

Tests the complete multi-target pipeline from prediction through formatting to CSV output
using the project's test_data instead of synthetic data.
"""
import numpy as np
import pytest
import pandas as pd
import tempfile
from pathlib import Path
from unittest.mock import Mock
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.ensemble import RandomForestRegressor

from emuses.pipelines.inference_stage import InferenceStage
from emuses.tools.features_utils import RawCoords, GWD


class TestMultiTargetEndToEnd:
    """Test complete multi-target pipeline end-to-end using real test_data."""
    
    @classmethod
    def setup_class(cls):
        """Load real test data once for all tests."""
        project_root = Path(__file__).parent.parent.parent
        
        # Load real test data
        features_path = project_root / 'test_data/features.csv'
        targets_path = project_root / 'test_data/regression_scores_multitarget.csv'
        
        cls.features = pd.read_csv(features_path, header=None).values  # 50 x 8
        cls.targets = pd.read_csv(targets_path, header=None).values    # 50 x 2
        
        # Use first 30 samples for training, last 20 for testing
        cls.train_features = cls.features[:30]  # 30 x 8 -> reduce to 2D for coordinates
        cls.test_features = cls.features[30:]   # 20 x 8 -> reduce to 2D for coordinates
        cls.train_targets = cls.targets[:30]    # 30 x 2
        cls.test_targets = cls.targets[30:]     # 20 x 2
        
        # Convert 8D features to 2D coordinates for compatibility with existing test
        # Use PCA-like reduction: take first 2 principal components
        cls.train_coords = cls.train_features[:, :2]  # Use first 2 features as coordinates
        cls.test_coords = cls.test_features[:, :2]    # Use first 2 features as coordinates

    def test_end_to_end_multi_target_pipeline_with_validation(self):
        """Test complete multi-target pipeline from prediction to CSV with validation using real data."""
        # Arrange
        config = Mock()
        config.output_folder = Path(tempfile.mkdtemp())
        stage = InferenceStage(config)
        
        # Use real test data instead of synthetic data
        train_coords = self.train_coords     # 30 x 2
        train_labels_t0 = self.train_targets[:, 0]  # 30 samples, target 0
        train_labels_t1 = self.train_targets[:, 1]  # 30 samples, target 1
        
        prediction_models = [
            # Target 0: 2 models
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=40))
                ]).fit(train_coords, train_labels_t0),
                'target': 'target_0',
                'fold_info': 'fold_0'
            },
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=41))
                ]).fit(train_coords, train_labels_t0),
                'target': 'target_0',
                'fold_info': 'fold_1'
            },
            
            # Target 1: 1 model with GWD features
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([
                        ("raw", RawCoords()),
                        ("gwd", GWD(sigma=0.1))
                    ])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=42))
                ]).fit(train_coords, train_labels_t1),
                'target': 'target_1',
                'fold_info': 'fold_0'
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        test_coords = self.test_coords  # Use real test coordinates (20 x 2)
        
        # Use real ground truth for validation (20 x 2)
        ground_truth = self.test_targets
        
        # Act - run prediction
        prediction_results = stage._predict(test_coords, models_dict)
        
        # Act - calculate validation metrics
        validation_metrics = stage._calculate_multi_target_validation_metrics(
            prediction_results['target_results'], ground_truth
        )
        
        # Act - format results
        performance_data = {
            'total_duration_ms': 100.0,
            'throughput_samples_per_sec': 80.0
        }
        formatted_results = stage._format_results(
            prediction_results, 'validation', performance_data, validation_metrics
        )
        
        # Act - save to CSV
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_end_to_end.csv"
            stage._save_predictions_csv(formatted_results, output_file)
            
            # Assert - CSV file structure
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Check basic structure
            assert len(df) == 20  # 20 test samples from real data
            assert 'sample_id' in df.columns
            assert 'target_0_ensemble_prediction' in df.columns
            assert 'target_1_ensemble_prediction' in df.columns
            assert 'target_0_confidence_score' in df.columns
            assert 'target_1_confidence_score' in df.columns
            
            # Check individual models are present
            target_0_models = [col for col in df.columns if col.startswith('target_0_') and ('fold' in col or 'model' in col)]
            target_1_models = [col for col in df.columns if col.startswith('target_1_') and ('fold' in col or 'model' in col)]
            
            assert len(target_0_models) == 2  # 2 models for target_0
            assert len(target_1_models) == 1  # 1 model for target_1
        
        # Assert - validation metrics structure
        assert validation_metrics is not None
        assert 'target_0' in validation_metrics
        assert 'target_1' in validation_metrics
        assert '_summary' in validation_metrics  # Multi-target summary
        
        # Assert - formatted results structure
        assert 'target_results' in formatted_results
        assert 'target_count' in formatted_results
        assert formatted_results['target_count'] == 2
        assert 'validation_metrics' in formatted_results
        
        # Assert - performance metadata preserved
        assert 'performance_breakdown' in formatted_results
        assert formatted_results['performance_breakdown']['total_ms'] == 100.0

    def test_end_to_end_single_target_consistent_format(self):
        """Test that single-target scenarios use consistent target_results format."""
        # Arrange
        config = Mock()
        config.output_folder = Path(tempfile.mkdtemp())
        stage = InferenceStage(config)
        
        # Use real test data for single-target (use only first target)
        train_coords = self.train_coords
        train_labels = self.train_targets[:, 0]  # Use only target 0
        
        prediction_models = [
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=43))
                ]).fit(train_coords, train_labels),
                'fold_info': 'fold_0'  # No target field - gets assigned target_0
            },
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=44))
                ]).fit(train_coords, train_labels),
                'fold_info': 'fold_1'  # No target field - gets assigned target_0
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        test_coords = self.test_coords
        ground_truth = self.test_targets[:, 0].reshape(-1, 1)  # Single target in multi-target format
        
        # Act - run prediction
        prediction_results = stage._predict(test_coords, models_dict)
        
        # Act - calculate validation metrics
        validation_metrics = stage._calculate_multi_target_validation_metrics(
            prediction_results['target_results'], ground_truth
        )
        
        # Assert - single-target results now have target_results structure
        assert 'target_results' in prediction_results
        assert 'target_0' in prediction_results['target_results']
        assert prediction_results['target_results']['target_0']['ensemble_predictions'].shape == (20,)  # 20 test samples
        assert prediction_results['target_count'] == 1
        
        # Act - format results
        performance_data = {'total_duration_ms': 50.0}
        formatted_results = stage._format_results(
            prediction_results, 'validation', performance_data, validation_metrics
        )
        
        # Act - save to CSV
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_single_target.csv"
            stage._save_predictions_csv(formatted_results, output_file)
            
            # Assert - single-target CSV structure with target_0_ prefixes
            assert output_file.exists()
            df = pd.read_csv(output_file)
            
            # Should use consistent target-prefixed format
            assert 'sample_id' in df.columns
            assert 'target_0_ensemble_prediction' in df.columns
            assert 'target_0_confidence_score' in df.columns
            
            # Individual model columns should have target_0_ prefix
            model_columns = [col for col in df.columns if col.startswith('target_0_') and col not in 
                            ['target_0_ensemble_prediction', 'target_0_confidence_score']]
            assert len(model_columns) == 2  # 2 individual models

    def test_end_to_end_multi_target_csv_data_consistency(self):
        """Test that multi-target CSV data matches prediction results."""
        # Arrange
        config = Mock()
        config.output_folder = Path(tempfile.mkdtemp())
        stage = InferenceStage(config)
        
        # Use subset of real training data for predictable results
        train_coords = self.train_coords[:10]  # Use first 10 training samples
        train_labels_t0 = self.train_targets[:10, 0]  # Target 0 for first 10 samples
        train_labels_t1 = self.train_targets[:10, 1]  # Target 1 for first 10 samples
        
        prediction_models = [
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=1, random_state=100))
                ]).fit(train_coords, train_labels_t0),
                'target': 'target_A',
                'fold_info': 'fold_0'
            },
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=1, random_state=200))
                ]).fit(train_coords, train_labels_t1),  # Use real target 1 data
                'target': 'target_B',
                'fold_info': 'fold_0'
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        test_coords = self.test_coords[:2]  # Use first 2 test samples for consistency
        
        # Act - run prediction and get target results
        prediction_results = stage._predict(test_coords, models_dict)
        target_results = prediction_results['target_results']
        
        # Act - format and save
        performance_data = {'total_duration_ms': 25.0}
        formatted_results = stage._format_results(prediction_results, 'inference', performance_data)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_consistency.csv"
            stage._save_predictions_csv(formatted_results, output_file)
            
            # Assert - CSV data matches prediction results
            df = pd.read_csv(output_file)
            
            # Check target A predictions match
            target_a_ensemble = target_results['target_A']['ensemble_predictions']
            csv_target_a = df['target_A_ensemble_prediction'].values
            np.testing.assert_array_almost_equal(target_a_ensemble, csv_target_a)
            
            # Check target B predictions match
            target_b_ensemble = target_results['target_B']['ensemble_predictions']
            csv_target_b = df['target_B_ensemble_prediction'].values
            np.testing.assert_array_almost_equal(target_b_ensemble, csv_target_b)
            
            # Check individual model predictions match
            target_a_individual = list(target_results['target_A']['individual_predictions'].keys())[0]
            target_a_individual_preds = target_results['target_A']['individual_predictions'][target_a_individual]
            
            # Find corresponding CSV column (may have target prefix)
            target_a_csv_col = None
            for col in df.columns:
                if 'target_A' in col and target_a_individual.replace('target_A_', '') in col:
                    target_a_csv_col = col
                    break
            
            assert target_a_csv_col is not None
            csv_individual_a = df[target_a_csv_col].values
            np.testing.assert_array_almost_equal(target_a_individual_preds, csv_individual_a)

    def test_end_to_end_validation_metrics_preservation(self):
        """Test that validation metrics are properly preserved through formatting."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create mock multi-target validation metrics
        validation_metrics = {
            'target_0': {
                'r2_score': 0.85,
                'mse': 0.15,
                'mae': 0.25,
                'rmse': 0.387
            },
            'target_1': {
                'r2_score': 0.92,
                'mse': 0.08,
                'mae': 0.18,
                'rmse': 0.283
            },
            '_summary': {
                'target_count': 2,
                'mean_r2_score': 0.885,
                'std_r2_score': 0.035,
                'min_r2_score': 0.85,
                'max_r2_score': 0.92
            }
        }
        
        # Create mock prediction results
        prediction_results = {
            'target_results': {
                'target_0': {
                    'ensemble_predictions': np.array([1.0, 2.0]),
                    'confidence_scores': np.array([0.8, 0.9]),
                    'individual_predictions': {},
                    'model_count': 1,
                    'model_names': ['model_1']
                },
                'target_1': {
                    'ensemble_predictions': np.array([10.0, 20.0]),
                    'confidence_scores': np.array([0.85, 0.95]),
                    'individual_predictions': {},
                    'model_count': 1,
                    'model_names': ['model_2']
                }
            },
            'target_count': 2,
            'model_count': 2,
            'individual_predictions': {},
            'model_names': ['model_1', 'model_2']
        }
        
        # Act - format results with validation metrics
        performance_data = {'total_duration_ms': 75.0}
        formatted_results = stage._format_results(
            prediction_results, 'validation', performance_data, validation_metrics
        )
        
        # Assert - validation metrics are preserved in formatted results
        assert 'validation_metrics' in formatted_results
        assert formatted_results['validation_metrics'] == validation_metrics
        
        # Assert - multi-target structure is preserved
        assert 'target_results' in formatted_results
        assert 'target_count' in formatted_results
        assert formatted_results['target_count'] == 2
        
        # Assert - metadata includes correct sample count
        assert formatted_results['metadata']['samples_processed'] == 2
        assert formatted_results['metadata']['model_count'] == 2