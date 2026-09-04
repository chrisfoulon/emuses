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

import numpy as np
import pytest

from emuses.tools.embedding_dimensionality import (
    HEATMAP_N_COMPONENTS, EmbeddingDimensionalityError,
    check_embedding_dimensionality, declared_n_components)


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
