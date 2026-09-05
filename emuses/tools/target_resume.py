"""Skip the nested-CV search for targets that a previous run already finished.

Why per target
--------------
The prediction search is the expensive half of EMUSES: ~19 h on ``DSD_repro``
across 87 targets, against minutes for the morphospace. Targets are independent
-- ``_optimise_target`` is called once per column and shares nothing between
columns -- so "already done" is a question that can be answered one target at a
time, with no reasoning about partial Optuna studies. Finer granularity (per
fold, or a half-finished study) means owning the study database's state machine,
which is a different and much larger job for a much smaller saving.

Why a fingerprint rather than "the files are there"
---------------------------------------------------
Fold models on disk say a search finished; they do not say it answers *this*
run's question. Reusing them after the morphospace changed, or after
``--prediction_optim_dict`` / ``--optuna_trials`` changed, produces a run that
completes and reports scores belonging to a different experiment. So a target is
reused only when everything that determined its result is unchanged: the
coordinates it was fitted on, the target values, the resolved search space, the
fold count, the trial budget and the seeds.

The fingerprint is compared, never trusted partially. Anything missing,
unreadable, or from another schema means "cannot confirm", which is treated as
"retrain" -- the same rule as ``cohort_identity``, and for the same reason: a
folder that predates this file is not evidence that nothing changed.

Full-precision scores
---------------------
``performance/performance_individual_folds_<tag>.csv`` rounds to 4 decimals, so
it cannot be the resume source without quietly changing the numbers a resumed run
reports. ``cv_scores.npy`` is written alongside it at full precision, and its
absence makes a target non-resumable rather than approximately resumable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from emuses.tools.cohort_identity import matrix_digest

SCORES_FILENAME = "cv_scores.npy"
FINGERPRINT_FILENAME = "search_fingerprint.json"
RESUME_SCHEMA = 1

_FOLD_RE = re.compile(r"best_pipeline_fold(\d+)")


def _stable_digest(value: Any) -> str:
    """SHA-256 over a JSON-canonical form, for dicts that must compare by value."""
    try:
        payload = json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        payload = repr(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_target_fingerprint(
    *,
    X,
    y,
    task: str,
    outer_folds: int,
    optuna_trials: int,
    optim_dict: Optional[Dict],
    seeds: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Everything that determines this target's result. None if not computable."""
    x_digest = matrix_digest(X)
    y_digest = matrix_digest(np.asarray(y).reshape(-1, 1))
    if x_digest is None or y_digest is None:
        return None
    return {
        "schema": RESUME_SCHEMA,
        "x_digest": x_digest,
        "y_digest": y_digest,
        "task": str(task),
        "outer_folds": int(outer_folds),
        "optuna_trials": int(optuna_trials),
        "optim_dict_digest": _stable_digest(optim_dict),
        # Seeds decide the search path, so a different seed is a different result.
        "seeds": {k: seeds.get(k) for k in ("cv_seed", "optuna_seed", "prediction_seed")},
    }


def write_target_artefacts(out_dir, tag: str, scores, fingerprint) -> None:
    """Record what this target produced, so a later run can decide to reuse it.

    Never raises: bookkeeping must not be able to destroy a search that just cost
    hours. A target whose artefacts fail to write simply is not resumable.
    """
    if out_dir is None or fingerprint is None:
        return
    try:
        folder = Path(out_dir) / tag
        folder.mkdir(parents=True, exist_ok=True)
        np.save(folder / SCORES_FILENAME, np.asarray(scores, dtype=np.float64))
        (folder / FINGERPRINT_FILENAME).write_text(json.dumps(fingerprint, indent=2))
    except Exception:  # noqa: BLE001 - see docstring
        pass


def _load_fold_pipelines(folder: Path) -> List[Any]:
    """Fold pipelines in fold order, or [] if any part of that is not possible.

    Ordering is taken from the filename's fold index, not from sort order: the
    saved names carry a version suffix, so lexical order is not fold order once
    there are ten or more folds.
    """
    import joblib

    numbered = []
    for path in folder.glob("best_pipeline_fold*.joblib"):
        match = _FOLD_RE.search(path.name)
        if match:
            numbered.append((int(match.group(1)), path))
    if not numbered:
        return []
    numbered.sort()
    if [i for i, _ in numbered] != list(range(len(numbered))):
        return []  # a gap means an interrupted target, not a finished one
    try:
        return [joblib.load(path) for _, path in numbered]
    except Exception:  # noqa: BLE001 - an unreadable model means "retrain"
        return []


def load_completed_target(
    out_dir, tag: str, fingerprint, *, logger: Optional[logging.Logger] = None
) -> Optional[Tuple[np.ndarray, List[Any]]]:
    """Return ``(scores, pipelines)`` for an already-finished target, or None.

    None means "run the search". Every failure path returns None, because the
    only cost of retraining is time, while the cost of wrongly reusing is a run
    that reports another experiment's numbers.
    """
    log = logger or logging.getLogger(__name__)
    if out_dir is None or fingerprint is None:
        return None

    folder = Path(out_dir) / tag
    try:
        stored_raw = (folder / FINGERPRINT_FILENAME).read_text()
        stored = json.loads(stored_raw)
    except Exception:  # noqa: BLE001 - missing or damaged: retrain
        return None
    if not isinstance(stored, dict) or stored.get("schema") != RESUME_SCHEMA:
        return None

    if stored != fingerprint:
        differing = sorted(
            k for k in set(stored) | set(fingerprint)
            if stored.get(k) != fingerprint.get(k)
        )
        log.info(
            "%s: not reusing the stored search, %s changed since it ran.",
            tag, ", ".join(differing),
        )
        return None

    scores_path = folder / SCORES_FILENAME
    if not scores_path.is_file():
        # Present for folders written before cv_scores.npy existed. The rounded
        # CSV is deliberately NOT used as a fallback: it would change the numbers.
        log.info("%s: fingerprint matches but %s is missing; re-running the search.",
                 tag, SCORES_FILENAME)
        return None
    try:
        scores = np.load(scores_path)
    except Exception:  # noqa: BLE001
        return None

    pipelines = _load_fold_pipelines(folder)
    if not pipelines:
        log.info("%s: fold models missing or unreadable; re-running the search.", tag)
        return None
    if len(pipelines) != len(scores):
        log.info(
            "%s: %d fold models but %d scores; re-running the search.",
            tag, len(pipelines), len(scores),
        )
        return None

    log.info(
        "%s: reusing the completed search (%d folds, mean=%.4f). "
        "Pass no --resume_targets to force a fresh search.",
        tag, len(pipelines), float(np.mean(scores)) if len(scores) else float("nan"),
    )
    return scores, pipelines
