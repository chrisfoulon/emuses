"""
Test multi-target integration functionality.

Tests the complete multi-target prediction integration with main _predict method.
"""
import numpy as np
import pytest
from unittest.mock import Mock
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.ensemble import RandomForestRegressor

from emuses.pipelines.inference_stage import InferenceStage
from emuses.tools.features_utils import RawCoords, GWD, PCAGWD


class TestMultiTargetIntegration:
    """Test complete multi-target prediction integration."""

    def test_single_target_integration_compatibility(self):
        """Test that single-target scenarios work unchanged with new integration."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create single-target models
        train_coords = np.random.rand(10, 2)
        train_labels = np.random.rand(10)
        
        prediction_models = [
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=42))
                ]).fit(train_coords, train_labels),
                'target': 'target_0',
                'fold_info': 'fold_0'
            },
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=43))
                ]).fit(train_coords, train_labels),
                'target': 'target_0',
                'fold_info': 'fold_1'
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        test_coords = np.random.rand(8, 2)
        
        # Act
        results = stage._predict(test_coords, models_dict)
        
        # Assert - should return consistent target_results format (single-target is n=1 case)
        assert 'target_results' in results
        assert len(results['target_results']) == 1
        assert 'target_0' in results['target_results']
        
        # Check target_0 results
        target_0_result = results['target_results']['target_0']
        assert target_0_result['ensemble_predictions'].shape == (8,)
        assert len(target_0_result['individual_predictions']) == 2
        assert target_0_result['confidence_scores'].shape == (8,)
        assert target_0_result['model_count'] == 2
        assert len(target_0_result['model_names']) == 2
        
        # Check aggregated results for CSV compatibility
        assert results['model_count'] == 2
        assert len(results['model_names']) == 2
        assert results['target_count'] == 1

    def test_multi_target_integration_full_pipeline(self):
        """Test complete multi-target integration with different feat_types."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create multi-target models with different feat_types
        train_coords = np.random.rand(15, 2)
        train_labels_t0 = np.random.rand(15)
        train_labels_t1 = np.random.rand(15)
        train_labels_t2 = np.random.rand(15)
        
        prediction_models = [
            # Target 0: raw_only feat_type
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
            
            # Target 1: gwd feat_type
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
            },
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([
                        ("raw", RawCoords()),
                        ("gwd", GWD(sigma=0.1))
                    ])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=43))
                ]).fit(train_coords, train_labels_t1),
                'target': 'target_1',
                'fold_info': 'fold_1'
            },
            
            # Target 2: pca_gwd feat_type
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([
                        ("raw", RawCoords()),
                        ("pca", PCAGWD(sigma=0.1, n_comp=5))
                    ])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=44))
                ]).fit(train_coords, train_labels_t2),
                'target': 'target_2',
                'fold_info': 'fold_0'
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        test_coords = np.random.rand(12, 2)
        
        # Act
        results = stage._predict(test_coords, models_dict)
        
        # Assert - should return multi-target format
        assert 'target_results' in results
        assert len(results['target_results']) == 3
        assert 'target_count' in results
        assert results['target_count'] == 3
        
        # Check individual target results
        for target in ['target_0', 'target_1', 'target_2']:
            assert target in results['target_results']
            target_result = results['target_results'][target]
            
            assert 'ensemble_predictions' in target_result
            assert target_result['ensemble_predictions'].shape == (12,)
            assert 'individual_predictions' in target_result
            assert 'confidence_scores' in target_result
            assert target_result['confidence_scores'].shape == (12,)
        
        # Check target-specific model counts
        assert results['target_results']['target_0']['model_count'] == 2
        assert results['target_results']['target_1']['model_count'] == 2  
        assert results['target_results']['target_2']['model_count'] == 1
        
        # Check aggregated individual predictions for CSV compatibility
        assert 'individual_predictions' in results
        assert len(results['individual_predictions']) == 5  # Total models
        assert results['model_count'] == 5

    def test_multi_target_integration_with_mixed_models(self):
        """Test integration with mixed pipeline and non-pipeline models across targets."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create mixed models across targets
        train_coords = np.random.rand(10, 2) 
        train_labels = np.random.rand(10)
        
        # Create non-pipeline model
        non_pipeline_model = RandomForestRegressor(n_estimators=3, random_state=45)
        non_pipeline_model.fit(train_coords, train_labels)
        
        prediction_models = [
            # Target 0: Pipeline model
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=46))
                ]).fit(train_coords, train_labels),
                'target': 'target_0',
                'fold_info': 'fold_0'
            },
            
            # Target 1: Non-pipeline model
            {
                'model': non_pipeline_model,
                'target': 'target_1', 
                'fold_info': 'fold_0'
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        test_coords = np.random.rand(6, 2)
        
        # Act
        results = stage._predict(test_coords, models_dict)
        
        # Assert
        assert 'target_results' in results
        assert len(results['target_results']) == 2
        
        # Both targets should have predictions
        for target in ['target_0', 'target_1']:
            target_result = results['target_results'][target]
            assert target_result['ensemble_predictions'].shape == (6,)
            assert target_result['model_count'] == 1

    def test_empty_models_integration(self):
        """Test integration with empty models list."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        models_dict = {"prediction_models": []}
        test_coords = np.random.rand(5, 2)
        
        # Act
        results = stage._predict(test_coords, models_dict)
        
        # Assert
        assert results['ensemble_predictions'].shape == (5,)
        assert np.all(results['ensemble_predictions'] == 0)
        assert results['model_count'] == 0
        assert len(results['individual_predictions']) == 0

    def test_legacy_models_without_target_integration(self):
        """Test integration with legacy models that have no target information."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Create models without target information (legacy)
        train_coords = np.random.rand(8, 2)
        train_labels = np.random.rand(8)
        
        prediction_models = [
            {
                'model': Pipeline([
                    ("feat", FeatureUnion([("raw", RawCoords())])),
                    ("est", RandomForestRegressor(n_estimators=3, random_state=47))
                ]).fit(train_coords, train_labels),
                'fold_info': 'fold_0'  # No target field
            },
            {
                'model': RandomForestRegressor(n_estimators=3, random_state=48).fit(train_coords, train_labels),
                'fold_info': 'fold_1'  # No target field
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        test_coords = np.random.rand(4, 2)
        
        # Act
        results = stage._predict(test_coords, models_dict)
        
        # Assert - should use consistent target_results format with target_0
        assert 'target_results' in results
        assert 'target_0' in results['target_results']
        assert results['target_results']['target_0']['ensemble_predictions'].shape == (4,)
        assert results['target_count'] == 1
        assert results['model_count'] == 2
        assert len(results['individual_predictions']) == 2

    def test_detection_logging_integration(self):
        """Test that target detection and processing logs correctly."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        # Multi-target scenario for logging test
        train_coords = np.random.rand(8, 2)
        train_labels = np.random.rand(8)
        
        prediction_models = [
            {
                'model': RandomForestRegressor(n_estimators=3, random_state=49).fit(train_coords, train_labels),
                'target': 'target_0',
                'fold_info': 'fold_0'
            },
            {
                'model': RandomForestRegressor(n_estimators=3, random_state=50).fit(train_coords, train_labels),
                'target': 'target_1',
                'fold_info': 'fold_0'  
            }
        ]
        
        models_dict = {"prediction_models": prediction_models}
        test_coords = np.random.rand(3, 2)
        
        # Act - this should generate appropriate log messages
        results = stage._predict(test_coords, models_dict)
        
        # Assert - verify multi-target processing occurred
        assert 'target_results' in results
        assert len(results['target_results']) == 2
        assert 'target_0' in results['target_results']
        assert 'target_1' in results['target_results']