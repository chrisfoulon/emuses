"""
Test to validate the session fixture works correctly.

This test validates that our session-scoped pipeline fixture
runs successfully and produces the expected outputs.

These assertions are deliberately strict. An earlier version reported `2 passed` while
both pipeline runs were in fact raising TypeError, because it only checked that the
results dict had the expected *keys* and treated a None value (the fixture's failure
marker) as an acceptable outcome. A fixture test that tolerates the fixture failing
tells nobody anything.
"""

import pytest
from pathlib import Path


EXPECTED_MODES = ['regression', 'multi_target_regression']


class TestSessionFixtureValidation:
    """Validate that session fixture produces expected pipeline outputs."""

    def test_session_fixture_setup(self, emuses_pipeline_results):
        """Test that session fixture creates expected pipeline results."""
        results = emuses_pipeline_results

        assert 'session_temp_dir' in results

        session_dir = results['session_temp_dir']
        assert isinstance(session_dir, Path)
        assert session_dir.exists(), f"Session temp directory does not exist: {session_dir}"

        for mode in EXPECTED_MODES:
            assert mode in results, f"Expected mode {mode} not found in results"
            # None is how the fixture records a pipeline exception. Failing here is the
            # point: the traceback is printed by the fixture itself.
            assert results[mode] is not None, (
                f"Pipeline failed for {mode} — see the fixture's traceback above"
            )
            assert results[mode].exists(), (
                f"Pipeline output directory missing for {mode}: {results[mode]}"
            )

    @pytest.mark.parametrize("mode", EXPECTED_MODES)
    def test_pipeline_output_is_a_complete_emuses_folder(
        self, mode, emuses_pipeline_results
    ):
        """
        The fixture must produce a folder the model registry will accept.

        This mirrors ModelIOManager._validate_emuses_folder_structure
        (emuses/tools/model_io.py:701), which is what install_model() enforces. It is
        spelled out here rather than calling that private method so the expected layout
        is readable, and so a change to either side shows up as a deliberate decision.

        Per ADR §2.1 an EMUSES model is an atomic folder: UMAP, HDBSCAN, prediction
        models, scalers and metadata trained together. All five conditions below are
        required for the folder to be installable.
        """
        output_path = emuses_pipeline_results[mode]
        assert output_path is not None, f"Pipeline failed for {mode}"

        # 1. a root manifest
        manifests = list(output_path.glob("*manifest*.json"))
        assert manifests, f"No root manifest in {output_path}"

        # 2. at least UMAP + HDBSCAN at the root
        joblibs = list(output_path.glob("*.joblib"))
        assert len(joblibs) >= 2, (
            f"Expected at least 2 root .joblib files (UMAP, HDBSCAN), "
            f"found {[p.name for p in joblibs]}"
        )

        # 3. embeddings and training data, under exactly these names — a --prefix
        #    renames them and makes the folder unregisterable (see conftest).
        for data_file in ("embeddings.npy", "input_matrix.npy"):
            assert (output_path / data_file).exists(), (
                f"Missing {data_file} in {output_path}"
            )

        # 4. at least one prediction target
        target_dirs = sorted(p for p in output_path.glob("target_*") if p.is_dir())
        assert target_dirs, f"No target_* directories in {output_path}"

        # 5. each target carries its own manifest and models
        for target_dir in target_dirs:
            assert (target_dir / "model_manifest.json").exists(), (
                f"Missing model_manifest.json in {target_dir}"
            )
            assert list(target_dir.glob("*.joblib")), (
                f"No .joblib files in {target_dir}"
            )

    def test_multi_target_produces_one_directory_per_target(
        self, emuses_pipeline_results
    ):
        """The multi-target scores file has two columns, so it must yield two targets."""
        output_path = emuses_pipeline_results['multi_target_regression']
        assert output_path is not None, "Pipeline failed for multi_target_regression"

        target_dirs = sorted(
            p.name for p in output_path.glob("target_*") if p.is_dir()
        )
        assert target_dirs == ["target_0", "target_1"], (
            f"Expected target_0 and target_1 from a 2-column scores file, "
            f"got {target_dirs}"
        )
