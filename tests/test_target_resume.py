"""Reusing a finished target must be equivalent to re-running it, or not happen.

The prediction search is the expensive half of EMUSES (~19 h on DSD_repro), and
targets are independent, so an interrupted run can resume a target at a time.
The danger is not the saving; it is reusing a stored result that answers a
different question -- after the morphospace changed, or the search space, or the
trial budget, or the seeds. Every one of those produces a run that completes and
reports another experiment's numbers.

Note on evidence (this cost a wrong conclusion once already): identical scores
after a resume prove NOTHING, because the search is seeded and re-running it
returns the same numbers anyway. The only decisive check is that the search is
never invoked, which is what `TestTheSearchIsActuallySkipped` asserts.
"""

import json

import numpy as np
import pytest

from emuses.tools.target_resume import (FINGERPRINT_FILENAME, SCORES_FILENAME,
                                        build_target_fingerprint,
                                        load_completed_target,
                                        write_target_artefacts)

BASE = dict(
    task="reg",
    outer_folds=5,
    optuna_trials=15,
    optim_dict={"param": {"model": {"model_type": {"choices": ["kernel"]}}}},
    seeds={"cv_seed": 42, "optuna_seed": 42, "prediction_seed": 42},
)


def _fp(**overrides):
    rng = np.random.default_rng(0)
    kwargs = dict(BASE)
    kwargs.setdefault("X", rng.random((20, 2)))
    kwargs.setdefault("y", rng.random(20))
    kwargs.update(overrides)
    return build_target_fingerprint(**kwargs)


def _complete_target(tmp_path, tag="target_0", n_folds=5, fingerprint=None, scores=None):
    """A target folder shaped like one a real run leaves behind."""
    import joblib
    from sklearn.dummy import DummyRegressor

    folder = tmp_path / tag
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n_folds):
        model = DummyRegressor(strategy="constant", constant=float(i))
        model.fit(np.zeros((3, 2)), np.zeros(3))
        # The real names carry a version suffix; use that shape, not a tidy one.
        joblib.dump(model, folder / f"best_pipeline_fold{i}_v1_0_0_joblib1_5_2.joblib")
    fingerprint = fingerprint or _fp()
    scores = np.arange(n_folds, dtype=np.float64) / 7.0 if scores is None else scores
    write_target_artefacts(tmp_path, tag, scores, fingerprint)
    return fingerprint, scores


class TestFingerprintSensitivity:
    """Anything that changes the answer must change the fingerprint."""

    def test_identical_inputs_match(self):
        assert _fp() == _fp()

    @pytest.mark.parametrize(
        "field,value",
        [
            ("task", "clf"),
            ("outer_folds", 10),
            ("optuna_trials", 7),
            ("optim_dict", {"param": {"model": {"model_type": {"choices": ["elastic"]}}}}),
            ("seeds", {"cv_seed": 1, "optuna_seed": 42, "prediction_seed": 42}),
        ],
    )
    def test_changing_the_search_invalidates(self, field, value):
        assert _fp() != _fp(**{field: value})

    def test_different_coordinates_invalidate(self):
        """The models were fitted on the morphospace; a new one voids them."""
        rng = np.random.default_rng(99)
        assert _fp() != _fp(X=rng.random((20, 2)))

    def test_different_targets_invalidate(self):
        rng = np.random.default_rng(98)
        assert _fp() != _fp(y=rng.random(20))

    def test_uncomputable_is_none(self):
        assert _fp(X=None) is None


class TestLoading:
    def test_a_complete_matching_target_is_reused(self, tmp_path):
        fingerprint, scores = _complete_target(tmp_path)
        loaded = load_completed_target(tmp_path, "target_0", fingerprint)
        assert loaded is not None
        assert np.array_equal(loaded[0], scores)
        assert len(loaded[1]) == 5

    def test_full_precision_is_preserved(self, tmp_path):
        """The per-fold CSV rounds to 4dp; resuming from that would move numbers."""
        scores = np.array([-0.13357123456, -0.98086987654, -0.2952781, -0.004920,
                           -0.36223114])
        fingerprint, _ = _complete_target(tmp_path, scores=scores)
        loaded = load_completed_target(tmp_path, "target_0", fingerprint)
        assert np.array_equal(loaded[0], scores)
        assert not np.array_equal(loaded[0], np.round(scores, 4))

    def test_a_changed_fingerprint_is_refused(self, tmp_path):
        _complete_target(tmp_path)
        assert load_completed_target(tmp_path, "target_0", _fp(optuna_trials=7)) is None

    def test_nothing_stored_is_none(self, tmp_path):
        assert load_completed_target(tmp_path, "target_0", _fp()) is None

    def test_a_damaged_fingerprint_is_none(self, tmp_path):
        _complete_target(tmp_path)
        (tmp_path / "target_0" / FINGERPRINT_FILENAME).write_text("{not json")
        assert load_completed_target(tmp_path, "target_0", _fp()) is None

    def test_a_future_schema_is_refused(self, tmp_path):
        fingerprint, _ = _complete_target(tmp_path)
        stored = json.loads((tmp_path / "target_0" / FINGERPRINT_FILENAME).read_text())
        stored["schema"] = 999
        (tmp_path / "target_0" / FINGERPRINT_FILENAME).write_text(json.dumps(stored))
        assert load_completed_target(tmp_path, "target_0", fingerprint) is None

    def test_missing_scores_refuses_rather_than_using_the_rounded_csv(self, tmp_path):
        fingerprint, _ = _complete_target(tmp_path)
        (tmp_path / "target_0" / SCORES_FILENAME).unlink()
        assert load_completed_target(tmp_path, "target_0", fingerprint) is None

    def test_missing_fold_models_refuses(self, tmp_path):
        fingerprint, _ = _complete_target(tmp_path)
        for p in (tmp_path / "target_0").glob("best_pipeline_fold*.joblib"):
            p.unlink()
        assert load_completed_target(tmp_path, "target_0", fingerprint) is None

    def test_an_interrupted_target_with_a_fold_gap_refuses(self, tmp_path):
        """fold0, fold1, fold3 is a crash mid-target, not a finished search."""
        fingerprint, _ = _complete_target(tmp_path)
        (tmp_path / "target_0" /
         "best_pipeline_fold2_v1_0_0_joblib1_5_2.joblib").unlink()
        assert load_completed_target(tmp_path, "target_0", fingerprint) is None

    def test_fold_count_must_match_score_count(self, tmp_path):
        fingerprint, _ = _complete_target(tmp_path, n_folds=5,
                                          scores=np.zeros(3, dtype=np.float64))
        assert load_completed_target(tmp_path, "target_0", fingerprint) is None

    def test_folds_load_in_fold_order_not_lexical_order(self, tmp_path):
        """With 10+ folds, 'fold10' sorts before 'fold2' as text.

        The pipelines are returned as a list whose position IS the fold, so
        lexical ordering silently pairs fold 10's model with fold 1's score.
        """
        fingerprint, _ = _complete_target(
            tmp_path, n_folds=12,
            fingerprint=_fp(outer_folds=12),
            scores=np.arange(12, dtype=np.float64),
        )
        loaded = load_completed_target(tmp_path, "target_0", fingerprint)
        assert loaded is not None
        # _complete_target sets each fold's constant to its own index.
        constants = [float(p.predict(np.zeros((1, 2)))[0]) for p in loaded[1]]
        assert constants == list(range(12)), (
            f"fold models came back in the wrong order: {constants}"
        )

    def test_writing_never_raises(self):
        assert write_target_artefacts(None, "target_0", np.zeros(3), _fp()) is None
        assert write_target_artefacts("/proc/nope", "t", np.zeros(3), _fp()) is None


class TestTheSearchIsActuallySkipped:
    """Structural: the stage must consult the resume path, and only on request.

    A behavioural version of this exists as a scratch probe that rigs
    nested_optuna_cv to raise; it cannot live here because it needs a full
    pipeline run. These pin the wiring that probe exercised.
    """

    def test_resume_is_opt_in(self):
        import inspect

        from emuses.pipelines.heatmap_stage import _optimise_target

        source = inspect.getsource(_optimise_target)
        assert 'getattr(cfg, "resume_targets", False)' in source, (
            "reuse must be gated on an explicit flag; silently skipping a search "
            "is the behaviour this codebase has repeatedly paid for"
        )

    def test_artefacts_are_written_even_without_the_flag(self):
        """The run that can be resumed is the one that crashed unexpectedly."""
        import ast
        import inspect
        import textwrap

        from emuses.pipelines.heatmap_stage import _optimise_target

        tree = ast.parse(textwrap.dedent(inspect.getsource(_optimise_target)))
        writes = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "write_target_artefacts"
        ]
        assert writes, "the target's artefacts are never written"
        # It must not sit inside an `if` -- that would make resumability depend
        # on having asked for it in the run that later crashed.
        for branch in (n for n in ast.walk(tree) if isinstance(n, ast.If)):
            inside = [
                n for n in ast.walk(branch)
                if isinstance(n, ast.Call)
                and getattr(n.func, "id", None) == "write_target_artefacts"
            ]
            assert not inside, (
                "write_target_artefacts is inside a conditional; a run must leave "
                "resumable artefacts whether or not it expected to be resumed"
            )
