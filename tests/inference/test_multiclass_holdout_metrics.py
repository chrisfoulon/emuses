"""Held-out scoring for one-vs-rest multi-class runs.

The defect these pin, measured on a real digits run (2026-08-25): ``--classification``
with ten classes makes ``HeatmapStage`` expand the label column into ten one-vs-rest
targets, but the expansion was a **local variable**. The test split was handed over as
the original single class column, so ``_calculate_multi_target_validation_metrics``
compared ten prediction columns against one ground-truth column, logged

    Ground truth dimensions (1) don't match target count (10)

and returned ``None``. The run exited 0 and wrote a metadata file containing only
timing - no held-out performance at all, from one WARNING line inside a 3.7 MB log. The
true accuracy, computed by hand from the predictions CSV afterwards, was 0.9750.

Two things are pinned here. First, the ground truth is expanded with the classes seen in
**training**: a split missing a class would otherwise yield fewer columns and shift every
target past the gap, which produces a plausible number that is silently wrong - strictly
worse than the missing metric. Second, targets are ordered numerically, because
``sorted()`` places ``target_10`` before ``target_2`` and ten classes is exactly where
that starts to bite.

Small explicit arrays are used deliberately: the value of these cases is that the
expected metric is checkable by hand, which a real-data fixture would obscure. The
real-data confirmation is the digits run itself.
"""

import logging

import numpy as np
import pytest

from emuses.pipelines.heatmap_stage import HeatmapStage
from emuses.pipelines.inference_stage import InferenceStage

LOGGER = logging.getLogger(__name__)
THREE_CLASSES = np.array([0.0, 1.0, 2.0])


@pytest.fixture
def stage():
    """An InferenceStage without running its constructor - these methods need no config."""
    return object.__new__(InferenceStage)


def _target_results(columns):
    """Build the target_results shape ``_predict`` returns (ADR 2.5b contract 1)."""
    return {
        f"target_{i}": {"ensemble_predictions": np.asarray(col, dtype=float)}
        for i, col in enumerate(columns)
    }


class TestLabelExpansion:
    def test_class_column_becomes_one_column_per_class(self):
        labels = np.array([[0.0], [1.0], [2.0], [1.0]])
        out = HeatmapStage._expand_ovr_labels(labels, THREE_CLASSES, {}, LOGGER)

        assert out.shape == (4, 3)
        assert (out.sum(axis=1) == 1).all(), "each row must mark exactly one class"
        np.testing.assert_array_equal(out[:, 1], [0, 1, 0, 1])

    def test_original_class_column_is_kept_for_multiclass_scoring(self):
        context = {}
        labels = np.array([[0.0], [2.0], [1.0]])
        HeatmapStage._expand_ovr_labels(labels, THREE_CLASSES, context, LOGGER)

        np.testing.assert_array_equal(
            context["inference_labels_multiclass"], [0.0, 2.0, 1.0]
        )

    def test_a_split_missing_a_class_keeps_the_training_column_layout(self):
        """The misalignment trap: recomputing classes from the split shifts columns.

        Class 1 is absent here. Deriving the classes from this split would give two
        columns, and what the models call class 2 would be scored against column 1.
        """
        labels = np.array([[0.0], [2.0], [0.0], [2.0]])

        out = HeatmapStage._expand_ovr_labels(labels, THREE_CLASSES, {}, LOGGER)

        assert out.shape[1] == 3, "must keep one column per TRAINING class"
        np.testing.assert_array_equal(out[:, 1], [0, 0, 0, 0])
        np.testing.assert_array_equal(out[:, 2], [0, 1, 0, 1])

    def test_regression_runs_are_untouched(self):
        """No one-vs-rest conversion happened, so nothing may be rewritten."""
        labels = np.array([[1.5], [2.5]])
        out = HeatmapStage._expand_ovr_labels(labels, None, {}, LOGGER)
        np.testing.assert_array_equal(out, labels)

    def test_already_multi_target_labels_pass_through(self):
        labels = np.array([[1.0, 2.0], [3.0, 4.0]])
        out = HeatmapStage._expand_ovr_labels(labels, THREE_CLASSES, {}, LOGGER)
        np.testing.assert_array_equal(out, labels)


class TestTargetOrdering:
    def test_targets_are_ordered_numerically_not_lexicographically(self, stage):
        results = {f"target_{i}": {} for i in range(12)}

        ordered = stage._order_targets(results)

        assert ordered[:3] == ["target_0", "target_1", "target_2"]
        assert ordered != sorted(results), (
            "sorted() puts target_10 before target_2, which pairs every prediction "
            "column with the wrong class from ten targets upward"
        )


class TestMulticlassScoring:
    def test_argmax_recovers_the_predicted_class(self, stage):
        # Rows predict class 2, 0, 1 respectively.
        results = _target_results([[0.0, 1.0, 0.2], [0.2, 0.0, 0.8], [1.0, 0.0, 0.0]])
        truth = np.array([2.0, 0.0, 1.0])

        m = stage._calculate_multiclass_validation_metrics(results, truth, THREE_CLASSES)

        assert m["accuracy"] == 1.0
        assert m["n_correct"] == 3
        assert m["n_classes"] == 3

    def test_a_wrong_prediction_lowers_accuracy(self, stage):
        results = _target_results([[0.0, 1.0], [0.2, 0.0], [1.0, 0.0]])
        truth = np.array([2.0, 1.0])  # second row predicts class 0, truth is 1

        m = stage._calculate_multiclass_validation_metrics(results, truth, THREE_CLASSES)

        assert m["accuracy"] == 0.5
        assert m["n_correct"] == 1

    def test_silent_and_tied_rows_are_counted_not_hidden(self, stage):
        """argmax resolves both by column order, so they must be reported.

        Row 0 is ``[0, 0, 0]``: no target fired. Row 1 is ``[1, 1, 0]``: two tie.
        A silent row counts as tied as well - every column is equal at zero - so
        the tie count is 2, not 1. That overlap is intentional: both mean "argmax
        picked a column for a reason that is not evidence".
        """
        results = _target_results([[0.0, 1.0], [0.0, 1.0], [0.0, 0.0]])
        truth = np.array([0.0, 0.0])

        m = stage._calculate_multiclass_validation_metrics(results, truth, THREE_CLASSES)

        assert m["rows_with_no_positive_target"] == 1
        assert m["rows_with_tied_targets"] == 2

    def test_returns_none_when_the_run_was_not_one_vs_rest(self, stage):
        results = _target_results([[0.1, 0.2]])
        assert stage._calculate_multiclass_validation_metrics(results, None, None) is None

    def test_returns_none_when_target_count_disagrees_with_class_count(self, stage):
        results = _target_results([[1.0, 0.0]])  # one target
        truth = np.array([0.0, 1.0])
        assert (
            stage._calculate_multiclass_validation_metrics(results, truth, THREE_CLASSES)
            is None
        )


class TestPerTargetScoringNoLongerBailsOut:
    def test_expanded_labels_are_scored_instead_of_skipped(self, stage):
        """The exact regression: 3 targets against a 1-column ground truth.

        Before the fix this returned None for any multi-class classification run.
        """
        results = _target_results([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        raw = np.array([[0.0], [1.0], [2.0]])

        assert stage._calculate_multi_target_validation_metrics(results, raw) is None

        expanded = HeatmapStage._expand_ovr_labels(raw, THREE_CLASSES, {}, LOGGER)
        metrics = stage._calculate_multi_target_validation_metrics(results, expanded)

        assert metrics is not None
        assert len([k for k in metrics if not k.startswith("_")]) == 3

    def test_per_target_pairing_survives_more_than_ten_targets(self, stage):
        """Ground truth columns are paired by POSITION, so ordering is correctness.

        Twelve targets, each predicting its own class perfectly. Under lexicographic
        ordering target_10 would be scored against class 1's column and every
        metric past index 1 would be wrong while still looking plausible.
        """
        n = 12
        eye = np.eye(n)
        results = _target_results([eye[:, i] for i in range(n)])
        truth = eye.astype(int)

        metrics = stage._calculate_multi_target_validation_metrics(results, truth)

        assert metrics is not None
        for i in range(n):
            assert metrics[f"target_{i}"]["accuracy"] == 1.0, (
                f"target_{i} was paired with the wrong ground-truth column"
            )

    def test_balanced_accuracy_is_reported_for_classification_targets(self, stage):
        """Training optimises balanced accuracy; validation must report it too.

        On an imbalanced one-vs-rest target, a model that always answers "no" scores
        well on plain accuracy. Balanced accuracy is what exposes that.
        """
        predictions = np.zeros(10)  # degenerate: never predicts the positive class
        truth = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1])

        m = stage._calculate_validation_metrics(predictions, truth)

        assert m["accuracy"] == pytest.approx(0.9)
        assert m["balanced_accuracy"] == pytest.approx(0.5), (
            "a model predicting only the majority class must not look 90% correct"
        )
