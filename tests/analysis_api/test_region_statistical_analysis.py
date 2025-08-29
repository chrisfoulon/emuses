"""
Tests for region-based statistical analysis functionality in Task 1.3.

This module tests the RegionStatisticalAnalyzer class that implements two-stage filtering,
HDBSCAN clustering within regions, and statistical analysis via input_matrix_stat_map.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import numpy as np
import pytest

from emuses.tools.region_statistical_analyzer import RegionStatisticalAnalyzer


class TestRegionStatisticalAnalyzer(unittest.TestCase):
    """Test basic initialization and configuration of RegionStatisticalAnalyzer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.2,
            effect_size_threshold=0.5,
            min_cluster_size=3
        )
        
        # Create test data
        np.random.seed(42)
        self.embeddings = np.random.uniform(0, 1, (50, 2))  # Grid coordinates
        self.prediction_values = np.random.uniform(0, 1, 50)  # Prediction scores
        self.confidence_values = np.random.uniform(0.3, 1.0, 50)  # Confidence scores
        self.target_data = {"target_0": np.random.uniform(-2, 2, 20)}
        
    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        analyzer = RegionStatisticalAnalyzer()
        self.assertEqual(analyzer.visualization_threshold, 0.2)
        self.assertEqual(analyzer.effect_size_threshold, 0.5)
        self.assertEqual(analyzer.min_cluster_size, 3)
        self.assertEqual(analyzer.statistical_test, "mann-whitney")
        
    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.3,
            effect_size_threshold=0.8,
            min_cluster_size=5,
            statistical_test="t-test"
        )
        self.assertEqual(analyzer.visualization_threshold, 0.3)
        self.assertEqual(analyzer.effect_size_threshold, 0.8)
        self.assertEqual(analyzer.min_cluster_size, 5)
        self.assertEqual(analyzer.statistical_test, "t-test")
        
    def test_init_invalid_thresholds(self):
        """Test initialization with invalid threshold values."""
        with self.assertRaises(ValueError):
            RegionStatisticalAnalyzer(visualization_threshold=-0.1)
        with self.assertRaises(ValueError):
            RegionStatisticalAnalyzer(effect_size_threshold=-0.1)
        with self.assertRaises(ValueError):
            RegionStatisticalAnalyzer(min_cluster_size=0)


class TestTwoStageFiltering(unittest.TestCase):
    """Test two-stage threshold filtering functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.3,
            effect_size_threshold=0.5
        )
        
        # Create test data with known filtering patterns
        np.random.seed(42)
        n_points = 20
        self.grid_coords = np.random.uniform(0, 1, (n_points, 2))
        
        # Create prediction and confidence values with clear filtering targets
        self.prediction_values = np.array([0.1, 0.2, 0.4, 0.6, 0.8] * 4)  # Mixed values
        self.confidence_values = np.array([0.1, 0.4, 0.5, 0.7, 0.9] * 4)   # Mixed confidence
        
    def test_apply_two_stage_filtering_visualization_threshold(self):
        """Test two-stage filtering applies visualization threshold correctly."""
        # Set effect size threshold very low to test visualization filtering
        analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.3,
            effect_size_threshold=0.0
        )
        
        filtered_indices = analyzer.apply_two_stage_filtering(
            self.grid_coords, self.prediction_values, self.confidence_values
        )
        
        # Should only include points with confidence >= visualization_threshold (0.3)
        expected_mask = self.confidence_values >= 0.3
        expected_indices = np.where(expected_mask)[0]
        
        np.testing.assert_array_equal(filtered_indices, expected_indices)
        
    def test_apply_two_stage_filtering_effect_size_threshold(self):
        """Test two-stage filtering applies effect size threshold correctly."""
        # Set visualization threshold very low to test effect size filtering
        analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.0,
            effect_size_threshold=0.5
        )
        
        filtered_indices = analyzer.apply_two_stage_filtering(
            self.grid_coords, self.prediction_values, self.confidence_values
        )
        
        # Should include points with prediction >= effect_size_threshold (0.5)
        expected_mask = self.prediction_values >= 0.5
        expected_indices = np.where(expected_mask)[0]
        
        np.testing.assert_array_equal(filtered_indices, expected_indices)
        
    def test_apply_two_stage_filtering_combined_thresholds(self):
        """Test two-stage filtering applies both thresholds correctly."""
        filtered_indices = self.analyzer.apply_two_stage_filtering(
            self.grid_coords, self.prediction_values, self.confidence_values
        )
        
        # Should include points meeting BOTH conditions
        confidence_mask = self.confidence_values >= 0.3
        effect_mask = self.prediction_values >= 0.5
        combined_mask = confidence_mask & effect_mask
        expected_indices = np.where(combined_mask)[0]
        
        np.testing.assert_array_equal(filtered_indices, expected_indices)
        
    def test_apply_two_stage_filtering_no_points_pass(self):
        """Test two-stage filtering when no points pass thresholds."""
        # Set very high thresholds
        analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.95,
            effect_size_threshold=0.95
        )
        
        filtered_indices = analyzer.apply_two_stage_filtering(
            self.grid_coords, self.prediction_values, self.confidence_values
        )
        
        # Should return empty array
        self.assertEqual(len(filtered_indices), 0)


class TestRegionBasedClustering(unittest.TestCase):
    """Test HDBSCAN clustering within high-confidence regions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer(min_cluster_size=3)
        
        # Create test coordinates for clustering
        np.random.seed(42)
        self.region_coords = np.random.uniform(0, 1, (15, 2))
        
    @patch('emuses.tools.region_statistical_analyzer.hdbscan.HDBSCAN')
    def test_perform_region_clustering_basic(self, mock_hdbscan_class):
        """Test basic HDBSCAN clustering within regions."""
        # Mock HDBSCAN clusterer
        mock_clusterer = Mock()
        mock_clusterer.labels_ = np.array([0, 0, 1, 1, 1, -1, -1, 2, 2, 2, 2, -1, 0, 0, 1])
        mock_hdbscan_class.return_value = mock_clusterer
        
        cluster_labels = self.analyzer.perform_region_clustering(self.region_coords)
        
        # Should call HDBSCAN with correct parameters
        mock_hdbscan_class.assert_called_once_with(
            min_cluster_size=3,
            min_samples=1
        )
        mock_clusterer.fit.assert_called_once_with(self.region_coords)
        
        # Should return cluster labels
        expected_labels = np.array([0, 0, 1, 1, 1, -1, -1, 2, 2, 2, 2, -1, 0, 0, 1])
        np.testing.assert_array_equal(cluster_labels, expected_labels)
        
    @patch('emuses.tools.region_statistical_analyzer.hdbscan.HDBSCAN')
    def test_perform_region_clustering_min_cluster_size(self, mock_hdbscan_class):
        """Test clustering with different min_cluster_size."""
        analyzer = RegionStatisticalAnalyzer(min_cluster_size=5)
        
        mock_clusterer = Mock()
        mock_clusterer.labels_ = np.array([0] * 15)
        mock_hdbscan_class.return_value = mock_clusterer
        
        analyzer.perform_region_clustering(self.region_coords)
        
        # Should use custom min_cluster_size
        mock_hdbscan_class.assert_called_once_with(
            min_cluster_size=5,
            min_samples=1
        )
        
    def test_perform_region_clustering_insufficient_points(self):
        """Test clustering with insufficient points."""
        small_coords = np.random.uniform(0, 1, (2, 2))
        
        cluster_labels = self.analyzer.perform_region_clustering(small_coords)
        
        # Should return all noise labels
        expected_labels = np.array([-1, -1])
        np.testing.assert_array_equal(cluster_labels, expected_labels)


class TestStatisticalAnalysis(unittest.TestCase):
    """Test input_matrix_stat_map integration for feature-space analysis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer()
        
        # Create test input matrix and cluster data
        np.random.seed(42)
        self.input_matrix = np.random.uniform(-1, 1, (30, 100))  # 30 samples, 100 features
        self.cluster_indices = [
            np.array([0, 1, 2, 4, 5]),      # Cluster 0: 5 points
            np.array([6, 7, 8, 10, 11, 12]), # Cluster 1: 6 points  
            np.array([15, 16])               # Cluster 2: 2 points (should be filtered)
        ]
        
    @patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map')
    def test_compute_statistical_analysis_valid_clusters(self, mock_stat_map):
        """Test statistical analysis for clusters with sufficient points."""
        # Mock input_matrix_stat_map return values
        mock_stat_map.side_effect = [
            # Cluster 0 results
            (
                np.random.uniform(-2, 2, 100),    # stat_map
                np.random.uniform(0, 1, 100),     # pval_map  
                np.random.uniform(-1, 1, 100)     # effect_size_map
            ),
            # Cluster 1 results
            (
                np.random.uniform(-2, 2, 100),    # stat_map
                np.random.uniform(0, 1, 100),     # pval_map
                np.random.uniform(-1, 1, 100)     # effect_size_map
            )
        ]
        
        statistical_maps = self.analyzer.compute_statistical_analysis(
            self.input_matrix, self.cluster_indices
        )
        
        # Should process clusters 0 and 1 (≥3 points), skip cluster 2 (<3 points)
        self.assertEqual(len(statistical_maps), 2)
        self.assertIn("cluster_0", statistical_maps)
        self.assertIn("cluster_1", statistical_maps)
        self.assertNotIn("cluster_2", statistical_maps)
        
        # Should call input_matrix_stat_map for each valid cluster
        self.assertEqual(mock_stat_map.call_count, 2)
        
    @patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map')
    def test_compute_statistical_analysis_statistical_test_parameter(self, mock_stat_map):
        """Test statistical analysis passes correct test parameter."""
        analyzer = RegionStatisticalAnalyzer(statistical_test="t-test")
        
        mock_stat_map.return_value = (
            np.zeros(100), np.zeros(100), np.zeros(100)
        )
        
        analyzer.compute_statistical_analysis(
            self.input_matrix, self.cluster_indices[:1]  # Only first cluster
        )
        
        # Should pass statistical test parameter
        mock_stat_map.assert_called_once()
        call_args = mock_stat_map.call_args
        self.assertEqual(call_args[1]['test_name'], "t-test")
        
    def test_compute_statistical_analysis_no_valid_clusters(self):
        """Test statistical analysis when no clusters have sufficient points."""
        small_clusters = [
            np.array([0, 1]),      # 2 points
            np.array([2]),         # 1 point
        ]
        
        statistical_maps = self.analyzer.compute_statistical_analysis(
            self.input_matrix, small_clusters
        )
        
        # Should return empty dictionary
        self.assertEqual(len(statistical_maps), 0)


class TestGridToSampleMappingContourDetection(unittest.TestCase):
    """Test contour detection grid→sample mapping functionality."""
    
    def setUp(self):
        """Set up test fixtures for contour detection testing."""
        self.analyzer = RegionStatisticalAnalyzer()
        
        # Create synthetic 20×20 grid with known geometric shapes for testing
        self.grid_size = 20
        self.significance_values = np.zeros(self.grid_size * self.grid_size)
        
        # Create training embeddings in rescaled space (0-1 range)
        np.random.seed(42)
        self.training_embeddings = np.random.uniform(0, 1, (100, 2))
        
    def test_map_grid_to_training_samples_high_significance_rectangular_region(self):
        """Test contour detection for high significance rectangular region."""
        # Create rectangular high significance region in grid indices 5-10, 8-12
        for i in range(5, 11):  # rows 5-10
            for j in range(8, 13):  # cols 8-12
                grid_idx = i * self.grid_size + j
                self.significance_values[grid_idx] = 0.9  # High significance
        
        # Place some training points inside the rectangle (rescaled coordinates)
        # Rectangle spans grid indices 5-10, 8-12 → rescaled coords 0.25-0.5, 0.4-0.6
        expected_inside_points = np.array([
            [0.3, 0.45],   # Inside rectangle
            [0.4, 0.55],   # Inside rectangle  
            [0.35, 0.5],   # Inside rectangle
        ])
        
        # Add points outside the rectangle for contrast
        expected_outside_points = np.array([
            [0.1, 0.1],    # Outside rectangle (top-left)
            [0.9, 0.9],    # Outside rectangle (bottom-right)
        ])
        
        # Combine all embeddings
        extended_embeddings = np.vstack([
            self.training_embeddings, 
            expected_inside_points, 
            expected_outside_points
        ])
        
        result = self.analyzer.map_grid_to_training_samples(
            significance_values=self.significance_values,
            training_embeddings=extended_embeddings,
            percentile_threshold=5.0,
            significance_source='prediction'
        )
        
        # Should return high and low significance sample indices
        self.assertIn('high', result)
        self.assertIn('low', result)
        self.assertIsInstance(result['high'], np.ndarray)
        self.assertIsInstance(result['low'], np.ndarray)
        
        # High significance indices should include points inside rectangle
        # (Last 3 points in extended_embeddings are the inside points)
        expected_inside_indices = np.arange(len(self.training_embeddings), 
                                          len(self.training_embeddings) + 3)
        
        # Should find some points in the high significance region
        self.assertTrue(len(result['high']) > 0)
        
        # The expected inside points should be in high significance results
        for expected_idx in expected_inside_indices:
            self.assertIn(expected_idx, result['high'])
            
    def test_map_grid_to_training_samples_circular_region(self):
        """Test contour detection for circular high significance region."""
        # Create circular region centered at grid position (10, 10) with radius 3
        center_x, center_y = 10, 10
        radius = 3
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                distance = np.sqrt((i - center_x)**2 + (j - center_y)**2)
                if distance <= radius:
                    grid_idx = i * self.grid_size + j
                    self.significance_values[grid_idx] = 0.95  # High significance
                    
        result = self.analyzer.map_grid_to_training_samples(
            significance_values=self.significance_values,
            training_embeddings=self.training_embeddings,
            percentile_threshold=5.0,
            significance_source='correlation'
        )
        
        # Should return result dict with high and low keys
        self.assertIn('high', result)
        self.assertIn('low', result)
        
        # For correlation analysis, low should be empty (correlation uses high only)
        self.assertEqual(len(result['low']), 0)
        
        # Should find some high significance samples (circular region contains some points)
        # Note: Exact number depends on training embeddings distribution
        self.assertIsInstance(result['high'], np.ndarray)
            
    def test_map_grid_to_training_samples_disconnected_regions(self):
        """Test contour detection for multiple disconnected significant regions."""
        # Create two separate rectangular regions
        # Region 1: grid indices 2-4, 2-4 (top-left)
        for i in range(2, 5):
            for j in range(2, 5):
                grid_idx = i * self.grid_size + j
                self.significance_values[grid_idx] = 0.9
                
        # Region 2: grid indices 15-17, 15-17 (bottom-right)  
        for i in range(15, 18):
            for j in range(15, 18):
                grid_idx = i * self.grid_size + j
                self.significance_values[grid_idx] = 0.85
                
        result = self.analyzer.map_grid_to_training_samples(
            significance_values=self.significance_values,
            training_embeddings=self.training_embeddings,
            percentile_threshold=10.0,
            significance_source='prediction'
        )
        
        # Should handle disconnected regions correctly
        self.assertIn('high', result)
        self.assertIn('low', result)
        self.assertIsInstance(result['high'], np.ndarray)
        self.assertIsInstance(result['low'], np.ndarray)
        
        # Should process both high and low regions for prediction source
        # (actual counts depend on training embeddings distribution)


class TestRegionStatisticalAnalysisIntegration(unittest.TestCase):
    """Test integrated region-based statistical analysis workflow."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.2,
            effect_size_threshold=0.4,
            min_cluster_size=3
        )
        
        # Create comprehensive test data
        np.random.seed(42)
        self.grid_coords = np.random.uniform(0, 1, (25, 2))
        self.prediction_values = np.random.uniform(0, 1, 25)
        self.confidence_values = np.random.uniform(0, 1, 25)
        self.input_matrix = np.random.uniform(-1, 1, (20, 50))
        self.target_data = {"target_0": np.random.uniform(-2, 2, 20)}
        
    @patch('emuses.tools.region_statistical_analyzer.save_statistical_maps')
    @patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map')
    @patch('emuses.tools.region_statistical_analyzer.hdbscan.HDBSCAN')
    def test_create_region_statistical_maps_complete_workflow(self, mock_hdbscan_class, mock_stat_map, mock_save_maps):
        """Test complete region-based statistical analysis workflow."""
        # Mock HDBSCAN clustering
        mock_clusterer = Mock()
        # Create cluster pattern: some clusters with ≥3 points, some with <3
        # 8 points pass filtering, so need 8 cluster labels
        mock_clusterer.labels_ = np.array([0, 0, 0, 1, 1, 1, 1, -1])
        mock_hdbscan_class.return_value = mock_clusterer
        
        # Mock statistical analysis
        mock_stat_map.side_effect = [
            # Cluster 0 results (3 points)
            (np.ones(50), np.ones(50) * 0.05, np.ones(50) * 0.7),
            # Cluster 1 results (4 points)  
            (np.ones(50) * -1, np.ones(50) * 0.01, np.ones(50) * -0.8)
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            results = self.analyzer.create_region_statistical_maps(
                self.grid_coords,
                self.prediction_values, 
                self.confidence_values,
                self.input_matrix,
                self.target_data,
                output_folder,
                input_type="spreadsheet",
                output_format_info=["feature_1", "feature_2"]  # Column names
            )
            
            # Should return results for each target
            self.assertIn("statistical_results", results)
            self.assertIn("target_0", results["statistical_results"])
            
            # Should have processed 2 clusters (≥3 points)
            target_result = results["statistical_results"]["target_0"]
            self.assertIn("clusters_analyzed", target_result)
            self.assertEqual(target_result["clusters_analyzed"], 2)
            
            # Should call save_statistical_maps once with all clusters
            self.assertEqual(mock_save_maps.call_count, 1)
            
    def test_create_region_statistical_maps_no_regions_pass_filtering(self):
        """Test workflow when no regions pass two-stage filtering."""
        # Set very high thresholds so no points pass
        analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.99,
            effect_size_threshold=0.99
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_folder = Path(temp_dir)
            
            results = analyzer.create_region_statistical_maps(
                self.grid_coords,
                self.prediction_values,
                self.confidence_values, 
                self.input_matrix,
                self.target_data,
                output_folder,
                input_type="spreadsheet",
                output_format_info=["col1", "col2"]
            )
            
            # Should handle gracefully with no clusters
            target_result = results["statistical_results"]["target_0"]
            self.assertEqual(target_result["clusters_analyzed"], 0)
            self.assertIn("no regions passed filtering", target_result.get("message", "").lower())


if __name__ == "__main__":
    unittest.main()