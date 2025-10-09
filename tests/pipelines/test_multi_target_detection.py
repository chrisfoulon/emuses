"""
Test multi-target detection and model grouping functionality.

Tests the target detection system for multi-target ensemble processing.
"""
import pytest
from unittest.mock import Mock

from emuses.pipelines.inference_stage import InferenceStage


class TestMultiTargetDetection:
    """Test multi-target detection and model grouping logic."""

    def test_detect_single_target_scenario(self):
        """Test detection of single-target scenario."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        prediction_models = [
            {'model': 'mock_model_1', 'target': 'target_0', 'fold_info': 'fold_0'},
            {'model': 'mock_model_2', 'target': 'target_0', 'fold_info': 'fold_1'},
            {'model': 'mock_model_3', 'target': 'target_0', 'fold_info': 'fold_2'},
        ]
        
        # Act
        is_multi_target, targets = stage._detect_multi_target_scenario(prediction_models)
        
        # Assert
        assert is_multi_target is False
        assert targets == ['target_0']

    def test_detect_multi_target_scenario(self):
        """Test detection of multi-target scenario."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        prediction_models = [
            {'model': 'mock_model_1', 'target': 'target_0', 'fold_info': 'fold_0'},
            {'model': 'mock_model_2', 'target': 'target_1', 'fold_info': 'fold_0'},
            {'model': 'mock_model_3', 'target': 'target_2', 'fold_info': 'fold_0'},
        ]
        
        # Act
        is_multi_target, targets = stage._detect_multi_target_scenario(prediction_models)
        
        # Assert
        assert is_multi_target is True
        assert targets == ['target_0', 'target_1', 'target_2']

    def test_detect_legacy_models_without_target(self):
        """Test detection with legacy models that have no target information."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        prediction_models = [
            {'model': 'mock_model_1', 'fold_info': 'fold_0'},  # No target
            {'model': 'mock_model_2', 'fold_info': 'fold_1'},  # No target
        ]
        
        # Act
        is_multi_target, targets = stage._detect_multi_target_scenario(prediction_models)
        
        # Assert
        assert is_multi_target is False
        assert targets == ['target_0']  # Default target

    def test_detect_empty_models_list(self):
        """Test detection with empty models list."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        prediction_models = []
        
        # Act
        is_multi_target, targets = stage._detect_multi_target_scenario(prediction_models)
        
        # Assert
        assert is_multi_target is False
        assert targets == []

    def test_group_models_by_target_single_target(self):
        """Test model grouping for single-target scenario."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        prediction_models = [
            {'model': 'model_1', 'target': 'target_0', 'fold_info': 'fold_0'},
            {'model': 'model_2', 'target': 'target_0', 'fold_info': 'fold_1'},
            {'model': 'model_3', 'target': 'target_0', 'fold_info': 'fold_2'},
        ]
        
        # Act
        models_by_target = stage._group_models_by_target(prediction_models)
        
        # Assert
        assert len(models_by_target) == 1
        assert 'target_0' in models_by_target
        assert len(models_by_target['target_0']) == 3

    def test_group_models_by_target_multi_target(self):
        """Test model grouping for multi-target scenario."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        prediction_models = [
            # Target 0 models
            {'model': 'model_t0_f0', 'target': 'target_0', 'fold_info': 'fold_0'},
            {'model': 'model_t0_f1', 'target': 'target_0', 'fold_info': 'fold_1'},
            # Target 1 models
            {'model': 'model_t1_f0', 'target': 'target_1', 'fold_info': 'fold_0'},
            {'model': 'model_t1_f1', 'target': 'target_1', 'fold_info': 'fold_1'},
            {'model': 'model_t1_f2', 'target': 'target_1', 'fold_info': 'fold_2'},
            # Target 2 models
            {'model': 'model_t2_f0', 'target': 'target_2', 'fold_info': 'fold_0'},
        ]
        
        # Act
        models_by_target = stage._group_models_by_target(prediction_models)
        
        # Assert
        assert len(models_by_target) == 3
        assert 'target_0' in models_by_target
        assert 'target_1' in models_by_target
        assert 'target_2' in models_by_target
        
        assert len(models_by_target['target_0']) == 2
        assert len(models_by_target['target_1']) == 3
        assert len(models_by_target['target_2']) == 1

    def test_group_models_mixed_with_and_without_target(self):
        """Test model grouping with mixed target information."""
        # Arrange
        config = Mock()
        stage = InferenceStage(config)
        
        prediction_models = [
            {'model': 'model_1', 'target': 'target_1', 'fold_info': 'fold_0'},
            {'model': 'model_2', 'fold_info': 'fold_1'},  # No target - should default to target_0
            {'model': 'model_3', 'target': 'target_1', 'fold_info': 'fold_2'},
        ]
        
        # Act
        models_by_target = stage._group_models_by_target(prediction_models)
        
        # Assert
        assert len(models_by_target) == 2
        assert 'target_0' in models_by_target  # Default for missing target
        assert 'target_1' in models_by_target
        
        assert len(models_by_target['target_0']) == 1  # The one without target
        assert len(models_by_target['target_1']) == 2  # The two with target_1