"""The raw/rescaled coordinate systems, and the loader that keeps them apart.

The bug these guard against does not raise. A run folder holds `embeddings.npy` in raw
UMAP coordinates and `test_embeddings.npy` rescaled onto [0, 1]; comparing one against
the other returns a number rather than an error, and the number looks like a finding.
Measured on the swiss roll, 2026-09-05: r = 0.2747 mixed, r = 0.9989 once both arrays
were in the same space.

So the assertions here are mostly about *refusing* rather than computing.
"""

import json

import numpy as np
import pytest

from emuses.tools.embedding_spaces import (RAW, RESCALED,
                                           inverse_rescale_embedding,
                                           load_embeddings, load_scaling,
                                           rescale_embedding)

MARGIN_CASES = [0, 5]


@pytest.fixture
def run_dir(tmp_path):
    """A minimal run folder, built the way UMAPStage builds one.

    Deliberately asymmetric: the training array is stored raw and the test array
    rescaled, because that is what is on disk. A fixture that stored both the same way
    would test a folder EMUSES never produces.
    """
    rng = np.random.default_rng(0)
    raw_train = rng.normal(loc=7.0, scale=3.0, size=(40, 2))
    raw_test = rng.normal(loc=7.0, scale=3.0, size=(11, 2))

    mins = raw_train.min(axis=0)
    maxs = raw_train.max(axis=0)

    np.save(tmp_path / "embeddings.npy", raw_train)
    np.save(
        tmp_path / "test_embeddings.npy",
        rescale_embedding(raw_test, preset_min=mins, preset_max=maxs),
    )
    (tmp_path / "embedding_scaling.json").write_text(
        json.dumps(
            {
                "min_embeddings": mins.tolist(),
                "max_embeddings": maxs.tolist(),
                "mode": "per_axis",
                "margin": 0,
                "embeddings_npy_space": "raw",
                "test_embeddings_npy_space": "rescaled",
            }
        )
    )
    return tmp_path, raw_train, raw_test


@pytest.mark.parametrize("margin", MARGIN_CASES)
def test_round_trip_recovers_the_original_coordinates(margin):
    rng = np.random.default_rng(1)
    raw = rng.normal(size=(50, 3)) * 12 - 4
    mins, maxs = raw.min(axis=0), raw.max(axis=0)

    there = rescale_embedding(raw, margin=margin, preset_min=mins, preset_max=maxs)
    back = inverse_rescale_embedding(
        there, margin=margin, min_value=mins, max_value=maxs
    )

    np.testing.assert_allclose(back, raw, rtol=1e-10, atol=1e-10)


def test_per_axis_rescaling_is_idempotent():
    """Documents why mixing the spaces is silent rather than loud.

    Rescaling an already-rescaled array returns it unchanged, so a double conversion
    -- the mistake most likely to happen -- destroys no data and raises nothing. There
    is no runtime signal to rely on, which is the whole argument for the loader.
    """
    rng = np.random.default_rng(2)
    raw = rng.normal(size=(30, 2))
    once = rescale_embedding(
        raw, preset_min=raw.min(axis=0), preset_max=raw.max(axis=0)
    )
    twice = rescale_embedding(
        once, preset_min=once.min(axis=0), preset_max=once.max(axis=0)
    )
    np.testing.assert_allclose(twice, once, rtol=1e-12, atol=1e-12)


def test_space_cannot_be_omitted(run_dir):
    """`space` is keyword-only and has no default, on purpose."""
    folder, _, _ = run_dir
    with pytest.raises(TypeError):
        load_embeddings(folder)


def test_space_cannot_be_positional(run_dir):
    folder, _, _ = run_dir
    with pytest.raises(TypeError):
        load_embeddings(folder, RAW)


def test_unknown_space_is_rejected_by_name(run_dir):
    folder, _, _ = run_dir
    with pytest.raises(ValueError, match="space must be one of"):
        load_embeddings(folder, space="normalised")


def test_unknown_split_is_rejected(run_dir):
    folder, _, _ = run_dir
    with pytest.raises(ValueError, match="split must be one of"):
        load_embeddings(folder, space=RAW, split="validation")


def test_train_raw_is_returned_untouched(run_dir):
    folder, raw_train, _ = run_dir
    np.testing.assert_allclose(load_embeddings(folder, space=RAW), raw_train)


def test_train_rescaled_spans_the_unit_interval(run_dir):
    folder, _, _ = run_dir
    got = load_embeddings(folder, space=RESCALED)
    # Per-axis: each dimension independently hits both ends.
    np.testing.assert_allclose(got.min(axis=0), 0.0, atol=1e-12)
    np.testing.assert_allclose(got.max(axis=0), 1.0, atol=1e-12)


def test_test_raw_recovers_the_original_test_coordinates(run_dir):
    """The inverse direction: test_embeddings.npy is stored rescaled."""
    folder, _, raw_test = run_dir
    np.testing.assert_allclose(
        load_embeddings(folder, space=RAW, split="test"), raw_test, rtol=1e-10
    )


def test_train_and_test_are_comparable_when_loaded_into_one_space(run_dir):
    """The regression this module exists for.

    Loaded naively -- both straight off disk -- train and test live in different
    coordinate systems and their distances are unrelated. Loaded through this API into
    a single named space, the nearest-neighbour structure survives.
    """
    folder, raw_train, raw_test = run_dir

    train_r = load_embeddings(folder, space=RESCALED, split="train")
    test_r = load_embeddings(folder, space=RESCALED, split="test")
    train_raw = load_embeddings(folder, space=RAW, split="train")
    test_raw = load_embeddings(folder, space=RAW, split="test")

    def nearest(a, b):
        return np.argmin(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1), axis=1)

    # Same answer whichever space you pick, as long as you pick ONE.
    np.testing.assert_array_equal(
        nearest(test_r, train_r), nearest(test_raw, train_raw)
    )

    # And the mixed reading -- the actual mistake -- disagrees, which is what makes it
    # worth a guard rather than a comment.
    mixed = nearest(np.load(folder / "test_embeddings.npy"), train_raw)
    assert not np.array_equal(mixed, nearest(test_r, train_r))


def test_missing_scaling_file_raises_rather_than_returning_none(tmp_path):
    """Returning None here is how absent factors become silently-raw coordinates."""
    rng = np.random.default_rng(3)
    np.save(tmp_path / "embeddings.npy", rng.normal(size=(10, 2)))

    with pytest.raises(FileNotFoundError, match="embedding_scaling.json"):
        load_scaling(tmp_path)

    # Reading the array in its stored space still works -- no conversion is needed, so
    # nothing should demand the file.
    load_embeddings(tmp_path, space=RAW)

    # Asking for the other space cannot be served, and says so.
    with pytest.raises(FileNotFoundError):
        load_embeddings(tmp_path, space=RESCALED)


def test_scaling_json_records_which_array_is_in_which_space(run_dir):
    """The descriptive fields are the point; a loader alone leaves the folder mute."""
    folder, _, _ = run_dir
    scaling = load_scaling(folder)
    assert scaling["embeddings_npy_space"] == RAW
    assert scaling["test_embeddings_npy_space"] == RESCALED
    assert scaling["mode"] == "per_axis"


def test_emuses_utils_reexports_the_same_objects():
    """One implementation, two import paths. Two implementations is the bug itself."""
    from emuses.tools import embedding_spaces, emuses_utils

    assert emuses_utils.rescale_embedding is embedding_spaces.rescale_embedding
    assert (
        emuses_utils.inverse_rescale_embedding
        is embedding_spaces.inverse_rescale_embedding
    )
