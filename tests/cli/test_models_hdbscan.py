"""
Test HDBSCAN model registration and CLI integration.

This test verifies that HDBSCAN models can be installed, registered,
and managed through the CLI and model registry system.
"""

import tempfile
import json
from pathlib import Path
import pytest
from unittest.mock import Mock, patch
import joblib

from emuses.tools.local_model_registry import LocalModelRegistry


class TestHDBSCANModelRegistration:
    """Test HDBSCAN model registration capabilities."""
    
    @pytest.fixture
    def temp_hdbscan_model(self):
        """Create a temporary HDBSCAN model for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        model_dir = temp_dir / "hdbscan_model"
        model_dir.mkdir()
        
        # Create mock HDBSCAN model
        try:
            import hdbscan
            # Create a simple HDBSCAN clusterer
            clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=3)
            
            # Create some dummy data and fit the model
            import numpy as np
            dummy_data = np.random.random((100, 10))
            clusterer.fit(dummy_data)
            
            # Save the model
            model_file = model_dir / "hdbscan_model.joblib"
            joblib.dump(clusterer, model_file)
        except ImportError:
            # If hdbscan is not available, create a mock model file
            model_file = model_dir / "hdbscan_model.joblib"
            mock_clusterer = {"model_type": "hdbscan", "fitted": True}
            joblib.dump(mock_clusterer, model_file)
        
        # Create manifest
        manifest = {
            "name": "test_hdbscan_model",
            "version": "1.0.0",
            "model_type": "hdbscan",
            "description": "Test HDBSCAN clustering model",
            "created_at": "2025-01-01T00:00:00Z"
        }
        with open(model_dir / "model_manifest.json", 'w') as f:
            json.dump(manifest, f)
        
        yield model_dir
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def temp_registry(self):
        """Create temporary model registry for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        registry = LocalModelRegistry(registry_path=temp_dir)
        yield registry
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_hdbscan_model_installation(self, temp_registry, temp_hdbscan_model):
        """Test that HDBSCAN models can be installed in the registry."""
        result = temp_registry.install_model(temp_hdbscan_model)
        
        assert result["status"] == "success"
        assert "model_id" in result
        assert "name" in result
        
    def test_hdbscan_model_listing(self, temp_registry, temp_hdbscan_model):
        """Test that installed HDBSCAN models appear in model listings."""
        # Install the model first
        result = temp_registry.install_model(temp_hdbscan_model)
        assert result["status"] == "success"
        
        # List all models
        models = temp_registry.list_models()
        assert len(models) >= 1
        
        # Check that HDBSCAN model is in the list
        hdbscan_models = [m for m in models if m.get('type') == 'hdbscan']
        assert len(hdbscan_models) >= 1
    
    def test_hdbscan_model_info_retrieval(self, temp_registry, temp_hdbscan_model):
        """Test that HDBSCAN model information can be retrieved."""
        # Install the model first
        result = temp_registry.install_model(temp_hdbscan_model)
        model_id = result["model_id"]
        
        # Get model info
        model_info = temp_registry.get_model_info(model_id)
        assert model_info is not None
        assert model_info["model_id"] == model_id
        assert model_info["type"] == "hdbscan"
    
    def test_hdbscan_cli_installation_command(self, temp_hdbscan_model):
        """Test HDBSCAN model installation through CLI command."""
        from emuses.cli.models_commands import install
        from typer.testing import CliRunner
        
        # Mock the console output to avoid side effects
        with patch('emuses.cli.models_commands.console'):
            # This should not raise an exception
            try:
                install(temp_hdbscan_model)
            except SystemExit as e:
                # CLI may exit with code 0 on success
                if e.code != 0:
                    pytest.fail(f"CLI installation failed with exit code {e.code}")
    
    def test_hdbscan_model_type_validation(self, temp_registry):
        """Test that HDBSCAN is recognized as a valid model type."""
        # Create a directory with HDBSCAN model file but no manifest
        temp_dir = Path(tempfile.mkdtemp())
        model_dir = temp_dir / "no_manifest_hdbscan"
        model_dir.mkdir()
        
        # Create a mock HDBSCAN model file
        model_file = model_dir / "model.joblib"
        mock_clusterer = {"model_type": "hdbscan", "fitted": True}
        joblib.dump(mock_clusterer, model_file)
        
        try:
            # This should work - the registry should be able to handle HDBSCAN models
            result = temp_registry.install_model(model_dir, name="test_hdbscan")
            assert result["status"] == "success"
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)