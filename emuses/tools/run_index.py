"""An index of the runs an output folder contains, so its results can be told apart.

The problem
-----------
``performance_summary/`` accumulates one timestamped pair of CSVs per run
(``performance_summary_statistics_reg_20260904_202030.csv`` and its per-fold
sibling), and nothing distinguishes them. Two runs into one folder -- which is
exactly what resuming, or sweeping ``--umap_n_components``, produces -- leave a
folder where picking "the results" means picking a filename by eye, and the
per-target files under ``target_N/performance/`` have meanwhile been overwritten
by whichever run went last. Reading such a folder a month later, there is no way
to know which numbers belong to which configuration.

Deleting the older files would be worse: the history is the point when comparing
configurations. So the files stay and this records what each one was.

What is recorded
----------------
Enough to tell runs apart *by configuration*, not just by clock time: the
embedding width, the search spaces, the fold and trial budgets, the seeds, and
whether the run skipped heatmaps or reused stored targets. ``latest`` names the
most recent entry so "the current results" is answerable without sorting
filenames.

This is a description of what happened, never an input to anything. Nothing reads
it back to make a decision, so a damaged or missing index costs information, not
correctness.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

RUN_INDEX_FILENAME = "runs.json"
RUN_INDEX_SCHEMA = 1


def build_run_entry(
    *,
    timestamp: str,
    task: str,
    n_targets: int,
    summary_file: Optional[str] = None,
    folds_file: Optional[str] = None,
    config: Optional[Any] = None,
    context: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Describe one run's aggregated results."""
    entry: Dict[str, Any] = {
        "timestamp": timestamp,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "task": str(task),
        "n_targets": int(n_targets),
        "summary_file": summary_file,
        "folds_file": folds_file,
    }

    context = context or {}
    coords = context.get("prediction_train_coords")
    width = getattr(coords, "shape", (None, None))
    entry["n_components"] = int(width[1]) if len(width) == 2 and width[1] else None
    entry["n_train_samples"] = int(width[0]) if len(width) == 2 and width[0] else None
    if context.get("heatmaps_skipped"):
        entry["heatmaps_skipped"] = context["heatmaps_skipped"].get("n_components")

    if config is not None:
        for field in ("optim_dict", "prediction_optim_dict", "outer_folds",
                      "optuna_trials", "umap_trials", "hdbscan_trials",
                      "random_state", "test_size", "input_normalization",
                      "scores_normalization", "resume_targets",
                      "allow_nd_without_heatmaps"):
            value = getattr(config, field, None)
            if value is not None:
                # Enums and Paths do not survive json.dumps unaided.
                entry[field] = value if isinstance(
                    value, (str, int, float, bool)
                ) else str(value)
    return entry


def record_run(output_folder, entry: Dict[str, Any]) -> Optional[Path]:
    """Append `entry` to the folder's run index. Never raises.

    A run whose index entry cannot be written is fully valid; it is only harder
    to identify later. Losing a completed run over bookkeeping would be the worse
    trade by a wide margin.
    """
    if not output_folder or not entry:
        return None
    try:
        folder = Path(output_folder) / "performance_summary"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / RUN_INDEX_FILENAME

        index: Dict[str, Any] = {"schema": RUN_INDEX_SCHEMA, "runs": []}
        if path.is_file():
            try:
                existing = json.loads(path.read_text())
                if (isinstance(existing, dict)
                        and existing.get("schema") == RUN_INDEX_SCHEMA
                        and isinstance(existing.get("runs"), list)):
                    index = existing
            except Exception:  # noqa: BLE001 - a damaged index is replaced, not merged
                pass

        index["runs"].append(entry)
        index["latest"] = entry
        index["n_runs"] = len(index["runs"])
        path.write_text(json.dumps(index, indent=2))
        return path
    except Exception:  # noqa: BLE001 - see docstring
        return None


def read_run_index(output_folder) -> Optional[Dict[str, Any]]:
    """Read the index, or None when there is not a usable one."""
    if not output_folder:
        return None
    try:
        path = Path(output_folder) / "performance_summary" / RUN_INDEX_FILENAME
        if not path.is_file():
            return None
        index = json.loads(path.read_text())
        return index if isinstance(index, dict) else None
    except Exception:  # noqa: BLE001
        return None
