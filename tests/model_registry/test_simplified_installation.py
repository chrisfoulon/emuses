"""
Tests for Simplified Installation Workflow with Basic Deduplication.

Tests the simplified deduplication system that uses stable content hashes
and basic exact-match duplicate detection.
"""

import json
import tempfile
from pathlib import Path

from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_io import ModelIOManager


class TestSimplifiedInstallationWorkflow:
    """Test simplified installation workflow with basic deduplication."""

    def test_install_with_deduplication_no_duplicates(self, tmp_path, make_real_emuses_model):
        """Test installation when no duplicates exist."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        model_dir = make_real_emuses_model("test_model")
        
        # Install with deduplication
        result = registry.install_model_with_deduplication(
            model_path=model_dir,
            model_name="test_model"
        )
        
        assert result["status"] == "success"
        assert "test_model" in result["name"]
        
    def test_install_with_deduplication_skip_duplicate(self, tmp_path, make_real_emuses_model):
        """Test that duplicates are skipped with clear messaging."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        model_dir = make_real_emuses_model("test_model")
        
        # Install first time
        result1 = registry.install_model_with_deduplication(
            model_path=model_dir,
            model_name="original_model"
        )
        assert result1["status"] == "success"
        
        # Install second time - should be skipped
        result2 = registry.install_model_with_deduplication(
            model_path=model_dir
        )
        assert result2["status"] == "skipped"
        assert result2["reason"] == "duplicate_model"
        assert "existing_model_id" in result2
        assert "existing_model_name" in result2
        
    def test_install_with_deduplication_force_duplicate(self, tmp_path, make_real_emuses_model):
        """Test forcing installation of duplicate by disabling duplicate check."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        model_dir = make_real_emuses_model("test_model")
        
        # Install first time
        result1 = registry.install_model_with_deduplication(
            model_path=model_dir,
            model_name="model1"
        )
        assert result1["status"] == "success"
        
        # Force install second time with different name
        result2 = registry.install_model_with_deduplication(
            model_path=model_dir,
            skip_duplicates=False,
            model_name="model2"
        )
        assert result2["status"] == "success"
        assert result2["name"] == "model2"

    def test_filesystem_artifacts_ignored(self, tmp_path, make_real_emuses_model):
        """Test that filesystem artifacts don't affect duplicate detection when content is truly identical."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        model_dir = make_real_emuses_model("shared_model")
        
        # First install - should succeed
        result1 = registry.install_model_with_deduplication(
            model_path=model_dir,
            model_name="shared_model"
        )
        assert result1["status"] == "success"
        
        # Add filesystem artifact to the same directory
        (model_dir / ".DS_Store").write_bytes(b"macos artifact")
        
        # Try to install the same directory again - should be detected as duplicate
        # even with the filesystem artifact present
        result2 = registry.install_model_with_deduplication(
            model_path=model_dir,
            model_name="shared_model"
        )
        assert result2["status"] == "skipped"
        assert result2["reason"] == "duplicate_model"


class TestBatchInstallationWorkflow:
    """Test simplified batch installation workflow."""
    
    def test_batch_install_basic_functionality(self, tmp_path, make_real_emuses_model):
        """Test basic batch installation functionality."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        # Three genuinely distinct complete models, not three component stubs.
        batch_models = [make_real_emuses_model(f"model_{i}") for i in range(3)]
        
        # Install batch
        results = registry.batch_install_models_with_deduplication(
            model_paths=batch_models,
            continue_on_error=True
        )
        
        assert len(results) == 3
        # All should succeed since they're unique
        for i, result in enumerate(results):
            assert result["status"] == "success"
            assert "batch_processed" in result
            assert result["batch_processed"] is True


class TestSemanticModelIdGeneration:
    """Test semantic model ID generation (kept from original functionality)."""
    
    def test_semantic_id_generation(self, tmp_path):
        """Test that semantic IDs are generated correctly."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Create test model with clear structure
        model_dir = tmp_path / "test_model"  
        model_dir.mkdir()
        (model_dir / "umap_model.pkl").write_bytes(b"umap content")
        
        # Create mock validation result
        model_io = ModelIOManager(tmp_path / "registry")
        validation_result = model_io.validate_model(model_dir)
        
        # Test semantic ID generation
        semantic_id = registry.generate_semantic_model_id(validation_result)
        
        assert isinstance(semantic_id, str)
        assert len(semantic_id) > 0
        # Should contain model name or meaningful identifier
        assert "test_model" in semantic_id.lower() or "umap" in semantic_id.lower()


class TestInteractiveWorkflowCompatibility:
    """Test that interactive methods properly delegate to simplified workflow."""
    
    def test_interactive_resolution_delegates(self, tmp_path, make_real_emuses_model):
        """Test that interactive resolution delegates to basic deduplication."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        model_dir = make_real_emuses_model("test_model")
        
        # Call interactive method - should work but use simplified logic
        result = registry.install_model_with_interactive_resolution(
            model_path=model_dir,
            model_name="test_model"
        )
        
        assert result["status"] == "success"
        assert "test_model" in result["name"]
        
    def test_batch_deduplication_delegates(self, tmp_path, make_real_emuses_model):
        """Test that batch deduplication delegates to basic deduplication."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        model_dir = make_real_emuses_model("test_model")
        
        # Call batch method - should work but use simplified logic
        result = registry.install_model_with_batch_deduplication(
            model_path=model_dir,
            model_name="test_model"
        )
        
        assert result["status"] == "success"
        assert "test_model" in result["name"]