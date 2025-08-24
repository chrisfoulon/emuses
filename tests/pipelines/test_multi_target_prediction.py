"""
Test multi-target prediction engine functionality.

Tests the core multi-target prediction processing with target-specific ensembles.
"""
import numpy as np
import pytest
from unittest.mock import Mock
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.ensemble import RandomForestRegressor

from emuses.pipelines.inference_stage import InferenceStage
from emuses.tools.features_utils import RawCoords, GWD


class TestMultiTargetPrediction:
    """Test multi-target prediction engine functionality."""

    def test_enhanced_model_name_generation(self):
        """Test enhanced model name generation for multi-target scenarios."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        test_cases = [
            # Test case: (model_info, expected_name)
            ({'name': 'custom_name', 'target': 'target_0'}, 'custom_name'),
            ({'model_name': 'alt_name', 'target': 'target_1'}, 'target_1_alt_name'),
            ({'fold_info': 'fold_0', 'target': 'target_0'}, 'target_0_fold_0'),
            ({'target': 'target_2'}, 'target_2'),
            ({'fold_info': 'best_pipeline_fold1_0.85'}, 'best_pipeline_fold1_0.85'),
            ({}, 'unknown'),  # No info available
        ]
        
        for model_info, expected_name in test_cases:
            # Act
            result = stage._get_enhanced_model_name(model_info)
            
            # Assert
            assert result == expected_name, f"Failed for {model_info}: expected {expected_name}, got {result}"

    def test_predict_multi_target_with_pipelines(self):
        """Test multi-target prediction with sklearn Pipeline models."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create training data
        n_samples = 20
        train_coords = np.random.rand(n_samples, 2)
        train_labels_t0 = np.random.rand(n_samples)
        train_labels_t1 = np.random.rand(n_samples)
        
        # Create models for different targets
        models_by_target = {
            'target_0': [
                {
                    'model': Pipeline([
                        ("feat", FeatureUnion([("raw", RawCoords())])),
                        ("est", RandomForestRegressor(n_estimators=3, random_state=42))
                    ]).fit(train_coords, train_labels_t0),
                    'target': 'target_0',
                    'fold_info': 'fold_0'
                },
                {
                    'model': Pipeline([
                        ("feat", FeatureUnion([("raw", RawCoords())])),
                        ("est", RandomForestRegressor(n_estimators=3, random_state=43))
                    ]).fit(train_coords, train_labels_t0),
                    'target': 'target_0', 
                    'fold_info': 'fold_1'
                }
            ],
            'target_1': [
                {
                    'model': Pipeline([
                        ("feat", FeatureUnion([
                            ("raw", RawCoords()),
                            ("gwd", GWD(sigma=0.1))
                        ])),
                        ("est", RandomForestRegressor(n_estimators=3, random_state=44))
                    ]).fit(train_coords, train_labels_t1),
                    'target': 'target_1',
                    'fold_info': 'fold_0'
                }
            ]
        }
        
        # Test data
        test_coords = np.random.rand(10, 2)
        
        # Act
        target_results = stage._predict_multi_target(test_coords, models_by_target)
        
        # Assert
        assert len(target_results) == 2
        assert 'target_0' in target_results
        assert 'target_1' in target_results
        
        # Check target_0 results
        t0_results = target_results['target_0']
        assert t0_results['ensemble_predictions'].shape == (10,)
        assert t0_results['confidence_scores'].shape == (10,)
        assert t0_results['model_count'] == 2
        assert len(t0_results['individual_predictions']) == 2
        assert len(t0_results['model_names']) == 2
        
        # Check target_1 results  
        t1_results = target_results['target_1']
        assert t1_results['ensemble_predictions'].shape == (10,)
        assert t1_results['confidence_scores'].shape == (10,)
        assert t1_results['model_count'] == 1
        assert len(t1_results['individual_predictions']) == 1
        assert len(t1_results['model_names']) == 1

    def test_predict_multi_target_with_mixed_models(self):
        """Test multi-target prediction with mixed pipeline and non-pipeline models."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create training data
        train_coords = np.random.rand(15, 2)
        train_labels = np.random.rand(15)
        
        # Create mixed models
        pipeline_model = Pipeline([
            ("feat", FeatureUnion([("raw", RawCoords())])),
            ("est", RandomForestRegressor(n_estimators=3, random_state=42))
        ]).fit(train_coords, train_labels)
        
        non_pipeline_model = RandomForestRegressor(n_estimators=3, random_state=43)
        non_pipeline_model.fit(train_coords, train_labels)
        
        models_by_target = {
            'target_0': [
                {'model': pipeline_model, 'target': 'target_0', 'fold_info': 'fold_0'},
                {'model': non_pipeline_model, 'target': 'target_0', 'fold_info': 'fold_1'}
            ]
        }
        
        # Test data
        test_coords = np.random.rand(8, 2)
        
        # Act
        target_results = stage._predict_multi_target(test_coords, models_by_target)
        
        # Assert
        assert len(target_results) == 1
        assert 'target_0' in target_results
        
        t0_results = target_results['target_0']
        assert t0_results['ensemble_predictions'].shape == (8,)
        assert t0_results['model_count'] == 2
        assert len(t0_results['individual_predictions']) == 2
        
        # Both models should produce predictions
        individual_preds = t0_results['individual_predictions']
        for model_name, predictions in individual_preds.items():
            assert predictions.shape == (8,)

    def test_predict_single_target_compatibility(self):
        """Test that single-target scenarios work with multi-target prediction engine."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Single target scenario
        train_coords = np.random.rand(12, 2)
        train_labels = np.random.rand(12)
        
        models_by_target = {
            'target_0': [
                {
                    'model': Pipeline([
                        ("feat", FeatureUnion([("raw", RawCoords())])),
                        ("est", RandomForestRegressor(n_estimators=3, random_state=42))
                    ]).fit(train_coords, train_labels),
                    'target': 'target_0',
                    'fold_info': 'fold_0'
                }
            ]
        }
        
        # Test data
        test_coords = np.random.rand(5, 2)
        
        # Act
        target_results = stage._predict_multi_target(test_coords, models_by_target)
        
        # Assert
        assert len(target_results) == 1
        assert 'target_0' in target_results
        
        t0_results = target_results['target_0']
        assert t0_results['ensemble_predictions'].shape == (5,)
        assert t0_results['model_count'] == 1
        assert len(t0_results['individual_predictions']) == 1

    def test_predict_empty_target_group(self):
        """Test handling of empty target groups."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        models_by_target = {
            'target_0': [],  # Empty target group
            'target_1': []   # Empty target group
        }
        
        # Test data
        test_coords = np.random.rand(5, 2)
        
        # Act
        target_results = stage._predict_multi_target(test_coords, models_by_target)
        
        # Assert
        assert len(target_results) == 2
        
        for target in ['target_0', 'target_1']:
            results = target_results[target]
            assert results['ensemble_predictions'].shape == (5,)
            assert np.all(results['ensemble_predictions'] == 0)  # Should be zeros
            assert results['model_count'] == 0
            assert len(results['individual_predictions']) == 0

    def test_confidence_scoring_multi_vs_single_model(self):
        """Test confidence scoring differences between multi-model and single-model targets."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create models with different prediction patterns for confidence testing
        train_coords = np.random.rand(10, 2)
        train_labels = np.random.rand(10)
        
        models_by_target = {
            'target_multi': [
                # Multiple models - should have varied confidence based on std
                {
                    'model': RandomForestRegressor(n_estimators=3, random_state=42).fit(train_coords, train_labels),
                    'target': 'target_multi',
                    'fold_info': 'fold_0'
                },
                {
                    'model': RandomForestRegressor(n_estimators=3, random_state=43).fit(train_coords, train_labels),
                    'target': 'target_multi', 
                    'fold_info': 'fold_1'
                }
            ],
            'target_single': [
                # Single model - should have uniform confidence of 0.8
                {
                    'model': RandomForestRegressor(n_estimators=3, random_state=44).fit(train_coords, train_labels),
                    'target': 'target_single',
                    'fold_info': 'fold_0'
                }
            ]
        }
        
        # Test data
        test_coords = np.random.rand(6, 2)
        
        # Act
        target_results = stage._predict_multi_target(test_coords, models_by_target)
        
        # Assert
        multi_confidence = target_results['target_multi']['confidence_scores']
        single_confidence = target_results['target_single']['confidence_scores']
        
        # Multi-model should have confidence based on std (varies)
        assert multi_confidence.shape == (6,)
        assert not np.all(multi_confidence == 0.8)  # Should vary based on prediction std
        
        # Single-model should have uniform confidence of 0.8
        assert single_confidence.shape == (6,)
        assert np.all(single_confidence == 0.8)  # Should be uniform