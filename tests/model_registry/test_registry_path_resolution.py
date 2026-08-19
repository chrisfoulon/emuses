"""Test registry path resolution service.

This module tests the core registry functionality - simple path lookup from model ID to EMUSES folder.
Following architectural guardrails: Registry as lookup service ONLY, no model abstractions.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from emuses.tools.local_model_registry import LocalModelRegistry
from tests.conftest import EXTERNAL_DATA_ROOT


class TestRegistryPathResolution:
    """Test core registry path resolution functionality."""

    def test_get_model_path_existing_model(self, tmp_path):
        """Test path resolution for registered model."""
        # Create temporary registry
        registry = LocalModelRegistry(registry_path=tmp_path / "test_registry")
        
        # Create test model directory
        test_model_dir = tmp_path / "test_model_folder"
        test_model_dir.mkdir()
        
        # Create minimal EMUSES structure for testing
        (test_model_dir / "model_manifest.json").write_text('{"name": "test_model"}')
        (test_model_dir / "best_umap_model.joblib").touch()
        (test_model_dir / "hdbscan_model.joblib").touch()
        target_dir = test_model_dir / "target_0"
        target_dir.mkdir()
        (target_dir / "model_manifest.json").write_text('{"target": "0"}')
        (target_dir / "best_pipeline_fold0.joblib").touch()
        
        # Register the model using install_model
        result = registry.install_model(test_model_dir, model_name="test_model_123")
        model_id = result["model_id"]
        
        # Test path resolution
        resolved_path = registry.get_model_path(model_id)
        
        # Verify path is resolved correctly
        assert resolved_path.exists()
        assert resolved_path.name == "test_model_folder"
        assert isinstance(resolved_path, Path)

    def test_get_model_path_nonexistent_model(self, tmp_path):
        """Test error handling for non-existent model ID."""
        registry = LocalModelRegistry(registry_path=tmp_path / "test_registry")
        
        with pytest.raises(KeyError, match="Model not found: nonexistent_id"):
            registry.get_model_path("nonexistent_id")

    def test_get_model_path_integration_with_real_folder(self, tmp_path):
        """Test registry path resolution with real EMUSES folder (critical integration)."""
        # Real EMUSES model folder, located outside the repo. Configured via
        # EMUSES_TEST_DATA_ROOT rather than hardcoded to one machine's layout.
        if EXTERNAL_DATA_ROOT is None:
            pytest.skip("EMUSES_TEST_DATA_ROOT is not set; integration test skipped")

        real_folder = EXTERNAL_DATA_ROOT / "HCP_psy" / "model_registry_final"
        if not real_folder.exists():
            pytest.skip(f"Real EMUSES folder not available: {real_folder}")
            
        # Create temporary registry
        registry = LocalModelRegistry(registry_path=tmp_path / "test_registry")
        
        # Register the real EMUSES folder
        result = registry.install_model(real_folder, model_name="integration_test_model")
        model_id = result["model_id"]
        
        # Test registry → path resolution integration
        resolved_path = registry.get_model_path(model_id)
        
        # Critical validation: registry correctly resolves to original folder
        assert resolved_path == real_folder
        assert resolved_path.exists()
        
        # Verify it's a complete EMUSES folder
        assert (resolved_path / "model_manifest.json").exists()
        assert len(list(resolved_path.glob("*umap*.joblib"))) > 0
        assert len(list(resolved_path.glob("*hdbscan*.joblib"))) > 0
        assert len(list(resolved_path.glob("target_*"))) > 0
        
        # This proves the registry → InferenceStage integration point works:
        # InferenceStage expects a folder path, registry provides folder path
        from emuses.pipelines.inference_stage import InferenceStage
        
        # Create minimal config just for initialization test
        class MockConfig:
            def __init__(self, model_path):
                self.model_path = model_path
                self.data_path = Path("/tmp")  
                self.output_path = Path("/tmp")
                self.validate_mode = False
        
        # Test InferenceStage can be initialized with resolved path
        mock_config = MockConfig(resolved_path)
        inference_stage = InferenceStage(mock_config)
        assert inference_stage.model_path == resolved_path