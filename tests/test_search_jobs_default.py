"""The search runs serially unless someone deliberately asks otherwise.

Why this file exists
--------------------
``optuna.study.optimize(n_jobs>1)`` runs trials concurrently, so TPE's suggestion
depends on which trials have finished when each one asks. That is thread timing,
and no seed controls it. Measured 2026-08-23: 10 of 20 metrics identical across
three repeats at ``umap_jobs=4``, 20 of 20 at ``umap_jobs=1``
(``dev-docs/issues/reproducibility_tolerances_2026_08.md``, ADR 2.9c).

Reproducibility is therefore the default and parallel search is an opt-in that
warns. These guards exist because the default was previously *correct by
accident* -- ``PipelineConfig.umap_jobs`` was ``None`` and ``UMAPStage`` mapped
``None -> 1`` at the point of use, so nothing declared it and nothing would have
noticed it changing.

The guard with teeth is ``test_no_optuna_search_runs_in_parallel_by_default``: it
watches the real ``Study.optimize`` calls of a real run rather than asserting on
an attribute, so neither a changed default nor a broken mapping can pass it.
"""

import argparse
import logging
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import optuna
import pandas as pd
import pytest

from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
from emuses.pipelines.pipeline_config import PipelineConfig
from emuses.pipelines.umap_stage import _as_jobs, _resolve_search_jobs

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# The declared defaults
# ---------------------------------------------------------------------------


def test_pipeline_config_defaults_to_serial_search():
    """Declared, not inferred from a None mapping downstream."""
    config = PipelineConfig(output_folder="/tmp/unused")
    assert config.umap_jobs == 1
    assert config.hdbscan_jobs == 1


def test_service_arg_mapping_defaults_to_serial_search():
    """The service path had the only default above 1 (hdbscan_jobs=4)."""
    runner = PipelineRunner(job_manager=MagicMock())
    args = runner._context_to_emuses_args({"config": {"output_folder": "/tmp/unused"}})
    assert args.umap_jobs == 1
    assert args.hdbscan_jobs == 1


def test_service_arg_mapping_still_honours_explicit_values():
    """Serial is a default, not an override: an explicit request survives."""
    runner = PipelineRunner(job_manager=MagicMock())
    args = runner._context_to_emuses_args(
        {"config": {"output_folder": "/tmp/unused", "umap_jobs": 6, "hdbscan_jobs": 2}}
    )
    assert args.umap_jobs == 6
    assert args.hdbscan_jobs == 2


# ---------------------------------------------------------------------------
# The resolution point
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 1),  # arg objects built before the explicit default
        (MagicMock(), 1),  # a Mock config fabricates the attribute
        ("4", 1),  # a string from a config file is not a job count
        (True, 1),  # bool is an int subclass; not a job count either
        (4, 4),
        (-1, -1),
    ],
)
def test_as_jobs_only_trusts_real_integers(value, expected):
    """The MagicMock trap, again.

    A ``Mock`` config fabricates any attribute on access, so ``getattr(cfg,
    "umap_jobs", 1)`` returns a Mock that is truthy and not an int. The same
    shape hid the broken parallelism detector and broke the seed wiring in
    ``heatmap_stage._seeds_from``.
    """
    assert _as_jobs(value) == expected


def test_parallel_search_warns_that_it_forfeits_reproducibility(caplog):
    config = PipelineConfig(output_folder="/tmp/unused", umap_jobs=4)
    with caplog.at_level(logging.WARNING):
        umap_jobs, _ = _resolve_search_jobs(config, logging.getLogger("test"))
    assert umap_jobs == 4, "the request must be honoured, not silently overridden"
    assert any("reproducib" in record.message.lower() for record in caplog.records)


def test_serial_search_does_not_warn(caplog):
    config = PipelineConfig(output_folder="/tmp/unused")
    with caplog.at_level(logging.WARNING):
        _resolve_search_jobs(config, logging.getLogger("test"))
    assert not [r for r in caplog.records if "reproducib" in r.message.lower()]


def test_hdbscan_jobs_is_declared_inert(caplog):
    """``--hdbscan_jobs`` is advertised and changes nothing.

    ``train_and_save_umap_optim_with_nested_clustering`` takes
    ``parallel_mode="umap"`` and no caller overrides it, so ``inner_n_jobs`` is
    only read in the ``parallel_mode == "hdbscan"`` branch. Decided 2026-08-23 to
    document rather than wire or remove it -- the same treatment as the five
    NOT_IMPLEMENTED options. If someone wires ``parallel_mode``, this fails and
    that decision gets revisited instead of drifting.
    """
    config = PipelineConfig(output_folder="/tmp/unused", hdbscan_jobs=8)
    with caplog.at_level(logging.WARNING):
        _, hdbscan_jobs = _resolve_search_jobs(config, logging.getLogger("test"))
    assert hdbscan_jobs == 8
    assert any("no effect" in record.message.lower() for record in caplog.records)


# ---------------------------------------------------------------------------
# The behavioural guard
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_no_optuna_search_runs_in_parallel_by_default(tmp_path, monkeypatch):
    """Watch the real calls, not the attributes.

    Spies on every ``Study.optimize`` in a real (single-trial) run and asserts
    that none of them was given ``n_jobs`` above 1. This covers both searches at
    once: a changed default, a broken ``None`` mapping, or a newly parallelised
    inner loop all fail here.

    ``optim_dict_test`` has every parameter fixed, so ``UMAP_utils`` collapses it
    to a single trial and the run is cheap.
    """
    from emuses.config.optim_configs import load_optim_dict
    from emuses.tools.UMAP_utils import \
        train_and_save_umap_optim_with_nested_clustering

    features = pd.read_csv(
        PROJECT_ROOT / "test_data" / "features.csv", header=None
    ).to_numpy(dtype=float)

    recorded = []
    original = optuna.study.Study.optimize

    def spy(self, func, *args, **kwargs):
        recorded.append(kwargs.get("n_jobs", 1))
        return original(self, func, *args, **kwargs)

    monkeypatch.setattr(optuna.study.Study, "optimize", spy)

    train_and_save_umap_optim_with_nested_clustering(
        input_matrix=features,
        output_folder=tmp_path,
        optim_dict=load_optim_dict("optim_dict_test"),
        n_trials=1,
        n_inner_trials=1,
        random_state=42,
    )

    assert recorded, "no Optuna study ran -- the guard would pass vacuously"
    assert all(
        jobs == 1 for jobs in recorded
    ), f"an Optuna search ran in parallel by default: n_jobs values {recorded}"


@pytest.mark.slow
def test_inner_search_stays_serial_even_when_asked_for_parallel(tmp_path, monkeypatch):
    """Behavioural proof of the inertness that the warning only claims.

    Asks for ``inner_n_jobs=8`` and checks that no study actually ran in
    parallel. Fails the day someone wires ``parallel_mode``, which is the point:
    decision 3 of 2026-08-23 should be revisited deliberately, not drifted past.
    """
    from emuses.config.optim_configs import load_optim_dict
    from emuses.tools.UMAP_utils import \
        train_and_save_umap_optim_with_nested_clustering

    features = pd.read_csv(
        PROJECT_ROOT / "test_data" / "features.csv", header=None
    ).to_numpy(dtype=float)

    recorded = []
    original = optuna.study.Study.optimize

    def spy(self, func, *args, **kwargs):
        recorded.append(kwargs.get("n_jobs", 1))
        return original(self, func, *args, **kwargs)

    monkeypatch.setattr(optuna.study.Study, "optimize", spy)

    train_and_save_umap_optim_with_nested_clustering(
        input_matrix=features,
        output_folder=tmp_path,
        optim_dict=load_optim_dict("optim_dict_test"),
        n_trials=1,
        n_inner_trials=1,
        inner_n_jobs=8,
        random_state=42,
    )

    assert recorded, "no Optuna study ran -- the guard would pass vacuously"
    assert all(jobs == 1 for jobs in recorded), (
        "inner_n_jobs is no longer inert: n_jobs values "
        f"{recorded}. Revisit decision 3 of 2026-08-23 rather than deleting this."
    )


@pytest.mark.slow
def test_umap_stage_passes_the_resolved_jobs_through(tmp_path, monkeypatch):
    """The stage is where ``None`` used to become 1; check what it actually sends."""
    import emuses.pipelines.umap_stage as umap_stage

    captured = {}

    def recorder(**kwargs):
        captured.update(kwargs)
        raise RuntimeError("stop here: only the arguments matter")

    monkeypatch.setattr(
        umap_stage, "train_and_save_umap_optim_with_nested_clustering", recorder
    )

    config = PipelineConfig(output_folder=tmp_path)
    # An arg object predating the explicit default still arrives with None.
    config.umap_jobs = None
    config.hdbscan_jobs = None
    stage = umap_stage.UMAPStage(config)

    with pytest.raises(RuntimeError):
        stage.run({"embedding_train_features": np.random.default_rng(0).normal(
            size=(48, 7)
        )})

    assert captured["n_jobs"] == 1
    assert captured["inner_n_jobs"] == 1
