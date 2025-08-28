"""
Tests for correlation grid creation functionality in Task 1.2.

This module tests the CorrelationGridCreator class that generates GWD-based 
correlation analysis with sigma optimization and multiple correlation methods.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import numpy as np
import pytest

from emuses.tools.correlation_grid_creator import CorrelationGridCreator


class TestCorrelationGridCreator(unittest.TestCase):
    """Test basic initialization and configuration of CorrelationGridCreator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.grid_size = 50  # Smaller grid for faster tests
        self.creator = CorrelationGridCreator(grid_size=self.grid_size)
        
        # Create test embeddings (0-1 range)
        np.random.seed(42)
        self.embeddings = np.random.uniform(0, 1, (20, 2))
        self.target_scores = np.random.uniform(-2, 2, 20)
        
    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        creator = CorrelationGridCreator()
        self.assertEqual(creator.grid_size, 100)
        self.assertEqual(creator.correlation_methods, ["pearson", "spearman"])
        self.assertIsNone(creator.sigma)
        
    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        creator = CorrelationGridCreator(
            grid_size=75,
            correlation_methods=["pearson", "point_biserial"],
            sigma=0.5
        )
        self.assertEqual(creator.grid_size, 75)
        self.assertEqual(creator.correlation_methods, ["pearson", "point_biserial"])
        self.assertEqual(creator.sigma, 0.5)
        
    def test_init_invalid_correlation_methods(self):
        """Test initialization with invalid correlation methods raises ValueError."""
        with self.assertRaises(ValueError) as context:
            CorrelationGridCreator(correlation_methods=["invalid_method"])
        self.assertIn("Invalid correlation method", str(context.exception))
        
    def test_init_invalid_sigma(self):
        """Test initialization with invalid sigma raises ValueError."""
        with self.assertRaises(ValueError):
            CorrelationGridCreator(sigma=-1.0)
        with self.assertRaises(ValueError):
            CorrelationGridCreator(sigma=0.0)


class TestSigmaOptimization(unittest.TestCase):
    """Test sigma optimization functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.creator = CorrelationGridCreator(grid_size=50)
        np.random.seed(42)
        self.embeddings = np.random.uniform(0, 1, (20, 2))
        self.target_scores = np.random.uniform(-2, 2, 20)
        
    @patch('emuses.tools.correlation_grid_creator.compute_sigma_median')
    def test_optimize_sigma_median_method(self, mock_compute_sigma):
        """Test sigma optimization using median method."""
        mock_compute_sigma.return_value = 0.3
        
        sigma = self.creator.optimize_sigma(self.embeddings, method="median")
        
        self.assertEqual(sigma, 0.3)
        mock_compute_sigma.assert_called_once_with(self.embeddings, sample_size=0)
        
    def test_optimize_sigma_invalid_method(self):
        """Test sigma optimization with invalid method raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.creator.optimize_sigma(self.embeddings, method="invalid")
        self.assertIn("Unknown sigma optimization method", str(context.exception))


class TestGWDVectorComputation(unittest.TestCase):
    """Test GWD vector computation for grid points."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.creator = CorrelationGridCreator(grid_size=50, sigma=0.2)
        np.random.seed(42)
        self.embeddings = np.random.uniform(0, 1, (20, 2))
        self.grid_coords = np.array([[0.1, 0.2], [0.5, 0.8], [0.9, 0.1]])
        
    @patch('emuses.tools.correlation_grid_creator.compute_gwd_for_point')
    def test_compute_gwd_vectors_for_grid(self, mock_gwd):
        """Test GWD vector computation for grid points."""
        # Mock GWD computation to return different values for each point
        mock_gwd.side_effect = [
            np.array([0.8, 0.3, 0.1, 0.9, 0.2] + [0.1] * 15),  # Point 1
            np.array([0.1, 0.7, 0.9, 0.2, 0.6] + [0.1] * 15),  # Point 2 
            np.array([0.9, 0.1, 0.8, 0.3, 0.4] + [0.1] * 15),  # Point 3
        ]
        
        gwd_vectors = self.creator.compute_gwd_vectors_for_grid(
            self.grid_coords, self.embeddings
        )
        
        # Should call compute_gwd_for_point for each grid point
        self.assertEqual(mock_gwd.call_count, 3)
        self.assertEqual(gwd_vectors.shape, (3, 20))  # 3 grid points x 20 embeddings
        
        # Verify each call
        for i, call in enumerate(mock_gwd.call_args_list):
            np.testing.assert_array_equal(call[0][1], self.grid_coords[i])  # coord arg
            self.assertEqual(call[0][2], 0.2)  # sigma arg
            
    def test_compute_gwd_vectors_no_sigma_raises_error(self):
        """Test GWD computation without sigma raises ValueError."""
        creator = CorrelationGridCreator(sigma=None)
        
        with self.assertRaises(ValueError) as context:
            creator.compute_gwd_vectors_for_grid(self.grid_coords, self.embeddings)
        self.assertIn("Sigma must be set", str(context.exception))


class TestCorrelationMethods(unittest.TestCase):
    """Test multiple correlation methods implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.creator = CorrelationGridCreator(
            correlation_methods=["pearson", "spearman", "point_biserial"]
        )
        
        # Create test data with known correlation patterns
        np.random.seed(42)
        self.n_points = 20
        
        # GWD vectors for 3 grid points
        self.gwd_vectors = np.random.uniform(0, 1, (3, self.n_points))
        
        # Target scores with some correlation structure
        self.target_scores = np.random.uniform(-2, 2, self.n_points)
        
    def test_compute_correlations_pearson(self):
        """Test Pearson correlation computation."""
        correlations = self.creator.compute_correlations(
            self.gwd_vectors, self.target_scores, methods=["pearson"]
        )
        
        self.assertIn("pearson", correlations)
        self.assertEqual(len(correlations["pearson"]), 3)  # 3 grid points
        self.assertTrue(all(-1 <= corr <= 1 for corr in correlations["pearson"]))
        
    def test_compute_correlations_multiple_methods(self):
        """Test multiple correlation methods computation."""
        correlations = self.creator.compute_correlations(
            self.gwd_vectors, self.target_scores, 
            methods=["pearson", "spearman", "point_biserial"]
        )
        
        # All methods should be present
        self.assertIn("pearson", correlations)
        self.assertIn("spearman", correlations)
        self.assertIn("point_biserial", correlations)
        
        # All should have same number of values (grid points)
        for method in correlations:
            self.assertEqual(len(correlations[method]), 3)
            
    def test_compute_correlations_invalid_method(self):
        """Test correlation computation with invalid method raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.creator.compute_correlations(
                self.gwd_vectors, self.target_scores, methods=["invalid"]
            )
        self.assertIn("Unknown correlation method", str(context.exception))


class TestCorrelationHeatmapGeneration(unittest.TestCase):
    """Test correlation heatmap generation with target score analysis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.creator = CorrelationGridCreator(grid_size=10, sigma=0.2)  # Very small grid for testing
        
        np.random.seed(42)
        self.embeddings = np.random.uniform(0, 1, (15, 2))
        self.target_data = {
            "target_0": np.random.uniform(-2, 2, 15),
            "target_1": np.random.uniform(0, 5, 15)
        }
        
    @patch('emuses.tools.correlation_grid_creator.compute_gwd_for_point')
    def test_create_correlation_heatmaps_basic(self, mock_gwd):
        """Test basic correlation heatmap creation."""
        # Mock GWD to return simple patterns
        mock_gwd.return_value = np.random.uniform(0, 1, 15)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            results = self.creator.create_correlation_heatmaps(
                self.embeddings, self.target_data, output_folder
            )
            
            # Should have results for both targets
            self.assertIn("correlation_results", results)
            self.assertIn("target_0", results["correlation_results"])
            self.assertIn("target_1", results["correlation_results"])
            
            # Check basic structure
            for target_name in ["target_0", "target_1"]:
                target_result = results["correlation_results"][target_name]
                self.assertIn("correlations", target_result)
                self.assertIn("artifacts", target_result)
                
                # Should have correlation values for each method
                for method in self.creator.correlation_methods:
                    self.assertIn(method, target_result["correlations"])
                    
    def test_create_correlation_heatmaps_file_structure(self):
        """Test that correlation heatmaps create proper file structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            with patch('emuses.tools.correlation_grid_creator.compute_gwd_for_point') as mock_gwd:
                mock_gwd.return_value = np.random.uniform(0, 1, 15)
                
                results = self.creator.create_correlation_heatmaps(
                    self.embeddings, self.target_data, output_folder
                )
                
                # Check directory structure
                for target_name in ["target_0", "target_1"]:
                    target_dir = output_folder / f"target_{target_name}" / "correlation-grids"
                    self.assertTrue(target_dir.exists())
                    
                    # Check for correlation files  
                    for method in self.creator.correlation_methods:
                        correlation_file = target_dir / f"correlation_values_{method}.npy"
                        self.assertTrue(correlation_file.exists())
                        
                    # Check metadata file
                    metadata_file = target_dir / "correlation_metadata.json"
                    self.assertTrue(metadata_file.exists())
                    
    def test_create_correlation_heatmaps_with_sigma_optimization(self):
        """Test correlation heatmap creation with sigma optimization."""
        creator = CorrelationGridCreator(grid_size=10, sigma=None)  # No preset sigma
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            with patch('emuses.tools.correlation_grid_creator.compute_sigma_median') as mock_sigma:
                mock_sigma.return_value = 0.25
                
                with patch('emuses.tools.correlation_grid_creator.compute_gwd_for_point') as mock_gwd:
                    mock_gwd.return_value = np.random.uniform(0, 1, 15)
                    
                    results = creator.create_correlation_heatmaps(
                        self.embeddings, self.target_data, output_folder,
                        optimize_sigma=True
                    )
                    
                    # Should have optimized sigma
                    self.assertEqual(creator.sigma, 0.25)
                    mock_sigma.assert_called_once_with(self.embeddings, sample_size=0)


if __name__ == "__main__":
    unittest.main()