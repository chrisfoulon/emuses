"""The two coordinate systems an EMUSES run writes to disk, and how to move between them.

A run folder contains embeddings in *two different coordinate systems*, under names
that do not say so:

    embeddings.npy        RAW       -- UMAP's own output, arbitrary location and scale
    test_embeddings.npy   RESCALED  -- the same space mapped onto [0, 1]

`umap_stage` saves the training array before it rescales and the test array after, so
the asymmetry is a consequence of write order rather than a decision anyone recorded.
Reading one as if it were the other is silent: it produces a plausible array of the
right shape whose relationship to the other is destroyed. Measured cost, 2026-09-05 --
recovering the swiss-roll parameter from an embedding scored r = 0.2747 when train
(raw) was compared against test (rescaled), and r = 0.9989 once both were in the same
space. Nothing errored, and the low number reads exactly like a real negative result.

Min-max rescaling is idempotent on the axis that spans the full range, which removes the
one signal that might have caught it: rescaling an already-rescaled array returns it
unchanged, or nearly so, rather than blowing up.

Hence `space` is a required keyword argument on `load_embeddings` with no default.
Code that has not decided which coordinate system it wants cannot silently get one.

WHY RESCALE AT ALL: UMAP's output has no meaningful location or scale, but the
predictors consuming it (kernel weighting, distance-based regressors, the discrete
grid) are all scale-sensitive, and a kernel bandwidth has to mean the same thing across
datasets. Mapping onto [0, 1] fixes both. The factors are saved so the same mapping can
be reapplied to data the model has never seen -- that is what inference reads.

THREE RESCALING MODES have existed, all reachable through `rescale_embedding`, and all
three are called "rescaled embeddings" in the code. `embedding_scaling.json` records
which one produced a given folder, in the "mode" field. They are NOT interchangeable.

  isotropic_global_range   what the pipeline writes since 2026-09-06. Each axis is
            shifted by its own minimum and every axis divided by ONE range, the largest.
            Both axes start at 0, the widest spans exactly [0, 1], proportions
            preserved. Passed as `preset_min` = per-axis minima and `preset_max` =
            those minima + the single range, so the shared denominator falls out of
            `(X - min) / (max - min)` without a separate code path. `preset_max` is
            therefore the top of the square box mapped onto [0, 1], NOT each axis's own
            maximum -- do not read it as an extent.

  per_axis  what the pipeline wrote before that, and what older run folders hold. Each
            dimension independently spans [0, 1]; proportions NOT preserved. Ill-posed
            on a UMAP embedding, which is fixed only up to rotation: rotating an
            embedding 45 degrees and re-normalising distorts pairwise distances by up
            to 37% (isotropic: 0.0%). See ADR 2.4d. Still read correctly -- a folder
            written under it keeps its own convention.

  global    (presets omitted) one scalar min and max across all dimensions;
            proportions preserved, but only the widest axis anchored at 0. Used by
            `DiscreteLatentSpace` in emuses_utils, which has no callers.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

#: The two coordinate systems. Use these rather than bare strings.
RAW = "raw"
RESCALED = "rescaled"
SPACES = (RAW, RESCALED)

SCALING_FILENAME = "embedding_scaling.json"

#: Values of the "mode" field in embedding_scaling.json. See the module docstring.
ISOTROPIC_GLOBAL_RANGE = "isotropic_global_range"
PER_AXIS = "per_axis"

#: Which space each artefact is stored in on disk. This is the fact the filenames
#: fail to carry; everything else in this module is derived from it.
ON_DISK_SPACE = {
    "train": RAW,
    "test": RESCALED,
}

SPLIT_FILENAMES = {
    "train": "embeddings.npy",
    "test": "test_embeddings.npy",
}


def isotropic_scaling_factors(embedding):
    """The `preset_min` / `preset_max` that map `embedding` onto [0, 1] isotropically.

    Each axis is shifted by its own minimum; every axis is divided by ONE range, the
    largest. So both axes start at 0, the widest spans exactly [0, 1], the others span
    less, and proportions are preserved.

    Returned as a (min, max) pair rather than an offset and a scale so that the result
    drops straight into `rescale_embedding`'s `(X - min) / (max - min)`: `max` is `min`
    plus the single shared range, which makes that denominator the same for every axis.
    **`max` is therefore the top of the square box mapped onto [0, 1], not each axis's
    own maximum.** Do not read it as an extent -- that is what the "mode" field in
    `embedding_scaling.json` is recorded for.

    Why not per-axis: a UMAP embedding is fixed only up to rotation, reflection and
    translation, so per-axis min-max depends on the arbitrary orientation the optimiser
    landed in. Measured on a 45-degree rotation -- per-axis distorts pairwise distances
    by up to 37% (mean 11.9%), isotropic by 0.0%.
    """
    embedding = np.asarray(embedding)
    lower = embedding.min(axis=0)
    span = float((embedding.max(axis=0) - lower).max())
    if not np.isfinite(span) or span <= 0:
        raise ValueError(
            f"The embedding has no extent to rescale (largest axis range = {span}). "
            f"Every sample sits at the same coordinate, so there is no morphospace "
            f"here. Rescaling would divide by zero and produce NaNs that only surface "
            f"much later, in the prediction scores."
        )
    return lower, lower + span


def rescale_embedding(embedding, margin=0, preset_max=None, preset_min=None):
    """Map an embedding onto [0, 1].

    With `preset_min`/`preset_max` omitted the bounds are taken as scalars over the
    whole array, which preserves proportions between dimensions. Passed as per-axis
    arrays -- what the pipeline does -- each dimension is stretched independently and
    proportions are not preserved. See the module docstring.
    """
    if preset_max is None:
        max_value = np.max(embedding)
    else:
        max_value = preset_max

    if preset_min is None:
        min_value = np.min(embedding)
    else:
        min_value = preset_min

    rescaled_embedding = (embedding - min_value) / (max_value - min_value)

    if margin != 0:
        # Compute the margin in the rescaled space
        margin_rescaled = margin / 100

        # Pull the extremes inward so nothing sits exactly on the boundary.
        rescaled_embedding = (
            rescaled_embedding * (1 - 2 * margin_rescaled) + margin_rescaled
        )

    return rescaled_embedding


def inverse_rescale_embedding(
    rescaled_embedding, margin=0, max_value=None, min_value=None
):
    """Map a [0, 1] embedding back to raw coordinates.

    Exact inverse of `rescale_embedding` given the same bounds and margin.
    """
    if margin != 0:
        # Reverse the margin scaling
        margin_rescaled = margin / 100
        rescaled_embedding = (rescaled_embedding - margin_rescaled) / (
            1 - 2 * margin_rescaled
        )

    embedding = rescaled_embedding * (max_value - min_value) + min_value

    return embedding


def load_scaling(run_dir):
    """Read `embedding_scaling.json` from a run folder.

    Returns a dict with `min_embeddings` and `max_embeddings` as arrays, plus whatever
    descriptive fields the writing run recorded. Raises FileNotFoundError rather than
    returning None: a caller that needs the factors cannot proceed without them, and
    returning None here is how a missing file turns into raw coordinates being used as
    if they were rescaled.
    """
    run_dir = Path(run_dir)
    scaling_file = run_dir / SCALING_FILENAME
    if not scaling_file.is_file():
        raise FileNotFoundError(
            f"No {SCALING_FILENAME} in {run_dir}. Without it the raw and rescaled "
            f"coordinate systems of this run cannot be related to each other. It is "
            f"written by UMAPStage; a folder lacking it predates that, or is not a "
            f"run folder."
        )
    with open(scaling_file, "r") as f:
        params = json.load(f)

    params["min_embeddings"] = np.asarray(params["min_embeddings"])
    params["max_embeddings"] = np.asarray(params["max_embeddings"])
    return params


def load_embeddings(run_dir, *, space, split="train", prefix=""):
    """Load a run's embeddings in the coordinate system you ask for.

    Args:
        run_dir: the run's output folder.
        space: `RAW` or `RESCALED`. Required, no default -- see the module docstring.
        split: "train" (`embeddings.npy`) or "test" (`test_embeddings.npy`).
        prefix: the run's filename prefix, if it has one.

    The conversion, when needed, uses the factors in `embedding_scaling.json`, so the
    result is in the same space as the rest of that run rather than in one rescaled
    from whatever subset happened to be loaded.
    """
    if space not in SPACES:
        raise ValueError(
            f"space must be one of {SPACES}, got {space!r}. It has no default on "
            f"purpose: a run folder holds both, and picking the wrong one fails "
            f"silently."
        )
    if split not in SPLIT_FILENAMES:
        raise ValueError(
            f"split must be one of {tuple(SPLIT_FILENAMES)}, got {split!r}"
        )

    run_dir = Path(run_dir)
    path = run_dir / f"{prefix}{SPLIT_FILENAMES[split]}"
    if not path.is_file():
        raise FileNotFoundError(f"No {path.name} in {run_dir}")

    embeddings = np.load(path)
    stored_space = ON_DISK_SPACE[split]
    if stored_space == space:
        return embeddings

    scaling = load_scaling(run_dir)
    margin = scaling.get("margin", 0)
    if space == RESCALED:
        return rescale_embedding(
            embeddings,
            margin=margin,
            preset_min=scaling["min_embeddings"],
            preset_max=scaling["max_embeddings"],
        )
    return inverse_rescale_embedding(
        embeddings,
        margin=margin,
        min_value=scaling["min_embeddings"],
        max_value=scaling["max_embeddings"],
    )
