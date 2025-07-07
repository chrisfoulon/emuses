#!/usr/bin/env python3
"""Quick test to check what status code is returned for large JSON payload."""

import sys
from unittest.mock import MagicMock

# Mock the problematic imports
sys.modules['emuses.pipelines.emuses_pipeline'] = MagicMock()
sys.modules['emuses.pipelines.pipeline_config'] = MagicMock()
sys.modules['emuses.pipelines.umap_stage'] = MagicMock()
sys.modules['emuses.pipelines.heatmap_stage'] = MagicMock()
sys.modules['emuses.pipelines.prediction_stage'] = MagicMock()

from fastapi.testclient import TestClient

try:
    # Import the real app
    from emuses.foundation_fastapi_service.app import app
    
    client = TestClient(app)
    
    # Test large payload - test exactly what the test expects
    large_config = {
        "input_file": "input.csv",
        "scores_file": "scores.csv",
        "output_folder": "output",
        "large_data": "x" * (11 * 1024 * 1024)  # 11MB string - over the 10MB limit
    }
    
    request_data = {
        "pipeline_config": large_config
    }
    
    response = client.post("/api/v1/jobs/pipeline/full", json=request_data)
    print(f"Status code: {response.status_code}")
    if response.text:
        print(f"Response body (first 500 chars): {response.text[:500]}")
    else:
        print("No response body")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
