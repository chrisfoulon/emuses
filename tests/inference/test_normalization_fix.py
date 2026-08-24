"""
Input normalization at inference time.

The rule, and the reason it matters: **EMUSESPipeline normalizes, InferenceStage does
not.** In inference mode the pipeline loads the model's saved ``input_scaler.joblib`` and
applies it to the incoming data, so the features it puts in the context are already in
the training input's space. ``InferenceStage._transform_features`` then hands them to
UMAP untouched. Normalizing in both places scales the data twice and collapses the UMAP
transform - the failure that produced (and cost a day to withdraw) an "inference emits
constant predictions" claim in August 2026.

These tests used to call ``pipeline.load_and_process_inputs()``, a method that no longer
exists, against a dataset path that did not exist either - so they failed in the
constructor and never reached what they were checking. They now drive the live path.
"""

import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from bcblib.tools.dataframe_filtering import normalize_dataframe

from emuses.pipelines.emuses_pipeline import EMUSESPipeline

TRAINING_DATA = pd.DataFrame({
    'feature1': [1.0, 2.0, 3.0, 4.0],
    'feature2': [10.0, 20.0, 30.0, 40.0],
})

INFERENCE_DATA = pd.DataFrame({
    'feature1': [5.0, 6.0],
    'feature2': [50.0, 60.0],
})


def inference_args(input_dataset, output_folder, model_path, normalization='robust'):
    """Args for an inference-mode pipeline run over a spreadsheet."""
    args = type('Args', (), {})()
    args.input_dataset = str(input_dataset)
    args.output_folder = str(output_folder)
    args.model_path = str(model_path)
    args.inference_mode = True
    args.input_normalization = normalization
    args.random_state = 42

    for attr in ['input_index_column', 'scores_header', 'scores_index_column',
                 'inputs_columns', 'scores_normalization', 'scores_column',
                 'recursive_search', 'input_file_types', 'bids_filters', 'scores',
                 'label_dataset']:
        setattr(args, attr, None)

    args.input_header = 0
    args.columns_are_features = True
    args.classification = False
    args.scores_normalization = "none"
    args.scores_are_rows = False
    args.filter_labelled_by_scores = False
    args.recursive_search = False
    args.arg_separator = ","
    return args


@pytest.fixture
def workspace():
    """A model directory with a saved input scaler, and an inference CSV."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        model_path = root / "model"
        model_path.mkdir()

        _, scaler = normalize_dataframe(TRAINING_DATA, method='robust')
        joblib.dump(scaler, model_path / "input_scaler.joblib")

        inference_csv = root / "inference.csv"
        INFERENCE_DATA.to_csv(inference_csv, index=False)

        yield {
            'root': root,
            'model_path': model_path,
            'scaler': scaler,
            'inference_csv': inference_csv,
        }


class TestInferenceNormalizationFix:
    """Inference mode applies the scaler saved at training time."""

    def test_input_normalization_applies_during_inference(self, workspace):
        pipeline = EMUSESPipeline(inference_args(
            workspace['inference_csv'], workspace['root'] / "out", workspace['model_path']
        ))

        features = pipeline.context["inference_features"]

        # Transformed, not raw
        assert not np.allclose(features, INFERENCE_DATA.values)

        # And transformed by *the training scaler*, not by one refitted on this data -
        # refitting would map these two rows onto themselves and lose the training scale.
        expected, _ = normalize_dataframe(
            INFERENCE_DATA, method='robust', scaling_factors=workspace['scaler']
        )
        np.testing.assert_array_almost_equal(features, expected.values, decimal=6)

    def test_input_normalization_warns_when_scaler_missing(self, workspace, caplog):
        """A missing scaler must not crash the run, and must say so."""
        no_scaler_model = workspace['root'] / "model_without_scaler"
        no_scaler_model.mkdir()

        pipeline = EMUSESPipeline(inference_args(
            workspace['inference_csv'], workspace['root'] / "out2", no_scaler_model
        ))

        assert "Input scaler not found" in caplog.text
        # Unnormalized rather than wrongly normalized
        np.testing.assert_array_equal(
            pipeline.context["inference_features"], INFERENCE_DATA.values
        )

    def test_the_scaler_is_not_applied_twice(self, workspace):
        """Feeding the pipeline's own output back in must not normalize it again.

        This is the shape of the withdrawn August 2026 "constant predictions" finding:
        ``split_dataset/test_features.npy`` is stored *after* normalization, and running
        inference on it normalizes a second time. The guard is that one pass over raw
        data and one pass over already-normalized data give different answers - if they
        did not, normalization would be a no-op and the test would prove nothing.
        """
        pipeline = EMUSESPipeline(inference_args(
            workspace['inference_csv'], workspace['root'] / "out3", workspace['model_path']
        ))
        once = pipeline.context["inference_features"]

        already_normalized_csv = workspace['root'] / "already_normalized.csv"
        pd.DataFrame(once, columns=INFERENCE_DATA.columns).to_csv(
            already_normalized_csv, index=False
        )
        twice = EMUSESPipeline(inference_args(
            already_normalized_csv, workspace['root'] / "out4", workspace['model_path']
        )).context["inference_features"]

        assert not np.allclose(once, twice), (
            "normalizing already-normalized input changed nothing - either the scaler is "
            "not being applied, or it is the identity and this test cannot detect double "
            "normalization"
        )
