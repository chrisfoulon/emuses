"""
Test folder naming updates for statistical analysis enhancement.

Tests the folder structure changes from "grids" to "heatmaps" terminology
in GridCreator and CorrelationGridCreator components.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from emuses.tools.grid_creator import GridCreator
from emuses.tools.correlation_grid_creator import CorrelationGridCreator


class TestGridCreatorFolderNaming:
    """Test folder naming changes in GridCreator from prediction-grids to prediction-heatmaps."""

    def test_prediction_heatmaps_folder_creation(self):
        """
        Test that GridCreator creates prediction-heatmaps/ folders instead of prediction-grids/.
        
        This test verifies Task 3.1.a.1: Change prediction-grids/ → prediction-heatmaps/ in GridCreator.
        """
        # Setup test data
        embeddings = np.random.rand(50, 2)  # 50 samples, 2D embeddings in 0-1 range
        target_data = {'0': np.random.rand(50)}
        
        # Mock trained models with required structure
        mock_model = MagicMock()
        mock_model.predict.return_value = np.random.rand(10000)  # Grid predictions
        del mock_model.predict_proba  # Remove predict_proba to simulate regression model
        
        trained_models = {
            'prediction_models': [
                {'model': mock_model, 'target': '0'}
            ],
            'scores_scaler': None,
            'metadata': {'scores_normalization_method': 'robust'}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Create GridCreator and run heatmap generation
            grid_creator = GridCreator(grid_size=100)
            results = grid_creator.create_prediction_heatmaps(
                embeddings=embeddings,
                trained_models=trained_models,
                target_data=target_data,
                output_folder=output_folder,
                denormalize=False
            )
            
            # Verify that prediction-heatmaps folder was created (not prediction-grids)
            expected_heatmap_folder = output_folder / "target_0" / "prediction-heatmaps"
            old_grids_folder = output_folder / "target_0" / "prediction-grids"
            
            # This should pass after implementing the folder name change
            assert expected_heatmap_folder.exists(), f"Expected prediction-heatmaps folder not found: {expected_heatmap_folder}"
            assert not old_grids_folder.exists(), f"Old prediction-grids folder should not exist: {old_grids_folder}"
            
            # Verify expected artifacts are created in the correct folder
            expected_files = [
                "prediction_values.npy",
                "confidence_values.npy", 
                "combined_values.npy",
                "grid_coordinates.npy",
                "prediction_metadata.json"
            ]
            
            for filename in expected_files:
                artifact_path = expected_heatmap_folder / filename
                assert artifact_path.exists(), f"Expected artifact not found: {artifact_path}"
            
            # Verify results metadata contains correct folder paths
            target_results = results['heatmap_results']['0']
            assert 'prediction-heatmaps' in target_results['artifacts']['prediction_values']
            assert 'prediction-grids' not in target_results['artifacts']['prediction_values']

    def test_backwards_compatibility_with_existing_artifacts(self):
        """
        Test that folder naming change maintains backwards compatibility.
        
        This test verifies Task 3.1.a.3: Verify backwards compatibility with existing artifacts.
        """
        # This test ensures that existing analysis results are not broken by the naming change.
        # For now, we'll test that the new naming convention doesn't conflict with old structure.
        
        embeddings = np.random.rand(30, 2)
        target_data = {'0': np.random.rand(30)}
        
        # Mock trained models
        mock_model = MagicMock()
        mock_model.predict.return_value = np.random.rand(10000)
        del mock_model.predict_proba  # Simulate regression model
        
        trained_models = {
            'prediction_models': [{'model': mock_model, 'target': '0'}],
            'scores_scaler': None,
            'metadata': {}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Pre-create an old-style prediction-grids folder structure
            old_structure = output_folder / "target_0" / "prediction-grids"
            old_structure.mkdir(parents=True, exist_ok=True)
            (old_structure / "old_artifact.npy").touch()
            
            # Run new heatmap generation
            grid_creator = GridCreator(grid_size=100)
            results = grid_creator.create_prediction_heatmaps(
                embeddings=embeddings,
                trained_models=trained_models,
                target_data=target_data,
                output_folder=output_folder,
                denormalize=False
            )
            
            # Verify both old and new folders can coexist
            new_structure = output_folder / "target_0" / "prediction-heatmaps"
            
            assert old_structure.exists(), "Old prediction-grids folder should still exist"
            assert (old_structure / "old_artifact.npy").exists(), "Old artifacts should be preserved"
            assert new_structure.exists(), "New prediction-heatmaps folder should be created"
            
            # Verify new artifacts are in the correct location
            assert (new_structure / "prediction_values.npy").exists()


class TestCorrelationGridCreatorFolderNaming:
    """Test folder naming changes in CorrelationGridCreator from correlation-grids to correlation-heatmaps."""

    def test_correlation_heatmaps_folder_creation(self):
        """
        Test that CorrelationGridCreator creates correlation-heatmaps/ folders instead of correlation-grids/.
        
        This test verifies Task 3.1.b.1: Change correlation-grids/ → correlation-heatmaps/ in CorrelationGridCreator.
        """
        # Setup test data
        embeddings = np.random.rand(50, 2)  # 50 samples, 2D embeddings in 0-1 range
        target_data = {'0': np.random.rand(50)}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Create CorrelationGridCreator with fixed sigma (no optimization)
            correlation_creator = CorrelationGridCreator(
                grid_size=100, 
                correlation_methods=["pearson"],
                sigma=0.1  # Fixed sigma to avoid optimization
            )
            
            # Run correlation heatmap generation
            results = correlation_creator.create_correlation_heatmaps(
                embeddings=embeddings,
                target_data=target_data,
                output_folder=output_folder,
                optimize_sigma=False
            )
            
            # Verify that correlation-heatmaps folder was created (not correlation-grids)
            expected_heatmap_folder = output_folder / "target_0" / "correlation-heatmaps"
            old_grids_folder = output_folder / "target_0" / "correlation-grids"
            
            # This should pass after implementing the folder name change
            assert expected_heatmap_folder.exists(), f"Expected correlation-heatmaps folder not found: {expected_heatmap_folder}"
            assert not old_grids_folder.exists(), f"Old correlation-grids folder should not exist: {old_grids_folder}"
            
            # Verify expected artifacts are created in the correct folder
            expected_files = [
                "correlation_values_pearson.npy",
                "grid_coordinates.npy", 
                "correlation_metadata.json"
            ]
            
            for filename in expected_files:
                artifact_path = expected_heatmap_folder / filename
                assert artifact_path.exists(), f"Expected artifact not found: {artifact_path}"
            
            # Verify results metadata contains correct folder paths
            target_results = results['correlation_results']['0']
            assert 'correlation-heatmaps' in target_results['artifacts']['correlation_values_pearson']
            assert 'correlation-grids' not in target_results['artifacts']['correlation_values_pearson']

    def test_backwards_compatibility_with_existing_correlation_artifacts(self):
        """
        Test that correlation folder naming change maintains backwards compatibility.
        
        This test verifies Task 3.1.b.3: Verify backwards compatibility with existing artifacts.
        """
        embeddings = np.random.rand(30, 2)
        target_data = {'0': np.random.rand(30)}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Pre-create an old-style correlation-grids folder structure
            old_structure = output_folder / "target_0" / "correlation-grids"
            old_structure.mkdir(parents=True, exist_ok=True)
            (old_structure / "old_correlation.npy").touch()
            
            # Run new heatmap generation
            correlation_creator = CorrelationGridCreator(
                grid_size=100,
                correlation_methods=["pearson"],
                sigma=0.1
            )
            results = correlation_creator.create_correlation_heatmaps(
                embeddings=embeddings,
                target_data=target_data,
                output_folder=output_folder,
                optimize_sigma=False
            )
            
            # Verify both old and new folders can coexist
            new_structure = output_folder / "target_0" / "correlation-heatmaps"
            
            assert old_structure.exists(), "Old correlation-grids folder should still exist"
            assert (old_structure / "old_correlation.npy").exists(), "Old artifacts should be preserved"
            assert new_structure.exists(), "New correlation-heatmaps folder should be created"
            
            # Verify new artifacts are in the correct location
            assert (new_structure / "correlation_values_pearson.npy").exists()