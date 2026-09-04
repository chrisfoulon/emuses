"""A reused morphospace must not be paired with someone else's subjects.

Coordinates were always re-derived for the current run, but cluster labels were
loaded wholesale from the previous one. Length was the only check, so cohorts of
DIFFERENT size were caught and cohorts of the SAME size were not: n labels
belonging to other subjects were pinned onto this run's coordinates and the run
completed normally.

The second thing pinned here is the privacy default. This record ships inside the
shared model folder, so a change that starts writing identifiers by default is a
data-protection regression, not a feature. See emuses/tools/cohort_identity.py
for why hashing the identifiers would not make writing them safe.
"""

import json

import numpy as np
import pytest

from emuses.tools.cohort_identity import (COHORT_FILENAME, build_cohort_record,
                                          cohorts_match, matrix_digest,
                                          read_cohort_record,
                                          write_cohort_record)


class TestDigest:
    def test_same_content_same_digest(self):
        rng = np.random.default_rng(0)
        m = rng.random((20, 5))
        assert matrix_digest(m) == matrix_digest(m.copy())

    def test_dtype_does_not_change_it(self):
        """A harmless float32/float64 difference must not read as a new cohort."""
        m = np.arange(40, dtype=np.float64).reshape(8, 5)
        assert matrix_digest(m) == matrix_digest(m.astype(np.float32))

    def test_equal_size_different_content_differs(self):
        """The case the length check could not see."""
        rng = np.random.default_rng(1)
        a, b = rng.random((20, 5)), rng.random((20, 5))
        assert a.shape == b.shape
        assert matrix_digest(a) != matrix_digest(b)

    def test_one_changed_value_is_enough(self):
        m = np.zeros((10, 3))
        other = m.copy()
        other[7, 2] = 1e-9
        assert matrix_digest(m) != matrix_digest(other)

    def test_unusable_input_is_none_not_a_guess(self):
        assert matrix_digest(None) is None
        assert matrix_digest(np.zeros(10)) is None       # 1-D is not a matrix
        assert matrix_digest(np.zeros((0, 3))) is None   # empty


class TestPrivacyDefault:
    """Identifiers must never appear unless explicitly asked for."""

    def test_no_identifiers_by_default(self):
        record = build_cohort_record(np.zeros((3, 2)), ids=["P001", "P002", "P003"])
        assert record["contains_identifiers"] is False
        assert "ids" not in record
        # And nothing per-subject smuggled in under another name.
        serialised = json.dumps(record)
        for pid in ("P001", "P002", "P003"):
            assert pid not in serialised

    def test_identifiers_only_on_explicit_request(self):
        record = build_cohort_record(
            np.zeros((3, 2)), ids=["P001", "P002", "P003"], record_ids=True
        )
        assert record["contains_identifiers"] is True
        assert record["ids"] == ["P001", "P002", "P003"]
        assert "identifier_warning" in record, (
            "a record carrying identifiers must say so in the file itself, since "
            "the file travels with a shared model folder"
        )

    def test_mismatched_ids_are_dropped_not_misaligned(self):
        """Fewer ids than subjects must not silently produce a wrong mapping."""
        record = build_cohort_record(
            np.zeros((5, 2)), ids=["P001", "P002"], record_ids=True
        )
        assert record["contains_identifiers"] is False
        assert "ids" not in record

    def test_the_cli_default_is_off(self):
        """The flag's default is the actual protection; a test on the helper is not."""
        import inspect

        from emuses.cli.pipeline_options import _shared_pipeline_options

        default = inspect.signature(_shared_pipeline_options).parameters[
            "record_cohort_ids"
        ].default
        assert default is False, (
            "--record_cohort_ids defaults to writing identifiers into a folder "
            "people share and publish"
        )


class TestMatching:
    def test_same_matrix_matches(self, tmp_path):
        rng = np.random.default_rng(2)
        m = rng.random((15, 4))
        write_cohort_record(tmp_path, build_cohort_record(m))
        assert cohorts_match(read_cohort_record(tmp_path), build_cohort_record(m)) is True

    def test_equal_size_different_cohort_does_not_match(self, tmp_path):
        rng = np.random.default_rng(3)
        write_cohort_record(tmp_path, build_cohort_record(rng.random((15, 4))))
        assert cohorts_match(
            read_cohort_record(tmp_path), build_cohort_record(rng.random((15, 4)))
        ) is False

    def test_missing_record_is_unknown_not_a_match(self, tmp_path):
        """Every folder written before this feature has no record.

        Returning False would be wrong (nothing says the cohort changed) and
        returning True would be catastrophic (nothing says it didn't). Unknown is
        the honest answer, and callers must treat it like a mismatch.
        """
        assert read_cohort_record(tmp_path) is None
        assert cohorts_match(None, build_cohort_record(np.zeros((3, 2)))) is None

    def test_a_damaged_record_is_unknown(self, tmp_path):
        (tmp_path / COHORT_FILENAME).write_text("{ this is not json")
        assert read_cohort_record(tmp_path) is None

    def test_a_future_schema_is_unknown_not_different(self, tmp_path):
        record = build_cohort_record(np.zeros((3, 2)))
        record["schema"] = 999
        write_cohort_record(tmp_path, record)
        assert cohorts_match(
            read_cohort_record(tmp_path), build_cohort_record(np.zeros((3, 2)))
        ) is None

    def test_writing_never_raises(self):
        """Bookkeeping must not be able to destroy a completed run."""
        assert write_cohort_record(None, {"a": 1}) is None
        assert write_cohort_record("/proc/nope/nope", {"a": 1}) is None


class TestUMAPStageUsesIt:
    """The helpers being right is not the same as the stage consulting them."""

    def test_stage_treats_unknown_like_a_mismatch(self):
        import inspect

        from emuses.pipelines.umap_stage import UMAPStage

        source = inspect.getsource(UMAPStage.run)
        assert "cohort_verdict is not True" in source, (
            "UMAPStage must re-derive labels unless the cohort is CONFIRMED to "
            "match. Testing `is False` instead would trust stored labels for every "
            "folder written before cohort.json existed."
        )

    def test_a_freshly_trained_run_is_exempt(self):
        """Labels from this run's own training must never be second-guessed."""
        import inspect

        from emuses.pipelines.umap_stage import UMAPStage

        source = inspect.getsource(UMAPStage.run)
        assert "reused_from is not None and cohort_verdict is not True" in source, (
            "the cohort check must be gated on the morphospace having been reused; "
            "applying it to a fresh training run would discard correct labels"
        )
