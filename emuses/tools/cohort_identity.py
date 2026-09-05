"""Say which cohort an output folder describes, so a reused morphospace cannot
be paired with someone else's subjects.

The defect this closes
----------------------
``UMAPStage`` re-derives embedding coordinates for whoever is in the current run,
but on the reuse paths (``--load_umap``, ``--load_embeddings``, the output-folder
resume) the *cluster labels* were loaded wholesale from ``cluster_labels.npy``.
Length was the only available signal, so a cohort of a different size was caught
and a cohort of the **same** size was not: n labels belonging to last year's
subjects were pinned onto this year's coordinates, and the run completed.

Why this stores no identifiers by default
-----------------------------------------
This record ships inside the model folder, which is the unit people share and
publish. Many EMUSES users cannot share patient identifiers at all, so the
default must be safe without anyone having to remember a flag.

Hashing the identifiers is **not** a fix. Clinical ids are drawn from small,
guessable spaces -- sequential integers, site prefixes, a known cohort list -- so
per-subject digests are recoverable by enumeration in seconds. A digest of a
predictable value is a pseudonym, not anonymity.

So the default record contains no per-subject data of any kind: a single digest
over the whole feature matrix, plus the sample count. That is sufficient for the
only question being asked ("is this the same cohort as the one the morphospace
was built on?"), reveals nothing about any individual, and as a bonus also
catches a same-cohort run with different preprocessing, which nothing currently
detects. Identifiers are stored only when ``record_ids`` is explicitly set, for
users who can share them and want to know *which* subjects changed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np

COHORT_FILENAME = "cohort.json"

# Bumped only if the digest definition changes. A record written by a different
# scheme must compare as "unknown" rather than "different" -- an old folder is
# not evidence of a cohort change.
COHORT_SCHEMA = 1


def matrix_digest(matrix) -> Optional[str]:
    """A stable SHA-256 over the feature matrix contents.

    Canonicalised to C-contiguous float64 so the digest does not change with
    array order or a harmless dtype difference. Returns None for anything that
    is not a real matrix, which the caller must treat as "unknown".
    """
    if matrix is None:
        return None
    try:
        arr = np.ascontiguousarray(np.asarray(matrix, dtype=np.float64))
    except (TypeError, ValueError):
        return None
    if arr.ndim != 2 or arr.size == 0:
        return None
    h = hashlib.sha256()
    h.update(str(arr.shape).encode("utf-8"))
    h.update(arr.tobytes())
    return h.hexdigest()


def build_cohort_record(
    matrix,
    *,
    ids: Optional[Sequence] = None,
    record_ids: bool = False,
) -> Optional[Dict[str, Any]]:
    """Describe the cohort this run was given. Returns None if it cannot.

    `ids` are used only when `record_ids` is set; see the module docstring for
    why identifiers are not written by default and why hashing them would not
    make writing them safe.
    """
    digest = matrix_digest(matrix)
    if digest is None:
        return None
    record: Dict[str, Any] = {
        "schema": COHORT_SCHEMA,
        "n_samples": int(np.asarray(matrix).shape[0]),
        "feature_digest": digest,
        "contains_identifiers": False,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    if record_ids and ids is not None and len(ids) == record["n_samples"]:
        record["ids"] = [str(i) for i in ids]
        record["contains_identifiers"] = True
        record["identifier_warning"] = (
            "This file contains subject identifiers because --record_cohort_ids "
            "was given. Remove it before sharing or publishing this model folder "
            "if the identifiers are not shareable."
        )
    return record


def write_cohort_record(output_folder, record) -> Optional[Path]:
    """Write the record beside the morphospace. Never raises.

    Bookkeeping must not be able to destroy a completed run, so every failure
    here is swallowed and reported by returning None.
    """
    if not output_folder or not record:
        return None
    try:
        folder = Path(output_folder)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / COHORT_FILENAME
        path.write_text(json.dumps(record, indent=2))
        return path
    except Exception:  # noqa: BLE001 - see docstring
        return None


def read_cohort_record(folder) -> Optional[Dict[str, Any]]:
    """Read a cohort record, or None when there is not a usable one."""
    if not folder:
        return None
    try:
        path = Path(folder) / COHORT_FILENAME
        if not path.is_file():
            return None
        record = json.loads(path.read_text())
        return record if isinstance(record, dict) else None
    except Exception:  # noqa: BLE001 - a damaged record is "unknown", not "different"
        return None


def cohorts_match(stored: Optional[Dict], current: Optional[Dict]) -> Optional[bool]:
    """True / False / None, where **None means unknown**.

    Unknown is returned for a missing record, a record from a different schema,
    or a digest that could not be computed. Callers must treat None like False
    when deciding whether to trust stored cluster labels: every folder written
    before this existed has no record, and "no evidence of a change" is not the
    same as "no change".
    """
    if not stored or not current:
        return None
    if stored.get("schema") != current.get("schema"):
        return None
    stored_digest = stored.get("feature_digest")
    current_digest = current.get("feature_digest")
    if not stored_digest or not current_digest:
        return None
    return stored_digest == current_digest
