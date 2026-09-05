"""An embedding wider than the heatmap can use must be refused, loudly and early.

Before 2026-09-04 an N-D run did not fail -- it *degraded silently*. UMAP and the
prediction search are both dimension-agnostic, so a run with ``n_components: 5``
would train the morphospace, complete the entire nested-CV search (~19 h on
``DSD_repro``), then fail the grid on every target and **exit 0 with no heatmaps**.
The only trace was one ``logger.error`` per target inside a multi-MB log, because
``heatmap_stage.py`` catches bare ``Exception`` around both grid call sites and
around the whole grid section.

The grid creators' own ``ValueError`` was never the problem; its *placement* was.
These tests pin the two things that make the refusal useful: that it happens
before training, and that nothing swallows it.

Guardrail note (G002): if one of these fails after a change to the grid code, the
answer is not to relax the assertion. Making the heatmap N-D is an open design
decision -- see ``dev-docs/methodology/external_evidence_dsd.md`` section 7.2.
"""

import inspect
import textwrap

import numpy as np
import pytest

from emuses.tools.embedding_dimensionality import (
    GRID_BINNED_METRICS, HEATMAP_N_COMPONENTS, EmbeddingDimensionalityError,
    check_embedding_dimensionality, check_embedding_matches_stages,
    declared_n_components, validate_metrics_for_dimensionality)


class TestDeclaredNComponents:
    """Every spec form `optim_utils.suggest_one` accepts must be understood.

    A form this function silently mis-reads is worse than one it rejects: the
    gate would pass and the run would reach the swallowed failure again.
    """

    def test_fixed_value(self):
        assert declared_n_components({"param": {"umap": {"n_components": {"value": 5}}}}) == {5}

    def test_categorical_choices(self):
        d = {"param": {"umap": {"n_components": {"choices": [2, 3, 10]}}}}
        assert declared_n_components(d) == {2, 3, 10}

    def test_integer_range_is_expanded(self):
        d = {"param": {"umap": {"n_components": {"low": 2, "high": 5}}}}
        assert declared_n_components(d) == {2, 3, 4, 5}

    def test_integer_range_with_step(self):
        d = {"param": {"umap": {"n_components": {"low": 2, "high": 8, "step": 3}}}}
        assert declared_n_components(d) == {2, 5, 8}

    def test_bare_literal(self):
        assert declared_n_components({"param": {"umap": {"n_components": 4}}}) == {4}

    def test_absent_is_unknown_not_two(self):
        """None means 'undeclared', which the caller resolves to UMAP's default.

        Returning {2} here would be a guess wearing the costume of a measurement.
        """
        assert declared_n_components({"param": {"umap": {}}}) is None
        assert declared_n_components({}) is None
        assert declared_n_components(None) is None


class TestGate:
    def test_refuses_nd_when_heatmap_is_enabled(self):
        d = {"param": {"umap": {"n_components": {"value": 5}}}}
        with pytest.raises(EmbeddingDimensionalityError) as exc:
            check_embedding_dimensionality(d, ["umap", "heatmap"], optim_dict_name="my_dict")
        message = str(exc.value)
        # The message has to be actionable, not just correct: this is the only
        # thing the user sees, and "shape must be (n, 2)" tells them nothing.
        assert "my_dict" in message, "the message must name the config to change"
        assert "emuses umap" in message, "the message must name what does work"
        assert "n_components" in message
        assert exc.value.declared == {5}
        assert exc.value.blocking_stages == ("heatmap",)

    def test_allows_nd_for_a_umap_only_run(self):
        """An N-D morphospace on its own is a supported output, not an error."""
        d = {"param": {"umap": {"n_components": {"value": 10}}}}
        assert check_embedding_dimensionality(d, ["umap"]) == {10}

    def test_allows_two_d_with_heatmap(self):
        d = {"param": {"umap": {"n_components": {"value": HEATMAP_N_COMPONENTS}}}}
        assert check_embedding_dimensionality(d, ["umap", "heatmap"]) == {2}

    def test_a_range_that_merely_includes_two_is_still_refused(self):
        """Optuna may pick any value in the range, so 'could be 2' is not enough."""
        d = {"param": {"umap": {"n_components": {"low": 2, "high": 4}}}}
        with pytest.raises(EmbeddingDimensionalityError):
            check_embedding_dimensionality(d, ["umap", "heatmap"])

    def test_undeclared_passes(self):
        assert check_embedding_dimensionality({}, ["umap", "heatmap"]) is None


def test_every_shipped_optim_dict_declares_two_components():
    """The gate must not refuse a configuration EMUSES ships.

    If this fails, a shipped dict was changed to N-D without the heatmap being
    made N-D capable -- which the gate would then refuse at runtime for every
    user of that dict.
    """
    from emuses.config import optim_configs

    checked = 0
    for name in dir(optim_configs):
        if not name.startswith("optim_dict"):
            continue
        candidate = getattr(optim_configs, name)
        if not isinstance(candidate, dict):
            continue
        declared = declared_n_components(candidate)
        if declared is None:
            continue
        checked += 1
        assert declared == {HEATMAP_N_COMPONENTS}, (
            f"optim_configs.{name} declares n_components={sorted(declared)}, which the "
            f"heatmap cannot consume. Either make the heatmap N-D capable or revert."
        )
    assert checked > 0, "no shipped optim_dict declared n_components; the scan is broken"


class TestHeatmapStageDoesNotSwallowIt:
    """The defect was never the missing check -- it was the four handlers above it."""

    def test_grid_analysis_raises_on_a_three_d_embedding(self):
        """Must raise, not log-and-continue.

        This is the perturbation that decides whether any of this works: before
        the fix, the same call logged an error per target and returned normally.
        """
        from emuses.pipelines.heatmap_stage import HeatmapStage

        stage = HeatmapStage.__new__(HeatmapStage)  # no config needed; check is first
        embeddings = np.random.default_rng(0).random((20, 3))
        target_matrix = np.random.default_rng(1).random((20, 2))

        import logging
        with pytest.raises(EmbeddingDimensionalityError) as exc:
            stage._execute_triple_grid_analysis(
                context={},
                embeddings=embeddings,
                target_matrix=target_matrix,
                output_folder="/nonexistent",
                logger=logging.getLogger(__name__),
            )
        assert "(20, 3)" in str(exc.value), "the message must name the shape it got"

    def test_two_d_embedding_gets_past_the_dimensionality_check(self):
        """The guard must not fire on the supported case.

        A guard that rejects everything is as useless as one that rejects
        nothing, and this one sits in front of the whole grid section.
        """
        from emuses.pipelines.heatmap_stage import HeatmapStage

        stage = HeatmapStage.__new__(HeatmapStage)
        embeddings = np.random.default_rng(0).random((20, 2))
        target_matrix = np.random.default_rng(1).random((20, 1))

        import logging
        # Everything past the check fails on the empty context; the point is only
        # that it is NOT EmbeddingDimensionalityError, i.e. the guard let it by.
        try:
            stage._execute_triple_grid_analysis(
                context={},
                embeddings=embeddings,
                target_matrix=target_matrix,
                output_folder="/nonexistent",
                logger=logging.getLogger(__name__),
            )
        except EmbeddingDimensionalityError:  # pragma: no cover - the failure we test for
            pytest.fail("the dimensionality guard fired on a supported 2-D embedding")
        except Exception:
            pass

    def test_the_outer_handler_still_re_raises_it(self):
        """Structural guard against a tidy-up.

        `HeatmapStage.run` wraps the grid call in `except Exception: log and
        continue`, which is deliberate for genuine runtime grid failures. The
        dimensionality error must keep its own `raise` above that, or the check
        two frames down stops reaching the user. Read the source rather than
        running a full stage: an assertion that needs a 19-hour pipeline to fail
        is an assertion nobody runs.
        """
        from emuses.pipelines.heatmap_stage import HeatmapStage

        source = inspect.getsource(HeatmapStage.run)
        assert "except EmbeddingDimensionalityError:" in source, (
            "HeatmapStage.run no longer re-raises EmbeddingDimensionalityError, so a "
            "wrong-width embedding is swallowed by the bare `except Exception` below "
            "it and the run completes with no heatmaps and exit 0."
        )
        # It must come first: a bare `except Exception` above it would win.
        assert source.index("except EmbeddingDimensionalityError:") < source.index(
            "logger.warning(\"Continuing pipeline without statistical grid analysis\")"
        ), "the specific handler must precede the catch-all it is protecting against"


class TestLoadedModelWidth:
    """The configuration gate cannot see a morphospace loaded from disk.

    ``--load_umap``, ``--load_embeddings`` and the output-folder resume all
    supply an embedding whose width is a property of the *file*, not of this
    run's optim_dict. A 5-D saved model therefore sails past the config check
    and, before this guard, would only fail inside HeatmapStage -- after the
    entire prediction search.
    """

    def test_refuses_a_wide_loaded_embedding_when_heatmap_is_enabled(self):
        emb = np.random.default_rng(0).random((50, 5))
        with pytest.raises(EmbeddingDimensionalityError) as exc:
            check_embedding_matches_stages(
                emb, heatmap_enabled=True, source="--load_umap /some/model.joblib"
            )
        message = str(exc.value)
        assert "5-D" in message
        assert "/some/model.joblib" in message, "must name where the embedding came from"
        assert "emuses umap" in message, "must name what does work"

    def test_allows_a_wide_loaded_embedding_for_a_umap_only_run(self):
        emb = np.random.default_rng(0).random((50, 5))
        check_embedding_matches_stages(emb, heatmap_enabled=False)  # must not raise

    def test_allows_two_d_with_heatmap(self):
        emb = np.random.default_rng(0).random((50, 2))
        check_embedding_matches_stages(emb, heatmap_enabled=True)  # must not raise

    def test_umap_stage_calls_it_after_the_embedding_exists(self):
        """Structural: the call must survive a refactor of UMAPStage.run.

        Placement is the whole point -- it has to sit after every route that can
        produce an embedding (train, --load_umap, --load_embeddings, resume) and
        before the stage hands anything downstream.
        """
        from emuses.pipelines.umap_stage import UMAPStage

        source = inspect.getsource(UMAPStage.run)
        assert "check_embedding_matches_stages(" in source, (
            "UMAPStage.run no longer checks the width of the embedding it actually "
            "produced, so a wide model loaded from disk reaches HeatmapStage and only "
            "fails there, after the prediction search."
        )


class TestGridBinnedMetricsAreRefusedInND:
    """`entropy` is enabled by EVERY shipped optim_dict and is unusable above 2-D.

    Measured 2026-09-04 on 1333 points: MemoryError from d=5 (50**5 cells), and
    before that a silent collapse -- occupancy 41% at d=2, 1.06% at d=3, 0.02%
    at d=4, where 1332 of 1333 points are alone in their own cell. The value
    then moves only with the log(n_bins**d) normaliser, so trials stop being
    distinguishable. Completing the search is the bad outcome here, not failing.
    """

    def _dict_with(self, metrics):
        return {"param": {"umap": {}}, "metrics": {"umap": metrics}}

    def test_refused_above_two_d(self):
        d = self._dict_with({"entropy": {"weight": 3.0}, "eigen_spread": {"weight": 2.0}})
        with pytest.raises(EmbeddingDimensionalityError) as exc:
            validate_metrics_for_dimensionality(d, 5)
        message = str(exc.value)
        assert "entropy" in message
        assert "optim_dict_nd" in message, "must name the dict that works"

    def test_allowed_at_two_d(self):
        d = self._dict_with({"entropy": {"weight": 3.0}})
        validate_metrics_for_dimensionality(d, 2)  # must not raise

    def test_dimension_stable_metrics_are_not_refused(self):
        d = self._dict_with(
            {"eigen_spread": {"weight": 3.0}, "density_variability": {}, "spread": {}}
        )
        validate_metrics_for_dimensionality(d, 10)  # must not raise

    def test_shipped_nd_dict_is_actually_usable_in_nd(self):
        """The escape hatch the error message points at must exist and work.

        An error that names a remedy which does not work is worse than one that
        names none.
        """
        from emuses.config.optim_configs import load_optim_dict

        nd = load_optim_dict("optim_dict_nd")
        enabled = set(nd["metrics"]["umap"])
        assert not (enabled & set(GRID_BINNED_METRICS)), (
            f"optim_dict_nd enables {enabled & set(GRID_BINNED_METRICS)}, which is the "
            f"exact thing it exists to avoid."
        )
        for d in (3, 5, 10):
            validate_metrics_for_dimensionality(nd, d)

    def test_every_other_shipped_dict_still_carries_entropy_at_two_d(self):
        """Guards against 'fixing' this by stripping entropy everywhere.

        entropy is meaningful at 2-D (41% cell occupancy) and is weighted most
        heavily in the default objective. Removing it from the 2-D dicts would
        silently change every existing morphospace, and the regression baselines
        pin those numbers.
        """
        from emuses.config import optim_configs

        two_d_dicts = [
            n for n in dir(optim_configs)
            if n.startswith("optim_dict") and n != "optim_dict_nd"
            and isinstance(getattr(optim_configs, n), dict)
            and getattr(optim_configs, n).get("metrics", {}).get("umap")
        ]
        assert two_d_dicts, "scan found no dicts; the test is broken, not the code"
        for name in two_d_dicts:
            enabled = set(getattr(optim_configs, name)["metrics"]["umap"])
            assert "entropy" in enabled, (
                f"optim_configs.{name} lost its entropy metric. That changes the 2-D "
                f"objective for every existing user; use optim_dict_nd for N-D instead."
            )


class TestResumeDetectionMatchesWhatIsActuallyWritten:
    """The resume branch spent its whole life unreachable.

    ``UMAPStage`` tested for ``best_umap_model.joblib`` / ``hdbscan_model.joblib``,
    but models are saved with a version suffix -- ``best_umap_model_v1_0_0_
    joblib1_5_2.joblib``. Those bare names are never written, so the four-file
    condition could not be true and every "resume" silently retrained from
    scratch. Nothing failed; it just quietly did the expensive thing.

    Measured 2026-09-04 by listing a real run's output folder, after reading the
    code had suggested the opposite.
    """

    @staticmethod
    def _code_only(func):
        """Source with comments and docstrings removed.

        The first version of this test matched the *comment* that explains the
        bug and failed against correct code -- the same colour-blind-grep trap
        that has faked a clean result in this repo before. Tokenize instead.
        """
        import io
        import tokenize

        src = textwrap.dedent(inspect.getsource(func))
        kept = []
        prev_type = None
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            # a bare string statement is a docstring
            if tok.type == tokenize.STRING and prev_type in (
                None, tokenize.INDENT, tokenize.NEWLINE, tokenize.NL
            ):
                continue
            kept.append(tok.string)
            if tok.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT):
                prev_type = tok.type
        return " ".join(kept)

    def test_umap_stage_does_not_look_for_the_bare_model_names(self):
        from emuses.pipelines.umap_stage import UMAPStage

        code = self._code_only(UMAPStage.run)
        # remove the legitimate globbed forms first, so only a bare use can match
        code = code.replace("best_umap_model*.joblib", "").replace(
            "hdbscan_model*.joblib", "")
        for bare in ("best_umap_model.joblib", "hdbscan_model.joblib"):
            assert bare not in code, (
                f"UMAPStage.run looks for {bare!r}, which is never written -- saved "
                f"models carry a version suffix. The resume branch becomes unreachable "
                f"and every reuse silently retrains."
            )

    def test_it_globs_for_the_versioned_artefact(self):
        from emuses.pipelines.umap_stage import UMAPStage

        source = inspect.getsource(UMAPStage.run)
        assert "best_umap_model*.joblib" in source
        assert "hdbscan_model*.joblib" in source

    def test_a_versioned_folder_is_recognised(self, tmp_path):
        """Behavioural mirror of the two structural checks above.

        Uses the real filename a run produced, not an invented one (G009).
        """
        (tmp_path / "best_umap_model_v1_0_0_joblib1_5_2.joblib").write_bytes(b"x")
        (tmp_path / "hdbscan_model_v1_0_0_joblib1_5_2.joblib").write_bytes(b"x")

        found_umap = sorted(tmp_path.glob("best_umap_model*.joblib"))
        found_hdb = sorted(tmp_path.glob("hdbscan_model*.joblib"))
        assert found_umap and found_hdb, "the glob must match the real saved names"
        # and the old exact-name test must NOT match, which is why it was dead
        assert not (tmp_path / "best_umap_model.joblib").exists()


class TestNDWithoutHeatmapsOptIn:
    """`--allow_nd_without_heatmaps`: predictions in N-D, heatmaps declared absent.

    Prediction training is the first half of `HeatmapStage.run` and
    `PredictionStage` is retired, so before this opt-in existed there was no way
    to obtain a prediction score at d>2 at all -- the refusal above also blocked
    the experiment it was built to protect. The opt-in must unblock that WITHOUT
    reintroducing the original defect, so what these pin is the difference
    between an absence you must notice and an absence the folder states.
    """

    def test_default_still_refuses(self):
        """The opt-in must be opt-IN. A default that allows N-D is the old bug."""
        d = {"param": {"umap": {"n_components": {"value": 5}}}}
        with pytest.raises(EmbeddingDimensionalityError):
            check_embedding_dimensionality(d, ["umap", "heatmap"])

    def test_opt_in_allows_the_configuration(self):
        d = {"param": {"umap": {"n_components": {"value": 5}}}}
        assert check_embedding_dimensionality(
            d, ["umap", "heatmap"], allow_nd_without_heatmaps=True
        ) == {5}

    def test_refusal_message_names_the_opt_in(self):
        """A refusal that does not say how to proceed sends people to the source."""
        d = {"param": {"umap": {"n_components": {"value": 5}}}}
        with pytest.raises(EmbeddingDimensionalityError) as exc:
            check_embedding_dimensionality(d, ["umap", "heatmap"])
        assert "--allow_nd_without_heatmaps" in str(exc.value)

    def test_width_check_returns_the_width_instead_of_raising(self):
        assert check_embedding_matches_stages(
            np.zeros((10, 5)), heatmap_enabled=True, allow_nd_without_heatmaps=True
        ) == 5

    def test_opt_in_does_not_change_the_two_d_path(self):
        """A 2-D run must be bit-for-bit unaffected by the flag being present."""
        assert check_embedding_matches_stages(
            np.zeros((10, 2)), heatmap_enabled=True, allow_nd_without_heatmaps=True
        ) is None

    def test_a_malformed_embedding_still_raises_even_with_the_opt_in(self):
        """The opt-in forgives width, not a non-embedding. 1-D is not a morphospace."""
        with pytest.raises(EmbeddingDimensionalityError):
            check_embedding_matches_stages(
                np.zeros(10), heatmap_enabled=True, allow_nd_without_heatmaps=True
            )

    def test_marker_records_the_reason_on_disk(self, tmp_path):
        import json

        from emuses.tools.embedding_dimensionality import (
            SKIPPED_MARKER_FILENAME, record_skipped_heatmaps)

        marker = record_skipped_heatmaps(tmp_path, 5, targets=["target_0"])
        assert marker == tmp_path / SKIPPED_MARKER_FILENAME
        payload = json.loads(marker.read_text())
        assert payload["n_components"] == 5
        assert payload["opted_in_with"] == "--allow_nd_without_heatmaps"
        # The folder must say the SCORES are still good, or a reader finding this
        # file has no way to tell whether the whole run is suspect.
        assert payload["predictions_trained"] is True
        assert "heatmap_visualizations" in payload["skipped"]

    def test_marker_failure_never_loses_a_completed_search(self):
        """Writing the marker is bookkeeping; the search behind it took hours."""
        from emuses.tools.embedding_dimensionality import record_skipped_heatmaps

        assert record_skipped_heatmaps(None, 5) is None
        assert record_skipped_heatmaps("/proc/nonexistent/nope", 5) is None


class TestSkipDoesNotStealTheInferenceHandoff:
    """The skip must not return early out of `HeatmapStage.run`.

    Everything after the grid section prepares `inference_features` /
    `inference_labels` for InferenceStage, which validates the models on the
    held-out set. An early return there would silently drop held-out validation
    on exactly the N-D runs that exist to be compared -- the same shape of defect
    as the original, introduced while fixing it. This was caught in review, not
    by a test, which is why it gets one.
    """

    def test_the_skip_branch_contains_no_return(self):
        import ast
        import textwrap

        from emuses.pipelines.heatmap_stage import HeatmapStage

        tree = ast.parse(textwrap.dedent(inspect.getsource(HeatmapStage.run)))
        guards = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and "skipped_width" in ast.dump(node.test)
            and any(isinstance(n, ast.Call) for n in ast.walk(node))
        ]
        assert guards, "no `skipped_width` guard found in HeatmapStage.run"
        for guard in guards:
            returns = [n for n in ast.walk(guard) if isinstance(n, ast.Return)]
            assert not returns, (
                "The N-D skip branch returns out of HeatmapStage.run. Everything "
                "below it prepares inference_features/inference_labels for "
                "InferenceStage, so returning here drops held-out validation on "
                "N-D runs without saying so. Skip the grid section, do not leave "
                "the method."
            )

    def test_the_inference_handoff_is_reachable_after_the_guard(self):
        """Structural check above is only meaningful if the handoff is really below."""
        from emuses.pipelines.heatmap_stage import HeatmapStage

        source = inspect.getsource(HeatmapStage.run)
        guard_at = source.index("skipped_width")
        handoff_at = source.index('context["inference_features"]')
        assert handoff_at > guard_at, (
            "the inference handoff no longer follows the skip guard; the "
            "no-early-return test above would stop meaning anything"
        )
