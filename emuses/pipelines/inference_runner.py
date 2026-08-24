"""Run inference against a trained EMUSES model.

This is the **single** implementation of "load a model, prepare new data the same way the
model's training data was prepared, and run :class:`InferenceStage` over it". Everything
that offers inference calls it:

- the service's inference job (``/api/v1/jobs/pipeline/inference``), which is where the
  CLI's ``emuses inference`` ends up;
- the synchronous ``/api/v1/inference`` and ``/api/v1/inference/async`` endpoints.

It exists because those callers had drifted into two shapes that behaved differently. The
CLI built an ``EMUSESPipeline`` in inference mode and handed :class:`InferenceStage` the
prepared context; the HTTP endpoints built a bare ``PipelineConfig`` and handed the stage a
context containing nothing but ``verify_integrity`` and ``output_format``. The second shape
could not work at all - measured 2026-08-24, ``POST /api/v1/inference`` returns 422 "No
inference features found in context" for every request, because nothing in that path ever
loads the data file. Keeping one function means the working path is the only path.

The data preparation matters and is not incidental: ``InferenceStage`` applies the model's
saved scaler, so the features it receives must be *raw* input in the same shape and space
as the training input. That is what ``EMUSESPipeline(inference_mode=True)`` produces.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _first(config: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return the first key present and not ``None``.

    Callers name the same three things differently - the CLI/service job config uses
    ``input_dataset``/``output_folder``/``model``, while :class:`InferenceRequest` uses
    ``data_path``/``output_path``/``model_path``. Accepting both keeps one implementation
    rather than one adapter per caller.
    """
    for key in keys:
        value = config.get(key)
        if value is not None:
            return value
    return None


def build_inference_args(config: Dict[str, Any]):
    """Build the argument object ``EMUSESPipeline`` expects for an inference run.

    Parameters
    ----------
    config : dict
        Inference configuration. See :func:`run_inference`.

    Returns
    -------
    object
        A plain namespace-style object with the attributes ``EMUSESPipeline`` reads.

    Notes
    -----
    Every preprocessing option here has to match what the model was trained with, so an
    option that is silently dropped produces a run that completes and is wrong. That is why
    this mapping is a named function with its own test rather than inline code.
    """
    args = type("Args", (), {})()

    args.input_dataset = str(_first(config, "input_dataset", "data"))
    args.output_folder = str(_first(config, "output_folder", "output"))
    args.random_state = None
    args.load_embeddings = None

    # Critical preprocessing parameters for data processing
    args.input_header = config.get("input_header")
    args.input_index_column = config.get("input_index_column")
    args.scores_header = config.get("scores_header")
    args.scores_index_column = config.get("scores_index_column")
    args.scores = str(config["scores"]) if config.get("scores") else None

    # Additional preprocessing parameters
    args.columns_are_features = config.get("columns_are_features", False)
    args.input_normalization = config.get("input_normalization", "none")
    args.inputs_columns = config.get("inputs_columns")
    args.classification = config.get("classification", False)

    # Advanced processing parameters
    args.scores_normalization = config.get("scores_normalization", "none")
    args.scores_are_rows = config.get("scores_are_rows", False)
    args.scores_column = config.get("scores_column")
    args.filter_labelled_by_scores = config.get("filter_labelled_by_scores", False)
    args.recursive_search = config.get("recursive_search", False)
    args.input_file_types = config.get("input_file_types")
    args.arg_separator = config.get("arg_separator", ",")
    args.bids_filters = config.get("bids_filters")

    # Skip training-specific operations
    args.inference_mode = True

    # Model path, used to load the training scalers
    model_path = _first(config, "model", "model_path")
    if model_path:
        args.model_path = str(model_path)

    return args


def run_inference(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run inference on new data with a trained EMUSES model.

    Parameters
    ----------
    config : dict
        Inference configuration. Required: the input dataset (``input_dataset`` or
        ``data``), the output folder (``output_folder`` or ``output``) and the trained
        model directory (``model`` or ``model_path``). Optional: ``validate``,
        ``verify``, ``output_format`` and the preprocessing options listed in
        :func:`build_inference_args`.

    Returns
    -------
    dict
        The results ``InferenceStage`` produced - mode, sample count, predictions,
        output file paths and, in validation mode, validation metrics.

    Raises
    ------
    ValueError
        If no model directory was supplied.
    """
    from emuses.pipelines.emuses_pipeline import EMUSESPipeline
    from emuses.pipelines.inference_stage import InferenceStage

    model_path = _first(config, "model", "model_path")
    if not model_path:
        raise ValueError("A trained model directory is required for inference")

    args = build_inference_args(config)

    # EMUSESPipeline prepares the data; format_args() handles inference mode, so there is
    # no second copy of the dataset-processing logic here.
    pipeline = EMUSESPipeline(args)

    # Copy so the stage's additions do not mutate the pipeline's own context.
    context = pipeline.context.copy()
    context.update(
        {
            "verify_integrity": config.get("verify", True),
            "output_format": config.get("output_format", "csv"),
            "model_path": str(model_path),
            "cli_inference_mode": True,
        }
    )

    inference_stage = InferenceStage(pipeline.config)
    inference_stage.model_path = str(model_path)
    inference_stage.output_path = str(_first(config, "output_folder", "output"))
    inference_stage.validate_mode = config.get("validate", False)

    results = inference_stage.run(context)

    logger.info(
        "Inference completed: mode=%s, samples=%s",
        results.get("mode", "inference"),
        results.get("samples_processed"),
    )
    return results
