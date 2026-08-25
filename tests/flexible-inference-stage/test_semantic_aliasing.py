"""
Test semantic aliasing pattern for context keys in InferenceStage.
"""
import tempfile
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from emuses.pipelines.inference_stage import InferenceStage
from emuses.pipelines.pipeline_config import PipelineConfig


class TestSemanticAliasing(unittest.TestCase):
    """Test semantic aliasing for multiple context key names"""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp_dir.name) / "test_model"
        self.model_path.mkdir(exist_ok=True)
        
        self.config = PipelineConfig(
            output_folder=self.temp_dir.name,
            model_path=str(self.model_path),
            data_path="test_data.csv",
            validate_mode=False
        )

    def tearDown(self):
        """Clean up test environment.""" 
        self.temp_dir.cleanup()

    def test_handover_key_wins_over_generic_and_split_keys(self):
        """``inference_features`` wins; the raw split keys are not read at all.

        This test previously asserted that ``prediction_test_features`` had the highest
        priority. It does not, and must not: ``HeatmapStage`` copies *either*
        ``prediction_test_features`` or ``prediction_train_features`` into
        ``inference_features``, so reading the test split here would silently override
        which split validation runs against. See
        tests/pipelines/test_inference_stage_context_integration.py, which pins the
        refusal of a context that never went through that handover.
        """
        stage = InferenceStage(self.config)

        # Mock model loading to avoid file system dependencies
        stage._load_trained_models_with_context = MagicMock(return_value={
            'umap_model': None,
            'prediction_models': [],
            'metadata': {}
        })

        split_features = np.random.rand(10, 5)
        standalone_features = np.random.rand(8, 4)
        generic_features = np.random.rand(6, 3)

        context = {
            "prediction_test_features": split_features,       # Raw split - not read
            "inference_features": standalone_features,        # The handover key - wins
            "features": generic_features                      # Generic fallback
        }

        # Extract features using the method
        features = stage._load_features_from_context(context)

        np.testing.assert_array_equal(features, standalone_features)
        self.assertEqual(features.shape, (8, 4))

    def test_standalone_context_keys_fallback(self):
        """Test that standalone context keys (inference_features) are used when pipeline keys missing"""
        stage = InferenceStage(self.config)
        
        # Create context with only standalone and generic keys
        standalone_features = np.random.rand(8, 4)
        generic_features = np.random.rand(6, 3)
        
        context = {
            "inference_features": standalone_features,        # Standalone context (should win)
            "features": generic_features                      # Generic fallback
        }
        
        features = stage._load_features_from_context(context)
        
        # Should get standalone features (second priority)
        np.testing.assert_array_equal(features, standalone_features)
        self.assertEqual(features.shape, (8, 4))

    def test_generic_fallback_keys(self):
        """Test that generic fallback keys (features, input_matrix) work when specific keys missing"""
        stage = InferenceStage(self.config)
        
        # Create context with only generic keys
        generic_features = np.random.rand(6, 3)
        
        context = {
            "features": generic_features                      # Generic fallback
        }
        
        features = stage._load_features_from_context(context)
        
        # Should get generic features (fallback)
        np.testing.assert_array_equal(features, generic_features)
        self.assertEqual(features.shape, (6, 3))

    def test_labels_semantic_aliasing(self):
        """Labels follow the same rule as features: the handover key is what is read.

        ``inference_labels`` first, then ``labels``, then ``scores``.
        ``prediction_test_labels`` is deliberately not among them - see
        test_handover_key_wins_over_generic_and_split_keys for why.
        """
        stage = InferenceStage(self.config)

        standalone_labels = np.array([6, 7, 8])
        generic_labels = np.array([9, 10, 11])

        context = {
            "inference_features": np.random.rand(3, 3),
            "inference_labels": standalone_labels,         # Handover key (wins)
            "labels": generic_labels,                      # Generic fallback
            "prediction_test_labels": np.array([1, 2, 3]),  # Raw split - not read
        }

        stage._load_features_from_context(context)

        self.assertIsNotNone(stage._detected_labels)
        np.testing.assert_array_equal(stage._detected_labels, standalone_labels)

    def test_split_labels_alone_are_not_picked_up(self):
        """A context holding only the raw split keys yields no labels (and no features)."""
        stage = InferenceStage(self.config)

        context = {
            "features": np.random.rand(3, 3),
            "prediction_test_labels": np.array([1, 2, 3]),
        }

        stage._load_features_from_context(context)

        self.assertIsNone(stage._detected_labels)

    def test_missing_context_raises_error(self):
        """Test that missing all context keys raises appropriate error"""
        stage = InferenceStage(self.config)
        
        # Context with no feature keys
        context = {
            "some_other_data": "irrelevant"
        }
        
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            stage._load_features_from_context(context)
            
        self.assertIn("No inference features found in context", str(cm.exception))
        self.assertIn("InferenceStage must receive data from EMUSESPipeline", str(cm.exception))