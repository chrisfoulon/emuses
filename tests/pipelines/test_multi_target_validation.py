"""
Test multi-target validation functionality.

Tests the multi-target validation metrics calculation system.
"""
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import Mock

from emuses.pipelines.inference_stage import InferenceStage


class TestMultiTargetValidation:
    """Test multi-target validation metrics calculation."""
    
    @classmethod
    def setup_class(cls):
        """Load real test data for validation metrics testing."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
        cls.train_coords = cls.features[:30, :2]  # First 2 features as coordinates
        cls.test_coords = cls.features[30:, :2]   # Last 20 samples for testing
        cls.train_targets = cls.targets[:30]       # Training targets
        cls.test_targets = cls.targets[30:]        # Test targets

    def test_single_target_validation(self):
        """Test validation with single-target results."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create realistic single-target predictions using real data
        from sklearn.ensemble import RandomForestRegressor
        model1 = RandomForestRegressor(n_estimators=3, random_state=42)
        model2 = RandomForestRegressor(n_estimators=3, random_state=43)
        
        model1.fit(self.train_coords, self.train_targets[:, 0])
        model2.fit(self.train_coords, self.train_targets[:, 0])
        
        pred1 = model1.predict(self.test_coords)
        pred2 = model2.predict(self.test_coords)
        ensemble_pred = (pred1 + pred2) / 2
        
        # Single-target results with real predictions
        target_results = {
            'target_0': {
                'ensemble_predictions': ensemble_pred,
                'individual_predictions': {},
                'confidence_scores': np.ones(len(ensemble_pred)) * 0.8,
                'model_count': 2,
                'model_names': ['model_1', 'model_2']
            }
        }
        
        # Use real ground truth for validation
        ground_truth = self.test_targets[:, 0]
        
        # Act
        validation_metrics = stage._calculate_multi_target_validation_metrics(target_results, ground_truth)
        
        # Assert
        assert validation_metrics is not None
        assert len(validation_metrics) == 1
        assert 'target_0' in validation_metrics
        
        target_metrics = validation_metrics['target_0']
        assert 'r2_score' in target_metrics
        assert 'mse' in target_metrics
        assert 'mae' in target_metrics
        assert 'rmse' in target_metrics
        
        # Should NOT have summary (single target)
        assert '_summary' not in validation_metrics

    def test_multi_target_validation(self):
        """Test validation with multi-target results."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create realistic multi-target predictions using real data
        from sklearn.ensemble import RandomForestRegressor
        
        # Train models for both targets
        model_t0_1 = RandomForestRegressor(n_estimators=3, random_state=42)
        model_t0_2 = RandomForestRegressor(n_estimators=3, random_state=43)
        model_t1_1 = RandomForestRegressor(n_estimators=3, random_state=44)
        model_t1_2 = RandomForestRegressor(n_estimators=3, random_state=45)
        model_t1_3 = RandomForestRegressor(n_estimators=3, random_state=46)
        model_t2 = RandomForestRegressor(n_estimators=3, random_state=47)
        
        model_t0_1.fit(self.train_coords, self.train_targets[:, 0])
        model_t0_2.fit(self.train_coords, self.train_targets[:, 0])
        model_t1_1.fit(self.train_coords, self.train_targets[:, 1])
        model_t1_2.fit(self.train_coords, self.train_targets[:, 1])
        model_t1_3.fit(self.train_coords, self.train_targets[:, 1])
        model_t2.fit(self.train_coords, self.train_targets[:, 0])  # Reuse target 0 for third
        
        # Generate predictions
        pred_t0_1 = model_t0_1.predict(self.test_coords)
        pred_t0_2 = model_t0_2.predict(self.test_coords)
        pred_t1_1 = model_t1_1.predict(self.test_coords)
        pred_t1_2 = model_t1_2.predict(self.test_coords)
        pred_t1_3 = model_t1_3.predict(self.test_coords)
        pred_t2 = model_t2.predict(self.test_coords)
        
        ensemble_t0 = (pred_t0_1 + pred_t0_2) / 2
        ensemble_t1 = (pred_t1_1 + pred_t1_2 + pred_t1_3) / 3
        ensemble_t2 = pred_t2
        
        # Multi-target results with real predictions
        target_results = {
            'target_0': {
                'ensemble_predictions': ensemble_t0,
                'individual_predictions': {},
                'confidence_scores': np.ones(len(ensemble_t0)) * 0.8,
                'model_count': 2,
                'model_names': ['t0_model_1', 't0_model_2']
            },
            'target_1': {
                'ensemble_predictions': ensemble_t1,
                'individual_predictions': {},
                'confidence_scores': np.ones(len(ensemble_t1)) * 0.9,
                'model_count': 3,
                'model_names': ['t1_model_1', 't1_model_2', 't1_model_3']
            },
            'target_2': {
                'ensemble_predictions': ensemble_t2,
                'individual_predictions': {},
                'confidence_scores': np.ones(len(ensemble_t2)) * 0.7,
                'model_count': 1,
                'model_names': ['t2_model_1']
            }
        }
        
        # Multi-target ground truth (3 targets) - create synthetic third target from real data
        ground_truth = np.column_stack([
            self.test_targets[:, 0],  # Target 0: real data
            self.test_targets[:, 1],  # Target 1: real data  
            self.test_targets[:, 0] * 0.1  # Target 2: scaled version for testing
        ])
        
        # Act
        validation_metrics = stage._calculate_multi_target_validation_metrics(target_results, ground_truth)
        
        # Assert
        assert validation_metrics is not None
        assert len(validation_metrics) == 4  # 3 targets + summary
        
        # Check individual target metrics
        for target in ['target_0', 'target_1', 'target_2']:
            assert target in validation_metrics
            target_metrics = validation_metrics[target]
            assert 'r2_score' in target_metrics
            assert 'mse' in target_metrics
            assert 'mae' in target_metrics
            assert 'rmse' in target_metrics
        
        # Check summary metrics
        assert '_summary' in validation_metrics
        summary = validation_metrics['_summary']
        assert 'mean_r2_score' in summary
        assert 'std_r2_score' in summary
        assert 'min_r2_score' in summary
        assert 'max_r2_score' in summary
        assert 'target_count' in summary
        assert summary['target_count'] == 3

    def test_validation_with_no_ground_truth(self):
        """Test validation when no ground truth is available."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        target_results = {
            'target_0': {
                'ensemble_predictions': np.array([1.0, 2.0, 3.0]),
                'individual_predictions': {},
                'confidence_scores': np.array([0.8, 0.8, 0.8]),
                'model_count': 1,
                'model_names': ['model_1']
            }
        }
        
        # Act
        validation_metrics = stage._calculate_multi_target_validation_metrics(target_results, None)
        
        # Assert
        assert validation_metrics is None

    def test_validation_dimension_mismatch(self):
        """Test validation when ground truth dimensions don't match target count."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # 2 targets in results
        target_results = {
            'target_0': {
                'ensemble_predictions': np.array([1.0, 2.0, 3.0]),
                'individual_predictions': {},
                'confidence_scores': np.array([0.8, 0.8, 0.8]),
                'model_count': 1,
                'model_names': ['model_1']
            },
            'target_1': {
                'ensemble_predictions': np.array([10.0, 20.0, 30.0]),
                'individual_predictions': {},
                'confidence_scores': np.array([0.9, 0.9, 0.9]),
                'model_count': 1,
                'model_names': ['model_2']
            }
        }
        
        # But 3 targets in ground truth
        ground_truth = np.array([
            [1.1, 10.1, 100.1],  # 3 targets
            [2.1, 20.1, 200.1],
            [3.1, 30.1, 300.1]
        ])
        
        # Act
        validation_metrics = stage._calculate_multi_target_validation_metrics(target_results, ground_truth)
        
        # Assert
        assert validation_metrics is None

    def test_validation_single_target_with_multi_target_predictions(self):
        """Test validation when ground truth is 1D but predictions are multi-target."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target results
        target_results = {
            'target_0': {
                'ensemble_predictions': np.array([1.0, 2.0, 3.0]),
                'individual_predictions': {},
                'confidence_scores': np.array([0.8, 0.8, 0.8]),
                'model_count': 1,
                'model_names': ['model_1']
            },
            'target_1': {
                'ensemble_predictions': np.array([10.0, 20.0, 30.0]),
                'individual_predictions': {},
                'confidence_scores': np.array([0.9, 0.9, 0.9]),
                'model_count': 1,
                'model_names': ['model_2']
            }
        }
        
        # Single-target ground truth (1D)
        ground_truth = np.array([1.1, 2.1, 3.1])
        
        # Act
        validation_metrics = stage._calculate_multi_target_validation_metrics(target_results, ground_truth)
        
        # Assert
        assert validation_metrics is None  # Should return None due to mismatch

    def test_validation_summary_calculations(self):
        """Test that validation summary statistics are calculated correctly."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create target metrics with known values for testing
        target_metrics = {
            'target_0': {
                'r2_score': 0.9,
                'mse': 0.1,
                'mae': 0.2,
                'rmse': 0.316,
                'correlation': 0.95
            },
            'target_1': {
                'r2_score': 0.8,
                'mse': 0.3,
                'mae': 0.4,
                'rmse': 0.548,
                'correlation': 0.89
            },
            'target_2': {
                'r2_score': 0.7,
                'mse': 0.2,
                'mae': 0.3,
                'rmse': 0.447,
                'correlation': 0.84
            }
        }
        
        # Act
        summary = stage._calculate_validation_summary(target_metrics)
        
        # Assert
        assert 'target_count' in summary
        assert summary['target_count'] == 3
        
        # Check mean calculations
        assert 'mean_r2_score' in summary
        assert abs(summary['mean_r2_score'] - 0.8) < 1e-6  # (0.9 + 0.8 + 0.7) / 3
        
        assert 'mean_mse' in summary
        assert abs(summary['mean_mse'] - 0.2) < 1e-6  # (0.1 + 0.3 + 0.2) / 3
        
        # Check std calculations
        assert 'std_r2_score' in summary
        r2_std = np.std([0.9, 0.8, 0.7])
        assert abs(summary['std_r2_score'] - r2_std) < 1e-6
        
        # Check min/max calculations
        assert 'min_r2_score' in summary
        assert summary['min_r2_score'] == 0.7
        
        assert 'max_r2_score' in summary
        assert summary['max_r2_score'] == 0.9

    def test_validation_with_empty_target_results(self):
        """Test validation with empty target results."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        target_results = {}
        ground_truth = np.array([1.0, 2.0, 3.0])
        
        # Act
        validation_metrics = stage._calculate_multi_target_validation_metrics(target_results, ground_truth)
        
        # Assert
        assert validation_metrics == {}  # Empty dict for empty results

    def test_validation_integration_single_target_compatibility(self):
        """Test that single-target validation still works with the enhanced system."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Single-target results (no target_results key)
        target_results = {
            'target_0': {
                'ensemble_predictions': np.array([1.0, 2.0, 3.0, 4.0]),
                'individual_predictions': {'model_1': np.array([1.1, 2.1, 2.9, 4.1])},
                'confidence_scores': np.array([0.8, 0.8, 0.8, 0.8]),
                'model_count': 1,
                'model_names': ['model_1']
            }
        }
        
        # Single-target ground truth
        ground_truth = np.array([1.0, 2.0, 3.0, 4.0])
        
        # Act
        validation_metrics = stage._calculate_multi_target_validation_metrics(target_results, ground_truth)
        
        # Assert
        assert validation_metrics is not None
        assert len(validation_metrics) == 1
        assert 'target_0' in validation_metrics
        assert '_summary' not in validation_metrics  # No summary for single target