"""Tests for configuration and content hash indexing for duplicate detection."""

import json
import pytest
from pathlib import Path

from emuses.tools.local_model_registry import LocalModelRegistry


class TestHashIndexing:
    """Test hash-based indexing for efficient duplicate detection."""
    
    @pytest.fixture
    def temp_registry(self, tmp_path):
        """Create a temporary registry for testing."""
        registry_path = tmp_path / "test_registry"
        return LocalModelRegistry(registry_path)
    
    @pytest.fixture
    def duplicate_models(self, tmp_path):
        """Create two models with identical configurations but different names."""
        models = []
        
        identical_config = {
            "umap_params": {"n_neighbors": 15, "min_dist": 0.1},
            "hdbscan_params": {"min_cluster_size": 50, "min_samples": 10},
            "prediction_params": {"n_estimators": 100, "max_depth": 10}
        }
        
        for i in range(2):
            model_dir = tmp_path / f"duplicate_model_{i+1}"
            model_dir.mkdir()
            
            manifest = {
                "name": f"duplicate_test_{i+1}",
                "version": "1.0.0",
                "model_type": "complete_emuses_model",
                "description": f"Duplicate model {i+1} for testing",
                "pipeline_config": identical_config,
                "created_at": "2025-08-20T15:30:00Z"
            }
            
            with open(model_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create identical model components for identical content hashes
            (model_dir / "umap_model.pkl").write_text("identical umap model data")
            (model_dir / "hdbscan_model.pkl").write_text("identical hdbscan model data")
            
            pred_dir = model_dir / "prediction_ensemble"
            pred_dir.mkdir()
            (pred_dir / "model_1.pkl").write_text("identical prediction model 1")
            (pred_dir / "model_2.pkl").write_text("identical prediction model 2")
            
            models.append(model_dir)
        
        return models
    
    @pytest.fixture
    def similar_models(self, tmp_path):
        """Create models with different configurations but similar content."""
        models = []
        
        configs = [
            {
                "umap_params": {"n_neighbors": 15, "min_dist": 0.1},
                "hdbscan_params": {"min_cluster_size": 50}
            },
            {
                "umap_params": {"n_neighbors": 30, "min_dist": 0.2},  # Different config
                "hdbscan_params": {"min_cluster_size": 100}  # Different config
            }
        ]
        
        for i, config in enumerate(configs):
            model_dir = tmp_path / f"similar_model_{i+1}"
            model_dir.mkdir()
            
            manifest = {
                "name": f"similar_test_{i+1}",
                "version": "1.0.0",
                "model_type": "complete_emuses_model",
                "description": f"Similar model {i+1} for testing",
                "pipeline_config": config
            }
            
            with open(model_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create identical content for identical content hashes
            (model_dir / "umap_model.pkl").write_text("same content for all")
            (model_dir / "hdbscan_model.pkl").write_text("same content for all")
            
            pred_dir = model_dir / "prediction_ensemble"
            pred_dir.mkdir()
            (pred_dir / "model_1.pkl").write_text("same prediction content")
            
            models.append(model_dir)
        
        return models
    
    def test_find_duplicates_by_configuration_hash(self, temp_registry, duplicate_models):
        """Test finding duplicate models by configuration hash."""
        # Install both duplicate models
        results = []
        for i, model_dir in enumerate(duplicate_models):
            result = temp_registry.install_model(
                model_dir,
                name=f"config_duplicate_{i+1}"
            )
            assert result["status"] == "success"
            results.append(result)
        
        # Both models should have the same configuration hash
        model1_info = temp_registry.get_model_info(results[0]["model_id"])
        model2_info = temp_registry.get_model_info(results[1]["model_id"])
        
        config_hash1 = model1_info["complete_model_info"]["configuration_hash"]
        config_hash2 = model2_info["complete_model_info"]["configuration_hash"]
        
        assert config_hash1 == config_hash2
        assert config_hash1 != ""
        
        # Test duplicate detection by configuration hash
        duplicates = temp_registry.find_duplicates_by_configuration_hash(config_hash1)
        assert len(duplicates) == 2
        
        duplicate_ids = [d["model_id"] for d in duplicates]
        assert results[0]["model_id"] in duplicate_ids
        assert results[1]["model_id"] in duplicate_ids
    
    def test_find_duplicates_by_content_hash(self, temp_registry, duplicate_models):
        """Test finding duplicate models by content hash."""
        # Install both duplicate models
        results = []
        for i, model_dir in enumerate(duplicate_models):
            result = temp_registry.install_model(
                model_dir,
                name=f"content_duplicate_{i+1}"
            )
            assert result["status"] == "success"
            results.append(result)
        
        # Both models should have the same content hash
        model1_info = temp_registry.get_model_info(results[0]["model_id"])
        model2_info = temp_registry.get_model_info(results[1]["model_id"])
        
        content_hash1 = model1_info["complete_model_info"]["content_hash"]
        content_hash2 = model2_info["complete_model_info"]["content_hash"]
        
        assert content_hash1 == content_hash2
        assert content_hash1 != ""
        
        # Test duplicate detection by content hash
        duplicates = temp_registry.find_duplicates_by_content_hash(content_hash1)
        assert len(duplicates) == 2
        
        duplicate_ids = [d["model_id"] for d in duplicates]
        assert results[0]["model_id"] in duplicate_ids
        assert results[1]["model_id"] in duplicate_ids
    
    def test_configuration_vs_content_hash_differentiation(self, temp_registry, similar_models):
        """Test that models with different configs but same content are correctly differentiated."""
        # Install both similar models
        results = []
        for i, model_dir in enumerate(similar_models):
            result = temp_registry.install_model(
                model_dir,
                name=f"differentiation_test_{i+1}"
            )
            assert result["status"] == "success"
            results.append(result)
        
        model1_info = temp_registry.get_model_info(results[0]["model_id"])
        model2_info = temp_registry.get_model_info(results[1]["model_id"])
        
        config_hash1 = model1_info["complete_model_info"]["configuration_hash"]
        config_hash2 = model2_info["complete_model_info"]["configuration_hash"]
        content_hash1 = model1_info["complete_model_info"]["content_hash"]
        content_hash2 = model2_info["complete_model_info"]["content_hash"]
        
        # Configuration hashes should be different (different configs)
        assert config_hash1 != config_hash2
        
        # Content hashes should be the same (same content)
        assert content_hash1 == content_hash2
        
        # Test configuration hash indexing - should find only one model each
        config1_duplicates = temp_registry.find_duplicates_by_configuration_hash(config_hash1)
        config2_duplicates = temp_registry.find_duplicates_by_configuration_hash(config_hash2)
        
        assert len(config1_duplicates) == 1
        assert len(config2_duplicates) == 1
        assert config1_duplicates[0]["model_id"] == results[0]["model_id"]
        assert config2_duplicates[0]["model_id"] == results[1]["model_id"]
        
        # Test content hash indexing - should find both models
        content_duplicates = temp_registry.find_duplicates_by_content_hash(content_hash1)
        assert len(content_duplicates) == 2
    
    def test_hash_index_performance_with_many_models(self, temp_registry, tmp_path):
        """Test hash indexing performance with many models."""
        # Create multiple models with varying configurations
        num_models = 10
        num_unique_configs = 3  # Some models will have duplicate configs
        
        config_templates = [
            {"umap_params": {"n_neighbors": 15}, "hdbscan_params": {"min_cluster_size": 50}},
            {"umap_params": {"n_neighbors": 30}, "hdbscan_params": {"min_cluster_size": 100}},
            {"umap_params": {"n_neighbors": 45}, "hdbscan_params": {"min_cluster_size": 150}}
        ]
        
        results = []
        for i in range(num_models):
            model_dir = tmp_path / f"performance_model_{i}"
            model_dir.mkdir()
            
            # Use config template based on modulo to create duplicates
            config = config_templates[i % num_unique_configs]
            
            manifest = {
                "name": f"performance_test_{i}",
                "version": "1.0.0",
                "model_type": "complete_emuses_model",
                "description": f"Performance test model {i}",
                "pipeline_config": config
            }
            
            with open(model_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create unique content for each model
            (model_dir / "umap_model.pkl").write_text(f"unique umap content {i}")
            (model_dir / "hdbscan_model.pkl").write_text(f"unique hdbscan content {i}")
            
            pred_dir = model_dir / "prediction_ensemble"
            pred_dir.mkdir()
            (pred_dir / "model_1.pkl").write_text(f"unique prediction content {i}")
            
            result = temp_registry.install_model(model_dir, model_name=f"perf_test_{i}")
            assert result["status"] == "success"
            results.append(result)
        
        # Test configuration hash indexing
        # Models 0, 3, 6, 9 should have the same configuration (config_templates[0])
        model_0_info = temp_registry.get_model_info(results[0]["model_id"])
        config_hash_0 = model_0_info["complete_model_info"]["configuration_hash"]
        
        config_duplicates = temp_registry.find_duplicates_by_configuration_hash(config_hash_0)
        expected_duplicate_count = len([i for i in range(num_models) if i % num_unique_configs == 0])
        assert len(config_duplicates) == expected_duplicate_count
        
        # Test that content hashes are all unique (unique content)
        content_hashes = set()
        for result in results:
            model_info = temp_registry.get_model_info(result["model_id"])
            content_hash = model_info["complete_model_info"]["content_hash"]
            content_hashes.add(content_hash)
        
        assert len(content_hashes) == num_models  # All content hashes should be unique
    
    def test_get_duplicate_summary(self, temp_registry, duplicate_models):
        """Test getting a summary of all duplicates in the registry."""
        # Install duplicate models
        for i, model_dir in enumerate(duplicate_models):
            result = temp_registry.install_model(
                model_dir,
                name=f"summary_test_{i+1}"
            )
            assert result["status"] == "success"
        
        # Get duplicate summary
        duplicate_summary = temp_registry.get_duplicate_summary()
        
        assert "configuration_duplicates" in duplicate_summary
        assert "content_duplicates" in duplicate_summary
        
        # Should have at least one group of configuration duplicates
        assert len(duplicate_summary["configuration_duplicates"]) >= 1
        
        # Should have at least one group of content duplicates
        assert len(duplicate_summary["content_duplicates"]) >= 1
        
        # Verify structure of duplicate groups
        for hash_value, models in duplicate_summary["configuration_duplicates"].items():
            assert len(models) >= 1  # At least one model per hash
            assert isinstance(hash_value, str)
            assert len(hash_value) > 0
            
            for model in models:
                assert "model_id" in model
                assert "name" in model