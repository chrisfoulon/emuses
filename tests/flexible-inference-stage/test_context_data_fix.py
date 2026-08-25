"""
Test to verify that InferenceStage integration tests can be fixed with proper context data.
"""
import tempfile
import unittest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock

from emuses.pipelines.inference_stage import InferenceStage
from emuses.pipelines.pipeline_config import PipelineConfig


def stub_umap(embeddings):
    """UMAP stand-in returning real embeddings.

    A bare MagicMock returns a MagicMock from transform(), which reaches a
    ``f"...{np.min(embeddings):.6f}"`` log line and raises
    "unsupported format string passed to MagicMock.__format__".
    """
    umap = MagicMock(spec=["transform"])
    umap.transform.return_value = embeddings
    return umap


def stub_estimator(predictions):
    """Estimator stand-in. ``spec`` matters: a bare MagicMock has ``named_steps``,
    so InferenceStage treats it as an sklearn Pipeline and ensembles MagicMocks
    into an empty array."""
    estimator = MagicMock(spec=["predict"])
    estimator.predict.return_value = predictions
    return estimator


class TestContextDataFix(unittest.TestCase):
    """Test that integration tests work with proper context data"""

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

    def test_integration_with_proper_context_data(self):
        """Test that integration works when proper context data is provided"""
        stage = InferenceStage(self.config)
        
        # Mock model loading to avoid file system dependencies
        mock_prediction_model = stub_estimator(np.array([1.0, 2.0, 3.0]))

        stage._load_trained_models_with_context = MagicMock(return_value={
            'umap_model': stub_umap(np.random.rand(3, 2)),
            'prediction_models': [
                {'model': mock_prediction_model, 'name': 'test_model', 'score': 0.90}
            ],
            'metadata': {}
        })
        
        # Create proper context with inference_features (standalone context)
        test_features = np.random.rand(3, 5)
        test_labels = np.array([1.1, 2.2, 3.3])  # For validation mode
        
        context = {
            "inference_features": test_features,    # Standalone context format
            "inference_labels": test_labels         # For validation mode
        }
        
        # This should work now without ValueError
        results = stage.run(context)
        
        # Verify results
        self.assertIsNotNone(results)
        self.assertEqual(results['mode'], 'validation')  # Should detect validation mode
        self.assertEqual(results['samples_processed'], 3)
        self.assertEqual(len(results['target_results']['target_0']['ensemble_predictions']), 3)

    def test_inference_features_wins_over_pipeline_keys(self):
        """The handover key wins; the raw split keys do not override it.

        This test used to assert the opposite - that ``prediction_test_features`` had
        priority. It does not, deliberately. ``HeatmapStage`` copies *either*
        ``prediction_test_features`` or ``prediction_train_features`` into
        ``inference_features`` (heatmap_stage.py), so honouring the test split here would
        silently override its choice and validate against the wrong data. InferenceStage
        reads what it was handed; it does not re-decide the split.
        """
        stage = InferenceStage(self.config)

        mock_prediction_model = stub_estimator(np.array([4.0, 5.0]))

        stage._load_trained_models_with_context = MagicMock(return_value={
            'umap_model': stub_umap(np.random.rand(2, 2)),
            'prediction_models': [
                {'model': mock_prediction_model, 'name': 'test_model', 'score': 0.85}
            ],
            'metadata': {}
        })

        handed_over = np.random.rand(2, 4)
        handed_over_labels = np.array([4.4, 5.5])

        context = {
            # What HeatmapStage prepared - this is what the stage must use
            "inference_features": handed_over,
            "inference_labels": handed_over_labels,
            # The raw split keys, still in the context, disagreeing on sample count
            "prediction_test_features": np.random.rand(7, 4),
            "prediction_test_labels": np.random.rand(7),
        }

        results = stage.run(context)

        self.assertIsNotNone(results)
        self.assertEqual(results['mode'], 'validation')  # Should detect validation mode
        self.assertEqual(results['samples_processed'], 2)  # Handover keys, not the 7-row split