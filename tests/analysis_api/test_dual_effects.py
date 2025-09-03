"""
Test dual effect size maps implementation with symmetric percentile thresholds.

Tests the enhanced RegionStatisticalAnalyzer for dual analysis pattern with
configurable percentile thresholds and significance source differentiation.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from emuses.tools.region_statistical_analyzer import RegionStatisticalAnalyzer


class TestDualEffectAnalysis:
    """Test enhanced RegionStatisticalAnalyzer for dual analysis with percentile thresholds."""
    
    @classmethod
    def setup_class(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values

    def test_significance_source_parameter(self):
        """
        Test RegionStatisticalAnalyzer supports significance_source parameter for dual analysis.
        
        This test verifies Task 3.2.a.1: Add significance_source parameter to create_statistical_maps().
        """
        analyzer = RegionStatisticalAnalyzer()
        
        # Setup test data using real test data with perfect square grid (49 = 7x7)
        n_grid = 49  # Perfect square
        grid_coords = np.tile(self.features[:25, :2], (2, 1))[:n_grid]  # Tile to get 49 samples
        embeddings = self.features[:50, :2]  # Training embeddings from real data
        prediction_values = np.tile(self.features[:25, 2], 2)[:n_grid]  # Third feature column
        confidence_values = np.tile(self.features[:25, 3], 2)[:n_grid]  # Fourth feature column
        # Ensure correlation_values has correct dimensions
        correlation_values = np.tile(self.targets[:25, 0], 2)[:n_grid]
        # Create input matrix by tiling real features
        base_features = self.features[:50]  # 50 samples
        n_features_needed = 1000
        input_matrix = np.tile(base_features, (1, n_features_needed // base_features.shape[1] + 1))[:, :n_features_needed]
        target_data = {'0': self.targets[:50, 0]}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Mock the input_matrix_stat_map function to avoid real computation
            with patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map') as mock_stat_map:
                # Use real data for mock return values
                stat_map = np.tile(self.features[:50, 0], (1000 // 50 + 1))[:1000]
                pval_map = np.tile(self.features[:50, 1], (1000 // 50 + 1))[:1000]
                effect_size_map = np.tile(self.targets[:50, 0], (1000 // 50 + 1))[:1000]
                mock_stat_map.return_value = (stat_map, pval_map, effect_size_map)
                
                # Test prediction significance source
                results_prediction = analyzer.create_statistical_maps(
                    grid_coords=grid_coords,
                    significance_values=prediction_values * confidence_values,  # prediction×confidence
                    input_matrix=input_matrix,
                    target_data=target_data,
                    output_folder=output_folder,
                    input_type='nifti',
                    output_format_info=None,
                    training_embeddings=embeddings,
                    significance_source='prediction',
                    percentile_threshold=5
                )
                
                # Test correlation significance source
                results_correlation = analyzer.create_statistical_maps(
                    grid_coords=grid_coords,
                    significance_values=np.abs(correlation_values),  # absolute correlation
                    input_matrix=input_matrix,
                    target_data=target_data,
                    output_folder=output_folder,
                    input_type='nifti',
                    output_format_info=None,
                    training_embeddings=embeddings,
                    significance_source='correlation',
                    percentile_threshold=5
                )
                
                # Verify different output folders were created
                prediction_folder = output_folder / "target_0" / "prediction-effects"
                correlation_folder = output_folder / "target_0" / "correlation-effects"
                
                assert prediction_folder.exists(), f"Prediction effects folder not found: {prediction_folder}"
                assert correlation_folder.exists(), f"Correlation effects folder not found: {correlation_folder}"
                
                # Verify results contain significance source info
                assert 'significance_source' in results_prediction['analysis_metadata']
                assert results_prediction['analysis_metadata']['significance_source'] == 'prediction'
                assert 'significance_source' in results_correlation['analysis_metadata']
                assert results_correlation['analysis_metadata']['significance_source'] == 'correlation'

    def test_percentile_threshold_parameter(self):
        """
        Test RegionStatisticalAnalyzer supports percentile_threshold parameter.
        
        This test verifies that the percentile_threshold parameter is properly passed through.
        """
        analyzer = RegionStatisticalAnalyzer()
        
        # Setup test data with known distribution using real data (perfect square: 49)
        n_grid = 49  # Perfect square (7x7)
        base_significance = self.features[:25, 0]  # Take first 25 values from real data
        significance_values = np.tile(base_significance, 2)[:n_grid]  # Tile to get 49 values
        grid_coords = np.tile(self.features[:25, :2], (2, 1))[:n_grid]
        embeddings = self.features[:50, :2]  # Training embeddings from real data
        # Create input matrix by tiling real features
        base_features = self.features[:50]
        n_features_needed = 1000
        input_matrix = np.tile(base_features, (1, n_features_needed // base_features.shape[1] + 1))[:, :n_features_needed]
        target_data = {'0': self.targets[:50, 0]}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            with patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map') as mock_stat_map:
                # Use real data for mock return values
                stat_map = np.tile(self.features[:50, 0], (1000 // 50 + 1))[:1000]
                pval_map = np.tile(self.features[:50, 1], (1000 // 50 + 1))[:1000]
                effect_size_map = np.tile(self.targets[:50, 0], (1000 // 50 + 1))[:1000]
                mock_stat_map.return_value = (stat_map, pval_map, effect_size_map)
                
                # Test with 5% threshold
                results = analyzer.create_statistical_maps(
                    grid_coords=grid_coords,
                    significance_values=significance_values,
                    input_matrix=input_matrix,
                    target_data=target_data,
                    output_folder=output_folder,
                    input_type='nifti',
                    output_format_info=None,
                    training_embeddings=embeddings,
                    significance_source='prediction',
                    percentile_threshold=5
                )
                
                # Verify basic percentile threshold is recorded in metadata
                assert 'percentile_threshold' in results['analysis_metadata']
                assert results['analysis_metadata']['percentile_threshold'] == 5

    def test_dual_output_files_creation(self):
        """
        Test that dual analysis creates separate output files for low and high significance regions.
        
        This test verifies the expected file structure with low_significance_regions.npy and 
        high_significance_regions.npy outputs.
        """
        analyzer = RegionStatisticalAnalyzer()
        
        # Setup test data using real test data (perfect square: 49)
        n_grid = 49  # Perfect square (7x7)
        grid_coords = np.tile(self.features[:25, :2], (2, 1))[:n_grid]
        embeddings = self.features[:50, :2]  # Training embeddings from real data
        significance_values = np.tile(self.features[:25, 2], 2)[:n_grid]  # Third feature column
        # Create input matrix by tiling real features
        base_features = self.features[:50]
        n_features_needed = 1000
        input_matrix = np.tile(base_features, (1, n_features_needed // base_features.shape[1] + 1))[:, :n_features_needed]
        target_data = {'0': self.targets[:50, 0]}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            with patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map') as mock_stat_map:
                # Use real data for mock return values
                stat_map = np.tile(self.features[:50, 0], (1000 // 50 + 1))[:1000]
                pval_map = np.tile(self.features[:50, 1], (1000 // 50 + 1))[:1000]
                effect_size_map = np.tile(self.targets[:50, 0], (1000 // 50 + 1))[:1000]
                mock_stat_map.return_value = (stat_map, pval_map, effect_size_map)
                
                # Run dual analysis
                results = analyzer.create_statistical_maps(
                    grid_coords=grid_coords,
                    significance_values=significance_values,
                    input_matrix=input_matrix,
                    target_data=target_data,
                    output_folder=output_folder,
                    input_type='nifti', 
                    output_format_info=None,
                    training_embeddings=embeddings,
                    significance_source='prediction',
                    percentile_threshold=10
                )
                
                # Verify expected output files are created
                effects_folder = output_folder / "target_0" / "prediction-effects"
                expected_files = [
                    "low_significance_regions.npy",
                    "high_significance_regions.npy", 
                    "metadata.json"
                ]
                
                for filename in expected_files:
                    file_path = effects_folder / filename
                    assert file_path.exists(), f"Expected file not found: {file_path}"
                
                # Verify regions files exist and are loadable
                low_regions = np.load(effects_folder / "low_significance_regions.npy")
                high_regions = np.load(effects_folder / "high_significance_regions.npy")
                
                # Verify arrays are valid numpy arrays (can be empty if no significant regions found)
                assert isinstance(low_regions, np.ndarray), "Low regions should be a numpy array"
                assert isinstance(high_regions, np.ndarray), "High regions should be a numpy array"