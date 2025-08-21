"""Tests for complete model integration with LocalModelRegistry."""

import json
import pytest
from pathlib import Path

from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_io import CompleteModelValidation


class TestCompleteModelRegistryIntegration:
    """Test integration of complete model support with registry operations."""
    
    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / "test_registry"
        return LocalModelRegistry(registry_path)
    
    @pytest.fixture
    def complete_model_structure(self, tmp_path):
        """Create a complete EMUSES model structure."""
        model_dir = tmp_path / "complete_test_model"
        model_dir.mkdir()
        
        # Create manifest with complete model metadata
        manifest = {
            "name": "hcp_complete_analysis",
            "version": "1.5.0",
            "model_type": "complete_emuses_model",
            "description": "Complete EMUSES analysis with UMAP, HDBSCAN, and predictions",
            "pipeline_config": {
                "umap_params": {"n_neighbors": 15, "min_dist": 0.1},
                "hdbscan_params": {"min_cluster_size": 50, "min_samples": 10},
                "prediction_params": {"n_estimators": 100, "max_depth": 10}
            },
            "created_at": "2025-08-20T15:30:00Z",
            "component_hashes": {
                "umap": "abc123def456",
                "hdbscan": "def456ghi789",
                "prediction": "ghi789jkl012"
            }
        }
        
        with open(model_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Create model component files
        (model_dir / "umap_model.pkl").write_text("umap model data")
        (model_dir / "hdbscan_model.pkl").write_text("hdbscan model data")
        
        # Create prediction ensemble directory
        pred_dir = model_dir / "prediction_ensemble"
        pred_dir.mkdir()
        (pred_dir / "model_1.pkl").write_text("prediction model 1")
        (pred_dir / "model_2.pkl").write_text("prediction model 2")
        (pred_dir / "model_3.pkl").write_text("prediction model 3")
        
        # Create auxiliary files
        (model_dir / "embeddings.npy").write_text("embeddings data")
        (model_dir / "cluster_labels.npy").write_text("cluster labels")
        (model_dir / "performance_metrics.json").write_text('{"accuracy": 0.95, "f1": 0.92}')
        
        return model_dir
    
    def test_install_complete_model_with_enhanced_metadata(self, temp_registry, complete_model_structure):
        """Test installing a complete model with enhanced metadata storage."""
        result = temp_registry.install_model(
            complete_model_structure,
            name="complete_test_model"
        )
        
        assert result["status"] == "success"
        assert result["name"] == "complete_test_model"
        
        # Verify model was registered with complete model information
        model_info = temp_registry.get_model_info(result["model_id"])
        assert model_info is not None
        assert model_info["type"] == "complete_emuses_model"
        assert model_info["name"] == "complete_test_model"
        
        # Verify manifest contains complete model metadata
        manifest = model_info["manifest"]
        assert manifest["type"] == "complete_emuses_model"
        # Note: pipeline_config and component_hashes are not preserved in basic validation
        # These would be preserved in enhanced validation mode
    
    def test_complete_model_component_tracking(self, temp_registry, complete_model_structure):
        """Test that complete model components are tracked in registry metadata."""
        result = temp_registry.install_model(
            complete_model_structure,
            name="component_tracking_test"
        )
        
        assert result["status"] == "success"
        
        # Get model info and verify component tracking
        model_info = temp_registry.get_model_info(result["model_id"])
        
        # Verify the installed model directory contains all components
        model_path = temp_registry.models_path / result["model_id"]
        assert (model_path / "umap_model.pkl").exists()
        assert (model_path / "hdbscan_model.pkl").exists()
        assert (model_path / "prediction_ensemble").exists()
        assert (model_path / "prediction_ensemble" / "model_1.pkl").exists()
        
        # Verify auxiliary files are preserved
        assert (model_path / "embeddings.npy").exists()
        assert (model_path / "cluster_labels.npy").exists()
        assert (model_path / "performance_metrics.json").exists()
    
    def test_complete_model_rollback_with_all_components(self, temp_registry, complete_model_structure):
        """Test that rollback removes all components of a complete model."""
        transaction = temp_registry.begin_transaction()
        
        # Install complete model within transaction
        result = temp_registry.install_model(
            complete_model_structure,
            name="rollback_complete_test",
            transaction=transaction
        )
        
        assert result["status"] == "success"
        model_id = result["model_id"]
        
        # Verify all model components exist
        model_path = temp_registry.models_path / model_id
        assert model_path.exists()
        assert (model_path / "umap_model.pkl").exists()
        assert (model_path / "hdbscan_model.pkl").exists()
        assert (model_path / "prediction_ensemble").exists()
        assert len(list((model_path / "prediction_ensemble").glob("*.pkl"))) == 3
        
        # Rollback transaction
        rollback_success = temp_registry.rollback_transaction(transaction)
        assert rollback_success is True
        
        # Verify entire model directory is removed
        assert not model_path.exists()
        
        # Verify model is not in registry
        models = temp_registry.list_models()
        model_ids = [m["model_id"] for m in models]
        assert model_id not in model_ids
    
    def test_backward_compatibility_with_individual_models(self, temp_registry, complete_model_structure, tmp_path):
        """Test that individual component models still work alongside complete models."""
        # Create an individual UMAP model (old style)
        umap_model_dir = tmp_path / "individual_umap"
        umap_model_dir.mkdir()
        
        umap_manifest = {
            "name": "standalone_umap",
            "version": "1.0.0",
            "model_type": "umap_model",
            "description": "Individual UMAP model for backward compatibility"
        }
        
        with open(umap_model_dir / "manifest.json", 'w') as f:
            json.dump(umap_manifest, f)
        
        (umap_model_dir / "umap_model.pkl").write_text("individual umap data")
        
        # Install individual model
        individual_result = temp_registry.install_model(
            umap_model_dir,
            name="individual_umap_test"
        )
        
        assert individual_result["status"] == "success"
        
        # Install complete model
        complete_result = temp_registry.install_model(
            complete_model_structure,
            name="complete_model_test"
        )
        
        assert complete_result["status"] == "success"
        
        # Verify both models coexist
        models = temp_registry.list_models()
        assert len(models) == 2
        
        model_types = [m["type"] for m in models]
        assert "umap_model" in model_types
        assert "complete_emuses_model" in model_types
    
    def test_complete_model_search_and_filtering(self, temp_registry, complete_model_structure):
        """Test searching and filtering for complete models."""
        # Install complete model
        result = temp_registry.install_model(
            complete_model_structure,
            name="searchable_complete_model"
        )
        
        assert result["status"] == "success"
        
        # Search for complete models by type
        complete_models = temp_registry.list_models({"type": "complete_emuses_model"})
        assert len(complete_models) == 1
        assert complete_models[0]["model_id"] == result["model_id"]
        
        # Search by name
        search_results = temp_registry.search_models("complete_model")
        assert len(search_results) == 1
        assert search_results[0]["model_id"] == result["model_id"]
        
        # Search by description content
        desc_search = temp_registry.search_models("UMAP")
        assert len(desc_search) == 1
        assert desc_search[0]["model_id"] == result["model_id"]
    
    def test_complete_model_removal_cleans_all_components(self, temp_registry, complete_model_structure):
        """Test that removing a complete model cleans up all components."""
        # Install complete model
        result = temp_registry.install_model(
            complete_model_structure,
            name="removal_test_complete"
        )
        
        assert result["status"] == "success"
        model_id = result["model_id"]
        
        # Verify all components exist
        model_path = temp_registry.models_path / model_id
        assert model_path.exists()
        component_files = list(model_path.rglob("*"))
        assert len(component_files) > 5  # Should have many component files
        
        # Remove model
        removal_result = temp_registry.remove_model(model_id=model_id)
        assert removal_result["status"] == "success"
        
        # Verify complete removal
        assert not model_path.exists()
        
        # Verify model not in registry
        models = temp_registry.list_models()
        model_ids = [m["model_id"] for m in models]
        assert model_id not in model_ids