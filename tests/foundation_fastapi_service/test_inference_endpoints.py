"""
Test suite for inference API endpoints in Foundation FastAPI Service.

This module tests the inference endpoints including request/response models,
error handling, and integration with the InferenceStage pipeline component.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from emuses.api.main import create_app


class TestInferenceEndpoints(unittest.TestCase):
    """Test inference API endpoints and integration."""

    def setUp(self):
        """Set up test environment with test client."""
        self.app = create_app()
        self.client = TestClient(self.app)
        
        # Create temporary directories for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # Create mock model and data paths
        self.model_path = self.temp_path / "test_models"
        self.model_path.mkdir()
        
        self.data_path = self.temp_path / "test_data.csv"
        self.data_path.write_text("feature1,feature2\n1.0,2.0\n3.0,4.0\n")
        
        self.output_path = self.temp_path / "inference_output"

    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()

    def test_inference_endpoint_exists_and_handles_errors(self):
        """Test that inference endpoint exists and properly handles missing models."""
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
        
        # Endpoint should exist and return 422 for missing models
        self.assertEqual(response.status_code, 422)
        
        # Check error response structure
        response_data = response.json()
        self.assertIn("detail", response_data)
        
        error_detail = response_data["detail"]
        self.assertIn("error_code", error_detail)
        self.assertIn("message", error_detail)
        self.assertIn("request_id", error_detail)
        self.assertEqual(error_detail["error_code"], "INFERENCE_VALIDATION_ERROR")

    def test_inference_request_model_validation(self):
        """Test InferenceRequest model validation and field validation."""
        from emuses.foundation_fastapi_service.models import InferenceRequest
        
        # Test valid request
        valid_request = InferenceRequest(
            model_path=str(self.model_path),
            data_path=str(self.data_path),
            output_path=str(self.output_path),
            validation_mode=False,
            verify_integrity=True,
            output_format="csv"
        )
        
        self.assertEqual(valid_request.model_path, str(self.model_path))
        self.assertEqual(valid_request.data_path, str(self.data_path))
        self.assertEqual(valid_request.output_format, "csv")
        self.assertFalse(valid_request.validation_mode)
        self.assertTrue(valid_request.verify_integrity)

    def test_inference_response_model_validation(self):
        """Test InferenceResponse model validation and structure."""
        from emuses.foundation_fastapi_service.models import InferenceResponse
        
        # Test valid response
        valid_response = InferenceResponse(
            status="completed",
            mode="inference",
            samples_processed=3,
            predictions=[0.5, 0.7, 0.3],
            confidence_scores=[0.9, 0.8, 0.7],
            processing_time_ms=150.5,
            throughput_samples_per_sec=20.0,
            model_info={"model_path": str(self.model_path), "loaded_models": 2},
            output_files={"predictions_csv": "predictions.csv", "metadata_file": "metadata.json"}
        )
        
        self.assertEqual(valid_response.status, "completed")
        self.assertEqual(valid_response.mode, "inference")
        self.assertEqual(valid_response.samples_processed, 3)
        self.assertEqual(len(valid_response.predictions), 3)
        self.assertIsNotNone(valid_response.confidence_scores)


if __name__ == '__main__':
    unittest.main()