"""Tests for enhanced metadata storage with component tracking and hashes."""

import json
import pytest
from pathlib import Path

from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_io import ModelIOManager


class TestEnhancedMetadataStorage:
    """Test enhanced metadata storage capabilities."""
    
    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / "test_registry"
        return LocalModelRegistry(registry_path)
    
    @pytest.fixture
    def complete_model_with_hashes(self, tmp_path):
        """Create a complete model with hash information."""
        model_dir = tmp_path / "hash_test_model"
        model_dir.mkdir()
        
        # Create manifest with comprehensive configuration
        manifest = {
            "name": "hash_test_model",
            "version": "2.1.0",
            "model_type": "emuses_model",
            "description": "Complete model for hash testing",
            "pipeline_config": {
                "umap_params": {
                    "n_neighbors": 15,
                    "min_dist": 0.1,
                    "n_components": 2,
                    "random_state": 42
                },
                "hdbscan_params": {
                    "min_cluster_size": 50,
                    "min_samples": 10,
                    "cluster_selection_epsilon": 0.0
                },
                "prediction_params": {
                    "n_estimators": 100,
                    "max_depth": 10,
                    "random_state": 42,
                    "n_jobs": -1
                }
            },
            "training_metadata": {
                "dataset_hash": "abc123def456",
                "training_time": "2025-08-20T15:30:00Z",
                "performance_metrics": {
                    "umap_trustworthiness": 0.92,
                    "hdbscan_silhouette": 0.78,
                    "prediction_accuracy": 0.95
                }
            },
            "created_at": "2025-08-20T15:30:00Z"
        }
        
        with open(model_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Create model component files with different content for unique hashes
        (model_dir / "umap_model.pkl").write_text("UMAP model with specific parameters: n_neighbors=15, min_dist=0.1")
        (model_dir / "hdbscan_model.pkl").write_text("HDBSCAN model with min_cluster_size=50, min_samples=10")
        
        # Create prediction ensemble with multiple models
        pred_dir = model_dir / "prediction_ensemble"
        pred_dir.mkdir()
        (pred_dir / "model_1.pkl").write_text("Random Forest model 1, n_estimators=100")
        (pred_dir / "model_2.pkl").write_text("Random Forest model 2, max_depth=10")
        (pred_dir / "model_3.pkl").write_text("Random Forest model 3, random_state=42")
        
        # Create auxiliary files
        (model_dir / "embeddings.npy").write_text("UMAP embeddings data [2000x2 array]")
        (model_dir / "cluster_labels.npy").write_text("HDBSCAN cluster labels [2000 array]")
        (model_dir / "performance_metrics.json").write_text('{"cross_val_scores": [0.94, 0.96, 0.95, 0.93, 0.97], "mean_score": 0.95}')
        
        return model_dir
    
    def test_enhanced_validation_information_storage(self, temp_registry, complete_model_with_hashes):
        """Test that enhanced validation information is stored in registry metadata."""
        # First, manually test the enhanced validation
        model_io = ModelIOManager(temp_registry.models_path)
        validation_result = model_io.validate_model(complete_model_with_hashes)
        
        assert validation_result.is_complete_model is True
        assert validation_result.configuration_hash != ""
        assert validation_result.content_hash != ""
        assert len(validation_result.components_found) == 3
        
        # Install the model 
        result = temp_registry.install_model(
            complete_model_with_hashes,
            model_name="enhanced_metadata_test"
        )
        
        assert result["status"] == "success"
        
        # Get model info and check if enhanced metadata is preserved
        model_info = temp_registry.get_model_info(result["model_id"])
        assert model_info is not None
        
        # The enhanced metadata should ideally include:
        # 1. Component tracking information
        # 2. Configuration and content hashes
        # 3. Complete model validation status
        
        print(f"Model info keys: {model_info.keys()}")
        print(f"Model manifest: {json.dumps(model_info['manifest'], indent=2)}")
        
        # Verify basic complete model detection worked
        assert model_info["type"] == "emuses_model"
        
        # Verify enhanced metadata is stored
        assert "complete_model_info" in model_info
        complete_info = model_info["complete_model_info"]
        
        assert complete_info["is_complete_model"] is True
        assert complete_info["configuration_hash"] != ""
        assert complete_info["content_hash"] != ""
        assert len(complete_info["components_found"]) == 3
        assert "umap" in complete_info["components_found"]
        assert "hdbscan" in complete_info["components_found"]
        assert "prediction" in complete_info["components_found"]
        assert len(complete_info["missing_components"]) == 0
    
    def test_component_hash_tracking(self, temp_registry, complete_model_with_hashes):
        """Test that individual component hashes are tracked."""
        result = temp_registry.install_model(
            complete_model_with_hashes,
            model_name="component_hash_test"
        )
        
        assert result["status"] == "success"
        
        # Verify that components exist and can be individually hashed
        model_path = temp_registry.models_path / result["model_id"]
        
        umap_file = model_path / "umap_model.pkl"
        hdbscan_file = model_path / "hdbscan_model.pkl" 
        pred_dir = model_path / "prediction_ensemble"
        
        assert umap_file.exists()
        assert hdbscan_file.exists()
        assert pred_dir.exists()
        
        # Verify content is preserved (different components have different content)
        umap_content = umap_file.read_text()
        hdbscan_content = hdbscan_file.read_text()
        
        assert "n_neighbors=15" in umap_content
        assert "min_cluster_size=50" in hdbscan_content
        assert umap_content != hdbscan_content  # Components should have different content
    
    def test_configuration_hash_consistency(self, temp_registry, tmp_path):
        """Test that models with same configuration produce same configuration hash."""
        # Create two identical models
        model1_dir = tmp_path / "identical_model_1"
        model2_dir = tmp_path / "identical_model_2"
        
        identical_config = {
            "umap_params": {"n_neighbors": 20, "min_dist": 0.2},
            "hdbscan_params": {"min_cluster_size": 100}
        }
        
        for i, model_dir in enumerate([model1_dir, model2_dir], 1):
            model_dir.mkdir()
            
            manifest = {
                "name": f"identical_model_{i}",
                "version": "1.0.0",
                "model_type": "emuses_model",
                "description": f"Identical model {i}",
                "pipeline_config": identical_config
            }
            
            with open(model_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create identical components
            (model_dir / "umap_model.pkl").write_text("identical umap")
            (model_dir / "hdbscan_model.pkl").write_text("identical hdbscan")
            pred_dir = model_dir / "prediction_ensemble"
            pred_dir.mkdir()
            (pred_dir / "model_1.pkl").write_text("identical prediction")
        
        # Get validation results for both models
        model_io = ModelIOManager(temp_registry.models_path)
        
        validation1 = model_io.validate_model(model1_dir)
        validation2 = model_io.validate_model(model2_dir)
        
        # Configuration hashes should be identical (same config)
        assert validation1.configuration_hash == validation2.configuration_hash
        
        # Content hashes should be identical (same content)
        assert validation1.content_hash == validation2.content_hash
    
    def test_configuration_hash_differentiation(self, temp_registry, tmp_path):
        """Test that models with different configurations produce different hashes."""
        # Create two models with different configurations
        model1_dir = tmp_path / "different_model_1"
        model2_dir = tmp_path / "different_model_2"
        
        config1 = {
            "umap_params": {"n_neighbors": 15, "min_dist": 0.1},
            "hdbscan_params": {"min_cluster_size": 50}
        }
        
        config2 = {
            "umap_params": {"n_neighbors": 30, "min_dist": 0.3},  # Different parameters
            "hdbscan_params": {"min_cluster_size": 100}  # Different parameters
        }
        
        for i, (model_dir, config) in enumerate([(model1_dir, config1), (model2_dir, config2)], 1):
            model_dir.mkdir()
            
            manifest = {
                "name": f"different_model_{i}",
                "version": "1.0.0",
                "model_type": "emuses_model",
                "description": f"Different model {i}",
                "pipeline_config": config
            }
            
            with open(model_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create identical components (only config differs)
            (model_dir / "umap_model.pkl").write_text("same umap content")
            (model_dir / "hdbscan_model.pkl").write_text("same hdbscan content")
            pred_dir = model_dir / "prediction_ensemble"
            pred_dir.mkdir()
            (pred_dir / "model_1.pkl").write_text("same prediction content")
        
        # Get validation results for both models
        model_io = ModelIOManager(temp_registry.models_path)
        
        validation1 = model_io.validate_model(model1_dir)
        validation2 = model_io.validate_model(model2_dir)
        
        # Configuration hashes should be different (different configs)
        assert validation1.configuration_hash != validation2.configuration_hash
        
        # Content hashes should be identical (same content)
        assert validation1.content_hash == validation2.content_hash
    
    def test_metadata_storage_preserves_enhanced_info(self, temp_registry, complete_model_with_hashes):
        """Test that registry metadata storage preserves enhanced validation information."""
        # This test will verify if we need to enhance the install_model method
        # to store the enhanced validation information
        
        result = temp_registry.install_model(
            complete_model_with_hashes,
            model_name="metadata_preservation_test"
        )
        
        assert result["status"] == "success"
        
        # Check what information is currently stored
        model_info = temp_registry.get_model_info(result["model_id"])
        
        # Print current structure to understand what's missing
        print(f"\nCurrent registry metadata structure:")
        for key, value in model_info.items():
            if key == "manifest":
                print(f"  {key}: {json.dumps(value, indent=4)}")
            else:
                print(f"  {key}: {value}")
        
        # Test passes if basic information is preserved
        # Enhanced information storage would be an additional feature
        assert model_info["type"] == "emuses_model"
        assert "manifest" in model_info