"""
Tests for heatmap visualization functions.

Tests the external plotting functions for prediction and correlation heatmaps
with UMAP scatter overlays and cluster highlighting.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import matplotlib.pyplot as plt
import numpy as np
import pytest

from emuses.tools.heatmap_visualization import (
    plot_prediction_heatmap,
    plot_prediction_cluster_overlay,
    plot_correlation_heatmap,
    plot_correlation_cluster_overlay
)


class TestPredictionHeatmapVisualization:
    """Test prediction heatmap visualization functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        np.random.seed(42)
        self.grid_size = 10  # Small grid for testing
        self.n_samples = 50
        
        # Test data
        self.heatmap_values = np.random.rand(self.grid_size * self.grid_size)
        self.training_embeddings = np.random.rand(self.n_samples, 2)
        self.target_scores = np.random.randn(self.n_samples)
        self.target_name = "test_target"
        self.cluster_sample_indices = np.array([0, 5, 10, 15, 20])  # Some sample indices
        self.cluster_name = "cluster_0"
    
    def test_plot_prediction_heatmap_basic(self):
        """Test basic prediction heatmap creation."""
        with patch('matplotlib.pyplot.show'):  # Prevent actual display
            fig = plot_prediction_heatmap(
                heatmap_values=self.heatmap_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                target_name=self.target_name,
                grid_size=self.grid_size,
                show_plot=False
            )
            
            # Verify figure was created
            assert isinstance(fig, plt.Figure)
            
            # Verify axes setup
            axes = fig.get_axes()
            assert len(axes) >= 1  # At least one axis for main plot
            
            ax = axes[0]
            assert ax.get_xlabel() == "UMAP Dimension 1"
            assert ax.get_ylabel() == "UMAP Dimension 2"
            assert self.target_name in ax.get_title()
            
            plt.close(fig)
    
    def test_plot_prediction_heatmap_file_output(self):
        """Test prediction heatmap saves to file correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_prediction_heatmap.png"
            
            with patch('matplotlib.pyplot.show'):
                fig = plot_prediction_heatmap(
                    heatmap_values=self.heatmap_values,
                    training_embeddings=self.training_embeddings,
                    target_scores=self.target_scores,
                    target_name=self.target_name,
                    output_path=output_path,
                    grid_size=self.grid_size,
                    show_plot=False
                )
                
                # Verify file was saved
                assert output_path.exists()
                assert output_path.stat().st_size > 0
                
                plt.close(fig)
    
    def test_plot_prediction_heatmap_invalid_grid_size(self):
        """Test prediction heatmap with invalid grid size raises error."""
        # Wrong number of heatmap values
        wrong_values = np.random.rand(50)  # Should be 100 for grid_size=10
        
        with pytest.raises(ValueError, match="Expected 100 heatmap values, got 50"):
            plot_prediction_heatmap(
                heatmap_values=wrong_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                target_name=self.target_name,
                grid_size=self.grid_size
            )
    
    def test_plot_prediction_cluster_overlay_basic(self):
        """Test basic prediction cluster overlay creation."""
        with patch('matplotlib.pyplot.show'):
            fig = plot_prediction_cluster_overlay(
                heatmap_values=self.heatmap_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                cluster_sample_indices=self.cluster_sample_indices,
                cluster_name=self.cluster_name,
                target_name=self.target_name,
                significance_type="high",
                grid_size=self.grid_size,
                show_plot=False
            )
            
            # Verify figure was created
            assert isinstance(fig, plt.Figure)
            
            # Verify axes setup
            axes = fig.get_axes()
            assert len(axes) >= 1
            
            ax = axes[0]
            assert ax.get_xlabel() == "UMAP Dimension 1"
            assert ax.get_ylabel() == "UMAP Dimension 2"
            assert self.target_name in ax.get_title()
            assert self.cluster_name in ax.get_title()
            assert "high" in ax.get_title()
            
            plt.close(fig)
    
    def test_plot_prediction_cluster_overlay_empty_cluster(self):
        """Test prediction cluster overlay with empty cluster indices."""
        empty_indices = np.array([])
        
        with patch('matplotlib.pyplot.show'):
            fig = plot_prediction_cluster_overlay(
                heatmap_values=self.heatmap_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                cluster_sample_indices=empty_indices,
                cluster_name=self.cluster_name,
                target_name=self.target_name,
                significance_type="low",
                grid_size=self.grid_size,
                show_plot=False
            )
            
            # Should still create figure without errors
            assert isinstance(fig, plt.Figure)
            plt.close(fig)


class TestCorrelationHeatmapVisualization:
    """Test correlation heatmap visualization functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        np.random.seed(42)
        self.grid_size = 10
        self.n_samples = 50
        
        # Test data - correlations range from -1 to 1
        self.correlation_values = np.random.uniform(-1, 1, self.grid_size * self.grid_size)
        self.training_embeddings = np.random.rand(self.n_samples, 2)
        self.target_scores = np.random.randn(self.n_samples)
        self.target_name = "test_target"
        self.cluster_sample_indices = np.array([1, 6, 11, 16, 21])
        self.cluster_name = "cluster_1"
        self.correlation_method = "pearson"
    
    def test_plot_correlation_heatmap_basic(self):
        """Test basic correlation heatmap creation."""
        with patch('matplotlib.pyplot.show'):
            fig = plot_correlation_heatmap(
                correlation_values=self.correlation_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                target_name=self.target_name,
                correlation_method=self.correlation_method,
                grid_size=self.grid_size,
                show_plot=False
            )
            
            # Verify figure was created
            assert isinstance(fig, plt.Figure)
            
            # Verify axes setup
            axes = fig.get_axes()
            assert len(axes) >= 1
            
            ax = axes[0]
            assert ax.get_xlabel() == "UMAP Dimension 1"
            assert ax.get_ylabel() == "UMAP Dimension 2"
            assert self.target_name in ax.get_title()
            assert "Pearson" in ax.get_title()  # Capitalized correlation method
            
            plt.close(fig)
    
    def test_plot_correlation_heatmap_symmetric_colormap(self):
        """Test correlation heatmap uses symmetric colormap around zero."""
        # Create data with known min/max values
        test_values = np.array([-0.8, -0.2, 0.0, 0.3, 0.9] + [0.0] * 95)  # Pad to 100 values
        
        with patch('matplotlib.pyplot.show'):
            fig = plot_correlation_heatmap(
                correlation_values=test_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                target_name=self.target_name,
                grid_size=self.grid_size,
                show_plot=False
            )
            
            # Find the imshow object
            axes = fig.get_axes()
            images = []
            for ax in axes:
                images.extend(ax.get_images())
            
            if images:
                im = images[0]  # First image should be the heatmap
                # Should be symmetric around 0
                assert im.get_clim()[0] == -im.get_clim()[1]
            
            plt.close(fig)
    
    def test_plot_correlation_cluster_overlay_basic(self):
        """Test basic correlation cluster overlay creation."""
        with patch('matplotlib.pyplot.show'):
            fig = plot_correlation_cluster_overlay(
                correlation_values=self.correlation_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                cluster_sample_indices=self.cluster_sample_indices,
                cluster_name=self.cluster_name,
                target_name=self.target_name,
                correlation_method=self.correlation_method,
                grid_size=self.grid_size,
                show_plot=False
            )
            
            # Verify figure was created
            assert isinstance(fig, plt.Figure)
            
            # Verify axes setup
            axes = fig.get_axes()
            assert len(axes) >= 1
            
            ax = axes[0]
            assert ax.get_xlabel() == "UMAP Dimension 1"
            assert ax.get_ylabel() == "UMAP Dimension 2"
            assert self.target_name in ax.get_title()
            assert self.cluster_name in ax.get_title()
            assert "Pearson" in ax.get_title()
            
            plt.close(fig)
    
    def test_plot_correlation_cluster_overlay_file_output(self):
        """Test correlation cluster overlay saves to file correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_correlation_overlay.png"
            
            with patch('matplotlib.pyplot.show'):
                fig = plot_correlation_cluster_overlay(
                    correlation_values=self.correlation_values,
                    training_embeddings=self.training_embeddings,
                    target_scores=self.target_scores,
                    cluster_sample_indices=self.cluster_sample_indices,
                    cluster_name=self.cluster_name,
                    target_name=self.target_name,
                    output_path=output_path,
                    grid_size=self.grid_size,
                    show_plot=False
                )
                
                # Verify file was saved
                assert output_path.exists()
                assert output_path.stat().st_size > 0
                
                plt.close(fig)


class TestVisualizationParameterValidation:
    """Test parameter validation across visualization functions."""
    
    def setup_method(self):
        """Set up minimal test fixtures."""
        self.grid_size = 5
        self.n_samples = 10
        self.heatmap_values = np.random.rand(self.grid_size * self.grid_size)
        self.correlation_values = np.random.uniform(-1, 1, self.grid_size * self.grid_size)
        self.training_embeddings = np.random.rand(self.n_samples, 2)
        self.target_scores = np.random.randn(self.n_samples)
        self.target_name = "test"
    
    def test_invalid_heatmap_values_length(self):
        """Test all functions validate heatmap values length correctly."""
        wrong_values = np.random.rand(10)  # Should be 25 for grid_size=5
        
        # Test prediction functions
        with pytest.raises(ValueError, match="Expected 25 heatmap values, got 10"):
            plot_prediction_heatmap(
                heatmap_values=wrong_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                target_name=self.target_name,
                grid_size=self.grid_size
            )
        
        with pytest.raises(ValueError, match="Expected 25 heatmap values, got 10"):
            plot_prediction_cluster_overlay(
                heatmap_values=wrong_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                cluster_sample_indices=np.array([0, 1]),
                cluster_name="test_cluster",
                target_name=self.target_name,
                significance_type="high",
                grid_size=self.grid_size
            )
    
    def test_invalid_correlation_values_length(self):
        """Test correlation functions validate correlation values length correctly."""
        wrong_values = np.random.rand(10)  # Should be 25 for grid_size=5
        
        # Test correlation functions
        with pytest.raises(ValueError, match="Expected 25 correlation values, got 10"):
            plot_correlation_heatmap(
                correlation_values=wrong_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                target_name=self.target_name,
                grid_size=self.grid_size
            )
        
        with pytest.raises(ValueError, match="Expected 25 correlation values, got 10"):
            plot_correlation_cluster_overlay(
                correlation_values=wrong_values,
                training_embeddings=self.training_embeddings,
                target_scores=self.target_scores,
                cluster_sample_indices=np.array([0, 1]),
                cluster_name="test_cluster",
                target_name=self.target_name,
                grid_size=self.grid_size
            )
    
    def test_output_path_directory_creation(self):
        """Test all functions create output directories when needed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "nested" / "dir" / "output.png"
            
            # Test prediction heatmap creates directories
            with patch('matplotlib.pyplot.show'):
                fig = plot_prediction_heatmap(
                    heatmap_values=self.heatmap_values,
                    training_embeddings=self.training_embeddings,
                    target_scores=self.target_scores,
                    target_name=self.target_name,
                    output_path=nested_path,
                    grid_size=self.grid_size,
                    show_plot=False
                )
                
                assert nested_path.exists()
                assert nested_path.parent.exists()
                plt.close(fig)


if __name__ == "__main__":
    pytest.main([__file__])