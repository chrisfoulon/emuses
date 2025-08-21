"""Test suite for LocalModelRegistry class.

This module tests the local file-based model registry implementation,
focusing on directory initialization, model management, and security.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_io import ModelIOManager, CompleteModelValidation


class TestLocalModelRegistryInitialization:
    """Test LocalModelRegistry initialization and directory setup."""

    def test_init_creates_directory_structure(self):
        """Test that initialization creates required directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            
            assert registry.registry_path.exists()
            assert registry.registry_path.is_dir()
            assert (registry.registry_path / "models").exists()
            assert (registry.registry_path / "registry.json").exists()

    def test_init_with_existing_directory(self):
        """Test initialization with existing registry directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "existing_registry"
            registry_path.mkdir()
            
            registry = LocalModelRegistry(registry_path=registry_path)
            assert registry.registry_path.exists()

    def test_default_registry_path(self):
        """Test that default registry path is set correctly."""
        registry = LocalModelRegistry()
        expected_path = Path.home() / ".emuses" / "model_registry"
        assert registry.registry_path == expected_path

    def test_registry_json_initialization(self):
        """Test that registry.json is created with correct structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            
            registry_file = registry.registry_path / "registry.json"
            assert registry_file.exists()
            
            # Test that it contains valid JSON structure
            import json
            with open(registry_file) as f:
                data = json.load(f)
            
            assert "version" in data
            assert "models" in data
            assert isinstance(data["models"], dict)


class TestLocalModelRegistryBasicOperations:
    """Test basic registry operations."""

    @pytest.fixture
    def temp_registry(self):
        """Create temporary registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            yield registry

    def test_registry_is_empty_initially(self, temp_registry):
        """Test that new registry starts empty."""
        models = temp_registry.list_models()
        assert len(models) == 0

    def test_get_registry_info(self, temp_registry):
        """Test getting basic registry information."""
        info = temp_registry.get_registry_info()
        assert "version" in info
        assert "model_count" in info
        assert info["model_count"] == 0


class TestLocalModelRegistryInstallation:
    """Test model installation functionality."""

    @pytest.fixture
    def temp_registry(self):
        """Create temporary registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            yield registry

    @pytest.fixture
    def mock_model_io(self):
        """Create mock ModelIOManager for testing."""
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock:
            mock_instance = Mock()
            mock.return_value = mock_instance
            # Mock validate_model to return CompleteModelValidation object
            mock_instance.validate_model.return_value = CompleteModelValidation(
                name="test_model",
                version="1.0.0",
                type="classification", 
                description="Test model for unit testing",
                is_complete_model=False,
                components_found={},
                missing_components=["umap", "hdbscan", "prediction"],
                validation_errors=[],
                configuration_hash="test_config_hash",
                content_hash="test_content_hash"
            )
            # Mock install_model to simulate successful installation
            mock_instance.install_model.return_value = "model_12345"
            yield mock_instance

    def test_install_model_success(self, temp_registry, mock_model_io):
        """Test successful model installation."""
        with tempfile.NamedTemporaryFile(suffix='.zip') as model_file:
            model_path = Path(model_file.name)
            
            result = temp_registry.install_model(model_path, model_name="custom_name")
            
            # Verify model was validated and installed
            mock_model_io.validate_model.assert_called_once_with(model_path)
            mock_model_io.install_model.assert_called_once()
            
            assert result["status"] == "success"
            assert result["model_id"] == "model_12345"
            assert result["name"] == "custom_name"

    def test_install_model_without_name(self, temp_registry, mock_model_io):
        """Test model installation using manifest name."""
        with tempfile.NamedTemporaryFile(suffix='.zip') as model_file:
            model_path = Path(model_file.name)
            
            result = temp_registry.install_model(model_path)
            
            assert result["status"] == "success"
            assert result["name"] == "test_model"  # From mock manifest

    def test_install_model_validation_failure(self, temp_registry):
        """Test model installation with validation failure."""
        with patch('emuses.tools.local_model_registry.ModelIOManager') as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance
            mock_instance.validate_model.side_effect = ValueError("Invalid model format")
            
            with tempfile.NamedTemporaryFile(suffix='.zip') as model_file:
                model_path = Path(model_file.name)
                
                result = temp_registry.install_model(model_path)
                
                assert result["status"] == "error"
                assert "Invalid model format" in result["message"]

    def test_install_model_updates_index(self, temp_registry, mock_model_io):
        """Test that model installation updates registry index."""
        with tempfile.NamedTemporaryFile(suffix='.zip') as model_file:
            model_path = Path(model_file.name)
            
            # Install model
            result = temp_registry.install_model(model_path, model_name="indexed_model")
            
            # Verify model appears in listing
            models = temp_registry.list_models()
            assert len(models) == 1
            assert models[0]["name"] == "indexed_model"
            assert models[0]["model_id"] == "model_12345"


class TestLocalModelRegistryIndexManagement:
    """Test registry index management functionality."""

    @pytest.fixture
    def temp_registry(self):
        """Create temporary registry for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            yield registry

    def test_index_corruption_recovery(self, temp_registry):
        """Test recovery from corrupted index file."""
        # Corrupt the index file
        with open(temp_registry.index_path, 'w') as f:
            f.write("invalid json{")
        
        # Registry should recover gracefully
        models = temp_registry.list_models()
        assert models == []
        
        info = temp_registry.get_registry_info()
        assert info["model_count"] == 0

    def test_index_backup_and_restore(self, temp_registry):
        """Test index backup and restoration functionality."""
        # Create backup
        backup_created = temp_registry.backup_index()
        assert backup_created is True
        
        # Verify backup file exists
        backup_files = list(temp_registry.registry_path.glob("registry.json.backup.*"))
        assert len(backup_files) > 0

    def test_index_validation(self, temp_registry):
        """Test index validation functionality."""
        # Test with valid index
        is_valid, issues = temp_registry.validate_index()
        assert is_valid is True
        assert len(issues) == 0

    def test_index_repair(self, temp_registry):
        """Test index repair functionality."""
        # Add invalid entry to index
        index = temp_registry._load_index()
        index["models"]["invalid_model"] = {"name": "broken", "model_id": "invalid"}
        temp_registry._save_index(index)
        
        # Repair index
        repaired = temp_registry.repair_index()
        assert "removed" in repaired or "validated" in repaired


class TestLocalModelRegistryDiscovery:
    """Test model discovery and filtering functionality."""

    @pytest.fixture
    def temp_registry_with_models(self):
        """Create temporary registry with sample models for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            
            # Add sample models to index
            index = registry._load_index()
            index["models"]["model_1"] = {
                "model_id": "model_1",
                "name": "fmri_classifier",
                "version": "1.0.0",
                "type": "classification",
                "tags": ["fMRI", "brain", "classification"],
                "description": "fMRI classification model",
                "installed_at": "2025-01-01T10:00:00"
            }
            index["models"]["model_2"] = {
                "model_id": "model_2", 
                "name": "eeg_detector",
                "version": "2.1.0",
                "type": "detection",
                "tags": ["EEG", "brain", "detection"],
                "description": "EEG anomaly detection model",
                "installed_at": "2025-01-02T11:00:00"
            }
            index["models"]["model_3"] = {
                "model_id": "model_3",
                "name": "pet_segmentation", 
                "version": "1.5.0",
                "type": "segmentation",
                "tags": ["PET", "brain", "segmentation"],
                "description": "PET scan segmentation model",
                "installed_at": "2025-01-03T12:00:00"
            }
            registry._save_index(index)
            yield registry

    def test_list_models_no_filters(self, temp_registry_with_models):
        """Test listing all models without filters."""
        models = temp_registry_with_models.list_models()
        assert len(models) == 3
        model_names = [m["name"] for m in models]
        assert "fmri_classifier" in model_names
        assert "eeg_detector" in model_names
        assert "pet_segmentation" in model_names

    def test_list_models_with_type_filter(self, temp_registry_with_models):
        """Test listing models filtered by type."""
        filters = {"type": "classification"}
        models = temp_registry_with_models.list_models(filters)
        assert len(models) == 1
        assert models[0]["name"] == "fmri_classifier"

    def test_list_models_with_tag_filter(self, temp_registry_with_models):
        """Test listing models filtered by tags.""" 
        filters = {"tags": ["fMRI"]}
        models = temp_registry_with_models.list_models(filters)
        assert len(models) == 1
        assert models[0]["name"] == "fmri_classifier"

    def test_list_models_with_multiple_filters(self, temp_registry_with_models):
        """Test listing models with multiple filters."""
        filters = {"type": "detection", "tags": ["brain"]}
        models = temp_registry_with_models.list_models(filters)
        assert len(models) == 1
        assert models[0]["name"] == "eeg_detector"

    def test_get_model_info_success(self, temp_registry_with_models):
        """Test getting detailed model information."""
        model_info = temp_registry_with_models.get_model_info("model_1")
        assert model_info is not None
        assert model_info["name"] == "fmri_classifier"
        assert model_info["version"] == "1.0.0"
        assert "fMRI" in model_info["tags"]

    def test_get_model_info_not_found(self, temp_registry_with_models):
        """Test getting info for non-existent model."""
        model_info = temp_registry_with_models.get_model_info("nonexistent")
        assert model_info is None

    def test_search_models_by_name(self, temp_registry_with_models):
        """Test searching models by name pattern."""
        results = temp_registry_with_models.search_models("fmri")
        assert len(results) == 1
        assert results[0]["name"] == "fmri_classifier"

    def test_search_models_by_description(self, temp_registry_with_models):
        """Test searching models by description content."""
        results = temp_registry_with_models.search_models("segmentation")
        assert len(results) == 1
        assert results[0]["name"] == "pet_segmentation"

    def test_search_models_case_insensitive(self, temp_registry_with_models):
        """Test case-insensitive model search."""
        results = temp_registry_with_models.search_models("EEG")
        assert len(results) == 1
        assert results[0]["name"] == "eeg_detector"


class TestLocalModelRegistryManagement:
    """Test model management operations like removal and maintenance."""

    @pytest.fixture
    def temp_registry_with_models(self):
        """Create temporary registry with sample models for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            registry_path = Path(temp_dir) / "test_registry"
            registry = LocalModelRegistry(registry_path=registry_path)
            
            # Add sample models to index and create directories
            index = registry._load_index()
            for i, model_id in enumerate(["model_1", "model_2", "model_3"]):
                index["models"][model_id] = {
                    "model_id": model_id,
                    "name": f"test_model_{i+1}",
                    "version": "1.0.0",
                    "type": "classification",
                    "description": f"Test model {i+1}",
                    "installed_at": f"2025-01-0{i+1}T10:00:00"
                }
                # Create model directory
                model_dir = registry.models_path / model_id
                model_dir.mkdir(parents=True, exist_ok=True)
                (model_dir / "manifest.json").write_text('{"test": true}')
            
            registry._save_index(index)
            yield registry

    def test_remove_model_success(self, temp_registry_with_models):
        """Test successful model removal."""
        result = temp_registry_with_models.remove_model("model_1")
        
        assert result["status"] == "success"
        assert result["model_id"] == "model_1"
        
        # Verify model is removed from index
        models = temp_registry_with_models.list_models()
        model_ids = [m["model_id"] for m in models]
        assert "model_1" not in model_ids
        assert len(models) == 2

    def test_remove_model_not_found(self, temp_registry_with_models):
        """Test removing non-existent model."""
        result = temp_registry_with_models.remove_model("nonexistent")
        
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_remove_model_filesystem_cleanup(self, temp_registry_with_models):
        """Test that model files are cleaned up."""
        model_dir = temp_registry_with_models.models_path / "model_1"
        assert model_dir.exists()
        
        result = temp_registry_with_models.remove_model("model_1")
        
        assert result["status"] == "success"
        assert not model_dir.exists()

    def test_cleanup_orphaned_models(self, temp_registry_with_models):
        """Test cleanup of orphaned model directories."""
        # Create orphaned directory (not in index)
        orphaned_dir = temp_registry_with_models.models_path / "orphaned_model"
        orphaned_dir.mkdir()
        (orphaned_dir / "test.txt").write_text("orphaned")
        
        result = temp_registry_with_models.cleanup_orphaned_models()
        
        assert result["removed_directories"] >= 1
        assert not orphaned_dir.exists()

    def test_cleanup_orphaned_models_preserves_valid(self, temp_registry_with_models):
        """Test that cleanup preserves valid model directories."""
        valid_dir = temp_registry_with_models.models_path / "model_1"
        assert valid_dir.exists()
        
        result = temp_registry_with_models.cleanup_orphaned_models()
        
        # Valid directory should still exist
        assert valid_dir.exists()

    def test_get_registry_stats(self, temp_registry_with_models):
        """Test getting detailed registry statistics."""
        stats = temp_registry_with_models.get_registry_stats()
        
        assert stats["total_models"] == 3
        assert stats["model_types"]["classification"] == 3
        assert "storage_usage" in stats
        assert "newest_model" in stats
        assert "oldest_model" in stats