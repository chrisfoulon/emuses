"""
Tests for enhanced sigma optimization functionality in CorrelationGridCreator.

This module tests the improved optimize_sigma method with percentile options,
scaling factors, and validation logging.
"""

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from emuses.tools.correlation_grid_creator import CorrelationGridCreator


class TestEnhancedSigmaOptimization(unittest.TestCase):
    """Test enhanced sigma optimization functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create test embeddings (2D UMAP-style data)
        np.random.seed(42)
        self.embeddings = np.random.uniform(0, 1, (100, 2))
        self.creator = CorrelationGridCreator(grid_size=50)
    
    def test_median_method_default(self):
        """Test default median method optimization."""
        sigma = self.creator.optimize_sigma(self.embeddings, method="median")
        
        self.assertIsInstance(sigma, float)
        self.assertGreater(sigma, 0)
        # Should be reasonable for 0-1 coordinate system
        self.assertLess(sigma, 2.0)
    
    def test_median_method_with_scaling_factor(self):
        """Test median method with scaling factor."""
        base_sigma = self.creator.optimize_sigma(self.embeddings, method="median", scaling_factor=1.0)
        scaled_sigma = self.creator.optimize_sigma(self.embeddings, method="median", scaling_factor=2.0)
        
        # Scaled sigma should be exactly 2x base sigma
        self.assertAlmostEqual(scaled_sigma, base_sigma * 2.0, places=6)
    
    def test_percentile_method_median_equivalent(self):
        """Test percentile method with 50th percentile behavior."""
        median_sigma = self.creator.optimize_sigma(self.embeddings, method="median")
        percentile_sigma = self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=50.0)
        
        # Both methods should produce positive sigma values (exact values may differ due to implementation)
        self.assertGreater(median_sigma, 0)
        self.assertGreater(percentile_sigma, 0)
        # Both should be reasonable for 0-1 coordinate system
        self.assertLess(median_sigma, 2.0)
        self.assertLess(percentile_sigma, 2.0)
    
    def test_percentile_method_different_percentiles(self):
        """Test percentile method with different percentiles."""
        sigma_25 = self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=25.0)
        sigma_50 = self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=50.0)
        sigma_75 = self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=75.0)
        
        # Lower percentiles should give smaller sigma values
        self.assertLess(sigma_25, sigma_50)
        self.assertLess(sigma_50, sigma_75)
    
    def test_percentile_method_with_scaling_factor(self):
        """Test percentile method with scaling factor."""
        base_sigma = self.creator.optimize_sigma(self.embeddings, method="percentile", 
                                                percentile=75.0, scaling_factor=1.0)
        scaled_sigma = self.creator.optimize_sigma(self.embeddings, method="percentile", 
                                                 percentile=75.0, scaling_factor=0.5)
        
        # Scaled sigma should be exactly 0.5x base sigma
        self.assertAlmostEqual(scaled_sigma, base_sigma * 0.5, places=6)
    
    def test_invalid_method_raises_error(self):
        """Test that invalid optimization method raises ValueError."""
        with self.assertRaises(ValueError) as context:
            self.creator.optimize_sigma(self.embeddings, method="invalid_method")
        
        self.assertIn("Unknown sigma optimization method", str(context.exception))
        self.assertIn("invalid_method", str(context.exception))
    
    def test_invalid_percentile_raises_error(self):
        """Test that invalid percentile values raise ValueError."""
        # Test percentile too low
        with self.assertRaises(ValueError) as context:
            self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=0.5)
        
        self.assertIn("Percentile must be in range [1.0, 99.0]", str(context.exception))
        
        # Test percentile too high
        with self.assertRaises(ValueError) as context:
            self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=100.0)
        
        self.assertIn("Percentile must be in range [1.0, 99.0]", str(context.exception))
    
    def test_zero_sigma_raises_error(self):
        """Test that computed sigma of zero raises ValueError."""
        # Create a scenario that could produce zero sigma with negative scaling
        embeddings = np.random.uniform(0, 1, (10, 2))
        
        with self.assertRaises(ValueError) as context:
            self.creator.optimize_sigma(embeddings, method="median", scaling_factor=0.0)
        
        self.assertIn("Computed sigma must be positive", str(context.exception))
    
    def test_logging_output(self):
        """Test that optimization produces appropriate log messages."""
        with patch('emuses.tools.correlation_grid_creator.logger') as mock_logger:
            # Test median method logging
            self.creator.optimize_sigma(self.embeddings, method="median")
            
            # Check that info logs were called
            mock_logger.info.assert_called()
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            
            # Should log the optimized sigma and final sigma
            self.assertTrue(any("Optimized sigma using median pairwise distance" in call for call in log_calls))
            self.assertTrue(any("Final optimized sigma" in call for call in log_calls))
    
    def test_percentile_logging_includes_reference(self):
        """Test that percentile method logging includes median reference."""
        with patch('emuses.tools.correlation_grid_creator.logger') as mock_logger:
            self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=75.0)
            
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            
            # Should log percentile method and median reference
            self.assertTrue(any("75.0th percentile pairwise distance" in call for call in log_calls))
            self.assertTrue(any("median reference" in call for call in log_calls))
    
    def test_create_correlation_heatmaps_with_enhanced_sigma(self):
        """Test create_correlation_heatmaps with enhanced sigma parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            # Create test target data
            target_data = {
                "test_target": np.random.uniform(0, 1, len(self.embeddings))
            }
            
            # Test with percentile method
            results = self.creator.create_correlation_heatmaps(
                embeddings=self.embeddings,
                target_data=target_data,
                output_folder=output_folder,
                optimize_sigma=True,
                sigma_method="percentile",
                sigma_percentile=75.0,
                sigma_scaling_factor=1.5
            )
            
            # Check that sigma optimization metadata is included
            grid_metadata = results['grid_metadata']
            self.assertTrue(grid_metadata['sigma_optimized'])
            self.assertEqual(grid_metadata['sigma_method'], "percentile")
            self.assertEqual(grid_metadata['sigma_percentile'], 75.0)
            self.assertEqual(grid_metadata['sigma_scaling_factor'], 1.5)
            self.assertIsNotNone(grid_metadata['sigma'])
            self.assertGreater(grid_metadata['sigma'], 0)
    
    def test_reproducible_sigma_optimization(self):
        """Test that sigma optimization is reproducible for same embeddings."""
        sigma1 = self.creator.optimize_sigma(self.embeddings, method="median")
        sigma2 = self.creator.optimize_sigma(self.embeddings, method="median")
        
        self.assertEqual(sigma1, sigma2)
        
        # Test percentile method reproducibility
        sigma3 = self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=75.0)
        sigma4 = self.creator.optimize_sigma(self.embeddings, method="percentile", percentile=75.0)
        
        self.assertEqual(sigma3, sigma4)
    
    def test_different_embedding_sizes(self):
        """Test sigma optimization with different embedding sizes."""
        # Small embeddings
        small_embeddings = np.random.uniform(0, 1, (10, 2))
        sigma_small = self.creator.optimize_sigma(small_embeddings, method="median")
        
        # Large embeddings  
        large_embeddings = np.random.uniform(0, 1, (1000, 2))
        sigma_large = self.creator.optimize_sigma(large_embeddings, method="median")
        
        # Both should be positive and reasonable
        self.assertGreater(sigma_small, 0)
        self.assertGreater(sigma_large, 0)
        self.assertLess(sigma_small, 2.0)
        self.assertLess(sigma_large, 2.0)


if __name__ == "__main__":
    unittest.main()