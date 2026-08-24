"""``run_inference`` is the one implementation of inference. Everything calls it.

Replaces ``tests/cli/test_cli_consolidation.py`` and
``tests/cli/test_inference_args_creation.py``, whose subject
(``emuses.cli.main._execute_inference_locally``) no longer exists: Phase 1F moved
``emuses inference`` onto the service, so the CLI submits a job and the service runs it
(ADR §4). Their intent is carried over - the option mapping, the absence of duplicate
dataset processing, the stage configuration.

One assertion from the old file is deliberately not carried over.
``test_cli_uses_consolidated_pipeline`` required ``EMUSESPipeline`` to be called with two
positional arguments, ``(args, inference_data)``, and to be given an ``inference_data``
dict holding ``input_path``/``model_path``. No such call ever existed - the code always
called ``EMUSESPipeline(args)`` - so the test had been failing against an interface that
was never built. It is dropped rather than "fixed", because making it pass would mean
inventing that interface.

What matters most here is the option mapping. Inference applies the model's *saved*
scaler, so the new data has to be read and scaled exactly as the training data was. An
option that silently fails to reach the pipeline does not produce an error; it produces a
run that completes and is wrong.
"""

from unittest.mock import Mock, patch

import numpy as np
import pytest

from emuses.pipelines.inference_runner import build_inference_args, run_inference


def _full_config(tmp_path):
    """A config exercising every option the mapping is responsible for."""
    return {
        "input_dataset": str(tmp_path / "data.csv"),
        "output_folder": str(tmp_path / "out"),
        "model": str(tmp_path / "model"),
        "validate": False,
        "verify": True,
        "output_format": "csv",
        "input_header": 0,
        "input_index_column": 1,
        "scores_header": 0,
        "scores_index_column": 1,
        "scores": str(tmp_path / "scores.csv"),
        "columns_are_features": True,
        "input_normalization": "robust",
        "inputs_columns": ["a", "b"],
        "classification": True,
        "scores_normalization": "zscore",
        "scores_are_rows": True,
        "scores_column": ["target"],
        "filter_labelled_by_scores": True,
        "recursive_search": True,
        "input_file_types": [".csv"],
        "arg_separator": ";",
        "bids_filters": {"suffix": "T1w"},
    }


@pytest.mark.parametrize(
    "key, attribute",
    [
        ("input_header", "input_header"),
        ("input_index_column", "input_index_column"),
        ("scores_header", "scores_header"),
        ("scores_index_column", "scores_index_column"),
        ("columns_are_features", "columns_are_features"),
        ("input_normalization", "input_normalization"),
        ("inputs_columns", "inputs_columns"),
        ("classification", "classification"),
        ("scores_normalization", "scores_normalization"),
        ("scores_are_rows", "scores_are_rows"),
        ("scores_column", "scores_column"),
        ("filter_labelled_by_scores", "filter_labelled_by_scores"),
        ("recursive_search", "recursive_search"),
        ("input_file_types", "input_file_types"),
        ("arg_separator", "arg_separator"),
        ("bids_filters", "bids_filters"),
    ],
)
def test_every_preprocessing_option_reaches_the_pipeline(tmp_path, key, attribute):
    """Each option is checked individually so a failure names the one that was dropped."""
    config = _full_config(tmp_path)
    args = build_inference_args(config)

    assert getattr(args, attribute) == config[key], (
        f"{key} does not reach EMUSESPipeline as args.{attribute}. Inference would run "
        "with a different preprocessing setup than the model was trained with, complete "
        "successfully, and be wrong."
    )


def test_paths_and_inference_mode(tmp_path):
    """Dataset, output, model and the inference-mode switch."""
    config = _full_config(tmp_path)
    args = build_inference_args(config)

    assert args.input_dataset == config["input_dataset"]
    assert args.output_folder == config["output_folder"]
    assert args.model_path == config["model"], (
        "without model_path the pipeline cannot load the training scalers"
    )
    assert args.inference_mode is True, (
        "inference_mode=False would make the pipeline attempt training-only work"
    )
    assert args.scores == config["scores"]


def test_the_callers_key_names_are_both_accepted(tmp_path):
    """The CLI job config and InferenceRequest name the same things differently.

    ``input_dataset``/``output_folder``/``model`` versus ``data``/``output``/
    ``model_path``. Both reach the same attributes, so there is one implementation rather
    than an adapter per caller.
    """
    args = build_inference_args(
        {
            "data": str(tmp_path / "d.csv"),
            "output": str(tmp_path / "o"),
            "model_path": str(tmp_path / "m"),
        }
    )

    assert args.input_dataset == str(tmp_path / "d.csv")
    assert args.output_folder == str(tmp_path / "o")
    assert args.model_path == str(tmp_path / "m")


def test_inference_without_a_model_is_refused(tmp_path):
    """A model is the one thing inference cannot proceed without."""
    with pytest.raises(ValueError, match="model"):
        run_inference(
            {
                "input_dataset": str(tmp_path / "d.csv"),
                "output_folder": str(tmp_path / "o"),
            }
        )


def _patched_run(config):
    """Run ``run_inference`` with the pipeline and stage replaced, returning both mocks."""
    pipeline = Mock()
    pipeline.context = {
        "inference_features": np.array([[1.0, 2.0], [3.0, 4.0]]),
        "inference_labels": np.array([0.1, 0.2]),
        "dataset_type": "csv",
    }
    stage = Mock()
    stage.run.return_value = {"mode": "inference", "samples_processed": 2}

    with patch(
        "emuses.pipelines.emuses_pipeline.EMUSESPipeline", return_value=pipeline
    ) as pipeline_class, patch(
        "emuses.pipelines.inference_stage.InferenceStage", return_value=stage
    ):
        results = run_inference(config)

    return pipeline_class, pipeline, stage, results


def test_the_stage_receives_the_pipelines_prepared_context(tmp_path):
    """The prepared data reaches the stage, and nothing processes the dataset twice."""
    pipeline_class, pipeline, stage, _ = _patched_run(_full_config(tmp_path))

    pipeline_class.assert_called_once()
    context = stage.run.call_args[0][0]
    assert "inference_features" in context, (
        "the stage was handed a context without the prepared features - the shape that "
        "made POST /api/v1/inference return 422 for every request"
    )
    assert context["cli_inference_mode"] is True
    assert context["model_path"] == str(tmp_path / "model")

    pipeline.process_dataset.assert_not_called()
    pipeline.load_and_process_scores.assert_not_called()


def test_stage_configuration_comes_from_the_config(tmp_path):
    config = _full_config(tmp_path)
    config["validate"] = True
    _, _, stage, results = _patched_run(config)

    assert stage.model_path == str(tmp_path / "model")
    assert stage.output_path == str(tmp_path / "out")
    assert stage.validate_mode is True
    assert results == {"mode": "inference", "samples_processed": 2}


def test_the_stages_context_does_not_mutate_the_pipelines(tmp_path):
    """The stage's additions must not leak back into the pipeline's own context."""
    _, pipeline, _, _ = _patched_run(_full_config(tmp_path))

    assert "cli_inference_mode" not in pipeline.context
