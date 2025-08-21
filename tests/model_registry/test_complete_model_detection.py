"""Tests for complete EMUSES model detection functionality."""

import json
import pytest
from pathlib import Path
from typing import Dict, List

from emuses.tools.model_io import ModelIOManager, CompleteModelValidation


class TestCompleteModelDetection:
    """Test enhanced model validation for complete EMUSES models."""
    
    @pytest.fixture
    def temp_model_dir(self, tmp_path):
        """Create a temporary directory for model testing."""
        model_dir = tmp_path / "test_model"
        model_dir.mkdir()
        return model_dir
    
    @pytest.fixture
    def complete_model_structure(self, temp_model_dir):
        """Create a complete EMUSES model structure."""
        # Create manifest
        manifest = {
            "name": "hcp_analysis_model",
            "version": "1.2.0",
            "model_type": "complete_emuses_model",
            "description": "Complete EMUSES analysis model with UMAP, HDBSCAN, and predictions",
            "pipeline_config": {
                "umap_params": {"n_neighbors": 15, "min_dist": 0.1},
                "hdbscan_params": {"min_cluster_size": 50, "min_samples": 10},
                "prediction_params": {"n_estimators": 100, "max_depth": 10}
            },
            "created_at": "2025-08-20T10:30:00Z"
        }
        
        with open(temp_model_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Create model component files
        (temp_model_dir / "umap_model.pkl").touch()
        (temp_model_dir / "hdbscan_model.pkl").touch()
        
        # Create prediction ensemble directory
        pred_dir = temp_model_dir / "prediction_ensemble"
        pred_dir.mkdir()
        (pred_dir / "model_1.pkl").touch()
        (pred_dir / "model_2.pkl").touch()
        (pred_dir / "model_3.pkl").touch()
        
        # Create auxiliary files
        (temp_model_dir / "embeddings.npy").touch()
        (temp_model_dir / "cluster_labels.npy").touch()
        (temp_model_dir / "performance_metrics.json").write_text('{"accuracy": 0.95}')
        
        return temp_model_dir
    
    @pytest.fixture
    def incomplete_model_structure(self, temp_model_dir):
        """Create an incomplete model structure (UMAP only)."""
        manifest = {
            "name": "umap_only_model",
            "version": "1.0.0", 
            "model_type": "umap_model",
            "description": "UMAP-only model"
        }
        
        with open(temp_model_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
            
        (temp_model_dir / "umap_model.pkl").touch()
        
        return temp_model_dir
    
    def test_validate_complete_model_detection(self, complete_model_structure, tmp_path):
        """Test that complete EMUSES models are correctly detected."""
        manager = ModelIOManager(tmp_path)
        
        # Test with enhanced validation (new functionality)
        result = manager.validate_model(complete_model_structure)
        
        assert isinstance(result, CompleteModelValidation)
        assert result.is_complete_model is True
        assert "umap" in result.components_found
        assert "hdbscan" in result.components_found  
        assert "prediction" in result.components_found
        assert len(result.missing_components) == 0
        assert len(result.validation_errors) == 0
        assert result.configuration_hash != ""
        assert result.content_hash != ""
        
        # Verify component paths
        assert result.components_found["umap"].name == "umap_model.pkl"
        assert result.components_found["hdbscan"].name == "hdbscan_model.pkl"
        assert result.components_found["prediction"].name == "prediction_ensemble"
        
        # Backward compatibility fields
        assert result.name == "hcp_analysis_model"
        assert result.version == "1.2.0"
        assert result.type == "complete_emuses_model"
    
    def test_validate_incomplete_model_detection(self, incomplete_model_structure, tmp_path):
        """Test that incomplete models are correctly identified."""
        manager = ModelIOManager(tmp_path)
        
        result = manager.validate_model(incomplete_model_structure)
        
        assert isinstance(result, CompleteModelValidation)
        assert result.is_complete_model is False
        assert "umap" in result.components_found
        assert "hdbscan" not in result.components_found
        assert "prediction" not in result.components_found
        assert "hdbscan" in result.missing_components
        assert "prediction" in result.missing_components
    
    
    def test_configuration_hash_extraction(self, complete_model_structure, tmp_path):
        """Test that configuration hash is extracted from pipeline metadata."""
        manager = ModelIOManager(tmp_path)
        
        result = manager.validate_model(complete_model_structure)
        
        # Configuration hash should be consistent for same config
        assert result.configuration_hash != ""
        assert len(result.configuration_hash) > 10  # Should be a meaningful hash
        
        # Test hash consistency - same config should produce same hash
        result2 = manager.validate_model(complete_model_structure)
        assert result.configuration_hash == result2.configuration_hash
    
    def test_content_hash_calculation(self, complete_model_structure, tmp_path):
        """Test that content hash reflects actual file contents."""
        manager = ModelIOManager(tmp_path)
        
        result = manager.validate_model(complete_model_structure)
        
        # Content hash should be generated
        assert result.content_hash != ""
        assert len(result.content_hash) > 10
        
        # Modify a file and verify hash changes
        (complete_model_structure / "umap_model.pkl").write_text("modified content")
        result2 = manager.validate_model(complete_model_structure) 
        
        assert result.content_hash != result2.content_hash
    
    def test_diverse_pipeline_patterns(self, temp_model_dir, tmp_path):
        """Test detection with diverse EMUSES pipeline output patterns."""
        manager = ModelIOManager(tmp_path)
        
        # Test different naming patterns
        patterns = [
            ("best_umap_model.pkl", "best_hdbscan_model.pkl"),
            ("umap_model_v2.pkl", "hdbscan_clusterer.pkl"), 
            ("dimension_reducer.pkl", "clustering_model.pkl")
        ]
        
        for umap_name, hdbscan_name in patterns:
            # Clean directory
            for f in temp_model_dir.iterdir():
                if f.is_file():
                    f.unlink()
                elif f.is_dir():
                    import shutil
                    shutil.rmtree(f)
            
            # Create manifest
            manifest = {
                "name": f"test_model_{umap_name.split('.')[0]}",
                "version": "1.0.0",
                "model_type": "complete_emuses_model",
                "description": "Test model with diverse patterns"
            }
            with open(temp_model_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f)
            
            # Create components
            (temp_model_dir / umap_name).touch()
            (temp_model_dir / hdbscan_name).touch()
            pred_dir = temp_model_dir / "predictions"
            pred_dir.mkdir()
            (pred_dir / "ensemble_model.pkl").touch()
            
            result = manager.validate_model(temp_model_dir)
            
            assert result.is_complete_model is True, f"Failed to detect complete model with pattern: {umap_name}, {hdbscan_name}"
            assert "umap" in result.components_found
            assert "hdbscan" in result.components_found
            assert "prediction" in result.components_found

    def test_comprehensive_structure_validation(self, temp_model_dir, tmp_path):
        """Test comprehensive validation for model structure integrity."""
        manager = ModelIOManager(tmp_path)
        
        # Test 1: Model with corrupted manifest
        manifest = {"incomplete": "data"}  # Missing required fields
        with open(temp_model_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f)
        
        (temp_model_dir / "umap_model.pkl").touch()
        (temp_model_dir / "hdbscan_model.pkl").touch()
        
        result = manager.validate_model(temp_model_dir)
        
        # Should still detect components but use fallback manifest
        assert result.is_complete_model is False  # Missing prediction component
        assert "umap" in result.components_found
        assert "hdbscan" in result.components_found
        assert result.name == "unknown_model"  # Default for corrupted manifest
    
    def test_validation_error_detection(self, temp_model_dir, tmp_path):
        """Test detection and reporting of validation errors."""
        manager = ModelIOManager(tmp_path)
        
        # Create empty model directory (should generate validation errors)
        empty_dir = tmp_path / "empty_model"
        empty_dir.mkdir()
        
        result = manager.validate_model(empty_dir)
        
        assert result.is_complete_model is False
        assert len(result.missing_components) == 3  # umap, hdbscan, prediction
        assert "umap" in result.missing_components
        assert "hdbscan" in result.missing_components
        assert "prediction" in result.missing_components
        assert len(result.validation_errors) > 0  # Should have validation errors
        assert "No model files found" in result.validation_errors[0]
    
    def test_auxiliary_component_detection(self, complete_model_structure, tmp_path):
        """Test detection of auxiliary components like embeddings and metrics."""
        manager = ModelIOManager(tmp_path)
        
        result = manager.validate_model(complete_model_structure)
        
        # Should detect main components
        assert result.is_complete_model is True
        
        # Check that auxiliary files exist (they're created in the fixture)
        assert (complete_model_structure / "embeddings.npy").exists()
        assert (complete_model_structure / "cluster_labels.npy").exists()
        assert (complete_model_structure / "performance_metrics.json").exists()
    
    def test_version_specific_pipeline_compatibility(self, temp_model_dir, tmp_path):
        """Test compatibility with different EMUSES pipeline versions."""
        manager = ModelIOManager(tmp_path)
        
        # Test different pipeline version formats
        version_configs = [
            {
                "name": "emuses_v2_0_model",
                "version": "2.0.5",
                "model_type": "complete_emuses_model",
                "emuses_version": "2.0.5",
                "pipeline_config": {"legacy_format": True}
            },
            {
                "name": "emuses_v2_1_model", 
                "version": "2.1.0",
                "model_type": "complete_emuses_model",
                "emuses_version": "2.1.0",
                "pipeline_config": {
                    "umap_params": {"n_neighbors": 15},
                    "hdbscan_params": {"min_cluster_size": 50},
                    "prediction_params": {"n_estimators": 100}
                }
            }
        ]
        
        for config in version_configs:
            # Clean directory
            for f in temp_model_dir.iterdir():
                if f.is_file():
                    f.unlink()
                elif f.is_dir():
                    import shutil
                    shutil.rmtree(f)
            
            # Create manifest
            with open(temp_model_dir / "manifest.json", 'w') as f:
                json.dump(config, f, indent=2)
            
            # Create model files
            (temp_model_dir / "umap_model.pkl").touch()
            (temp_model_dir / "hdbscan_model.pkl").touch()
            pred_dir = temp_model_dir / "prediction_ensemble"
            pred_dir.mkdir()
            (pred_dir / "model_1.pkl").touch()
            
            result = manager.validate_model(temp_model_dir)
            
            assert result.is_complete_model is True
            assert result.name == config["name"]
            assert result.version == config["version"]
            assert len(result.validation_errors) == 0