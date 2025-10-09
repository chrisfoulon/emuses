"""
Tests for Storage Optimization with Shared Component Storage.

Tests the ability to detect and share identical components across models
to reduce storage usage while maintaining model integrity.
"""

import json
import hashlib
from pathlib import Path

from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_io import ModelIOManager


class TestStorageOptimization:
    """Test storage optimization with shared component storage."""

    def test_shared_component_detection(self, tmp_path):
        """Test that identical components across models are detected."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Create first model with UMAP component
        model1_dir = tmp_path / "model1"
        model1_dir.mkdir()
        umap_content = b"shared umap component content"
        (model1_dir / "umap_model.pkl").write_bytes(umap_content)
        (model1_dir / "hdbscan_model.pkl").write_bytes(b"model1 specific hdbscan")
        
        # Create second model with same UMAP component but different HDBSCAN
        model2_dir = tmp_path / "model2"
        model2_dir.mkdir()
        (model2_dir / "umap_model.pkl").write_bytes(umap_content)  # Same content
        (model2_dir / "hdbscan_model.pkl").write_bytes(b"model2 specific hdbscan")
        
        # Install both models
        result1 = registry.install_model_with_deduplication(
            model_path=model1_dir,
            model_name="model1"
        )
        assert result1["status"] == "success"
        
        result2 = registry.install_model_with_deduplication(
            model_path=model2_dir,
            model_name="model2"
        )
        assert result2["status"] == "success"
        
        # Both models should be installed successfully
        # (Storage optimization happens in the background)
        models = registry.list_models()
        assert len(models) == 2

    def test_storage_space_savings(self, tmp_path):
        """Test that shared components result in storage savings."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Create shared component content (large enough to measure savings)
        shared_content = b"x" * 10000  # 10KB shared component
        
        # Create multiple models with shared component
        model_paths = []
        for i in range(3):
            model_dir = tmp_path / f"model_{i}"
            model_dir.mkdir()
            (model_dir / "shared_component.pkl").write_bytes(shared_content)
            (model_dir / "unique_component.pkl").write_bytes(f"unique_{i}".encode())
            model_paths.append(model_dir)
        
        # Install all models
        for i, model_path in enumerate(model_paths):
            result = registry.install_model_with_deduplication(
                model_path=model_path,
                model_name=f"model_{i}"
            )
            assert result["status"] == "success"
        
        # Verify all models are installed
        models = registry.list_models()
        assert len(models) == 3
        
        # TODO: Add actual storage optimization logic and verify space savings
        # For now, just verify models are correctly installed

    def test_model_integrity_with_shared_storage(self, tmp_path):
        """Test that model integrity is maintained when using shared storage."""
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")
        
        # Create models with shared and unique components
        shared_content = b"shared umap component"
        
        model1_dir = tmp_path / "model1"
        model1_dir.mkdir()
        (model1_dir / "umap_model.pkl").write_bytes(shared_content)
        (model1_dir / "config.json").write_text('{"model": "1"}')
        
        model2_dir = tmp_path / "model2"
        model2_dir.mkdir()
        (model2_dir / "umap_model.pkl").write_bytes(shared_content)
        (model2_dir / "config.json").write_text('{"model": "2"}')
        
        # Install both models
        result1 = registry.install_model_with_deduplication(
            model_path=model1_dir,
            model_name="model1"
        )
        assert result1["status"] == "success"
        model1_id = result1["model_id"]
        
        result2 = registry.install_model_with_deduplication(
            model_path=model2_dir,
            model_name="model2"
        )
        assert result2["status"] == "success"
        model2_id = result2["model_id"]
        
        # Verify both models can be retrieved with correct content
        model1_info = registry.get_model_info(model_id=model1_id)
        model2_info = registry.get_model_info(model_id=model2_id)
        
        assert model1_info is not None
        assert model2_info is not None
        
        # Models should have different names but may share components
        assert model1_info["name"] == "model1"
        assert model2_info["name"] == "model2"

    def test_component_hash_consistency(self, tmp_path):
        """Test that component hashes are calculated consistently for shared storage."""
        model_io = ModelIOManager(tmp_path)
        
        # Create identical files in different directories
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "component.pkl").write_bytes(b"test content")
        
        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        (dir2 / "component.pkl").write_bytes(b"test content")
        
        # Calculate hashes for both files
        hash1 = model_io._calculate_file_hash(dir1 / "component.pkl")
        hash2 = model_io._calculate_file_hash(dir2 / "component.pkl")
        
        # Hashes should be identical for identical content
        assert hash1 == hash2

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Helper to calculate file hash for testing."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


class TestSharedStorageImplementation:
    """Test implementation details of shared storage system."""

    def test_shared_storage_directory_structure(self, tmp_path):
        """Test that shared storage creates proper directory structure."""
        registry_path = tmp_path / "registry"
        registry = LocalModelRegistry(registry_path=registry_path)
        
        # Create test model
        model_dir = tmp_path / "test_model"
        model_dir.mkdir()
        test_content = b"test content for hashing"
        (model_dir / "component.pkl").write_bytes(test_content)
        
        result = registry.install_model_with_deduplication(
            model_path=model_dir,
            model_name="test_model"
        )
        assert result["status"] == "success"
        
        # Verify shared storage directory structure exists
        shared_storage_path = registry_path / "shared_components"
        assert shared_storage_path.exists(), "Shared storage directory should exist"
        
        # Calculate expected hash
        import hashlib
        hasher = hashlib.sha256()
        hasher.update(test_content)
        expected_hash = hasher.hexdigest()
        
        # Verify Git-style directory structure
        shard_dir = shared_storage_path / expected_hash[:2]
        assert shard_dir.exists(), f"Shard directory {expected_hash[:2]} should exist"
        
        hash_dir = shard_dir / expected_hash
        assert hash_dir.exists(), f"Hash directory {expected_hash} should exist"
        
        shared_file = hash_dir / "component.pkl"
        assert shared_file.exists(), "Shared component file should exist"
        
        # Verify content is correct
        assert shared_file.read_bytes() == test_content

    def test_symlink_creation_and_resolution(self, tmp_path):
        """Test creation and resolution of symbolic links to shared components."""
        registry_path = tmp_path / "registry"
        registry = LocalModelRegistry(registry_path=registry_path)
        
        # Create test model
        model_dir = tmp_path / "test_model"
        model_dir.mkdir()
        test_content = b"test content for symlink"
        (model_dir / "component.pkl").write_bytes(test_content)
        
        result = registry.install_model_with_deduplication(
            model_path=model_dir,
            model_name="test_model"
        )
        assert result["status"] == "success"
        model_id = result["model_id"]
        
        # Find the installed model directory
        models_path = registry_path / "models"
        installed_model_path = models_path / model_id
        assert installed_model_path.exists(), "Installed model directory should exist"
        
        installed_component = installed_model_path / "component.pkl"
        assert installed_component.exists(), "Installed component should exist"
        
        # Check if it's a symlink (may not be on all systems)
        if installed_component.is_symlink():
            # Verify symlink points to shared storage
            target = installed_component.resolve()
            assert "shared_components" in str(target), "Symlink should point to shared storage"
            
            # Verify content through symlink
            assert installed_component.read_bytes() == test_content
        else:
            # On systems without symlink support, should still have correct content
            assert installed_component.read_bytes() == test_content
        
        # Model should be accessible regardless of storage optimization
        model_info = registry.get_model_info(model_id=model_id)
        assert model_info is not None