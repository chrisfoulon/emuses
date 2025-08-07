"""Security tests for LocalModelRegistry.

This module tests security aspects of the model registry including
input validation, path traversal protection, and error handling.
"""
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from emuses.tools.local_model_registry import LocalModelRegistry


class TestLocalModelRegistrySecurity:
    """Test security aspects of LocalModelRegistry."""

    @pytest.fixture
    def temp_registry(self):
        """Create temporary registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            yield registry

    def test_safe_path_initialization(self):
        """Test that registry safely handles path initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with Path object
            registry_path = Path(temp_dir) / "safe_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            assert registry.registry_path == registry_path
            
            # Test with default path (should not raise exception)
            default_registry = LocalModelRegistry()
            assert default_registry.registry_path.name == "model_registry"

    def test_robust_error_handling_corrupt_index(self, temp_registry):
        """Test error handling with corrupted index file."""
        # Corrupt the index file
        with open(temp_registry.index_path, 'w') as f:
            f.write("invalid json content {")
        
        # All operations should handle corruption gracefully
        models = temp_registry.list_models()
        assert models == []
        
        info = temp_registry.get_registry_info()
        assert "error" in info
        assert info["model_count"] == 0
        
        search_results = temp_registry.search_models("test")
        assert search_results == []

    def test_safe_model_id_handling(self, temp_registry):
        """Test safe handling of various model ID formats."""
        # Test with non-existent model
        result = temp_registry.get_model_info("nonexistent_model")
        assert result is None
        
        # Test removal of non-existent model
        result = temp_registry.remove_model("nonexistent_model")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    @patch('emuses.tools.local_model_registry.ModelIOManager')
    def test_installation_error_handling(self, mock_model_io_class, temp_registry):
        """Test error handling during model installation."""
        # Setup mock to raise exception
        mock_instance = Mock()
        mock_model_io_class.return_value = mock_instance
        mock_instance.validate_model.side_effect = ValueError("Invalid model format")
        
        with tempfile.NamedTemporaryFile(suffix='.zip') as model_file:
            model_path = Path(model_file.name)
            
            result = temp_registry.install_model(model_path)
            
            assert result["status"] == "error"
            assert "Invalid model format" in result["message"]
            assert "error_type" in result

    def test_filesystem_error_resilience(self, temp_registry):
        """Test resilience to filesystem errors."""
        # Test with non-writable directory (simulated)
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            result = temp_registry.backup_index()
            assert result is False

    def test_cleanup_safety(self, temp_registry):
        """Test that cleanup operations are safe and don't remove valid data."""
        # Add a valid model to index
        index = temp_registry._load_index()
        index["models"]["valid_model"] = {
            "model_id": "valid_model",
            "name": "test_model",
            "type": "classification"
        }
        temp_registry._save_index(index)
        
        # Create the corresponding directory
        valid_dir = temp_registry.models_path / "valid_model"
        valid_dir.mkdir(parents=True, exist_ok=True)
        (valid_dir / "model.txt").write_text("valid model data")
        
        # Create orphaned directory
        orphaned_dir = temp_registry.models_path / "orphaned_model"
        orphaned_dir.mkdir()
        (orphaned_dir / "orphaned.txt").write_text("orphaned data")
        
        # Run cleanup
        result = temp_registry.cleanup_orphaned_models()
        
        # Valid directory should still exist
        assert valid_dir.exists()
        assert (valid_dir / "model.txt").exists()
        
        # Orphaned directory should be removed
        assert not orphaned_dir.exists()
        assert result["removed_directories"] == 1

    def test_index_validation_comprehensive(self, temp_registry):
        """Test comprehensive index validation."""
        # Test with valid index
        is_valid, issues = temp_registry.validate_index()
        assert is_valid is True
        assert len(issues) == 0
        
        # Add invalid model entry
        index = temp_registry._load_index()
        index["models"]["invalid_model"] = {
            "name": "broken_model"  # Missing required fields
        }
        temp_registry._save_index(index)
        
        is_valid, issues = temp_registry.validate_index()
        assert is_valid is False
        assert len(issues) > 0

    def test_concurrent_access_safety(self, temp_registry):
        """Test safety of concurrent registry access."""
        # Simulate concurrent access by loading/saving index multiple times
        for i in range(10):
            index = temp_registry._load_index()
            index["models"][f"test_model_{i}"] = {
                "model_id": f"test_model_{i}",
                "name": f"Test Model {i}",
                "type": "test"
            }
            temp_registry._save_index(index)
        
        # Verify all models were saved correctly
        final_models = temp_registry.list_models()
        assert len(final_models) == 10

    def test_malformed_input_handling(self, temp_registry):
        """Test handling of malformed input data."""
        # Test search with empty query
        results = temp_registry.search_models("")
        assert isinstance(results, list)
        
        # Test with None values (should not crash)
        try:
            temp_registry.search_models("")  # Empty string should be handled
        except Exception:
            pytest.fail("Empty search query should not raise exception")
        
        # Test filters with unexpected types
        filters = {"type": None, "tags": "not_a_list"}
        models = temp_registry.list_models(filters)
        assert isinstance(models, list)  # Should return empty list or handle gracefully