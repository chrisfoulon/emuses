"""
Tests for FastAPI Analysis Endpoints in Task 2.1.

This module tests the REST API endpoints for triple analysis: statistical maps,
prediction grids, and correlation grids.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from emuses.api.main import create_app


class TestStatisticalMapsEndpoint(unittest.TestCase):
    """Test POST /api/v1/analysis/statistical-maps endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)
        
        # Create test data
        self.test_request = {
            "model_path": "/path/to/test/model",
            "input_data_path": "/path/to/test/data.csv",
            "output_folder": "/tmp/test_output",
            "targets": ["target_0", "target_1"],
            "statistical_test": "mann-whitney",
            "visualization_threshold": 0.2,
            "effect_size_threshold": 0.5,
            "min_cluster_size": 3,
            "input_type": "spreadsheet"
        }

    def test_statistical_maps_endpoint_exists(self):
        """Test that the statistical-maps endpoint exists and accepts POST requests."""
        response = self.client.post("/api/v1/analysis/statistical-maps", json=self.test_request)
        
        # Should not return 404 (endpoint exists)
        self.assertNotEqual(response.status_code, 404)
        # Should not return 405 (method allowed)
        self.assertNotEqual(response.status_code, 405)

    def test_statistical_maps_endpoint_validation(self):
        """Test request validation for statistical-maps endpoint."""
        # Test missing required fields
        incomplete_request = {"model_path": "/test/path"}
        response = self.client.post("/api/v1/analysis/statistical-maps", json=incomplete_request)
        
        # Should return validation error
        self.assertEqual(response.status_code, 422)
        response_data = response.json()
        self.assertIn("detail", response_data)

    @patch('emuses.tools.region_statistical_analyzer.RegionStatisticalAnalyzer')
    @patch('emuses.tools.grid_creator.GridCreator') 
    def test_statistical_maps_endpoint_success(self, mock_grid_creator, mock_analyzer):
        """Test successful statistical maps generation."""
        # Mock grid creator
        mock_grid_instance = Mock()
        mock_grid_instance.create_prediction_grid.return_value = {
            'grid_coords': np.random.uniform(0, 1, (100, 2)),
            'prediction_values': np.random.uniform(0, 1, 100),
            'confidence_values': np.random.uniform(0.3, 1.0, 100)
        }
        mock_grid_creator.return_value = mock_grid_instance
        
        # Mock statistical analyzer
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.create_region_statistical_maps.return_value = {
            'statistical_results': {
                'target_0': {
                    'clusters_analyzed': 2,
                    'filtering_results': {
                        'total_grid_points': 100,
                        'points_after_filtering': 25,
                        'clusters_found': 2,
                        'valid_clusters': 2
                    }
                }
            },
            'analysis_metadata': {
                'visualization_threshold': 0.2,
                'effect_size_threshold': 0.5,
                'min_cluster_size': 3,
                'statistical_test': 'mann-whitney'
            }
        }
        mock_analyzer.return_value = mock_analyzer_instance
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary test input file
            test_data_path = Path(temp_dir) / "test_data.csv"
            test_data_path.write_text("feature1,feature2,target\n1.0,2.0,0.5\n2.0,3.0,1.0\n")
            
            test_request = self.test_request.copy()
            test_request["input_data_path"] = str(test_data_path)
            test_request["output_folder"] = temp_dir
            
            response = self.client.post("/api/v1/analysis/statistical-maps", json=test_request)
            
            # Should return success
            self.assertEqual(response.status_code, 200)
            response_data = response.json()
            
            # Should contain expected response structure
            self.assertIn("statistical_results", response_data)
            self.assertIn("analysis_metadata", response_data)
            self.assertIn("target_0", response_data["statistical_results"])

    def test_statistical_maps_endpoint_parameter_validation(self):
        """Test parameter validation for statistical-maps endpoint."""
        # Test invalid statistical test
        invalid_request = self.test_request.copy()
        invalid_request["statistical_test"] = "invalid-test"
        
        response = self.client.post("/api/v1/analysis/statistical-maps", json=invalid_request)
        self.assertEqual(response.status_code, 422)
        
        # Test negative thresholds
        invalid_request = self.test_request.copy()
        invalid_request["visualization_threshold"] = -0.1
        
        response = self.client.post("/api/v1/analysis/statistical-maps", json=invalid_request)
        self.assertEqual(response.status_code, 422)

    @patch('emuses.tools.region_statistical_analyzer.RegionStatisticalAnalyzer')
    def test_statistical_maps_endpoint_error_handling(self, mock_analyzer):
        """Test error handling in statistical-maps endpoint."""
        # Mock analyzer to raise exception
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.create_region_statistical_maps.side_effect = Exception("Analysis failed")
        mock_analyzer.return_value = mock_analyzer_instance
        
        response = self.client.post("/api/v1/analysis/statistical-maps", json=self.test_request)
        
        # Should return 500 internal server error
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertIn("detail", response_data)


class TestHeatmapsEndpoint(unittest.TestCase):
    """Test POST /api/v1/analysis/heatmaps endpoint."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = create_app()
        self.client = TestClient(self.app)
        
        # Create test data
        self.test_request = {
            "model_path": "/path/to/test/model",
            "input_data_path": "/path/to/test/data.csv",
            "output_folder": "/tmp/test_output",
            "targets": ["target_0", "target_1"],
            "grid_size": [100, 100],
            "denormalize_predictions": True,
            "correlation_methods": ["pearson", "spearman"],
            "sigma_optimization": True,
            "max_sigma_trials": 50
        }

    def test_heatmaps_endpoint_exists(self):
        """Test that the heatmaps endpoint exists and accepts POST requests."""
        response = self.client.post("/api/v1/analysis/heatmaps", json=self.test_request)
        
        # Should not return 404 (endpoint exists)
        self.assertNotEqual(response.status_code, 404)
        # Should not return 405 (method allowed)
        self.assertNotEqual(response.status_code, 405)

    def test_heatmaps_endpoint_validation(self):
        """Test request validation for heatmaps endpoint."""
        # Test missing required fields
        incomplete_request = {"model_path": "/test/path"}
        response = self.client.post("/api/v1/analysis/heatmaps", json=incomplete_request)
        
        # Should return validation error
        self.assertEqual(response.status_code, 422)
        response_data = response.json()
        self.assertIn("detail", response_data)

    def test_heatmaps_endpoint_correlation_method_validation(self):
        """Test correlation method validation for heatmaps endpoint."""
        # Test invalid correlation method
        invalid_request = self.test_request.copy()
        invalid_request["correlation_methods"] = ["invalid-method"]
        
        response = self.client.post("/api/v1/analysis/heatmaps", json=invalid_request)
        self.assertEqual(response.status_code, 422)

    @patch('emuses.tools.correlation_grid_creator.CorrelationGridCreator')
    @patch('emuses.tools.grid_creator.GridCreator') 
    def test_heatmaps_endpoint_success(self, mock_grid_creator, mock_correlation_creator):
        """Test successful heatmaps generation."""
        # Mock grid creator
        mock_grid_instance = Mock()
        mock_grid_instance.create_prediction_grid.return_value = {
            'grid_coords': np.random.uniform(0, 1, (100, 2)),
            'prediction_values': np.random.uniform(0, 1, 100),
            'confidence_values': np.random.uniform(0.3, 1.0, 100)
        }
        mock_grid_creator.return_value = mock_grid_instance
        
        # Mock correlation grid creator
        mock_correlation_instance = Mock()
        mock_correlation_instance.create_correlation_grid.return_value = {
            'correlation_values': np.random.uniform(-1, 1, 100),
            'optimal_sigma': 0.15
        }
        mock_correlation_creator.return_value = mock_correlation_instance
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary test input file
            test_data_path = Path(temp_dir) / "test_data.csv"
            test_data_path.write_text("feature1,feature2,target\n1.0,2.0,0.5\n2.0,3.0,1.0\n")
            
            test_request = self.test_request.copy()
            test_request["input_data_path"] = str(test_data_path)
            test_request["output_folder"] = temp_dir
            
            response = self.client.post("/api/v1/analysis/heatmaps", json=test_request)
            
            # Should return success
            self.assertEqual(response.status_code, 200)
            response_data = response.json()
            
            # Should contain expected response structure
            self.assertIn("prediction_results", response_data)
            self.assertIn("correlation_results", response_data)
            self.assertIn("analysis_metadata", response_data)
            self.assertIn("processing_info", response_data)
            
            # Should contain results for both targets
            self.assertIn("target_0", response_data["prediction_results"])
            self.assertIn("target_1", response_data["prediction_results"])
            self.assertIn("target_0", response_data["correlation_results"])
            self.assertIn("target_1", response_data["correlation_results"])

    @patch('emuses.tools.grid_creator.GridCreator')
    def test_heatmaps_endpoint_error_handling(self, mock_grid_creator):
        """Test error handling in heatmaps endpoint."""
        # Mock grid creator to raise exception
        mock_grid_creator.side_effect = Exception("Grid creation failed")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_data_path = Path(temp_dir) / "test_data.csv"
            test_data_path.write_text("feature1,feature2,target\n1.0,2.0,0.5\n")
            
            test_request = self.test_request.copy()
            test_request["input_data_path"] = str(test_data_path)
            test_request["output_folder"] = temp_dir
            
            response = self.client.post("/api/v1/analysis/heatmaps", json=test_request)
            
            # Should return 500 internal server error
            self.assertEqual(response.status_code, 500)
            response_data = response.json()
            self.assertIn("detail", response_data)


if __name__ == "__main__":
    unittest.main()