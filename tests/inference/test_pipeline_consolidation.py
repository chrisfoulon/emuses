"""
Tests for EMUSESPipeline inference-mode consolidation.

Inference and training go through the same pipeline: ``inference_mode`` on the args is
what separates them. The dataset is processed once, no split is performed, and
``inference_features`` / ``inference_labels`` land in the context for InferenceStage.

These tests used to exercise an ``EMUSESPipeline(args, inference_data=...)`` injection
parameter. That parameter was stored on the instance and never read again - it did
nothing - and was removed in Phase 4. What it claimed to protect (the dataset is not
processed twice on the way to InferenceStage) is asserted against the live path in
``tests/pipelines/test_inference_runner.py::test_the_stage_receives_the_pipelines_prepared_context``.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from emuses.pipelines.emuses_pipeline import EMUSESPipeline


def make_args(input_dataset, output_folder, inference_mode):
    """Minimal args object accepted by PipelineConfig."""
    args = type('Args', (), {})()
    args.input_dataset = str(input_dataset)
    args.output_folder = str(output_folder)
    args.random_state = 42
    args.inference_mode = inference_mode

    for attr in ['input_header', 'input_index_column', 'scores_header', 'scores_index_column',
                 'columns_are_features', 'input_normalization', 'inputs_columns', 'classification',
                 'scores_normalization', 'scores_are_rows', 'scores_column',
                 'filter_labelled_by_scores', 'recursive_search', 'input_file_types',
                 'arg_separator', 'bids_filters', 'scores', 'model_path']:
        setattr(args, attr, None)

    # Rows are samples. With columns_are_features False the matrix is transposed, which
    # is the option's job, not a bug - a 3x2 CSV then yields 2 samples of 3 features.
    args.columns_are_features = True
    args.input_normalization = "none"
    args.classification = False
    args.scores_normalization = "none"
    args.scores_are_rows = False
    args.filter_labelled_by_scores = False
    args.recursive_search = False
    args.arg_separator = ","
    return args


class TestInferenceModeContext(unittest.TestCase):
    """What inference mode puts in the context, and what it skips."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.input_dataset = self.temp_path / "test_data.csv"
        np.savetxt(self.input_dataset, np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]), delimiter=',')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _pipeline(self, inference_mode):
        return EMUSESPipeline(
            make_args(self.input_dataset, self.temp_path / "output", inference_mode)
        )

    def test_inference_mode_prepares_the_keys_inference_stage_reads(self):
        pipeline = self._pipeline(inference_mode=True)

        self.assertIn("inference_features", pipeline.context)
        self.assertIn("inference_labels", pipeline.context)
        self.assertIsInstance(pipeline.context["inference_features"], np.ndarray)
        self.assertEqual(pipeline.context["inference_features"].shape[0], 3)

    def test_inference_mode_keeps_the_pipeline_wide_context_keys(self):
        pipeline = self._pipeline(inference_mode=True)

        for key in ("dataset_type", "output_format_info", "random_seeds", "output_folder"):
            with self.subTest(key=key):
                self.assertIn(key, pipeline.context)

    def test_inference_mode_does_not_split_the_dataset(self):
        """No train/test split: there is nothing to hold out at inference time."""
        with patch.object(EMUSESPipeline, 'split_dataset') as mock_split:
            pipeline = self._pipeline(inference_mode=True)

        mock_split.assert_not_called()
        self.assertNotIn("prediction_train_features", pipeline.context)

    def test_training_mode_splits_and_does_not_set_inference_keys(self):
        with patch.object(EMUSESPipeline, 'split_dataset') as mock_split:
            pipeline = self._pipeline(inference_mode=False)

        mock_split.assert_called_once()
        self.assertNotIn("inference_features", pipeline.context)

    def test_the_dataset_is_processed_once(self):
        """One pass over the data. The double processing this file was written for was
        the CLI building its own pipeline context on top of the pipeline's."""
        with patch.object(
            EMUSESPipeline, 'process_dataset',
            return_value=(np.array([[1.0, 2.0], [3.0, 4.0]]), "spreadsheet", [0, 1], None)
        ) as mock_process:
            with patch.object(EMUSESPipeline, 'load_and_process_scores'):
                self._pipeline(inference_mode=True)

        self.assertEqual(mock_process.call_count, 1)


if __name__ == "__main__":
    unittest.main()
