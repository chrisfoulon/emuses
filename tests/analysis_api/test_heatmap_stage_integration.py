"""
Test cases for HeatmapStage triple grid analysis integration.

Tests the dual RegionStatisticalAnalyzer calls with enhanced create_statistical_maps method.
"""

import unittest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
import shutil

from emuses.pipelines.heatmap_stage import HeatmapStage


class TestHeatmapStageTripleGridIntegration(unittest.TestCase):
    """Test the updated _execute_triple_grid_analysis method with dual analysis pattern."""

    @classmethod
    def setUpClass(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values

    def setUp(self):
        """Set up test data."""
        # Create temporary directory for outputs
        self.temp_dir = tempfile.mkdtemp()
        self.output_folder = Path(self.temp_dir)
        
        # Use real data patterns
        # Embeddings (rescaled to 0-1 range as required for heatmaps)
        raw_embeddings = self.features[:100, :2]
        self.embeddings = (raw_embeddings - raw_embeddings.min(axis=0)) / (raw_embeddings.max(axis=0) - raw_embeddings.min(axis=0))
        
        # Target matrix (2 targets, scaled to [0, 1])
        target_col_1 = self.targets[:100, 0] if self.targets.shape[1] > 0 else self.features[:100, 0]
        target_col_2 = self.targets[:100, 1] if self.targets.shape[1] > 1 else self.features[:100, 1]
        # Scale to [0, 1] range
        target_col_1 = (target_col_1 - target_col_1.min()) / (target_col_1.max() - target_col_1.min())
        target_col_2 = (target_col_2 - target_col_2.min()) / (target_col_2.max() - target_col_2.min())
        self.target_matrix = np.column_stack([target_col_1, target_col_2])
        
        # Input matrix (scaled to [0, 1])
        base_input = np.tile(self.features[:100, :], (1, 5))[:, :500]  # Tile to get 500 features
        self.input_matrix = (base_input - base_input.min()) / (base_input.max() - base_input.min())
        
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
        
        # Mock return values for prediction and correlation results using real data patterns
        grid_points = 10000
        
        # Use real data for grid coordinates (rescaled to 0-1 range)
        base_coords = np.tile(self.features[:5000, :2], (2, 1))  # Tile to get 10000 points
        grid_coords = (base_coords - base_coords.min(axis=0)) / (base_coords.max(axis=0) - base_coords.min(axis=0))
        
        # Use real data for combined values (scaled to [0, 1])
        base_combined = np.tile(self.features[:5000, 0], 2)  # 10000 values
        combined_values = (base_combined - base_combined.min()) / (base_combined.max() - base_combined.min())
        
        # Use real data for correlation values (scaled to [-1, 1] with mix of positive/negative)
        base_corr = np.tile(self.targets[:5000, 0], 2) if self.targets.shape[1] > 0 else np.tile(self.features[:5000, 0], 2)
        correlation_values = 2 * (base_corr - base_corr.min()) / (base_corr.max() - base_corr.min()) - 1
        
        prediction_results = {
            'grid_coordinates': grid_coords,
            'combined_values': combined_values
        }
        correlation_results = {
            'grid_coordinates': grid_coords, 
            'pearson_correlation': correlation_values
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
        
        # Mock return values using real data patterns
        grid_points = 10000
        
        # Use real data for grid coordinates (rescaled to 0-1 range)
        base_coords = np.tile(self.features[:5000, :2], (2, 1))  # Tile to get 10000 points
        grid_coords = (base_coords - base_coords.min(axis=0)) / (base_coords.max(axis=0) - base_coords.min(axis=0))
        
        # Use real data for combined values (scaled to [0, 1])
        base_combined = np.tile(self.features[:5000, 0], 2)  # 10000 values
        combined_values = (base_combined - base_combined.min()) / (base_combined.max() - base_combined.min())
        
        # Use real data for correlation values (scaled to [-1, 1])
        base_corr = np.tile(self.targets[:5000, 0], 2) if self.targets.shape[1] > 0 else np.tile(self.features[:5000, 0], 2)
        correlation_values = 2 * (base_corr - base_corr.min()) / (base_corr.max() - base_corr.min()) - 1
        
        prediction_results = {
            'grid_coordinates': grid_coords,
            'combined_values': combined_values  # prediction×confidence values
        }
        correlation_results = {
            'grid_coordinates': grid_coords,
            'pearson_correlation': correlation_values
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
        
        # Create specific correlation values with negative values to test absolute value processing
        correlation_values = np.array([-0.8, -0.3, 0.1, 0.6, -0.9])
        
        # Use real data for grid coordinates (rescaled to 0-1 range)
        base_coords = self.features[:5, :2]
        grid_coords = (base_coords - base_coords.min(axis=0)) / (base_coords.max(axis=0) - base_coords.min(axis=0))
        
        # Use real data for combined values (scaled to [0, 1])
        base_combined = self.features[:5, 0]
        combined_values = (base_combined - base_combined.min()) / (base_combined.max() - base_combined.min())
        
        prediction_results = {
            'grid_coordinates': grid_coords,
            'combined_values': combined_values
        }
        correlation_results = {
            'grid_coordinates': grid_coords,
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