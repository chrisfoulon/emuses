"""
End-to-end integration tests for EMUSES inference workflow.

This module provides comprehensive validation testing across CLI, API,
and pipeline components to ensure complete inference workflow integrity.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from emuses.api.main import create_app


class TestInferenceWorkflowE2E(unittest.TestCase):
    """End-to-end tests for complete inference workflow."""

    def setUp(self):
        """Set up test environment with mock models and data."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # Create mock trained model structure
        self.model_path = self.temp_path / "trained_models"
        self.model_path.mkdir()
        
        # Create required model files
        (self.model_path / "umap_model.pkl").write_text("mock_umap_model")
        (self.model_path / "prediction_models").mkdir()
        (self.model_path / "prediction_models" / "model_1.pkl").write_text("mock_model_1")
        (self.model_path / "prediction_models" / "metrics.json").write_text('{"accuracy": 0.85}')
        
        # Create test input data
        self.data_path = self.temp_path / "test_data.csv"
        self.data_path.write_text("feature1,feature2\n1.0,2.0\n3.0,4.0\n5.0,6.0\n")
        
        # Output directory
        self.output_path = self.temp_path / "inference_results"
        
        # API client
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    @patch('emuses.pipelines.inference_stage.InferenceStage.run')
    def test_cli_to_pipeline_integration_success(self, mock_run):
        """Test CLI command integration with InferenceStage pipeline success path."""
        # Mock successful inference execution
        mock_run.return_value = {
            'mode': 'inference',
            'samples_processed': 3,
            'predictions': [0.7, 0.8, 0.6],
            'confidence_scores': [0.9, 0.85, 0.75],
            'processing_time_ms': 150.0,
            'throughput_samples_per_sec': 20.0,
            'model_info': {'loaded_models': 1},
            'output_files': {'predictions_csv': str(self.output_path / 'predictions.csv')}
        }
        
        cmd = [
            "python", "-m", "emuses.cli", "inference",
            str(self.model_path), str(self.data_path),
            "--output-path", str(self.output_path),
            "--output-format", "csv"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/chrisfoulon/neuro_apps/emuses")
        
        # Should succeed with mocked pipeline
        self.assertEqual(result.returncode, 0)
        mock_run.assert_called_once()

    def test_api_to_pipeline_integration_fails(self):
        """Test API endpoint integration with InferenceStage pipeline (expect failure)."""
        # This should fail initially - no real models exist
        response = self.client.post(
            "/api/v1/inference",
            json={
                "model_path": str(self.model_path),
                "data_path": str(self.data_path),
                "output_path": str(self.output_path),
                "validation_mode": False,
                "verify_integrity": True,
                "output_format": "csv"
            }
        )
        
        # Should fail due to missing real model artifacts
        self.assertEqual(response.status_code, 422)
        response_data = response.json()
        self.assertIn("detail", response_data)
        self.assertIn("error_code", response_data["detail"])

    def test_pipeline_component_isolation_fails(self):
        """Test InferenceStage pipeline component directly (expect failure)."""
        from emuses.pipelines.inference_stage import InferenceStage
        
        # This should fail initially - mock models won't work
        with patch('emuses.pipelines.pipeline_config.PipelineConfig') as mock_config:
            mock_config.return_value.input_file = str(self.data_path)
            mock_config.return_value.output_folder = str(self.output_path)
            
            inference_stage = InferenceStage(mock_config.return_value)
            
            # Should fail due to invalid model artifacts
            with self.assertRaises(Exception):
                inference_stage.run(str(self.model_path), validation_mode=False)

    def test_output_format_consistency(self):
        """Test output format consistency across CLI and API (TDD placeholder)."""
        # This will be implemented after core functionality works
        self.skipTest("Implementation pending - requires working inference pipeline")

    def test_error_handling_consistency(self):
        """Test error handling consistency across CLI and API (TDD placeholder)."""
        # This will be implemented after core functionality works  
        self.skipTest("Implementation pending - requires working inference pipeline")


if __name__ == '__main__':
    unittest.main()