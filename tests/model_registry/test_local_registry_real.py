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
    def sklearn_model_dir(self):
        """Create a complete sklearn model directory with all required files."""
        temp_dir = Path(tempfile.mkdtemp())
        model_dir = temp_dir / "sklearn_model"
        model_dir.mkdir()

        # Create a realistic sklearn pipeline
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            # Create and train a simple model
            pipeline = Pipeline([
                ('scaler', StandardScaler()),
                ('classifier', RandomForestClassifier(n_estimators=10, random_state=42))
            ])

            # Generate dummy data and train
            X = np.random.random((100, 10))
            y = np.random.randint(0, 2, 100)
            pipeline.fit(X, y)

            # Save the trained model
            joblib.dump(pipeline, model_dir / "model.joblib")

        except ImportError:
            # If sklearn is not available, create a mock model
            mock_pipeline = {"type": "sklearn_pipeline", "fitted": True}
            joblib.dump(mock_pipeline, model_dir / "model.joblib")

        # Create comprehensive manifest
        manifest = {
            "name": "test_sklearn_model",
            "version": "1.0.0",
            "model_type": "sklearn_pipeline",
            "description": "Test sklearn pipeline for integration testing",
            "created_at": datetime.now(timezone.utc).isoformat() + "Z",
            "framework": "sklearn",
            "tags": ["test", "classification", "pipeline"]
        }

        with open(model_dir / "model_manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)

        # Add additional metadata files
        (model_dir / "training_metrics.json").write_text(json.dumps({
            "accuracy": 0.95,
            "precision": 0.93,
            "recall": 0.94,
            "f1_score": 0.935
        }))

        (model_dir / "feature_info.txt").write_text("Feature names: feature_0, feature_1, ..., feature_9")

        yield model_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def umap_model_dir(self):
        """Create a UMAP model directory."""
        temp_dir = Path(tempfile.mkdtemp())
        model_dir = temp_dir / "umap_model"
        model_dir.mkdir()

        # Create mock UMAP model
        try:
            import umap
            import numpy as np
            # Create a simple UMAP model
            mapper = umap.UMAP(n_neighbors=5, n_components=2, random_state=42)
            X = np.random.random((100, 20))
            mapper.fit(X)
            joblib.dump(mapper, model_dir / "umap_model.pkl")
        except ImportError:
            mock_umap = {"type": "umap", "n_components": 2, "fitted": True}
            joblib.dump(mock_umap, model_dir / "umap_model.pkl")

        # Create manifest
        manifest = {
            "name": "test_umap_model",
            "version": "1.1.0",
            "model_type": "umap",
            "description": "UMAP dimensionality reduction model",
            "created_at": datetime.now(timezone.utc).isoformat() + "Z"
        }

        with open(model_dir / "model_manifest.json", 'w') as f:
            json.dump(manifest, f)

        yield model_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_complete_model_installation_workflow(self, registry, sklearn_model_dir):
        """Test complete end-to-end model installation using real ModelIOManager."""
        # This test verifies the full workflow: validate → install → register
        result = registry.install_model(sklearn_model_dir)
        
        # Verify successful installation
        assert result["status"] == "success"
        assert "model_id" in result
        assert result["name"] == "test_sklearn_model"
        
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
        assert installed_model["name"] == "test_sklearn_model"
        assert installed_model["type"] == "sklearn_pipeline"
        assert installed_model["version"] == "1.0.0"

    def test_model_validation_integration(self, registry, sklearn_model_dir, temp_registry_dir):
        """Test that ModelIOManager validation is properly integrated."""
        # Create ModelIOManager directly and test validation
        model_io = ModelIOManager(temp_registry_dir / "models")
        
        # This should work without errors using the real validate_model method
        manifest = model_io.validate_model(sklearn_model_dir)
        
        assert manifest["name"] == "test_sklearn_model"
        assert manifest["version"] == "1.0.0"
        assert manifest["type"] == "sklearn_pipeline"
        assert manifest["description"] == "Test sklearn pipeline for integration testing"

    def test_model_installation_with_custom_name(self, registry, sklearn_model_dir):
        """Test model installation with custom naming."""
        custom_name = "my_custom_classifier"
        result = registry.install_model(sklearn_model_dir, name=custom_name)
        
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
        
        model_types = [model["type"] for model in models]
        assert "sklearn_pipeline" in model_types
        assert "umap" in model_types

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
            # This should work - ModelIOManager should generate a manifest
            result = registry.install_model(model_dir, name="no_manifest_test")
            assert result["status"] == "success"
            
            # Verify the model was installed with generated metadata
            model_info = registry.get_model_info(result["model_id"])
            assert model_info["name"] == "no_manifest_test"
            assert model_info["version"] == "1.0.0"  # Default version
            
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
        model_types = [model.get("type") for model in all_models]
        assert "sklearn_pipeline" in model_types
        assert "umap" in model_types

    def test_concurrent_model_operations(self, registry, sklearn_model_dir):
        """Test that model operations work correctly when performed in sequence."""
        # Install model
        result = registry.install_model(sklearn_model_dir, name="concurrent_test_1")
        model_id_1 = result["model_id"]
        
        # Install same model again with different name
        result = registry.install_model(sklearn_model_dir, name="concurrent_test_2")
        model_id_2 = result["model_id"]
        
        # Both should exist and be different
        assert model_id_1 != model_id_2
        
        model_1 = registry.get_model_info(model_id_1)
        model_2 = registry.get_model_info(model_id_2)
        
        assert model_1["name"] == "concurrent_test_1"
        assert model_2["name"] == "concurrent_test_2"
        assert model_1["model_id"] != model_2["model_id"]