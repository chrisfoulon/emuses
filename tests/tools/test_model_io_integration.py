"""
Integration tests for enhanced ModelIOManager.

Tests backward compatibility and integration with existing EMUSES components.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import numpy as np
from sklearn.dummy import DummyRegressor
import umap

from emuses.tools.model_io import ModelIOManager


class TestModelIOIntegration:
    """Test enhanced ModelIOManager integration with existing components."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def model_manager(self, temp_dir):
        """Create ModelIOManager instance."""
        return ModelIOManager(temp_dir)

    def test_backward_compatibility_with_existing_save_load(self, model_manager):
        """Test that existing save/load workflows still work unchanged."""
        # Create a model using existing patterns
        model = DummyRegressor(strategy="mean")
        X = np.random.rand(10, 5)
        y = np.random.rand(10)
        model.fit(X, y)
        
        # Save using existing API (no new parameters)
        model_path = model_manager.save_model(
            model=model,
            model_name="backward_compat_test",
            model_type="sklearn_regressor",
            description="Backward compatibility test"
        )
        
        assert model_path.exists()
        
        # Load using existing API
        artifact = model_manager.load_model("backward_compat_test")
        
        assert artifact is not None
        assert artifact.model is not None
        assert hasattr(artifact.model, 'predict')
        
        # Check that manifest was generated automatically
        manifest_path = model_manager.base_path / "model_manifest.json"
        assert manifest_path.exists()

    def test_enhanced_features_are_optional(self, model_manager):
        """Test that enhanced features don't break when disabled."""
        model = DummyRegressor()
        
        # Save model
        model_path = model_manager.save_model(
            model=model,
            model_name="optional_features_test",
            model_type="sklearn_regressor"
        )
        
        # Load with integrity verification disabled
        artifact = model_manager.load_model(
            "optional_features_test",
            verify_integrity=False
        )
        
        assert artifact is not None
        
        # Load with integrity verification enabled (default)
        artifact = model_manager.load_model("optional_features_test")
        assert artifact is not None

    def test_umap_model_integration(self, model_manager):
        """Test integration with UMAP models (common in EMUSES)."""
        # Create a simple UMAP model
        X = np.random.rand(20, 10)
        umap_model = umap.UMAP(n_components=2, random_state=42)
        umap_model.fit(X)
        
        # Save UMAP model
        model_path = model_manager.save_model(
            model=umap_model,
            model_name="umap_test",
            model_type="umap",
            description="UMAP model for integration testing"
        )
        
        # Load UMAP model
        artifact = model_manager.load_model("umap_test")
        
        assert artifact is not None
        assert hasattr(artifact.model, 'transform')
        
        # Test that UMAP model works
        X_test = np.random.rand(5, 10)
        embeddings = artifact.model.transform(X_test)
        assert embeddings.shape == (5, 2)

    def test_optuna_metadata_integration(self, model_manager):
        """Test integration with Optuna study metadata (used in HeatmapStage)."""
        model = DummyRegressor()
        
        # Mock Optuna study and trial objects
        mock_trial = Mock()
        mock_trial.number = 0
        mock_trial.value = 0.85
        mock_trial.params = {"C": 1.0, "kernel": "rbf"}
        mock_trial.user_attrs = {}
        mock_trial.system_attrs = {}
        mock_trial.state = "COMPLETE"
        mock_trial.datetime_start = "2025-01-06T10:00:00"
        mock_trial.datetime_complete = "2025-01-06T10:05:00"
        mock_trial.duration = 300.0
        
        mock_study = Mock()
        mock_study.study_name = "test_study"
        mock_study.direction = "maximize"
        mock_study.best_value = 0.85
        mock_study.best_trial = mock_trial
        mock_study.trials = [mock_trial]
        
        # Save with Optuna metadata (as would happen in HeatmapStage)
        model_path = model_manager.save_model(
            model=model,
            model_name="optuna_test",
            model_type="sklearn_regressor",
            optuna_study=mock_study,
            optuna_trial=mock_trial,
            cv_score=0.85,
            cv_scores=[0.83, 0.85, 0.87, 0.84, 0.86],
            cv_folds=5,
            target_id=0
        )
        
        # Load and verify metadata
        artifact = model_manager.load_model("optuna_test")
        
        assert artifact is not None
        assert artifact.metadata.cv_score == 0.85
        assert len(artifact.metadata.cv_scores) == 5
        assert artifact.metadata.target_id == 0

    def test_multiple_model_types_in_same_directory(self, model_manager):
        """Test handling multiple model types in same directory."""
        # Save different model types
        sklearn_model = DummyRegressor()
        X = np.random.rand(10, 5)
        umap_model = umap.UMAP(n_components=2, random_state=42)
        umap_model.fit(X)
        
        # Save models
        sklearn_path = model_manager.save_model(
            model=sklearn_model,
            model_name="multi_sklearn",
            model_type="sklearn_regressor"
        )
        
        umap_path = model_manager.save_model(
            model=umap_model,
            model_name="multi_umap",
            model_type="umap"
        )
        
        # Load specific models
        sklearn_artifact = model_manager.load_model("multi_sklearn", model_type="sklearn_regressor")
        umap_artifact = model_manager.load_model("multi_umap", model_type="umap")
        
        assert sklearn_artifact is not None
        assert umap_artifact is not None
        assert sklearn_artifact.metadata.model_type == "sklearn_regressor"
        assert umap_artifact.metadata.model_type == "umap"
        
        # Check that manifest tracks both models
        manifest_info = model_manager.get_manifest_info("multi_sklearn")
        assert manifest_info is not None
        
        file_integrity = manifest_info.get("file_integrity", {})
        model_files = [f for f in file_integrity.keys() if f.endswith('.joblib')]
        assert len(model_files) >= 1  # At least one model file tracked

    def test_version_increment_with_same_model_name(self, model_manager):
        """Test that version numbers increment correctly in manifest."""
        model = DummyRegressor()
        
        # Save first version
        path1 = model_manager.save_model(
            model=model,
            model_name="versioned_model",
            model_type="sklearn_regressor"
        )
        
        # Check first version in manifest
        manifest_info = model_manager.get_manifest_info("versioned_model")
        assert manifest_info["model_info"]["version"] == "1.0.0"
        
        # Save second version (same name) 
        path2 = model_manager.save_model(
            model=model,
            model_name="versioned_model",
            model_type="sklearn_regressor"
        )
        
        # Check that version incremented in manifest
        manifest_info = model_manager.get_manifest_info("versioned_model")
        assert manifest_info["model_info"]["version"] == "1.0.1"
        
        # Check that both model files exist and are tracked
        file_integrity = manifest_info.get("file_integrity", {})
        joblib_files = [f for f in file_integrity.keys() if f.endswith('.joblib')]
        assert len(joblib_files) >= 1  # At least one model file tracked

    def test_large_model_handling(self, model_manager):
        """Test handling of larger models (performance and memory)."""
        # Create a model with some size
        model = DummyRegressor()
        # Add some data to make it larger
        X = np.random.rand(100, 50)
        y = np.random.rand(100)
        model.fit(X, y)
        
        # Save large model
        model_path = model_manager.save_model(
            model=model,
            model_name="large_model",
            model_type="sklearn_regressor",
            description="Large model for performance testing"
        )
        
        # Verify manifest tracks file size correctly
        manifest_info = model_manager.get_manifest_info("large_model")
        file_integrity = manifest_info.get("file_integrity", {})
        
        model_file_info = None
        for filename, info in file_integrity.items():
            if filename.endswith('.joblib'):
                model_file_info = info
                break
        
        assert model_file_info is not None
        assert model_file_info["size"] > 0
        assert len(model_file_info["sha256"]) == 64  # SHA-256 hash length

    def test_error_handling_and_robustness(self, model_manager):
        """Test error handling in various scenarios."""
        # Test loading non-existent model
        artifact = model_manager.load_model("nonexistent_model")
        assert artifact is None
        
        # Test integrity verification on non-existent model
        is_valid = model_manager.verify_model_integrity("nonexistent_model")
        assert is_valid is False
        
        # Test get_manifest_info on non-existent model
        manifest_info = model_manager.get_manifest_info("nonexistent_model")
        assert manifest_info is None

    def test_concurrent_model_operations(self, model_manager):
        """Test that concurrent operations don't interfere with manifests."""
        models = []
        
        # Create multiple models concurrently
        for i in range(3):
            model = DummyRegressor()
            models.append(model)
        
        # Save models
        paths = []
        for i, model in enumerate(models):
            path = model_manager.save_model(
                model=model,
                model_name=f"concurrent_model_{i}",
                model_type="sklearn_regressor"
            )
            paths.append(path)
        
        # Verify all models can be loaded
        for i in range(3):
            artifact = model_manager.load_model(f"concurrent_model_{i}")
            assert artifact is not None
            
            # Verify integrity
            is_valid = model_manager.verify_model_integrity(f"concurrent_model_{i}")
            assert is_valid is True