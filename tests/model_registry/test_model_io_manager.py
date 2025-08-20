"""
Tests for ModelIOManager missing methods - validate_model and install_model.

This test file focuses on the critical infrastructure methods that are currently missing
but required by LocalModelRegistry for model installation workflows.
"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from emuses.tools.model_io import ModelIOManager


class TestModelIOManagerMissingMethods:
    """Test the missing methods required by LocalModelRegistry."""

    @pytest.fixture
    def temp_model_dir(self):
        """Create a temporary directory with a mock model."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create a mock model directory structure
        model_dir = temp_dir / "test_model"
        model_dir.mkdir()
        
        # Create model manifest
        manifest_data = {
            "name": "test_model", 
            "version": "1.0.0",
            "model_type": "sklearn_pipeline",
            "description": "Test model for validation",
            "created_at": datetime.now(timezone.utc).isoformat() + "Z"
        }
        
        with open(model_dir / "model_manifest.json", 'w') as f:
            json.dump(manifest_data, f)
        
        # Create a mock model file
        mock_model_file = model_dir / "model.joblib"
        mock_model_file.write_text("mock model data")
        
        yield model_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def manager(self):
        """Create ModelIOManager instance."""
        temp_dir = Path(tempfile.mkdtemp())
        manager = ModelIOManager(temp_dir)
        yield manager
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_model_with_manifest(self, manager, temp_model_dir):
        """Test validate_model method with existing manifest."""
        result = manager.validate_model(temp_model_dir)
        
        assert result is not None
        assert result["name"] == "test_model"
        assert result["version"] == "1.0.0" 
        assert result["type"] == "sklearn_pipeline"
        assert result["description"] == "Test model for validation"

    def test_validate_model_nonexistent_path(self, manager):
        """Test validate_model with non-existent path."""
        with pytest.raises(FileNotFoundError, match="Model path does not exist"):
            manager.validate_model(Path("/non/existent/path"))

    def test_validate_model_invalid_manifest(self, manager):
        """Test validate_model with invalid manifest structure."""
        temp_dir = Path(tempfile.mkdtemp())
        model_dir = temp_dir / "invalid_model"
        model_dir.mkdir(parents=True)
        
        # Create invalid manifest
        with open(model_dir / "model_manifest.json", 'w') as f:
            json.dump({"incomplete": "manifest"}, f)
            
        try:
            with pytest.raises(ValueError, match="Invalid manifest structure"):
                manager.validate_model(model_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_model_generate_manifest(self, manager):
        """Test validate_model generates manifest from directory structure."""
        temp_dir = Path(tempfile.mkdtemp())
        model_dir = temp_dir / "no_manifest_model"
        model_dir.mkdir(parents=True)
        
        # Create model files without manifest
        (model_dir / "model.joblib").write_text("model data")
        (model_dir / "scaler.pkl").write_text("scaler data")
        
        try:
            result = manager.validate_model(model_dir)
            
            assert result is not None
            assert result["name"] == "no_manifest_model"
            assert result["version"] == "1.0.0"
            assert result["type"] == "unknown"  # No files to determine type
            assert "Model from no_manifest_model" in result["description"]
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_install_model_success(self, manager, temp_model_dir):
        """Test successful model installation."""
        destination = manager.base_path / "installed"
        
        model_id = manager.install_model(temp_model_dir, destination)
        
        assert model_id is not None
        assert model_id.startswith("test_model_")
        
        # Check installed structure
        installed_path = destination / model_id
        assert installed_path.exists()
        assert (installed_path / "model_manifest.json").exists()
        assert (installed_path / "model.joblib").exists()

    def test_install_model_custom_name(self, manager, temp_model_dir):
        """Test model installation with custom name."""
        destination = manager.base_path / "installed"
        
        model_id = manager.install_model(temp_model_dir, destination, name="custom_model")
        
        assert model_id.startswith("custom_model_")

    def test_install_model_existing_destination(self, manager, temp_model_dir):
        """Test model installation when destination already exists."""
        destination = manager.base_path / "installed"
        
        # First installation
        model_id1 = manager.install_model(temp_model_dir, destination)
        
        # Create the same directory to simulate collision
        (destination / model_id1).mkdir(parents=True, exist_ok=True)
        
        # Second installation should handle collision
        model_id2 = manager.install_model(temp_model_dir, destination)
        
        # Should have different model IDs
        assert model_id1 != model_id2

    def test_install_model_invalid_source(self, manager):
        """Test install_model with invalid source."""
        destination = manager.base_path / "installed"
        
        with pytest.raises(FileNotFoundError):
            manager.install_model(Path("/non/existent"), destination)