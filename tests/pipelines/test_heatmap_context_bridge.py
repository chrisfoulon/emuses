"""
Test pipeline context bridge functionality for InferenceStage integration.

Tests that HeatmapStage properly prepares context for InferenceStage by setting
the inference_features and inference_labels keys expected downstream.
"""
import numpy as np
import pytest
from unittest.mock import Mock, patch

from emuses.pipelines.heatmap_stage import HeatmapStage


class TestHeatmapContextBridge:
    """Test HeatmapStage context preparation for InferenceStage."""

    def test_context_bridge_with_test_features(self):
        """
        Test that HeatmapStage sets inference_features from prediction_test_features.
        
        This is the primary use case - using test data for inference validation.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        config.classification = False
        config.n_jobs = 1
        
        stage = HeatmapStage(config, output_format_info=(64,))
        
        # Create mock context with test features (the typical case)
        test_features = np.random.rand(10, 5)  # 10 samples, 5 features
        test_labels = np.random.rand(10, 1)    # 10 samples, 1 target
        train_coords = np.random.rand(20, 2)   # 20 samples, 2 UMAP coords
        train_labels = np.random.rand(20, 1)   # 20 samples, 1 target
        
        context = {
            "prediction_test_features": test_features,
            "prediction_test_labels": test_labels,
            "prediction_train_coords": train_coords, 
            "prediction_train_labels": train_labels,
        }
        
        # Mock all the heavy processing to focus only on context bridge
        with patch.object(stage, '_generate_performance_csv_files'), \
             patch('emuses.pipelines.heatmap_stage._optimise_target') as mock_optimize, \
             patch('emuses.tools.parallelism_utils.create_safe_parallel') as mock_parallel:
            
            # Mock parallel processing to return empty results
            mock_parallel.return_value.return_value = []
            mock_optimize.return_value = ("target_0", np.array([]), [])
            
            # Act
            stage.run(context)
        
        # Assert - InferenceStage expects these keys
        assert "inference_features" in context
        assert "inference_labels" in context
        
        # Verify test features are used (preferred for inference)
        np.testing.assert_array_equal(context["inference_features"], test_features)
        np.testing.assert_array_equal(context["inference_labels"], test_labels)

    def test_context_bridge_fallback_to_train_features(self):
        """
        Test fallback to train features when test features unavailable.
        
        This handles edge cases where no test split was created.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        config.classification = False
        config.n_jobs = 1
        
        stage = HeatmapStage(config, output_format_info=(64,))
        
        # Context with only train features (no test data)
        train_features = np.random.rand(15, 8)  # 15 samples, 8 features
        train_labels = np.random.rand(15, 1)    # 15 samples, 1 target
        train_coords = np.random.rand(15, 2)    # 15 samples, 2 UMAP coords
        
        context = {
            "prediction_train_features": train_features,
            "prediction_train_labels": train_labels,
            "prediction_train_coords": train_coords,
            "prediction_train_labels": train_labels,
            # No test features available
        }
        
        # Mock the internal processing
        with patch.object(stage, '_generate_performance_csv_files'), \
             patch('emuses.pipelines.heatmap_stage._optimise_target') as mock_optimize, \
             patch('emuses.tools.parallelism_utils.create_safe_parallel') as mock_parallel:
            
            # Mock parallel processing to return empty results
            mock_parallel.return_value.return_value = []
            mock_optimize.return_value = ("target_0", np.array([]), [])
            
            # Act
            stage.run(context)
        
        # Assert - Should fallback to train features
        assert "inference_features" in context
        assert "inference_labels" in context
        
        # Verify train features are used as fallback
        np.testing.assert_array_equal(context["inference_features"], train_features)
        np.testing.assert_array_equal(context["inference_labels"], train_labels)

    def test_context_bridge_with_missing_labels(self):
        """
        Test context bridge when labels are None but features available.
        
        Should set inference_features but gracefully handle missing labels.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        config.classification = False
        config.n_jobs = 1
        
        stage = HeatmapStage(config, output_format_info=(64,))
        
        # Context with features but no labels
        test_features = np.random.rand(5, 3)
        train_coords = np.random.rand(10, 2)
        train_labels = np.random.rand(10, 1)
        
        context = {
            "prediction_test_features": test_features,
            "prediction_test_labels": None,  # No labels available
            "prediction_train_coords": train_coords,
            "prediction_train_labels": train_labels,
        }
        
        # Mock the internal processing
        with patch.object(stage, '_generate_performance_csv_files'), \
             patch('emuses.pipelines.heatmap_stage._optimise_target') as mock_optimize, \
             patch('emuses.tools.parallelism_utils.create_safe_parallel') as mock_parallel:
            
            # Mock parallel processing to return empty results
            mock_parallel.return_value.return_value = []
            mock_optimize.return_value = ("target_0", np.array([]), [])
            
            # Act
            stage.run(context)
        
        # Assert
        assert "inference_features" in context
        np.testing.assert_array_equal(context["inference_features"], test_features)
        
        # Labels should not be set when None
        assert context.get("inference_labels") is None

    def test_context_bridge_with_no_prediction_features(self):
        """
        Test graceful handling when no prediction features available.
        
        Should not crash but also not set inference_features.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        config.classification = False
        config.n_jobs = 1
        
        stage = HeatmapStage(config, output_format_info=(64,))
        
        # Context with minimal required data but no prediction features  
        train_coords = np.random.rand(5, 2)
        train_labels = np.random.rand(5, 1)
        
        context = {
            "prediction_train_coords": train_coords,
            "prediction_train_labels": train_labels,
            # No prediction_test_features or prediction_train_features
        }
        
        # Mock the internal processing
        with patch.object(stage, '_generate_performance_csv_files'), \
             patch('emuses.pipelines.heatmap_stage._optimise_target') as mock_optimize, \
             patch('emuses.tools.parallelism_utils.create_safe_parallel') as mock_parallel:
            
            # Mock parallel processing to return empty results
            mock_parallel.return_value.return_value = []
            mock_optimize.return_value = ("target_0", np.array([]), [])
            
            # Act - should not crash
            stage.run(context)
        
        # Assert - should not set inference features
        assert "inference_features" not in context
        assert "inference_labels" not in context