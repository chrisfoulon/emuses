"""An output folder holding several runs must say which results are which.

`performance_summary/` keeps one timestamped pair of CSVs per run and the
per-target CSVs are overwritten by whichever run went last, so without an index
"the results" in a reused folder is a filename picked by eye. Deleting older
runs is not the answer: comparing configurations (say n_components 2 vs 5) is
the reason a folder holds more than one.

The index is descriptive only. Nothing reads it back to make a decision, so its
failure modes must cost information and never correctness.
"""

import json

import numpy as np
import pytest

from emuses.tools.run_index import (RUN_INDEX_FILENAME, build_run_entry,
                                    read_run_index, record_run)


class _Config:
    output_folder = None
    optim_dict = "optim_dict_default"
    prediction_optim_dict = "quick_train_dict"
    outer_folds = 5
    optuna_trials = 15
    random_state = 42
    resume_targets = False
    allow_nd_without_heatmaps = False


def _entry(**kw):
    defaults = dict(timestamp="20260904_120000", task="reg", n_targets=1,
                    summary_file="s.csv", folds_file="f.csv", config=_Config())
    defaults.update(kw)
    return build_run_entry(**defaults)


class TestEntryContents:
    def test_records_the_embedding_width(self):
        """The whole point of a multi-run folder is comparing configurations."""
        entry = _entry(context={"prediction_train_coords": np.zeros((40, 5))})
        assert entry["n_components"] == 5
        assert entry["n_train_samples"] == 40

    def test_records_the_search_configuration(self):
        entry = _entry()
        assert entry["optuna_trials"] == 15
        assert entry["prediction_optim_dict"] == "quick_train_dict"
        assert entry["outer_folds"] == 5

    def test_records_that_heatmaps_were_skipped(self):
        entry = _entry(context={
            "prediction_train_coords": np.zeros((40, 5)),
            "heatmaps_skipped": {"n_components": 5},
        })
        assert entry["heatmaps_skipped"] == 5

    def test_missing_context_does_not_explode(self):
        entry = _entry(context=None)
        assert entry["n_components"] is None

    def test_non_json_config_values_are_stringified(self):
        """Enums and Paths reach here from the CLI and must not break the write."""
        from pathlib import Path

        class Cfg(_Config):
            input_normalization = Path("robust")

        entry = _entry(config=Cfg())
        json.dumps(entry)  # must not raise


class TestIndexFile:
    def test_appends_rather_than_replaces(self, tmp_path):
        record_run(tmp_path, _entry(timestamp="a", summary_file="a.csv"))
        record_run(tmp_path, _entry(timestamp="b", summary_file="b.csv"))
        index = read_run_index(tmp_path)
        assert index["n_runs"] == 2
        assert [r["timestamp"] for r in index["runs"]] == ["a", "b"]

    def test_latest_points_at_the_most_recent(self, tmp_path):
        record_run(tmp_path, _entry(timestamp="a", summary_file="a.csv"))
        record_run(tmp_path, _entry(timestamp="b", summary_file="b.csv"))
        assert read_run_index(tmp_path)["latest"]["summary_file"] == "b.csv"

    def test_a_damaged_index_does_not_lose_the_new_run(self, tmp_path):
        """History is nice; recording the run that just finished matters more."""
        folder = tmp_path / "performance_summary"
        folder.mkdir(parents=True)
        (folder / RUN_INDEX_FILENAME).write_text("{ not json")
        assert record_run(tmp_path, _entry(timestamp="new")) is not None
        index = read_run_index(tmp_path)
        assert index["n_runs"] == 1
        assert index["runs"][0]["timestamp"] == "new"

    def test_writing_never_raises(self):
        assert record_run(None, _entry()) is None
        assert record_run("/proc/nope/nope", _entry()) is None

    def test_reading_a_folder_without_one_is_none(self, tmp_path):
        assert read_run_index(tmp_path) is None


def test_the_stage_records_every_run():
    """The helper working is not the same as the stage calling it."""
    import ast
    import inspect
    import textwrap

    from emuses.pipelines.heatmap_stage import HeatmapStage

    tree = ast.parse(textwrap.dedent(
        inspect.getsource(HeatmapStage._generate_performance_csv_files)))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "record_run"]
    assert calls, (
        "HeatmapStage writes timestamped aggregate CSVs but never records which "
        "run produced them"
    )
