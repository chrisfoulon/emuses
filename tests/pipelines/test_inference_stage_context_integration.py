"""
Test InferenceStage integration with HeatmapStage context bridge.

Validates that the context preparation fixes the original pipeline regression.
"""
import numpy as np
import pytest
from unittest.mock import Mock

from emuses.pipelines.inference_stage import InferenceStage


class TestInferenceStageContextIntegration:
    """Test InferenceStage can load context prepared by HeatmapStage."""

    def test_inference_stage_loads_prepared_context(self):
        """
        Test that InferenceStage successfully loads context from HeatmapStage.
        
        This validates the fix for the original regression where InferenceStage
        failed with "No inference features found in context".
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        stage = InferenceStage(config)
        
        # Simulate context as prepared by HeatmapStage context bridge
        test_features = np.random.rand(8, 4)  # 8 samples, 4 features  
        test_labels = np.random.rand(8, 1)    # 8 samples, 1 target
        
        context = {
            "inference_features": test_features,    # Set by HeatmapStage context bridge
            "inference_labels": test_labels,        # Set by HeatmapStage context bridge
            # Additional context that might be present
            "prediction_models": [],
        }
        
        # Act & Assert - should not raise ValueError
        loaded_features = stage._load_features_from_context(context)
        
        # Verify features are loaded correctly
        np.testing.assert_array_equal(loaded_features, test_features)

    def test_inference_stage_handles_missing_labels_gracefully(self):
        """
        Test InferenceStage works when only features provided (no labels).
        
        This covers the case where HeatmapStage sets inference_features
        but not inference_labels.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        stage = InferenceStage(config)
        
        # Context with features but no labels
        test_features = np.random.rand(5, 3)
        
        context = {
            "inference_features": test_features,
            # No inference_labels - should handle gracefully
        }
        
        # Act - should not crash
        loaded_features = stage._load_features_from_context(context)
        
        # Assert
        np.testing.assert_array_equal(loaded_features, test_features)
        assert stage._detected_labels is None

    def test_inference_stage_fallback_behavior_preserved(self):
        """
        Test that InferenceStage fallback logic still works.
        
        Ensures backward compatibility with other context key names.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test"
        stage = InferenceStage(config)
        
        # Context using fallback key names
        test_features = np.random.rand(3, 6)
        
        context = {
            "features": test_features,  # Fallback key name
            # No inference_features
        }
        
        # Act
        loaded_features = stage._load_features_from_context(context)
        
        # Assert - fallback still works
        np.testing.assert_array_equal(loaded_features, test_features)

    def test_original_regression_scenario_resolved(self):
        """
        Test the exact regression scenario that was failing.
        
        Simulates the pipeline context state when InferenceStage was called
        but HeatmapStage hadn't prepared the inference_features key.
        """
        # Arrange
        config = Mock()
        config.output_folder = "/tmp/test" 
        stage = InferenceStage(config)
        
        # This was the failing scenario - context with prediction data but no inference_features
        test_features = np.random.rand(10, 5)
        test_labels = np.random.rand(10, 1)
        
        # BEFORE FIX: This context would cause ValueError
        context_before_fix = {
            "prediction_test_features": test_features,  # Available but not used
            "prediction_test_labels": test_labels,      # Available but not used
            "prediction_models": [],
            # Missing: inference_features (InferenceStage couldn't find this)
        }
        
        # AFTER FIX: HeatmapStage now prepares inference_features
        context_after_fix = {
            "prediction_test_features": test_features,
            "prediction_test_labels": test_labels,
            "inference_features": test_features,        # Now set by HeatmapStage
            "inference_labels": test_labels,           # Now set by HeatmapStage
            "prediction_models": [],
        }
        
        # Act & Assert - Before fix would raise ValueError
        with pytest.raises(ValueError, match="No inference features found in context"):
            stage._load_features_from_context(context_before_fix)
        
        # After fix should work
        loaded_features = stage._load_features_from_context(context_after_fix)
        np.testing.assert_array_equal(loaded_features, test_features)