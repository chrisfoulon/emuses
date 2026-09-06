"""The rescaling must not depend on which way the embedding happens to be pointing.

WHY THIS PROPERTY, and why it is a test rather than a comment.

UMAP's loss depends only on pairwise distances. A solution is therefore fixed only up to
rotation, reflection and translation: rotate an embedding by any angle and you have an
equally valid output of the same fit, with the same neighbourhood structure and the same
information content. Nothing downstream should be able to tell the difference.

Under the per-axis min-max EMUSES used until 2026-09-06, everything downstream could.
Each dimension was stretched independently onto [0, 1], so the stretch depended on the
arbitrary orientation the optimiser landed in. A circle in per-axis space is an ellipse
in UMAP space whose orientation is set by the seed. Measured on a 45-degree rotation:

    per-axis    pearson r of pairwise distances 0.9598, max distortion 37.0%
    isotropic   pearson r 1.000000,                     max distortion  0.0%

Everything consuming the rescaled coordinates is metric -- kernel bandwidths,
distance-weighted regressors, grid geometry, region extents -- so a distorted metric is
a distorted scientific result, with no error and no warning.

`test_per_axis_is_the_thing_this_replaced` keeps the counter-example in the suite. Both
tests would pass on an implementation that did nothing at all; the pair is what pins the
distinction.

See ADR 2.4d and dev-docs/methodology/embedding_scaling_and_boundary_bias_plan.md.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.spatial.distance import pdist

from emuses.tools.embedding_spaces import (ISOTROPIC_GLOBAL_RANGE,
                                           isotropic_scaling_factors,
                                           rescale_embedding)


def _rotation(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s], [s, c]])


def _embedding(seed=0, n=400):
    """Deliberately anisotropic and off-centre -- the case that separates the modes."""
    rng = np.random.default_rng(seed)
    points = rng.normal(0, 1, (n, 2)) * np.array([6.0, 1.5])
    return points + np.array([-13.0, 40.0])


def _isotropic(embedding):
    lo, hi = isotropic_scaling_factors(embedding)
    return rescale_embedding(embedding, preset_min=lo, preset_max=hi)


def _per_axis(embedding):
    return rescale_embedding(
        embedding, preset_min=embedding.min(axis=0), preset_max=embedding.max(axis=0)
    )


@pytest.mark.parametrize("degrees", [15, 45, 90, 137])
def test_rotating_the_embedding_does_not_change_its_rescaled_geometry(degrees):
    """The property per-axis lacked, and the reason for the change.

    Distances are compared up to a single overall factor, because a rotated embedding
    can have a different widest extent and so a different divisor. What must not change
    is the *shape*: every pairwise distance scaled by the same number.
    """
    original = _embedding()
    rotated = original @ _rotation(np.deg2rad(degrees)).T

    a, b = pdist(_isotropic(original)), pdist(_isotropic(rotated))
    ratio = b / a
    assert np.allclose(ratio, ratio[0], rtol=1e-12, atol=0), (
        f"rotating by {degrees} deg changed the rescaled shape: distance ratios span "
        f"[{ratio.min():.12f}, {ratio.max():.12f}] instead of being constant"
    )
    assert abs(np.corrcoef(a, b)[0, 1] - 1.0) < 1e-12


def test_per_axis_is_the_thing_this_replaced():
    """The counter-example. Without it the test above could be passing vacuously."""
    original = _embedding()
    rotated = original @ _rotation(np.deg2rad(45)).T

    a, b = pdist(_per_axis(original)), pdist(_per_axis(rotated))
    ratio = b / a
    distortion = ratio.max() / ratio.min() - 1
    assert distortion > 0.10, (
        f"per-axis rescaling was expected to distort this embedding under rotation by "
        f"well over 10%, but distorted it by {distortion:.1%}. Either the fixture "
        f"stopped being anisotropic or rescale_embedding's per-axis path changed -- "
        f"in both cases the isotropic test above has lost its counter-example."
    )


class TestIsotropicFactors:
    def test_every_axis_starts_at_zero_and_the_widest_reaches_one(self):
        rescaled = _isotropic(_embedding())
        np.testing.assert_allclose(rescaled.min(axis=0), [0.0, 0.0], atol=1e-12)
        assert rescaled.max(axis=0).max() == pytest.approx(1.0, abs=1e-12)

    def test_the_narrow_axis_keeps_its_true_proportion(self):
        """The whole point: the aspect ratio survives, rather than being flattened."""
        embedding = _embedding()
        extents = embedding.max(axis=0) - embedding.min(axis=0)
        rescaled = _isotropic(embedding)

        np.testing.assert_allclose(
            rescaled.max(axis=0), extents / extents.max(), atol=1e-12
        )
        assert rescaled.max(axis=0).min() < 0.9, (
            "this fixture must be visibly anisotropic or the test asserts nothing"
        )

    def test_everything_lands_inside_the_unit_box(self):
        """Downstream code and the grid assume [0, 1]; nothing may sit outside it."""
        rescaled = _isotropic(_embedding(seed=4))
        assert rescaled.min() >= 0.0
        assert rescaled.max() <= 1.0 + 1e-12

    def test_max_is_the_box_not_the_extent(self):
        """A trap worth pinning: `preset_max` is NOT each axis's own maximum.

        It is the corner of the square box mapped onto [0, 1], which is what makes the
        shared denominator fall out of `(X - min) / (max - min)`. Code that reads it as
        an extent gets the narrow axis wrong.
        """
        embedding = _embedding()
        lo, hi = isotropic_scaling_factors(embedding)
        np.testing.assert_allclose(lo, embedding.min(axis=0), atol=1e-12)
        assert np.all((hi - lo) == (hi - lo)[0]), "the divisor must be one number"
        narrow = int(np.argmin(embedding.max(axis=0) - embedding.min(axis=0)))
        assert hi[narrow] > embedding[:, narrow].max()

    def test_a_degenerate_embedding_raises_rather_than_producing_nan(self):
        """Dividing by a zero range yields NaNs that only surface in the scores."""
        with pytest.raises(ValueError, match="no extent"):
            isotropic_scaling_factors(np.zeros((10, 2)))

    def test_it_survives_the_round_trip_through_a_run_folder(self, tmp_path):
        """The factors have to mean the same thing after JSON and back."""
        import json

        from emuses.tools.embedding_spaces import (SCALING_FILENAME,
                                                   inverse_rescale_embedding,
                                                   load_scaling)

        embedding = _embedding(seed=9)
        lo, hi = isotropic_scaling_factors(embedding)
        (tmp_path / SCALING_FILENAME).write_text(
            json.dumps(
                {
                    "min_embeddings": lo.tolist(),
                    "max_embeddings": hi.tolist(),
                    "mode": ISOTROPIC_GLOBAL_RANGE,
                    "margin": 0,
                }
            )
        )
        params = load_scaling(tmp_path)
        assert params["mode"] == ISOTROPIC_GLOBAL_RANGE

        there = rescale_embedding(
            embedding,
            preset_min=params["min_embeddings"],
            preset_max=params["max_embeddings"],
        )
        back = inverse_rescale_embedding(
            there,
            min_value=params["min_embeddings"],
            max_value=params["max_embeddings"],
        )
        np.testing.assert_allclose(back, embedding, rtol=1e-10, atol=1e-10)
