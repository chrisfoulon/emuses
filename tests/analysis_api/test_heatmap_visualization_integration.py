"""
Tests for heatmap visualization integration in HeatmapStage.

Tests that the HeatmapStage properly calls heatmap visualization functions
and creates the expected output files.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import numpy as np
import pytest

from emuses.pipelines.heatmap_stage import HeatmapStage


class TestHeatmapVisualizationIntegration:
    """Test heatmap visualization integration in HeatmapStage."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock config and output format info for HeatmapStage constructor
        mock_config = Mock()
        mock_config.output_folder = Path("/tmp/test")
        
        mock_output_format_info = {
            'affine': np.eye(4),
            'shape': (64, 64, 64),
            'format': 'nifti'
        }
        
        self.heatmap_stage = HeatmapStage(mock_config, mock_output_format_info)
        
        # Test data
        np.random.seed(42)
        self.n_samples = 50
        self.grid_size = 10  # Small grid for testing
        
        self.embeddings = np.random.rand(self.n_samples, 2)
        self.target_matrix = np.random.randn(self.n_samples, 2)  # 2 targets
        self.input_matrix = np.random.randn(self.n_samples, 100)
        
        # Create proper mock trained models with target information
        mock_models = []
        for target_idx in range(2):  # 2 targets
            for fold in range(2):  # 2 models per target (CV folds)
                mock_model = Mock()
                mock_model.predict.return_value = np.random.randn(100)  # Grid predictions
                mock_model.get = Mock(return_value=str(target_idx))  # Target "0" or "1"
                mock_models.append(mock_model)
        
        self.context = {
            "prediction_models": mock_models,
            "input_matrix": self.input_matrix,
            "input_type": "nifti"
        }
        
        self.logger = Mock()
        
    @patch('emuses.pipelines.heatmap_stage.plot_clustering_interactive_with_hover')
    @patch('emuses.tools.region_statistical_analyzer.RegionStatisticalAnalyzer')
    @patch('emuses.tools.correlation_grid_creator.CorrelationGridCreator')
    @patch('emuses.tools.grid_creator.GridCreator')
    def test_heatmap_visualization_integration(
        self, mock_grid_creator, mock_correlation_creator, mock_statistical_analyzer,
        mock_interactive_plot
    ):
        """Test that HeatmapStage calls heatmap visualization functions correctly."""
        
        # Mock grid creators to return test data
        mock_grid_instance = mock_grid_creator.return_value
        mock_grid_instance.create_prediction_heatmaps.return_value = {
            'grid_coordinates': np.random.rand(self.grid_size * self.grid_size, 2),
            'combined_values': np.random.rand(self.grid_size * self.grid_size),  # prediction×confidence
            'artifacts': {}
        }
        
        mock_correlation_instance = mock_correlation_creator.return_value
        mock_correlation_instance.create_correlation_heatmaps.return_value = {
            'grid_coordinates': np.random.rand(self.grid_size * self.grid_size, 2),
            'pearson_correlation': np.random.uniform(-1, 1, self.grid_size * self.grid_size),
            'artifacts': {}
        }
        
        # Mock statistical analyzer
        mock_statistical_instance = mock_statistical_analyzer.return_value
        mock_statistical_instance.create_statistical_maps.return_value = {
            'statistical_results': {},
            'analysis_metadata': {}
        }
        
        # Mock interactive plot to prevent actual file operations
        mock_interactive_plot.return_value = Mock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Mock the visualization functions using patch context managers
            with patch('emuses.tools.heatmap_visualization.plot_prediction_heatmap') as mock_plot_prediction, \
                 patch('emuses.tools.heatmap_visualization.plot_correlation_heatmap') as mock_plot_correlation:
                
                mock_plot_prediction.return_value = Mock()
                mock_plot_correlation.return_value = Mock()
                
                # Execute the method
                self.heatmap_stage._execute_triple_grid_analysis(
                    context=self.context,
                    embeddings=self.embeddings,
                    target_matrix=self.target_matrix,
                    output_folder=output_folder,
                    logger=self.logger
                )
                
                # Verify prediction heatmap visualization was called for each target
                assert mock_plot_prediction.call_count == 2  # 2 targets
                
                # Check first prediction heatmap call
                first_pred_call = mock_plot_prediction.call_args_list[0]
                pred_kwargs = first_pred_call[1]  # keyword arguments
                
                assert 'heatmap_values' in pred_kwargs
                assert 'training_embeddings' in pred_kwargs
                assert 'target_scores' in pred_kwargs
                assert 'target_name' in pred_kwargs
                assert 'output_path' in pred_kwargs
                assert pred_kwargs['show_plot'] is False
                
                # Verify training embeddings passed correctly
                np.testing.assert_array_equal(pred_kwargs['training_embeddings'], self.embeddings)
                
                # Verify correlation heatmap visualization was called for each target
                assert mock_plot_correlation.call_count == 2  # 2 targets
                
                # Check first correlation heatmap call
                first_corr_call = mock_plot_correlation.call_args_list[0]
                corr_kwargs = first_corr_call[1]
                
                assert 'correlation_values' in corr_kwargs
                assert 'training_embeddings' in corr_kwargs
                assert 'target_scores' in corr_kwargs
                assert 'target_name' in corr_kwargs
                assert 'correlation_method' in corr_kwargs
                assert 'output_path' in corr_kwargs
                assert corr_kwargs['show_plot'] is False
                assert corr_kwargs['correlation_method'] == "pearson"
                
                # Verify training embeddings passed correctly
                np.testing.assert_array_equal(corr_kwargs['training_embeddings'], self.embeddings)
    
    @patch('emuses.pipelines.heatmap_stage.plot_clustering_interactive_with_hover')
    @patch('emuses.tools.region_statistical_analyzer.RegionStatisticalAnalyzer')
    @patch('emuses.tools.correlation_grid_creator.CorrelationGridCreator')
    @patch('emuses.tools.grid_creator.GridCreator')
    def test_heatmap_visualization_file_structure(
        self, mock_grid_creator, mock_correlation_creator, mock_statistical_analyzer,
        mock_interactive_plot
    ):
        """Test that heatmap visualizations create proper output file paths."""
        
        # Mock grid creators
        mock_grid_instance = mock_grid_creator.return_value
        mock_grid_instance.create_prediction_heatmaps.return_value = {
            'grid_coordinates': np.random.rand(100, 2),
            'combined_values': np.random.rand(100),
            'artifacts': {}
        }
        
        mock_correlation_instance = mock_correlation_creator.return_value
        mock_correlation_instance.create_correlation_heatmaps.return_value = {
            'grid_coordinates': np.random.rand(100, 2),
            'pearson_correlation': np.random.uniform(-1, 1, 100),
            'artifacts': {}
        }
        
        # Mock statistical analyzer
        mock_statistical_instance = mock_statistical_analyzer.return_value
        mock_statistical_instance.create_statistical_maps.return_value = {
            'statistical_results': {},
            'analysis_metadata': {}
        }
        
        # Mock interactive plot
        mock_interactive_plot.return_value = Mock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Mock the visualization functions using patch context managers
            with patch('emuses.tools.heatmap_visualization.plot_prediction_heatmap') as mock_plot_prediction, \
                 patch('emuses.tools.heatmap_visualization.plot_correlation_heatmap') as mock_plot_correlation:
                
                mock_plot_prediction.return_value = Mock()
                mock_plot_correlation.return_value = Mock()
                
                # Execute the method
                self.heatmap_stage._execute_triple_grid_analysis(
                    context=self.context,
                    embeddings=self.embeddings,
                    target_matrix=self.target_matrix,
                    output_folder=output_folder,
                    logger=self.logger
                )
                
                # Verify output paths follow expected structure
                for call in mock_plot_prediction.call_args_list:
                    output_path = call[1]['output_path']
                    path_obj = Path(output_path)
                    
                    # Should be in target_*/heatmap_visualizations/ folder
                    assert "target_" in str(path_obj)
                    assert "heatmap_visualizations" in str(path_obj)
                    assert path_obj.name.startswith("prediction_heatmap_")
                    assert path_obj.suffix == ".png"
                
                for call in mock_plot_correlation.call_args_list:
                    output_path = call[1]['output_path']
                    path_obj = Path(output_path)
                    
                    # Should be in target_*/heatmap_visualizations/ folder
                    assert "target_" in str(path_obj)
                    assert "heatmap_visualizations" in str(path_obj)
                    assert path_obj.name.startswith("correlation_heatmap_")
                    assert path_obj.suffix == ".png"
    
    @patch('emuses.pipelines.heatmap_stage.plot_clustering_interactive_with_hover')
    @patch('emuses.tools.region_statistical_analyzer.RegionStatisticalAnalyzer')
    @patch('emuses.tools.correlation_grid_creator.CorrelationGridCreator')
    @patch('emuses.tools.grid_creator.GridCreator')
    def test_heatmap_visualization_error_handling(
        self, mock_grid_creator, mock_correlation_creator, mock_statistical_analyzer,
        mock_interactive_plot
    ):
        """Test that heatmap visualization errors are handled gracefully."""
        
        # Mock grid creators
        mock_grid_instance = mock_grid_creator.return_value
        mock_grid_instance.create_prediction_heatmaps.return_value = {
            'grid_coordinates': np.random.rand(100, 2),
            'combined_values': np.random.rand(100),
            'artifacts': {}
        }
        
        mock_correlation_instance = mock_correlation_creator.return_value
        mock_correlation_instance.create_correlation_heatmaps.return_value = {
            'grid_coordinates': np.random.rand(100, 2),
            'pearson_correlation': np.random.uniform(-1, 1, 100),
            'artifacts': {}
        }
        
        # Mock statistical analyzer
        mock_statistical_instance = mock_statistical_analyzer.return_value
        mock_statistical_instance.create_statistical_maps.return_value = {
            'statistical_results': {},
            'analysis_metadata': {}
        }
        
        # Mock interactive plot
        mock_interactive_plot.return_value = Mock()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Mock the visualization functions using patch context managers
            with patch('emuses.tools.heatmap_visualization.plot_prediction_heatmap') as mock_plot_prediction, \
                 patch('emuses.tools.heatmap_visualization.plot_correlation_heatmap') as mock_plot_correlation:
                
                # Mock visualization functions to raise errors
                mock_plot_prediction.side_effect = Exception("Visualization failed")
                mock_plot_correlation.return_value = Mock()
                
                # Should not raise exception, just log error
                self.heatmap_stage._execute_triple_grid_analysis(
                    context=self.context,
                    embeddings=self.embeddings,
                    target_matrix=self.target_matrix,
                    output_folder=output_folder,
                    logger=self.logger
                )
                
                # Verify error was logged
                error_calls = [call for call in self.logger.error.call_args_list 
                              if "Heatmap visualization failed" in str(call)]
                assert len(error_calls) > 0
                
                # Verify interactive visualization still continued after heatmap error
                assert mock_interactive_plot.call_count == 2  # Should still be called for both targets


if __name__ == "__main__":
    pytest.main([__file__])