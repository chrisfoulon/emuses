"""
Test dual effect size maps implementation with symmetric percentile thresholds.

Tests the enhanced RegionStatisticalAnalyzer for dual analysis pattern with
configurable percentile thresholds and significance source differentiation.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from emuses.tools.region_statistical_analyzer import RegionStatisticalAnalyzer


class TestDualEffectAnalysis:
    """Test enhanced RegionStatisticalAnalyzer for dual analysis with percentile thresholds."""

    def test_significance_source_parameter(self):
        """
        Test RegionStatisticalAnalyzer supports significance_source parameter for dual analysis.
        
        This test verifies Task 3.2.a.1: Add significance_source parameter to create_statistical_maps().
        """
        analyzer = RegionStatisticalAnalyzer()
        
        # Setup test data
        grid_coords = np.random.rand(100, 2)
        prediction_values = np.random.rand(100)
        confidence_values = np.random.rand(100)
        correlation_values = np.random.rand(100)
        input_matrix = np.random.rand(50, 1000)
        target_data = {'0': np.random.rand(50)}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Mock the input_matrix_stat_map function to avoid real computation
            with patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map') as mock_stat_map:
                mock_stat_map.return_value = (
                    np.random.rand(1000),  # stat_map
                    np.random.rand(1000),  # pval_map  
                    np.random.rand(1000)   # effect_size_map
                )
                
                # Test prediction significance source
                results_prediction = analyzer.create_statistical_maps(
                    grid_coords=grid_coords,
                    significance_values=prediction_values * confidence_values,  # prediction×confidence
                    input_matrix=input_matrix,
                    target_data=target_data,
                    output_folder=output_folder,
                    input_type='nifti',
                    output_format_info=None,
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
        Test RegionStatisticalAnalyzer supports percentile_threshold for symmetric ranges.
        
        This test verifies Task 3.2.a.2: Add percentile_threshold parameter for symmetric range.
        """
        analyzer = RegionStatisticalAnalyzer()
        
        # Setup test data with known distribution
        significance_values = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0] * 10)  # 100 values
        grid_coords = np.random.rand(100, 2)
        input_matrix = np.random.rand(50, 1000)
        target_data = {'0': np.random.rand(50)}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            with patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map') as mock_stat_map:
                mock_stat_map.return_value = (np.random.rand(1000), np.random.rand(1000), np.random.rand(1000))
                
                # Test with 5% threshold (should identify values < 5th percentile AND > 95th percentile)
                results = analyzer.create_statistical_maps(
                    grid_coords=grid_coords,
                    significance_values=significance_values,
                    input_matrix=input_matrix,
                    target_data=target_data,
                    output_folder=output_folder,
                    input_type='nifti',
                    output_format_info=None,
                    significance_source='prediction',
                    percentile_threshold=5
                )
                
                # Verify percentile threshold is recorded in metadata
                assert 'percentile_threshold' in results['analysis_metadata']
                assert results['analysis_metadata']['percentile_threshold'] == 5
                
                # Verify computed percentile ranges are recorded
                assert 'low_percentile_threshold' in results['analysis_metadata']
                assert 'high_percentile_threshold' in results['analysis_metadata']
                assert results['analysis_metadata']['low_percentile_threshold'] == np.percentile(significance_values, 5)
                assert results['analysis_metadata']['high_percentile_threshold'] == np.percentile(significance_values, 95)

    def test_dual_output_files_creation(self):
        """
        Test that dual analysis creates separate output files for low and high significance regions.
        
        This test verifies the expected file structure with low_significance_regions.npy and 
        high_significance_regions.npy outputs.
        """
        analyzer = RegionStatisticalAnalyzer()
        
        # Setup test data
        grid_coords = np.random.rand(100, 2) 
        significance_values = np.random.rand(100)
        input_matrix = np.random.rand(50, 1000)
        target_data = {'0': np.random.rand(50)}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            with patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map') as mock_stat_map:
                mock_stat_map.return_value = (np.random.rand(1000), np.random.rand(1000), np.random.rand(1000))
                
                # Run dual analysis
                results = analyzer.create_statistical_maps(
                    grid_coords=grid_coords,
                    significance_values=significance_values,
                    input_matrix=input_matrix,
                    target_data=target_data,
                    output_folder=output_folder,
                    input_type='nifti', 
                    output_format_info=None,
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
                
                # Verify low and high regions are actually different
                low_regions = np.load(effects_folder / "low_significance_regions.npy")
                high_regions = np.load(effects_folder / "high_significance_regions.npy")
                
                # Should not be identical (unless by extreme coincidence)
                assert not np.array_equal(low_regions, high_regions), "Low and high regions should be different"