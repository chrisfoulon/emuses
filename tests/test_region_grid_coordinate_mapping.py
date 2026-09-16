"""Grid indices must map back to the coordinates the grid was actually built on.

`RegionStatisticalAnalyzer` finds significant regions as connected components of a
grid-shaped array, then converts those grid indices back into embedding coordinates to
decide which training samples fall inside each region. Those samples are what the
voxelwise statistics are computed on, so this conversion sits directly under the
scientific claim.

It used to be ``region_coords / grid_size``, which was wrong three ways at once, and all
three are silent -- the outputs keep their shape and their plausibility, only the sample
membership moves:

1. **It assumed the grid spans exactly [0, 1].** True only because the embedding was
   rescaled per-axis; false under the isotropic rescale, where the narrow axis stops
   short of 1 and the grid spans the data rather than the unit square.
2. **It was off by one.** ``linspace(lo, hi, n)`` puts index ``n-1`` at ``hi``; dividing
   by ``n`` puts it at ``(n-1)/n``.
3. **It compared transposed axes.** ``reshape(g, g)`` indexes ``[y, x]``, because
   `GridCreator` ravels ``meshgrid(x, y)`` row-major over y. So ``np.where`` returns
   ``(iy, ix)`` and it was compared column-for-column against `training_embeddings`,
   whose columns are ``(x, y)``. Every region was reflected about the diagonal.

Defect 3 is invisible on a square grid over a square extent with roughly symmetric data,
which is exactly what the old per-axis rescale always produced -- another instance of one
wrong thing hiding another.

These tests use `GridCreator` to build the grid rather than constructing one by hand, so
they check the two components agree rather than checking each against the test author's
idea of the convention.
"""

from __future__ import annotations

import numpy as np
import pytest

from emuses.tools.grid_creator import GridCreator
from emuses.tools.region_statistical_analyzer import RegionStatisticalAnalyzer

GRID_SIZE = 20
#: Patch side length. PATCH**2 / GRID_SIZE**2 must exceed the 5% threshold below.
PATCH = 5


@pytest.fixture
def embeddings():
    """Anisotropic and not anchored at the unit square's corners.

    A square, [0, 1]-filling cloud makes every one of the three defects invisible.
    """
    rng = np.random.default_rng(0)
    pts = rng.random((200, 2)) * np.array([1.0, 0.4]) + np.array([0.0, 0.05])
    # Pin the corners so the extent is exactly known.
    pts[0] = [0.0, 0.05]
    pts[1] = [1.0, 0.45]
    return pts


@pytest.fixture
def grid(embeddings):
    return GridCreator(grid_size=GRID_SIZE).generate_coordinate_grid(embeddings)


class TestGridAxes:
    def test_axes_are_recovered_from_the_grid_itself(self, grid, embeddings):
        x_axis, y_axis = RegionStatisticalAnalyzer._grid_axes(grid, GRID_SIZE)

        np.testing.assert_allclose(
            x_axis, np.linspace(embeddings[:, 0].min(), embeddings[:, 0].max(), GRID_SIZE)
        )
        np.testing.assert_allclose(
            y_axis, np.linspace(embeddings[:, 1].min(), embeddings[:, 1].max(), GRID_SIZE)
        )

    def test_the_endpoints_are_the_data_extent_not_the_unit_square(self, grid, embeddings):
        """The off-by-one and the [0, 1] assumption, in one assertion."""
        x_axis, y_axis = RegionStatisticalAnalyzer._grid_axes(grid, GRID_SIZE)
        assert y_axis[-1] == pytest.approx(embeddings[:, 1].max())
        assert y_axis[-1] < 0.5, "this fixture must not reach 1 or the test is vacuous"
        assert y_axis[-1] != pytest.approx((GRID_SIZE - 1) / GRID_SIZE)

    def test_a_grid_of_the_wrong_size_is_refused(self, grid):
        """Two descriptions of one grid that disagree must not be quietly reconciled."""
        with pytest.raises(ValueError, match="same grid"):
            RegionStatisticalAnalyzer._grid_axes(grid, GRID_SIZE + 1)


class TestRegionToSampleMapping:
    def _map(self, embeddings, grid, significance):
        return RegionStatisticalAnalyzer().map_grid_to_training_samples(
            significance_values=significance,
            training_embeddings=embeddings,
            percentile_threshold=5.0,
            significance_source="correlation",
            grid_coords=grid,
        )

    def test_a_region_selects_the_samples_that_are_actually_under_it(
        self, embeddings, grid
    ):
        """The end-to-end property, and the one the axis swap broke.

        Make a single significant patch in one corner of the grid, then check the
        selected samples are the ones inside that patch's real coordinate box.
        """
        # The patch must be LARGER than percentile_threshold, or np.percentile puts
        # the cut at 0.0 and "significant" means the whole grid. 5x5 of 20x20 is 6.25%
        # against a 5% threshold.
        significance = np.zeros(GRID_SIZE * GRID_SIZE)
        sig_grid = significance.reshape(GRID_SIZE, GRID_SIZE)
        # A patch at HIGH x and LOW y -- deliberately not symmetric under transposition.
        sig_grid[0:PATCH, GRID_SIZE - PATCH:] = 1.0

        selected = self._map(embeddings, grid, significance)["high"]
        assert len(selected) > 0, "the patch must catch some samples or nothing is tested"

        x_axis, y_axis = RegionStatisticalAnalyzer._grid_axes(grid, GRID_SIZE)
        x_lo, x_hi = x_axis[GRID_SIZE - PATCH], x_axis[-1]
        y_lo, y_hi = y_axis[0], y_axis[PATCH - 1]

        chosen = embeddings[selected]
        assert np.all(chosen[:, 0] >= x_lo - 1e-12) and np.all(chosen[:, 0] <= x_hi + 1e-12)
        assert np.all(chosen[:, 1] >= y_lo - 1e-12) and np.all(chosen[:, 1] <= y_hi + 1e-12)

        expected = np.where(
            (embeddings[:, 0] >= x_lo) & (embeddings[:, 0] <= x_hi)
            & (embeddings[:, 1] >= y_lo) & (embeddings[:, 1] <= y_hi)
        )[0]
        np.testing.assert_array_equal(np.sort(selected), np.sort(expected))

    def test_the_transposed_region_selects_different_samples(self, embeddings, grid):
        """The counter-example that makes the test above load-bearing.

        If reflecting the patch about the diagonal selected the same samples, the test
        above would pass with the axis bug present.
        """
        def patch(rows, cols):
            s = np.zeros(GRID_SIZE * GRID_SIZE)
            s.reshape(GRID_SIZE, GRID_SIZE)[rows, cols] = 1.0
            return self._map(embeddings, grid, s)["high"]

        upright = patch(slice(0, PATCH), slice(GRID_SIZE - PATCH, None))
        flipped = patch(slice(GRID_SIZE - PATCH, None), slice(0, PATCH))
        assert set(upright.tolist()) != set(flipped.tolist()), (
            "this fixture is symmetric under transposition, so it cannot detect the "
            "axis swap -- make the extents or the patch more asymmetric"
        )

    def test_the_whole_grid_selects_every_sample(self, embeddings, grid):
        """A sanity bound: marking everything significant must lose nobody.

        Under the old `region_coords / grid_size`, the top edge mapped to
        (n-1)/n of a range it had also mis-scaled, so samples near the maximum fell
        outside their own region's bounding box.
        """
        significance = np.ones(GRID_SIZE * GRID_SIZE)
        significance[0] = 0.0  # keep a percentile threshold meaningful
        selected = self._map(embeddings, grid, significance)["high"]
        assert len(selected) == len(embeddings)
