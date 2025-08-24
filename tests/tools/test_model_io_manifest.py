"""
Tests for Model I/O Manager manifest functionality.

Tests the manifest generation, verification, and integrity checking features
added to support inference pipeline with universal model format.
"""

import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import numpy as np
from sklearn.dummy import DummyRegressor

from emuses.tools.model_io import ModelIOManager


class TestModelManifestGeneration:
    """Test manifest generation during model saving."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def model_manager(self, temp_dir):
        """Create ModelIOManager instance."""
        return ModelIOManager(temp_dir)

    @pytest.fixture
    def dummy_model(self):
        """Create a simple model for testing."""
        model = DummyRegressor(strategy="mean")
        X = np.random.rand(10, 5)
        y = np.random.rand(10)
        model.fit(X, y)
        return model

    def test_manifest_generated_on_save(self, model_manager, dummy_model, temp_dir):
        """Test that manifest.json is automatically generated when saving a model."""
        model_path = model_manager.save_model(
            model=dummy_model,
            model_name="test_model",
            model_type="sklearn_regressor",
            description="Test model for manifest generation"
        )
        
        # Check that manifest exists
        manifest_path = temp_dir / "model_manifest.json"
        assert manifest_path.exists(), "Manifest file should be created"
        
        # Load and validate manifest structure
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Validate required sections
        assert "file_integrity" in manifest
        assert "training_context" in manifest
        assert "compatibility" in manifest
        
        # Validate top-level model metadata
        assert manifest["name"] == "test_model"
        assert "version" in manifest
        assert "created_at" in manifest
        assert "emuses_version" in manifest
        assert manifest["description"] == "Test model for manifest generation"

    def test_manifest_file_integrity_section(self, model_manager, dummy_model, temp_dir):
        """Test that file integrity section contains SHA-256 hashes."""
        model_path = model_manager.save_model(
            model=dummy_model,
            model_name="test_model",
            model_type="sklearn_regressor"
        )
        
        manifest_path = temp_dir / "model_manifest.json"
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        file_integrity = manifest["file_integrity"]
        model_filename = model_path.name
        
        # Check that model file is tracked
        assert model_filename in file_integrity
        
        file_info = file_integrity[model_filename]
        assert "sha256" in file_info
        assert "size" in file_info
        assert "modified" in file_info
        
        # Verify SHA-256 hash is correct
        with open(model_path, 'rb') as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        assert file_info["sha256"] == actual_hash

    def test_manifest_version_increment(self, model_manager, dummy_model):
        """Test that version numbers auto-increment for same model name."""
        # Save first model
        model_manager.save_model(
            model=dummy_model,
            model_name="versioned_model",
            model_type="sklearn_regressor"
        )
        
        # Save second model with same name
        model_manager.save_model(
            model=dummy_model,
            model_name="versioned_model", 
            model_type="sklearn_regressor"
        )
        
        # Check that versions incremented
        manifest_path = model_manager.base_path / "model_manifest.json"
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Should be version 1.0.1 (second save)
        version = manifest["version"]
        assert version == "1.0.1"


class TestModelManifestVerification:
    """Test manifest verification during model loading."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def model_manager(self, temp_dir):
        return ModelIOManager(temp_dir)

    @pytest.fixture
    def dummy_model(self):
        model = DummyRegressor(strategy="mean")
        X = np.random.rand(10, 5)
        y = np.random.rand(10)
        model.fit(X, y)
        return model

    def test_integrity_verification_success(self, model_manager, dummy_model):
        """Test successful integrity verification when files are unchanged."""
        # Save model (generates manifest)
        model_path = model_manager.save_model(
            model=dummy_model,
            model_name="integrity_test",
            model_type="sklearn_regressor"
        )
        
        # Load with integrity verification
        artifact = model_manager.load_model(
            model_name="integrity_test",
            verify_integrity=True
        )
        
        assert artifact is not None
        assert artifact.model is not None

    def test_integrity_verification_detects_modification(self, model_manager, dummy_model, temp_dir):
        """Test that integrity verification detects file modifications."""
        # Save model
        model_path = model_manager.save_model(
            model=dummy_model,
            model_name="modified_test",
            model_type="sklearn_regressor"
        )
        
        # Modify the model file
        with open(model_path, 'ab') as f:
            f.write(b"corrupted_data")
        
        # Loading with verification should detect corruption
        with pytest.raises(ValueError, match="integrity verification failed"):
            model_manager.load_model(
                model_name="modified_test",
                verify_integrity=True
            )

    def test_load_without_verification_works_with_modified_file(self, model_manager, dummy_model):
        """Test that loading without verification works even with modified files."""
        # Save model
        model_path = model_manager.save_model(
            model=dummy_model,
            model_name="no_verify_test",
            model_type="sklearn_regressor"
        )
        
        # Modify the model file
        with open(model_path, 'ab') as f:
            f.write(b"corrupted_data")
        
        # Loading without verification should still work (backwards compatibility)
        artifact = model_manager.load_model(
            model_name="no_verify_test",
            verify_integrity=False
        )
        
        # Note: This will likely fail at joblib.load() due to corruption,
        # but that's expected behavior - we're testing the verification flag
        # For this test, we just want to ensure it doesn't fail at manifest check


class TestBackwardCompatibility:
    """Test backward compatibility with existing models without manifests."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def model_manager(self, temp_dir):
        return ModelIOManager(temp_dir)

    def test_load_legacy_model_without_manifest(self, model_manager, temp_dir):
        """Test loading models saved before manifest implementation."""
        # Create a legacy model file (no manifest)
        dummy_model = DummyRegressor()
        legacy_path = temp_dir / "legacy_model_v1.0.0.joblib"
        
        import joblib
        joblib.dump(dummy_model, legacy_path)
        
        # Should load successfully without manifest
        artifact = model_manager.load_model(
            model_name="legacy_model",
            verify_integrity=False  # Can't verify without manifest
        )
        
        assert artifact is not None
        assert artifact.model is not None

    def test_legacy_model_integrity_verification_skipped(self, model_manager, temp_dir):
        """Test that integrity verification is gracefully skipped for legacy models."""
        # Create legacy model
        dummy_model = DummyRegressor()
        legacy_path = temp_dir / "legacy_model_v1.0.0.joblib"
        
        import joblib
        joblib.dump(dummy_model, legacy_path)
        
        # Should load successfully and log warning about missing manifest
        artifact = model_manager.load_model(
            model_name="legacy_model",
            verify_integrity=True  # Requested but should be skipped
        )
        
        assert artifact is not None
        # Should succeed with warning logged (not tested here, but expected behavior)


class TestManifestUtilities:
    """Test utility functions for manifest management."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def model_manager(self, temp_dir):
        return ModelIOManager(temp_dir)

    def test_get_manifest_info(self, model_manager, temp_dir):
        """Test retrieving manifest information without loading model."""
        # Save a model first
        dummy_model = DummyRegressor()
        model_manager.save_model(
            model=dummy_model,
            model_name="info_test",
            model_type="sklearn_regressor",
            description="Test model for info retrieval"
        )
        
        # Get manifest info
        manifest_info = model_manager.get_manifest_info("info_test")
        
        assert manifest_info is not None
        assert manifest_info["model_info"]["name"] == "info_test"
        assert manifest_info["model_info"]["description"] == "Test model for info retrieval"

    def test_verify_model_integrity_standalone(self, model_manager, temp_dir):
        """Test standalone integrity verification function."""
        # Save a model
        dummy_model = DummyRegressor()
        model_path = model_manager.save_model(
            model=dummy_model,
            model_name="standalone_verify",
            model_type="sklearn_regressor"
        )
        
        # Verify integrity using standalone function
        is_valid = model_manager.verify_model_integrity("standalone_verify")
        assert is_valid is True
        
        # Modify file and test again
        with open(model_path, 'ab') as f:
            f.write(b"corruption")
        
        is_valid = model_manager.verify_model_integrity("standalone_verify")
        assert is_valid is False