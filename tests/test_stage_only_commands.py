"""`emuses umap` and `emuses heatmap` must run, or refuse for a reason the user can act on.

Both commands were unrunnable before 2026-08-23. Phase 1C fixed the CLI wiring (a shared
option declaration, the "command" key, the missing service routes), and then three further
defects surfaced only by actually running them - which is the point of these tests. A test
that mocks the pipeline would have passed against every one of them.

The defects, in the order the run hit them:

1. ``split_dataset`` passed ``self.scores`` straight to ``train_test_split``. On an
   unsupervised run scores are ``None`` and sklearn tried to index it.
2. ``InferenceStage`` was added whenever ``test_size > 0``, including to a UMAP-only job
   that has no prediction models for it to validate.
3. ``HeatmapStage`` consumed ``prediction_train_coords`` without checking it, so a
   heatmap-only run died as ``TypeError: 'NoneType' object is not subscriptable`` inside a
   joblib worker, four frames below anything the user controls.

Standalone ``heatmap`` remains unsupported *by design*: it fits against UMAP embeddings, and
``--load_umap``/``--load_embeddings`` are read by UMAPStage, which a heatmap-only run does
not execute. So the test pins the quality of the refusal, not a success.

Correction (2026-09-04): the sentence above was only half true when it was written.
``--load_embeddings`` was read by UMAPStage; ``--load_umap`` was read by **nothing** -- it was
declared, stored on PipelineConfig, plumbed through the service, and named by the refusal
message below as the remedy, while silently retraining instead. It is now genuinely wired, so
the refusal message stopped promising something that did not happen. Kept as a reminder that
"the error message says so" is not evidence that a flag does anything.
"""

import numpy as np
import pytest

from emuses.pipelines.pipeline_config import PipelineConfig


def test_unsupervised_split_does_not_index_none():
    """Defect 1, at the unit that had it."""
    from emuses.pipelines.emuses_pipeline import EMUSESPipeline

    source = __import__("inspect").getsource(EMUSESPipeline.split_dataset)
    assert "elif self.scores is None:" in source, (
        "split_dataset no longer special-cases scores=None, so an unsupervised run "
        "(`emuses umap`) passes None into train_test_split and dies indexing it."
    )


def test_inference_stage_requires_the_heatmap_stage_that_produces_its_input():
    """Defect 2. InferenceStage validates HeatmapStage's models; without them it cannot run."""
    from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

    source = __import__("inspect").getsource(PipelineRunner._run_pipeline_in_process)
    inference_block = source[source.index('config_dict.get("inference_stage_enabled"') - 400:]
    assert '"heatmap" in enabled_stages' in inference_block, (
        "InferenceStage is added without checking that HeatmapStage ran. A UMAP-only job "
        "then fails with 'No inference features found in context'."
    )


class _Ctx(dict):
    pass


def test_heatmap_stage_refuses_without_embeddings_and_says_why(tmp_path):
    """Defect 3: the refusal must name the missing input and a real way forward.

    Asserting on the message rather than merely on the exception type: the failure this
    replaced *was* an exception, just an unactionable one.
    """
    from emuses.pipelines.heatmap_stage import HeatmapStage

    stage = HeatmapStage(PipelineConfig(output_folder=tmp_path), [])
    context = {
        "prediction_train_coords": None,
        "prediction_train_labels": np.zeros(10),
    }

    with pytest.raises(ValueError) as excinfo:
        stage.run(context)

    message = str(excinfo.value)
    assert "prediction_train_coords" in message, "the message must name the missing input"
    assert "UMAPStage" in message, "the message must say which stage produces it"
    assert "emuses full" in message, "the message must offer a command that works"


def test_heatmap_stage_refuses_without_scores_and_says_why(tmp_path):
    from emuses.pipelines.heatmap_stage import HeatmapStage

    stage = HeatmapStage(PipelineConfig(output_folder=tmp_path), [])
    context = {
        "prediction_train_coords": np.zeros((10, 2)),
        "prediction_train_labels": None,
    }

    with pytest.raises(ValueError) as excinfo:
        stage.run(context)

    assert "--scores" in str(excinfo.value), (
        "the message must tell the user which flag supplies the missing scores"
    )
