"""A reused morphospace must keep the scaling of the run that trained it.

THE DEFECT, stated once so nobody has to reconstruct it from the assertions.

UMAP's output has no meaningful location or scale, so EMUSES maps it onto [0, 1] and
records the factors in ``embedding_scaling.json``. Those factors *are* the coordinate
system: a kernel bandwidth, a grid cell and a region boundary all mean something only
relative to them.

``UMAPStage`` computed them from ``self.embeddings.min(axis=0)`` / ``.max(axis=0)`` on
every route, including the routes that do not train anything. On ``--load_umap`` the
coordinates at that point are *this* cohort pushed through *someone else's* model, so
the run silently redefined [0, 1] against whoever happened to be in it. Consequences:

* the same subject landed at a different rescaled coordinate depending on its
  neighbours, so two runs of "the same" morphospace were not the same space;
* inference reads the factors from the file instead of recomputing them, so a model
  and the runs reusing it disagreed about where their own subjects were.

Nothing errors. Min-max rescaling a valid embedding always yields a valid embedding, in
exactly the expected range, and the run completes. That is why this is a test and not a
code comment.

The fix: fresh factors only when the morphospace was trained in this run. Every reuse
route reads the source run's file. See
``dev-docs/methodology/embedding_scaling_and_boundary_bias_plan.md`` (Step 1) and ADR
section 2.4b.

These tests run UMAPStage for real -- one trial, 120 synthetic samples, a few seconds
each. Mocking the stage would not have caught this: the bug is in which numbers reach
the arithmetic, and a mock supplies whichever numbers the test author expected.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from emuses.tools.embedding_spaces import SCALING_FILENAME, rescale_embedding

N_SAMPLES = 120
N_FEATURES = 8


def _config(output_folder):
    """The smallest config UMAPStage will run on. One trial: this is not a search test."""
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        output_folder=output_folder,
        prefix="",
        dataset_name="scaling_reuse",
        umap_trials=1,
        hdbscan_trials=1,
        optim_dict=None,
        load_umap=None,
        load_clusterer=None,
        load_cluster_labels=None,
        load_embeddings=None,
        umap_n_components=2,
        heatmap_stage_enabled=True,
        allow_nd_without_heatmaps=False,
        n_jobs=1,
        umap_jobs=1,
        hdbscan_jobs=1,
        hdbscan_approx_min_span_tree=True,
        hdbscan_core_dist_n_jobs=1,
        record_cohort_ids=False,
    )


def _cohort(seed, n=N_SAMPLES, d=N_FEATURES):
    """Three well-separated blobs, so HDBSCAN has something to find at one trial."""
    rng = np.random.default_rng(seed)
    centres = rng.normal(0, 4, (3, d))
    return np.vstack([c + rng.normal(0, 0.6, (n // 3, d)) for c in centres])


def _context(seed):
    return {
        "embedding_train_features": _cohort(seed),
        "random_seeds": {"umap_seed": 42, "clustering_seed": 42},
    }


def _run_stage(config, context):
    from emuses.pipelines.umap_stage import UMAPStage

    UMAPStage(config).run(context)
    return context


def _scaling(run_dir):
    return json.loads((Path(run_dir) / SCALING_FILENAME).read_text())


@pytest.fixture(scope="module")
def trained_run(tmp_path_factory):
    """Run A: a morphospace trained here, on cohort 0. The source of truth."""
    folder = tmp_path_factory.mktemp("morphospace_A")
    _run_stage(_config(folder), _context(seed=0))
    assert (folder / SCALING_FILENAME).is_file()
    return folder


class TestReuseKeepsTheSourceScaling:
    def test_load_umap_on_a_different_cohort_keeps_the_source_factors(
        self, trained_run, tmp_path
    ):
        """The headline case: --load_umap, different subjects, same coordinate system."""
        config = _config(tmp_path / "B")
        config.load_umap = str(trained_run)
        _run_stage(config, _context(seed=99))

        source, reused = _scaling(trained_run), _scaling(config.output_folder)
        assert reused == source, (
            "the reusing run recorded different scaling factors from the run that "
            "trained the morphospace, so the two are not the same [0, 1] space"
        )

        # THE ANTI-TAUTOLOGY CHECK. Equality above means nothing unless recomputing
        # would actually have given a different answer -- if this run's own extent
        # happened to match the source's, the assertion would pass with the bug
        # present. Assert the two genuinely differ.
        own = np.load(config.output_folder / "embeddings.npy")
        recomputed_min, recomputed_max = own.min(axis=0), own.max(axis=0)
        assert not np.allclose(
            recomputed_min, source["min_embeddings"], atol=1e-3
        ) or not np.allclose(recomputed_max, source["max_embeddings"], atol=1e-3), (
            "this cohort's own extent coincides with the source run's, so the test "
            "cannot distinguish reusing the factors from recomputing them. Change the "
            "cohort seed -- do not delete this assertion."
        )

    def test_a_fixed_raw_point_lands_in_the_same_place_in_both_runs(
        self, trained_run, tmp_path
    ):
        """The property the factors exist to provide, checked on a probe point.

        Equal JSON is the mechanism; this is the meaning. A coordinate in the shared
        raw space must rescale to one coordinate, not to one per run.
        """
        config = _config(tmp_path / "B_probe")
        config.load_umap = str(trained_run)
        _run_stage(config, _context(seed=7))

        probe = np.array([[1.25, -0.5], [4.0, 9.0], [0.0, 0.0]])
        landed = []
        for run_dir in (trained_run, config.output_folder):
            params = _scaling(run_dir)
            landed.append(
                rescale_embedding(
                    probe,
                    margin=params["margin"],
                    preset_min=np.asarray(params["min_embeddings"]),
                    preset_max=np.asarray(params["max_embeddings"]),
                )
            )
        np.testing.assert_allclose(landed[0], landed[1], rtol=0, atol=0)

    def test_load_embeddings_takes_the_scaling_from_beside_the_file(
        self, trained_run, tmp_path
    ):
        """--load_embeddings names a .npy; its folder owns the coordinate system.

        This route sets no `reused_from` (it reuses no clusterer), so it is the one
        most easily missed when wiring the others.

        The file deliberately holds a SUBGROUP of the source run's coordinates, not
        all of them -- which is what this flag is for, and the only version of this
        test that can fail. Pointed at the full `embeddings.npy`, recomputing the
        factors from the loaded array reproduces the source's factors exactly, so the
        assertion below holds with or without the fix and proves nothing. That was
        the first version of this test; it survived the perturbation that deletes the
        branch it is supposed to cover.
        """
        full = np.load(Path(trained_run) / "embeddings.npy")
        order = np.argsort(full[:, 0])
        trimmed = full[order[len(order) // 5 : -len(order) // 5]]
        subgroup = Path(trained_run) / "subgroup_embeddings.npy"
        np.save(subgroup, trimmed)
        assert not np.allclose(trimmed.min(axis=0), full.min(axis=0)), (
            "the subgroup must not span the full extent, or this test cannot tell "
            "reusing the factors from recomputing them"
        )

        config = _config(tmp_path / "B_emb")
        config.load_embeddings = str(subgroup)
        _run_stage(config, _context(seed=123))

        assert _scaling(config.output_folder) == _scaling(trained_run), (
            "a subgroup analysed inside an existing morphospace rescaled itself "
            "against its own extent, so its coordinates are not comparable with the "
            "parent run's"
        )

    def test_resuming_into_a_folder_does_not_redefine_its_space(self, tmp_path):
        """Running twice into one output folder must not move the coordinate system.

        Same cohort, so recomputing happens to give the same answer today -- but the
        resume path reaches the rescale via a fresh `transform`, and the factors it
        writes on the second pass must come from the first pass's record either way.
        """
        folder = tmp_path / "resume"
        _run_stage(_config(folder), _context(seed=5))
        first = _scaling(folder)

        _run_stage(_config(folder), _context(seed=5))
        assert _scaling(folder) == first


class TestMissingScalingIsRefused:
    def test_reusing_a_folder_without_scaling_raises(self, trained_run, tmp_path):
        """Silently recomputing is the bug; refusing is the only safe alternative.

        A run folder with a model but no embedding_scaling.json cannot say what its
        coordinate system was. Falling back to this run's own extent would produce a
        DIFFERENT space and a successful-looking run, which is exactly what this
        change exists to stop.
        """
        stripped = tmp_path / "no_scaling"
        shutil.copytree(trained_run, stripped)
        (stripped / SCALING_FILENAME).unlink()

        config = _config(tmp_path / "B_missing")
        config.load_umap = str(stripped)

        with pytest.raises(RuntimeError, match=SCALING_FILENAME):
            _run_stage(config, _context(seed=11))


class TestFreshTrainingStillComputesItsOwn:
    def test_a_training_run_derives_the_factors_from_its_own_embedding(self, tmp_path):
        """The other half of the rule. A trained morphospace is the source.

        Without this, "always load from somewhere else" would pass every test above
        and leave nothing able to produce factors in the first place.
        """
        folder = tmp_path / "fresh"
        _run_stage(_config(folder), _context(seed=3))

        params = _scaling(folder)
        raw = np.load(folder / "embeddings.npy")
        np.testing.assert_allclose(
            params["min_embeddings"], raw.min(axis=0), rtol=1e-6, atol=1e-6
        )
        np.testing.assert_allclose(
            params["max_embeddings"], raw.max(axis=0), rtol=1e-6, atol=1e-6
        )
