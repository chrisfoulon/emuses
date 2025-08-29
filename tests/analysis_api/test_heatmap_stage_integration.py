"""
Test cases for HeatmapStage triple grid analysis integration.

Tests the dual RegionStatisticalAnalyzer calls with enhanced create_statistical_maps method.
"""

import unittest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import shutil

from emuses.pipelines.heatmap_stage import HeatmapStage


class TestHeatmapStageTripleGridIntegration(unittest.TestCase):
    """Test the updated _execute_triple_grid_analysis method with dual analysis pattern."""

    def setUp(self):
        """Set up test data."""
        # Create temporary directory for outputs
        self.temp_dir = tempfile.mkdtemp()
        self.output_folder = Path(self.temp_dir)
        
        # Mock data
        self.embeddings = np.random.rand(100, 2)
        self.target_matrix = np.random.rand(100, 2)
        self.input_matrix = np.random.rand(100, 500)
        
        # Mock context with trained models
        self.context = {
            "prediction_models": [
                {"target": "target_0", "model": "mock_model_0"},
                {"target": "target_1", "model": "mock_model_1"}
            ],
            "prediction_train_features": self.input_matrix
        }
        
        # Mock logger
        self.logger = Mock()
        
        # Create HeatmapStage instance with required parameters
        mock_config = Mock()
        mock_output_format_info = Mock()
        self.heatmap_stage = HeatmapStage(mock_config, mock_output_format_info)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    @patch('emuses.tools.region_statistical_analyzer.RegionStatisticalAnalyzer')
    @patch('emuses.tools.correlation_grid_creator.CorrelationGridCreator')
    @patch('emuses.tools.grid_creator.GridCreator')
    def test_dual_statistical_analysis_calls(self, mock_grid_creator, mock_correlation_creator, mock_statistical_analyzer):
        """Test that RegionStatisticalAnalyzer.create_statistical_maps is called twice with different significance sources."""
        
        # Mock the creator instances and their methods
        mock_grid_instance = Mock()
        mock_correlation_instance = Mock()
        mock_statistical_instance = Mock()
        
        mock_grid_creator.return_value = mock_grid_instance
        mock_correlation_creator.return_value = mock_correlation_instance
        mock_statistical_analyzer.return_value = mock_statistical_instance
        
        # Mock return values for prediction and correlation results
        prediction_results = {
            'grid_coordinates': np.random.rand(10000, 2),
            'combined_values': np.random.rand(10000)
        }
        correlation_results = {
            'grid_coordinates': np.random.rand(10000, 2), 
            'pearson_correlation': np.random.rand(10000) - 0.5  # Mix of positive/negative
        }
        
        mock_grid_instance.create_prediction_heatmaps.return_value = prediction_results
        mock_correlation_instance.create_correlation_heatmaps.return_value = correlation_results
        
        # Execute the method
        self.heatmap_stage._execute_triple_grid_analysis(
            context=self.context,
            embeddings=self.embeddings,
            target_matrix=self.target_matrix,
            output_folder=self.output_folder,
            logger=self.logger
        )
        
        # Verify RegionStatisticalAnalyzer.create_statistical_maps was called twice
        # Should be called once per target (2 targets) * 2 analyses (prediction + correlation) = 4 calls total
        self.assertEqual(mock_statistical_instance.create_statistical_maps.call_count, 4)
        
        # Get all the calls
        calls = mock_statistical_instance.create_statistical_maps.call_args_list
        
        # Verify calls contain both 'prediction' and 'correlation' significance sources
        prediction_calls = [call for call in calls if call[1]['significance_source'] == 'prediction']
        correlation_calls = [call for call in calls if call[1]['significance_source'] == 'correlation']
        
        self.assertEqual(len(prediction_calls), 2)  # One per target
        self.assertEqual(len(correlation_calls), 2)  # One per target
        
        # Verify all calls have the required parameters
        for call in calls:
            args, kwargs = call
            self.assertIn('grid_coords', kwargs)
            self.assertIn('significance_values', kwargs)
            self.assertIn('input_matrix', kwargs)
            self.assertIn('target_data', kwargs)
            self.assertIn('output_folder', kwargs)
            self.assertIn('training_embeddings', kwargs)
            self.assertIn('significance_source', kwargs)
            self.assertIn('percentile_threshold', kwargs)

    @patch('emuses.tools.region_statistical_analyzer.RegionStatisticalAnalyzer')
    @patch('emuses.tools.correlation_grid_creator.CorrelationGridCreator')
    @patch('emuses.tools.grid_creator.GridCreator')
    def test_prediction_significance_values_processing(self, mock_grid_creator, mock_correlation_creator, mock_statistical_analyzer):
        """Test that prediction analysis uses combined_values (prediction×confidence)."""
        
        # Setup mocks
        mock_grid_instance = Mock()
        mock_correlation_instance = Mock()
        mock_statistical_instance = Mock()
        
        mock_grid_creator.return_value = mock_grid_instance
        mock_correlation_creator.return_value = mock_correlation_instance
        mock_statistical_analyzer.return_value = mock_statistical_instance
        
        # Mock return values
        prediction_results = {
            'grid_coordinates': np.random.rand(10000, 2),
            'combined_values': np.random.rand(10000)  # prediction×confidence values
        }
        correlation_results = {
            'grid_coordinates': np.random.rand(10000, 2),
            'pearson_correlation': np.random.rand(10000) - 0.5
        }
        
        mock_grid_instance.create_prediction_heatmaps.return_value = prediction_results
        mock_correlation_instance.create_correlation_heatmaps.return_value = correlation_results
        
        # Execute with single target for simplicity
        single_target_matrix = self.target_matrix[:, :1]
        
        self.heatmap_stage._execute_triple_grid_analysis(
            context=self.context,
            embeddings=self.embeddings,
            target_matrix=single_target_matrix,
            output_folder=self.output_folder,
            logger=self.logger
        )
        
        # Get prediction analysis call
        calls = mock_statistical_instance.create_statistical_maps.call_args_list
        prediction_call = [call for call in calls if call[1]['significance_source'] == 'prediction'][0]
        
        # Verify prediction analysis uses combined_values
        np.testing.assert_array_equal(
            prediction_call[1]['significance_values'],
            prediction_results['combined_values']
        )

    @patch('emuses.tools.region_statistical_analyzer.RegionStatisticalAnalyzer')
    @patch('emuses.tools.correlation_grid_creator.CorrelationGridCreator')
    @patch('emuses.tools.grid_creator.GridCreator')
    def test_correlation_significance_values_processing(self, mock_grid_creator, mock_correlation_creator, mock_statistical_analyzer):
        """Test that correlation analysis uses absolute correlation values."""
        
        # Setup mocks
        mock_grid_instance = Mock()
        mock_correlation_instance = Mock()
        mock_statistical_instance = Mock()
        
        mock_grid_creator.return_value = mock_grid_instance
        mock_correlation_creator.return_value = mock_correlation_instance
        mock_statistical_analyzer.return_value = mock_statistical_instance
        
        # Mock return values with negative correlations to test absolute value processing
        correlation_values = np.array([-0.8, -0.3, 0.1, 0.6, -0.9])
        prediction_results = {
            'grid_coordinates': np.random.rand(5, 2),
            'combined_values': np.random.rand(5)
        }
        correlation_results = {
            'grid_coordinates': np.random.rand(5, 2),
            'pearson_correlation': correlation_values
        }
        
        mock_grid_instance.create_prediction_heatmaps.return_value = prediction_results
        mock_correlation_instance.create_correlation_heatmaps.return_value = correlation_results
        
        # Execute with single target
        single_target_matrix = self.target_matrix[:, :1]
        
        self.heatmap_stage._execute_triple_grid_analysis(
            context=self.context,
            embeddings=self.embeddings,
            target_matrix=single_target_matrix,
            output_folder=self.output_folder,
            logger=self.logger
        )
        
        # Get correlation analysis call
        calls = mock_statistical_instance.create_statistical_maps.call_args_list
        correlation_call = [call for call in calls if call[1]['significance_source'] == 'correlation'][0]
        
        # Verify correlation analysis uses absolute values
        expected_abs_correlation = np.abs(correlation_values)
        np.testing.assert_array_equal(
            correlation_call[1]['significance_values'],
            expected_abs_correlation
        )


if __name__ == '__main__':
    unittest.main()