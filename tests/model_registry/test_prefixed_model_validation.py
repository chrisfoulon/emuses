"""
Tests that a model trained with --prefix is still recognised as a complete EMUSES folder.

Training applies the run prefix to its output file names: ``--prefix myrun`` produces
``myrun_embeddings.npy`` and ``myrun_input_matrix.npy`` rather than ``embeddings.npy`` and
``input_matrix.npy`` (``UMAP_utils.py``, ``train_and_save_umap_optim``). The registry's
completeness check looked for the unprefixed names only, so every prefixed model was
rejected with "Not a complete EMUSES training folder" and could not be registered.

The folder layout used here is taken from a real pipeline run
(EMUSESPipeline + UMAPStage + HeatmapStage over test_data/features.csv), not invented.
Only the file names matter to this validator, so the payloads are small real arrays.
"""

import json
import numpy as np
import pytest

from emuses.tools.model_io import ModelIOManager


def build_emuses_folder(root, prefix=""):
    """
    Write the file layout a completed EMUSES training run leaves behind.

    Parameters
    ----------
    root : Path
        Folder to populate.
    prefix : str
        Run prefix, as passed to --prefix. Empty for a default run.

    Returns
    -------
    Path
        The populated folder.
    """
    stem = f"{prefix}_" if prefix else ""
    root.mkdir(parents=True, exist_ok=True)

    # Root manifest
    (root / "model_manifest.json").write_text(json.dumps({
        "name": f"{stem}hdbscan_model",
        "version": "1.0.0",
        "model_type": "hdbscan",
    }))

    # UMAP + HDBSCAN + scaler at the root
    for name in (
        f"{stem}best_umap_model_v1_0_0.joblib",
        f"{stem}hdbscan_model_v1_0_0.joblib",
        "input_scaler.joblib",
    ):
        (root / name).write_bytes(b"joblib placeholder")

    # Training arrays carry the prefix; test_embeddings.npy never does
    np.save(root / f"{stem}embeddings.npy", np.zeros((50, 2)))
    np.save(root / f"{stem}input_matrix.npy", np.zeros((50, 8)))
    np.save(root / f"{stem}cluster_labels.npy", np.zeros(50))
    np.save(root / "test_embeddings.npy", np.zeros((10, 2)))

    # The arguments log is where the prefix is recoverable from
    log_dir = root / "log"
    log_dir.mkdir(exist_ok=True)
    (log_dir / "arguments_2026-08-06 22-57-53.json").write_text(
        json.dumps({"prefix": prefix, "umap_trials": 1, "outer_folds": 5})
    )

    # One prediction target with its own manifest and fold models
    target = root / "target_0"
    target.mkdir(exist_ok=True)
    (target / "model_manifest.json").write_text(json.dumps({"target_id": "0"}))
    for fold in range(2):
        (target / f"best_pipeline_fold{fold}_v1_0_0.joblib").write_bytes(b"joblib")

    return root


class TestPrefixedModelValidation:
    """A prefix must not decide whether a trained model can be registered."""

    @pytest.mark.parametrize("prefix", ["", "myrun", "HCP_cognitive_2026"])
    def test_folder_validates_regardless_of_prefix(self, tmp_path, prefix):
        """Both a default run and a prefixed run are complete EMUSES folders."""
        folder = build_emuses_folder(tmp_path / "model", prefix=prefix)
        manager = ModelIOManager(str(folder))

        assert manager._validate_emuses_folder_structure(folder) is True, (
            f"folder with prefix {prefix!r} should validate as complete"
        )

    def test_prefix_is_recovered_from_the_arguments_log(self, tmp_path):
        """The prefix is not in the manifest; it comes from log/arguments_*.json."""
        folder = build_emuses_folder(tmp_path / "model", prefix="myrun")
        manager = ModelIOManager(str(folder))

        assert manager._resolve_artifact_prefix(folder) == "myrun"

    def test_missing_arguments_log_falls_back_to_no_prefix(self, tmp_path):
        """A folder with no arguments log is read as a default, unprefixed run."""
        folder = build_emuses_folder(tmp_path / "model", prefix="")
        for stale in (folder / "log").glob("arguments_*.json"):
            stale.unlink()
        manager = ModelIOManager(str(folder))

        assert manager._resolve_artifact_prefix(folder) == ""
        assert manager._validate_emuses_folder_structure(folder) is True

    def test_test_embeddings_alone_does_not_satisfy_the_check(self, tmp_path):
        """
        Guards the reason a glob is the wrong fix here.

        test_embeddings.npy is a real EMUSES output — the held-out set's coordinates —
        and so are best_embeddings.npy and unlabeled_embeddings.npy. Matching
        ``*embeddings.npy`` would accept a folder that has none of the training data.
        """
        folder = build_emuses_folder(tmp_path / "model", prefix="myrun")
        (folder / "myrun_embeddings.npy").unlink()
        manager = ModelIOManager(str(folder))

        assert (folder / "test_embeddings.npy").exists()
        assert manager._validate_emuses_folder_structure(folder) is False

    def test_missing_input_matrix_still_rejected(self, tmp_path):
        """The fix resolves names; it does not relax what a complete folder needs."""
        folder = build_emuses_folder(tmp_path / "model", prefix="myrun")
        (folder / "myrun_input_matrix.npy").unlink()
        manager = ModelIOManager(str(folder))

        assert manager._validate_emuses_folder_structure(folder) is False
