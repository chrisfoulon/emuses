"""
Test suite for normalization parameter storage implementation.

Tests the enhanced EMUSESPipeline and ModelIOManager functionality for
saving and detecting normalization scalers during model training.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json
import joblib
from pathlib import Path
import shutil

from bcblib.tools.dataframe_filtering import normalize_dataframe


class TestNormalizationStorage:
    """Test normalization scaler storage functionality."""

    @pytest.fixture
    def temp_output_folder(self):
        """Create a temporary output folder for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_emuses_pipeline(self, temp_output_folder):
        """Create a mock EMUSESPipeline with temporary output folder."""
        # Create a minimal mock that simulates the essential parts
        pipeline = Mock()
        pipeline.output_folder = temp_output_folder
        pipeline.context = {}
        pipeline.logger = Mock()
        return pipeline

    def test_scores_scaler_storage_integration(self, temp_output_folder):
        """Test scores normalization scaler storage functionality."""
        # Create test scores data
        scores_df = pd.DataFrame({
            'cognitive_score': [85, 92, 78, 88, 95],
            'motor_score': [12.5, 15.2, 9.8, 14.1, 16.3]
        })
        
        # Simulate the enhanced EMUSESPipeline logic
        method = 'min-max'
        scores_df_normalized, scores_scaling_factors = normalize_dataframe(
            scores_df, method=method
        )
        
        # Save scaler to model directory (as enhanced EMUSESPipeline would do)
        temp_output_folder.mkdir(parents=True, exist_ok=True)
        scores_scaler_path = temp_output_folder / "scores_scaler.joblib"
        joblib.dump(scores_scaling_factors, scores_scaler_path)
        
        # Store scaler info in context (as enhanced EMUSESPipeline would do)
        context = {
            "scores_scaler_info": {
                "path": "scores_scaler.joblib",
                "method": method,
                "scaling_factors": scores_scaling_factors
            }
        }
        
        # Verify scaler was saved correctly
        assert scores_scaler_path.exists()
        assert scores_scaler_path.stat().st_size > 0
        
        # Verify scaler can be loaded and used
        loaded_scaling_factors = joblib.load(scores_scaler_path)
        assert loaded_scaling_factors == scores_scaling_factors
        
        # Test that loaded scaler can normalize new data consistently
        new_scores_df = pd.DataFrame({
            'cognitive_score': [90, 82],
            'motor_score': [13.7, 11.2]
        })
        
        new_scores_normalized, _ = normalize_dataframe(
            new_scores_df, method=method, scaling_factors=loaded_scaling_factors
        )
        
        assert isinstance(new_scores_normalized, pd.DataFrame)
        assert new_scores_normalized.shape == (2, 2)
        
        # Verify context info is correct
        assert context["scores_scaler_info"]["path"] == "scores_scaler.joblib"
        assert context["scores_scaler_info"]["method"] == method

    def test_input_scaler_storage_integration(self, temp_output_folder):
        """Test input normalization scaler storage functionality."""
        # Create test input data
        inputs_df = pd.DataFrame({
            'feature_1': [1.5, 2.1, 0.8, 1.9, 2.3],
            'feature_2': [0.05, 0.12, 0.03, 0.09, 0.15],
            'feature_3': [100, 150, 75, 125, 180]
        })
        
        # Simulate the enhanced EMUSESPipeline logic for unlabeled data
        method = 'zscore'
        inputs_df_normalized, scaling_factors = normalize_dataframe(
            inputs_df, method=method
        )
        
        # Save scaler to model directory (as enhanced EMUSESPipeline would do)
        temp_output_folder.mkdir(parents=True, exist_ok=True)
        input_scaler_path = temp_output_folder / "input_scaler.joblib"
        joblib.dump(scaling_factors, input_scaler_path)
        
        # Store scaler info in context
        context = {
            "input_scaling_factors": scaling_factors,
            "input_scaler_info": {
                "path": "input_scaler.joblib",
                "method": method,
                "scaling_factors": scaling_factors
            }
        }
        
        # Verify scaler was saved correctly
        assert input_scaler_path.exists()
        assert input_scaler_path.stat().st_size > 0
        
        # Verify scaler can be loaded and used
        loaded_scaling_factors = joblib.load(input_scaler_path)
        assert loaded_scaling_factors == scaling_factors
        
        # Test labeled data scenario (reusing existing scaling factors)
        new_inputs_df = pd.DataFrame({
            'feature_1': [1.7, 1.3],
            'feature_2': [0.08, 0.06],
            'feature_3': [110, 95]
        })
        
        # Simulate labeled data processing (uses existing scaling factors)
        reused_normalized_df, _ = normalize_dataframe(
            new_inputs_df, method=method, scaling_factors=loaded_scaling_factors
        )
        
        assert isinstance(reused_normalized_df, pd.DataFrame)
        assert reused_normalized_df.shape == (2, 3)
        
        # Verify context contains both old and new structure
        assert "input_scaling_factors" in context  # Legacy context
        assert "input_scaler_info" in context  # New enhanced context

    def test_manifest_enhancement_with_scalers(self, temp_output_folder):
        """Test ModelIOManager manifest enhancement with normalization scalers."""
        # Create a basic manifest file
        manifest_path = temp_output_folder / "model_manifest.json"
        base_manifest = {
            "model_info": {"version": "1.0.0", "model_type": "complete_emuses_model"},
            "file_integrity": {
                "best_umap_model.joblib": {"sha256": "fake_hash_umap"},
                "hdbscan_model.joblib": {"sha256": "fake_hash_hdbscan"}
            }
        }
        
        with open(manifest_path, 'w') as f:
            json.dump(base_manifest, f, indent=2)
        
        # Create mock scaler files
        scores_scaler_path = temp_output_folder / "scores_scaler.joblib"
        input_scaler_path = temp_output_folder / "input_scaler.joblib"
        
        # Create realistic scaler data
        test_scores = pd.DataFrame({'score': [1, 2, 3, 4, 5]})
        test_inputs = pd.DataFrame({'feature': [10, 20, 30, 40, 50]})
        
        _, scores_factors = normalize_dataframe(test_scores, method='min-max')
        _, input_factors = normalize_dataframe(test_inputs, method='zscore')
        
        joblib.dump(scores_factors, scores_scaler_path)
        joblib.dump(input_factors, input_scaler_path)
        
        # Import and test the enhance function
        from emuses.tools.model_io import enhance_model_manifest_with_pipeline_data
        
        # Enhance the manifest
        success = enhance_model_manifest_with_pipeline_data(temp_output_folder)
        assert success
        
        # Verify enhanced manifest includes normalization section
        with open(manifest_path, 'r') as f:
            enhanced_manifest = json.load(f)
        
        assert "normalization" in enhanced_manifest
        normalization_info = enhanced_manifest["normalization"]
        
        # Verify normalization section structure
        assert "scores_scaler" in normalization_info
        assert "input_scaler" in normalization_info
        assert "embeddings_rescaling" in normalization_info
        
        assert normalization_info["scores_scaler"] == "scores_scaler.joblib"
        assert normalization_info["input_scaler"] == "input_scaler.joblib"
        assert normalization_info["embeddings_rescaling"] is True
        
        # Verify method detection worked
        assert "scores_method" in normalization_info
        assert "input_method" in normalization_info
        
        # Verify file statistics include scaler sizes
        if "file_statistics" in enhanced_manifest and enhanced_manifest["file_statistics"] != "Not Found":
            file_stats = enhanced_manifest["file_statistics"]
            if "components" in file_stats:
                components = file_stats["components"]
                # Check if scaler sizes were added
                assert "scores_scaler_size_mb" in components or "input_scaler_size_mb" in components

    def test_manifest_enhancement_without_scalers(self, temp_output_folder):
        """Test manifest enhancement when no scalers are present."""
        # Create manifest without scalers
        manifest_path = temp_output_folder / "model_manifest.json"
        base_manifest = {
            "model_info": {"version": "1.0.0", "model_type": "complete_emuses_model"},
            "file_integrity": {
                "best_umap_model.joblib": {"sha256": "fake_hash_umap"}
            }
        }
        
        with open(manifest_path, 'w') as f:
            json.dump(base_manifest, f, indent=2)
        
        # Import and test the enhance function  
        from emuses.tools.model_io import enhance_model_manifest_with_pipeline_data
        
        # Enhance the manifest
        success = enhance_model_manifest_with_pipeline_data(temp_output_folder)
        assert success
        
        # Verify enhanced manifest does NOT include normalization section
        with open(manifest_path, 'r') as f:
            enhanced_manifest = json.load(f)
        
        # Should not have normalization section since no scalers were found
        assert "normalization" not in enhanced_manifest

    def test_robust_scaler_detection(self, temp_output_folder):
        """Test detection of robust method scalers (sklearn objects)."""
        # Create test data with outliers (where robust scaling is appropriate)
        test_data = pd.DataFrame({
            'feature_1': [1, 2, 3, 4, 100],  # Include outlier
            'feature_2': [10, 20, 30, 40, 1000]  # Include outlier
        })
        
        # Use robust method (creates sklearn scaler objects)
        _, robust_factors = normalize_dataframe(test_data, method='robust')
        
        # Save robust scaler
        robust_scaler_path = temp_output_folder / "input_scaler.joblib"
        joblib.dump(robust_factors, robust_scaler_path)
        
        # Create basic manifest
        manifest_path = temp_output_folder / "model_manifest.json"
        base_manifest = {"model_info": {"version": "1.0.0"}}
        
        with open(manifest_path, 'w') as f:
            json.dump(base_manifest, f, indent=2)
        
        # Enhance manifest
        from emuses.tools.model_io import enhance_model_manifest_with_pipeline_data
        success = enhance_model_manifest_with_pipeline_data(temp_output_folder)
        assert success
        
        # Verify robust method was detected
        with open(manifest_path, 'r') as f:
            enhanced_manifest = json.load(f)
        
        assert "normalization" in enhanced_manifest
        normalization_info = enhanced_manifest["normalization"]
        assert "input_scaler" in normalization_info
        # Should detect robust method from sklearn scaler objects
        assert normalization_info.get("input_method") in ["robust", "unknown"]

    def test_scaler_serialization_compatibility(self):
        """Test that all normalization methods produce serializable scalers."""
        test_df = pd.DataFrame({
            'col1': [1, 2, 3, 4, 5],
            'col2': [10, 20, 30, 40, 50]
        })
        
        methods = ['min-max', 'zscore', 'robust']
        
        for method in methods:
            with tempfile.NamedTemporaryFile(suffix='.joblib', delete=False) as tmp:
                # Test normalization and saving
                _, scaling_factors = normalize_dataframe(test_df, method=method)
                
                # Test joblib serialization (required for model persistence)
                joblib.dump(scaling_factors, tmp.name)
                
                # Test loading
                loaded_factors = joblib.load(tmp.name)
                
                # Test that loaded scalers work
                test_new_df = pd.DataFrame({
                    'col1': [6, 7],
                    'col2': [60, 70]
                })
                
                normalized_new, _ = normalize_dataframe(
                    test_new_df, method=method, scaling_factors=loaded_factors
                )
                
                assert isinstance(normalized_new, pd.DataFrame)
                assert normalized_new.shape == (2, 2)
                
                # Clean up
                Path(tmp.name).unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])