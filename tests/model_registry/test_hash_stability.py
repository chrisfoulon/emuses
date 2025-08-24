"""Tests for hash stability across filesystem operations."""

import pytest
import hashlib
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from emuses.tools.model_io import ModelIOManager


class TestHashStability:
    """Test hash consistency across filesystem operations."""

    def test_hash_consistent_after_directory_move(self, tmp_path):
        """Verify hash unchanged when model directory moved."""
        # Create test model structure
        model_dir1 = tmp_path / "model_original"
        model_dir1.mkdir()
        (model_dir1 / "umap_model.pkl").write_bytes(b"test umap content")
        (model_dir1 / "hdbscan_model.pkl").write_bytes(b"test hdbscan content")
        
        # Calculate hash at original location
        manager = ModelIOManager(tmp_path)
        original_hash = self._calculate_test_hash(manager, model_dir1)
        
        # Move directory to new location
        model_dir2 = tmp_path / "model_moved"
        shutil.move(str(model_dir1), str(model_dir2))
        
        # Calculate hash at new location
        moved_hash = self._calculate_test_hash(manager, model_dir2)
        
        # Hash should be identical despite path change
        assert original_hash == moved_hash, "Hash changed after directory move"

    def test_hash_ignores_filesystem_artifacts(self, tmp_path):
        """Verify .DS_Store, Thumbs.db don't affect hash."""
        # Create model without artifacts
        model_dir1 = tmp_path / "clean_model"
        model_dir1.mkdir()
        (model_dir1 / "umap_model.pkl").write_bytes(b"test content")
        
        manager = ModelIOManager(tmp_path)
        clean_hash = self._calculate_test_hash(manager, model_dir1)
        
        # Create identical model with filesystem artifacts
        model_dir2 = tmp_path / "dirty_model"
        model_dir2.mkdir()
        (model_dir2 / "umap_model.pkl").write_bytes(b"test content")
        (model_dir2 / ".DS_Store").write_bytes(b"macos artifact")
        (model_dir2 / "Thumbs.db").write_bytes(b"windows artifact")
        (model_dir2 / "._hidden").write_bytes(b"resource fork")
        
        dirty_hash = self._calculate_test_hash(manager, model_dir2)
        
        # Hash should be identical despite artifacts
        assert clean_hash == dirty_hash, "Filesystem artifacts affected hash"

    def test_cross_platform_hash_simulation(self, tmp_path):
        """Simulate cross-platform scenarios with path separators."""
        # Create model structure
        model_dir = tmp_path / "test_model"
        nested_dir = model_dir / "nested" / "structure"
        nested_dir.mkdir(parents=True)
        (model_dir / "umap_model.pkl").write_bytes(b"content")
        (nested_dir / "deep_file.pkl").write_bytes(b"nested content")
        
        manager = ModelIOManager(tmp_path)
        
        # Get hash with current system
        original_hash = self._calculate_test_hash(manager, model_dir)
        
        # Simulate different path representations (this will fail with current implementation)
        # The hash should be path-independent, focusing only on content
        # This test documents expected behavior after fix
        with patch('pathlib.Path.relative_to') as mock_relative:
            # Mock different path representations
            mock_relative.side_effect = [
                Path("nested/structure/deep_file.pkl"),  # Unix-style
                Path("umap_model.pkl")
            ]
            
            # This should produce same hash regardless of path separator style
            # (Will fail with current path-sensitive implementation)
            cross_platform_hash = self._calculate_test_hash(manager, model_dir)
            
            # After Phase 2C fix, this should pass
            # Currently will fail due to path-sensitive hashing
            assert original_hash == cross_platform_hash, "Hash varies across path representations"

    def _calculate_test_hash(self, manager, model_path):
        """Helper to calculate content hash for testing."""
        # Simulate the hash calculation that will be fixed
        components = {
            "umap": model_path / "umap_model.pkl" if (model_path / "umap_model.pkl").exists() else model_path,
            "hdbscan": model_path / "hdbscan_model.pkl" if (model_path / "hdbscan_model.pkl").exists() else model_path
        }
        
        # Filter out non-existent components
        components = {k: v for k, v in components.items() if v.exists()}
        
        return manager._calculate_content_hash(model_path, components)


class TestSimpleDuplicateDetection:
    """Test basic hash-based duplicate detection."""
    
    def test_exact_duplicate_detection(self, tmp_path):
        """Test basic hash-based duplicate detection."""
        from emuses.tools.local_model_registry import LocalModelRegistry
        from emuses.tools.model_io import ModelIOManager
        
        # Create test model
        models_path = tmp_path / "models"
        models_path.mkdir()
        registry = LocalModelRegistry(models_path)
        
        model_dir = tmp_path / "test_model" 
        model_dir.mkdir()
        (model_dir / "umap_model.pkl").write_bytes(b"test umap content")
        (model_dir / "hdbscan_model.pkl").write_bytes(b"test hdbscan content")
        
        # Get validation result
        model_io = ModelIOManager(models_path)
        validation_result = model_io.validate_model(model_dir)
        
        # Test: No duplicate found initially
        result = registry._check_exact_duplicate(validation_result)
        assert not result["duplicate_found"]
        
        # Install the model
        install_result = registry.install_model(model_dir, model_name="test_model")
        assert install_result["status"] == "success"
        
        # Test: Same model detected as duplicate
        result = registry._check_exact_duplicate(validation_result)
        assert result["duplicate_found"]
        assert result["existing_model"]["name"] == "test_model"
        
    def test_different_models_not_duplicates(self, tmp_path):
        """Verify different models correctly identified as unique."""
        from emuses.tools.local_model_registry import LocalModelRegistry
        from emuses.tools.model_io import ModelIOManager
        
        # Create test models with different content
        models_path = tmp_path / "models"
        models_path.mkdir()
        registry = LocalModelRegistry(models_path)
        
        model1_dir = tmp_path / "model1" 
        model1_dir.mkdir()
        (model1_dir / "umap_model.pkl").write_bytes(b"model 1 umap content")
        
        model2_dir = tmp_path / "model2"
        model2_dir.mkdir()
        (model2_dir / "umap_model.pkl").write_bytes(b"model 2 umap content")
        
        # Get validation results
        model_io = ModelIOManager(models_path)
        validation1 = model_io.validate_model(model1_dir)
        validation2 = model_io.validate_model(model2_dir)
        
        # Install first model
        registry.install_model(model1_dir, model_name="model1")
        
        # Test: Different model not detected as duplicate
        result = registry._check_exact_duplicate(validation2)
        assert not result["duplicate_found"]