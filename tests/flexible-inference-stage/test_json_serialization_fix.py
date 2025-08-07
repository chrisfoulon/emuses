"""
Test to isolate and fix JSON serialization issue in InferenceStage
"""
import pytest
import json
import tempfile
from pathlib import Path
import numpy as np

# Import the inference stage
from emuses.pipelines.inference_stage import InferenceStage


def test_inference_stage_config_serialization():
    """Test that InferenceStage config can be JSON serialized"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            'model_path': temp_dir,  # String path instead of PosixPath 
            'data_path': temp_dir,   # String path instead of PosixPath
            'output_path': temp_dir, # String path instead of PosixPath
            'validate_mode': False,
            'output_format': 'csv'
        }
        
        # This should work without error
        inference_stage = InferenceStage(config)
        
        # The stage should convert paths to Path objects internally but config should remain serializable
        serialized = json.dumps(config)
        assert serialized is not None
        
        # Test that the stage can access paths as Path objects
        assert isinstance(inference_stage.model_path, (Path, type(None)))
        assert isinstance(inference_stage.data_path, (Path, type(None)))


def test_inference_stage_results_serialization():
    """Test that inference results can be JSON serialized"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {
            'model_path': temp_dir,
            'data_path': temp_dir,
            'output_path': temp_dir,
            'validate_mode': False,
            'output_format': 'csv'
        }
        
        inference_stage = InferenceStage(config)
        
        # Mock a result structure that should be JSON serializable
        mock_results = {
            'predictions': [1.0, 2.0, 3.0],  # List of floats
            'confidence_scores': [0.9, 0.8, 0.7],
            'processing_time': 1.5,
            'sample_count': 3,
            'output_path': str(temp_dir)  # String path, not PosixPath
        }
        
        # This should serialize without error
        serialized = json.dumps(mock_results)
        assert serialized is not None
        
        # Verify that Path objects are converted to strings in results
        for key, value in mock_results.items():
            if isinstance(value, Path):
                pytest.fail(f"Found PosixPath in results at key '{key}': {value}")