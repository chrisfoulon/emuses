"""
Integration tests for LocalModelRegistry using real ModelIOManager methods.

These tests verify that the complete model installation workflow works
end-to-end without mocking, using the actual ModelIOManager.validate_model()
and install_model() methods that were implemented in Sub-Plan 0A.1.
"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import joblib
import pytest

from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_io import ModelIOManager


class TestLocalModelRegistryIntegration:
    """Integration tests using real ModelIOManager methods."""

    @pytest.fixture
    def temp_registry_dir(self):
        """Create temporary directory for registry testing."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def registry(self, temp_registry_dir):
        """Create LocalModelRegistry instance."""
        return LocalModelRegistry(registry_path=temp_registry_dir)

    @pytest.fixture
    def sklearn_model_dir(self, real_emuses_model):
        """A genuine complete EMUSES model folder.

        Named for what it used to be. It previously built a directory holding a
        bare sklearn ``Pipeline`` and one manifest, and every test that tried to
        install it failed with ``assert 'error' == 'success'``. That was correct
        behaviour: ADR 2.1 states an EMUSES model is an entire output folder -
        UMAP, HDBSCAN, prediction pipelines, scalers and metadata trained
        together - and that components are not separable. A lone sklearn
        pipeline is a component, and the registry is supposed to refuse it.

        Now supplied by ``real_emuses_model`` (tests/conftest.py), a copy of a
        folder a real pipeline run produced. Per G009 it is not assembled by
        hand to satisfy the validator.
        """
        return real_emuses_model

    @pytest.fixture
    def umap_model_dir(self, real_emuses_model_alt):
        """A second, genuinely different complete EMUSES model.

        Was a lone fitted UMAP mapper - again a component, again correctly
        rejected. Now the multi-target run, so tests needing two models get two
        that actually differ rather than duplicates.
        """
        return real_emuses_model_alt

    def test_complete_model_installation_workflow(self, registry, sklearn_model_dir):
        """Test complete end-to-end model installation using real ModelIOManager."""
        # This test verifies the full workflow: validate → install → register
        result = registry.install_model(sklearn_model_dir)
        
        # Verify successful installation
        assert result["status"] == "success"
        assert "model_id" in result
        # Name comes from the folder. A complete EMUSES model's own manifest
        # carries component metadata (often "hdbscan_model"), so the registry
        # deliberately prefers the descriptive folder name over it.
        assert result["name"] == sklearn_model_dir.name
        
        model_id = result["model_id"]
        
        # Verify model appears in listings
        models = registry.list_models()
        assert len(models) >= 1
        
        installed_model = None
        for model in models:
            if model.get("model_id") == model_id:
                installed_model = model
                break
                
        assert installed_model is not None
        assert installed_model["name"] == sklearn_model_dir.name
        assert installed_model["type"] == "emuses_model"
        assert installed_model["version"] == "1.0.0"

    def test_model_validation_integration(self, registry, sklearn_model_dir, temp_registry_dir):
        """Test that ModelIOManager validation is properly integrated."""
        # Create ModelIOManager directly and test validation
        model_io = ModelIOManager(temp_registry_dir / "models")
        
        # This should work without errors using the real validate_model method
        validation = model_io.validate_model(sklearn_model_dir)

        # validate_model returns a CompleteModelValidation, not a dict.
        assert validation.is_complete_model, validation.validation_errors

        # Read the version off the folder rather than hardcoding "1.0.0". The
        # pipeline's manifest version is not a constant, and pinning it here was
        # asserting a fixture detail rather than the behaviour under test: that
        # validate_model reports what the folder actually says.
        on_disk = json.loads(
            (sklearn_model_dir / "model_manifest.json").read_text()
        )
        assert validation.version == on_disk.get("version", "1.0.0")

        # Deliberately not asserting validation.name == the folder name.
        # validate_model reports the name from the folder's own manifest, which for
        # a real EMUSES run is component metadata ("hdbscan_model"). install_model
        # overrides it with the folder name, so the two disagree about what a model
        # is called. Recorded in dev-docs/issues/test_suite_triage_2026_07.md rather
        # than asserted either way here.
        assert validation.name
        # One type, not a component type. Per ADR 2.1 a complete folder is an
        # atomic emuses_model; "sklearn_pipeline" described a component, which is
        # the model this suite was written against and which was reverted.
        assert validation.type == "emuses_model"
        assert validation.description

    def test_model_installation_with_custom_name(self, registry, sklearn_model_dir):
        """Test model installation with custom naming."""
        custom_name = "my_custom_classifier"
        # model_name, not name: install_model does not read **kwargs, so `name=`
        # is silently discarded and the folder name is used instead.
        result = registry.install_model(sklearn_model_dir, model_name=custom_name)
        
        assert result["status"] == "success"
        assert result["name"] == custom_name
        
        # Verify the custom name is used
        model_info = registry.get_model_info(result["model_id"])
        assert model_info["name"] == custom_name

    def test_multiple_model_installation(self, registry, sklearn_model_dir, umap_model_dir):
        """Test installing multiple different model types."""
        # Install sklearn model
        result1 = registry.install_model(sklearn_model_dir)
        assert result1["status"] == "success"
        
        # Install UMAP model
        result2 = registry.install_model(umap_model_dir)
        assert result2["status"] == "success"
        
        # Verify both are listed
        models = registry.list_models()
        assert len(models) == 2
        
        # Both are complete EMUSES folders, so both are emuses_model. The real
        # assertion is that two genuinely different models coexist - which the
        # old component-type check never made.
        assert all(model["type"] == "emuses_model" for model in models)
        assert len({model["model_id"] for model in models}) == 2

    def test_model_directory_structure_validation(self, registry, temp_registry_dir):
        """Test installation with models that need manifest generation."""
        # Create a model directory without a manifest
        temp_dir = Path(tempfile.mkdtemp())
        model_dir = temp_dir / "no_manifest_model"
        model_dir.mkdir()
        
        # Create model files without manifest
        mock_model = {"type": "custom_model", "data": "test"}
        joblib.dump(mock_model, model_dir / "model.pkl")
        joblib.dump({"scaler": "standard"}, model_dir / "preprocessor.joblib")
        
        try:
            # Inverted deliberately. This asserted that a directory of loose model
            # files installs successfully once a manifest is generated for it -
            # the separable-component model that ADR 2.1 records as a violation
            # since corrected. The registry now refuses anything that is not a
            # complete EMUSES output folder, and that refusal is the contract
            # worth testing. Do not "fix" this by relaxing the validator.
            result = registry.install_model(model_dir, model_name="no_manifest_test")

            assert result["status"] == "error", (
                f"A directory of loose model files is not a complete EMUSES "
                f"folder and must be refused, got: {result}"
            )
            assert "complete" in result["message"].lower() or \
                   "emuses" in result["message"].lower(), (
                f"Rejection should say why, got: {result['message']}"
            )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_model_integrity_verification(self, registry, sklearn_model_dir, temp_registry_dir):
        """Test that model integrity verification works in the full workflow."""
        # Install the model first
        result = registry.install_model(sklearn_model_dir)
        assert result["status"] == "success"
        model_id = result["model_id"]
        
        # Get the installed model path
        installed_path = temp_registry_dir / "models" / model_id
        assert installed_path.exists()
        
        # Verify manifest was created with integrity hash
        manifest_path = installed_path / "model_manifest.json"
        assert manifest_path.exists()
        
        with open(manifest_path) as f:
            manifest = json.load(f)
            
        # Should have integrity hash from installation
        assert "integrity_hash" in manifest
        assert manifest["integrity_hash"] is not None
        assert len(manifest["integrity_hash"]) == 64  # SHA-256 hex length

    def test_error_handling_invalid_model_path(self, registry):
        """Test error handling for invalid model paths."""
        non_existent_path = Path("/non/existent/path")
        
        result = registry.install_model(non_existent_path)
        assert result["status"] == "error"
        assert "not exist" in result["message"].lower()

    def test_error_handling_invalid_model_structure(self, registry):
        """Test error handling for directories without model files."""
        temp_dir = Path(tempfile.mkdtemp())
        empty_dir = temp_dir / "empty_model"
        empty_dir.mkdir()
        
        # Create directory with no model files
        (empty_dir / "readme.txt").write_text("This is not a model")
        
        try:
            result = registry.install_model(empty_dir)
            assert result["status"] == "error"
            assert "no model files found" in result["message"].lower()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_model_search_basic(self, registry, sklearn_model_dir, umap_model_dir):
        """Test basic model search capabilities."""
        # Install different types of models
        registry.install_model(sklearn_model_dir)
        registry.install_model(umap_model_dir)
        
        # Test basic search (should return all models)
        all_models = registry.search_models("")
        assert len(all_models) >= 2
        
        # Verify we have both model types
        assert all(model.get("type") == "emuses_model" for model in all_models)
        assert len({model.get("model_id") for model in all_models}) >= 2

    def test_concurrent_model_operations(self, registry, sklearn_model_dir):
        """Test that model operations work correctly when performed in sequence."""
        # Install model
        result = registry.install_model(sklearn_model_dir, model_name="concurrent_test_1")
        model_id_1 = result["model_id"]
        
        # Install same model again with different name
        result = registry.install_model(sklearn_model_dir, model_name="concurrent_test_2")
        model_id_2 = result["model_id"]
        
        # Both should exist and be different
        assert model_id_1 != model_id_2
        
        model_1 = registry.get_model_info(model_id_1)
        model_2 = registry.get_model_info(model_id_2)
        
        assert model_1["name"] == "concurrent_test_1"
        assert model_2["name"] == "concurrent_test_2"
        assert model_1["model_id"] != model_2["model_id"]