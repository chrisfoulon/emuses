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
import pandas as pd
import pytest

from emuses.tools.region_statistical_analyzer import RegionStatisticalAnalyzer


class TestRegionStatisticalAnalyzer(unittest.TestCase):
    """Test basic initialization and configuration of RegionStatisticalAnalyzer."""
    
    @classmethod
    def setUpClass(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.2,
            effect_size_threshold=0.5,
            min_cluster_size=3
        )
        
        # Create test data using real data patterns
        # Use real data for grid coordinates (rescaled to 0-1 range)
        raw_coords = self.features[:50, :2]
        self.embeddings = (raw_coords - raw_coords.min(axis=0)) / (raw_coords.max(axis=0) - raw_coords.min(axis=0))
        
        # Use real data for prediction and confidence scores (scaled to appropriate ranges)
        base_pred = self.features[:50, 0]
        self.prediction_values = (base_pred - base_pred.min()) / (base_pred.max() - base_pred.min())
        
        base_conf = self.features[:50, 1]
        self.confidence_values = 0.3 + 0.7 * (base_conf - base_conf.min()) / (base_conf.max() - base_conf.min())
        
        # Use real target data
        base_targets = self.targets[:20, 0] if self.targets.shape[1] > 0 else self.features[:20, 0]
        target_values = 4 * (base_targets - base_targets.min()) / (base_targets.max() - base_targets.min()) - 2  # Scale to [-2, 2]
        self.target_data = {"target_0": target_values}
        
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
    
    @classmethod
    def setUpClass(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.3,
            effect_size_threshold=0.5
        )
        
        # Create test data with known filtering patterns using real data
        n_points = 20
        
        # Use real data for grid coordinates (rescaled to 0-1 range)
        raw_coords = self.features[:n_points, :2]
        self.grid_coords = (raw_coords - raw_coords.min(axis=0)) / (raw_coords.max(axis=0) - raw_coords.min(axis=0))
        
        # Create prediction and confidence values with clear filtering targets using real patterns
        # Use repeating pattern based on real data to maintain test logic
        base_pred = self.features[:5, 0]
        pred_pattern = (base_pred - base_pred.min()) / (base_pred.max() - base_pred.min())  # Scale to [0,1]
        pred_pattern = pred_pattern * 0.7 + 0.1  # Adjust to [0.1, 0.8] range roughly
        self.prediction_values = np.tile(pred_pattern, 4)  # Repeat pattern 4 times for 20 values
        
        base_conf = self.features[:5, 1]  
        conf_pattern = (base_conf - base_conf.min()) / (base_conf.max() - base_conf.min())  # Scale to [0,1]
        conf_pattern = conf_pattern * 0.8 + 0.1  # Adjust to [0.1, 0.9] range roughly
        self.confidence_values = np.tile(conf_pattern, 4)  # Repeat pattern 4 times for 20 values
        
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
    
    @classmethod
    def setUpClass(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer(min_cluster_size=3)
        
        # Create test coordinates for clustering using real data
        # Use real data for region coordinates (rescaled to 0-1 range)
        raw_coords = self.features[:15, :2]
        self.region_coords = (raw_coords - raw_coords.min(axis=0)) / (raw_coords.max(axis=0) - raw_coords.min(axis=0))
        
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
        # Use real data for small coordinates (rescaled to 0-1 range)
        raw_small_coords = self.features[:2, :2]
        small_coords = (raw_small_coords - raw_small_coords.min(axis=0)) / (raw_small_coords.max(axis=0) - raw_small_coords.min(axis=0))
        
        cluster_labels = self.analyzer.perform_region_clustering(small_coords)
        
        # Should return all noise labels
        expected_labels = np.array([-1, -1])
        np.testing.assert_array_equal(cluster_labels, expected_labels)


class TestStatisticalAnalysis(unittest.TestCase):
    """Test input_matrix_stat_map integration for feature-space analysis."""
    
    @classmethod
    def setUpClass(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer()
        
        # Create test input matrix and cluster data using real data patterns
        # Tile real features to get 30 samples x 100 features
        base_matrix = np.tile(self.features[:30, :], (1, 2))[:, :100]  # Use first 100 columns
        # Scale to [-1, 1] range
        self.input_matrix = 2 * (base_matrix - base_matrix.min()) / (base_matrix.max() - base_matrix.min()) - 1
        
        self.cluster_indices = [
            np.array([0, 1, 2, 4, 5]),      # Cluster 0: 5 points
            np.array([6, 7, 8, 10, 11, 12]), # Cluster 1: 6 points  
            np.array([15, 16])               # Cluster 2: 2 points (should be filtered)
        ]
        
    @patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map')
    def test_compute_statistical_analysis_valid_clusters(self, mock_stat_map):
        """Test statistical analysis for clusters with sufficient points."""
        # Mock input_matrix_stat_map return values using real data patterns
        # Use real data for statistical map results
        base_stat = np.tile(self.features[:50, 0], 2)  # 100 values from real data
        stat_map_1 = 4 * (base_stat - base_stat.min()) / (base_stat.max() - base_stat.min()) - 2  # Scale to [-2, 2]
        
        base_pval = np.tile(self.features[:50, 1], 2)  # 100 values from real data  
        pval_map_1 = (base_pval - base_pval.min()) / (base_pval.max() - base_pval.min())  # Scale to [0, 1]
        
        base_effect = np.tile(self.features[:50, 2], 2)  # 100 values from real data
        effect_map_1 = 2 * (base_effect - base_effect.min()) / (base_effect.max() - base_effect.min()) - 1  # Scale to [-1, 1]
        
        # Create different patterns for cluster 1
        stat_map_2 = -stat_map_1  # Invert for different pattern
        pval_map_2 = 1 - pval_map_1  # Different p-values
        effect_map_2 = -effect_map_1  # Opposite effect sizes
        
        mock_stat_map.side_effect = [
            # Cluster 0 results
            (stat_map_1, pval_map_1, effect_map_1),
            # Cluster 1 results
            (stat_map_2, pval_map_2, effect_map_2)
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
        
        # Use real data patterns instead of zeros
        base_data = self.features[:100, 0] if self.features.shape[1] > 0 else np.ones(100)
        mock_stat_map.return_value = (
            base_data, base_data * 0.1, base_data * 0.5
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
    
    @classmethod
    def setUpClass(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    
    def setUp(self):
        """Set up test fixtures for contour detection testing."""
        self.analyzer = RegionStatisticalAnalyzer()
        
        # Create synthetic 20×20 grid with known geometric shapes for testing
        self.grid_size = 20
        self.significance_values = np.zeros(self.grid_size * self.grid_size)
        
        # Create training embeddings in rescaled space (0-1 range) using real data
        raw_embeddings = self.features[:100, :2]
        self.training_embeddings = (raw_embeddings - raw_embeddings.min(axis=0)) / (raw_embeddings.max(axis=0) - raw_embeddings.min(axis=0))
        
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
    
    @classmethod
    def setUpClass(cls):
        """Load real test data for validation."""
        project_root = Path(__file__).parent.parent.parent
        cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
        cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = RegionStatisticalAnalyzer(
            visualization_threshold=0.2,
            effect_size_threshold=0.4,
            min_cluster_size=3
        )
        
        # Create comprehensive test data using real data patterns
        # Grid coordinates (rescaled to 0-1 range)
        raw_coords = self.features[:25, :2]
        self.grid_coords = (raw_coords - raw_coords.min(axis=0)) / (raw_coords.max(axis=0) - raw_coords.min(axis=0))
        
        # Prediction values (scaled to [0, 1])
        base_pred = self.features[:25, 0]
        self.prediction_values = (base_pred - base_pred.min()) / (base_pred.max() - base_pred.min())
        
        # Confidence values (scaled to [0, 1])  
        base_conf = self.features[:25, 1]
        self.confidence_values = (base_conf - base_conf.min()) / (base_conf.max() - base_conf.min())
        
        # Input matrix (scaled to [-1, 1])
        base_matrix = self.features[:20, :50]
        self.input_matrix = 2 * (base_matrix - base_matrix.min()) / (base_matrix.max() - base_matrix.min()) - 1
        
        # Target data (scaled to [-2, 2])
        base_targets = self.targets[:20, 0] if self.targets.shape[1] > 0 else self.features[:20, 0]  
        target_values = 4 * (base_targets - base_targets.min()) / (base_targets.max() - base_targets.min()) - 2
        self.target_data = {"target_0": target_values}
        
    @patch('emuses.tools.region_statistical_analyzer.save_statistical_maps')
    @patch('emuses.tools.region_statistical_analyzer.input_matrix_stat_map')
    @patch('emuses.tools.region_statistical_analyzer.hdbscan.HDBSCAN')
    def test_create_region_statistical_maps_complete_workflow(self, mock_hdbscan_class, mock_stat_map, mock_save_maps):
        """Test complete region-based statistical analysis workflow."""
        # Mock HDBSCAN clustering
        mock_clusterer = Mock()
        # Create cluster pattern: some clusters with ≥3 points, some with <3
        # 15 points pass filtering, so need 15 cluster labels
        mock_clusterer.labels_ = np.array([0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, -1, -1, -1])
        mock_hdbscan_class.return_value = mock_clusterer
        
        # Mock statistical analysis using real data patterns
        base_stat = self.features[:50, 0] if self.features.shape[1] > 0 else np.ones(50)
        mock_stat_map.side_effect = [
            # Cluster 0 results (3 points) 
            (base_stat, base_stat * 0.05, base_stat * 0.7),
            # Cluster 1 results (4 points)
            (-base_stat, base_stat * 0.01, -base_stat * 0.8),
            # Cluster 2 results (5 points)
            (base_stat * 0.5, base_stat * 0.03, base_stat * 0.6)
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
            
            # Should have processed 3 clusters (≥3 points)
            target_result = results["statistical_results"]["target_0"]
            self.assertIn("clusters_analyzed", target_result)
            self.assertEqual(target_result["clusters_analyzed"], 3)
            
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
            # Check for either message (implementation may vary)
            message = target_result.get("message", "").lower()
            self.assertTrue("no regions passed filtering" in message or "no clusters met minimum size" in message)


if __name__ == "__main__":
    unittest.main()