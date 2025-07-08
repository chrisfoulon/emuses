#!/usr/bin/env python3
"""
Simple test to verify API connectivity and basic functionality.
"""

import asyncio
import httpx
import json
import tempfile
import csv
from pathlib import Path


async def test_api_with_dummy_data():
    """Test API with dummy data files."""
    
    print("🚀 Testing API with dummy data...")
    
    # Create dummy data files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create dummy features file
        features_file = temp_path / "features.csv"
        with open(features_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['subject'] + [f'feature_{i}' for i in range(10)])
            for i in range(100):
                writer.writerow([f'subj_{i}'] + [i*j for j in range(10)])
        
        # Create dummy scores file
        scores_file = temp_path / "scores.csv"
        with open(scores_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['fluid_int_adj'])
            for i in range(100):
                writer.writerow([i % 10])
        
        print(f"✅ Created dummy data files:")
        print(f"   Features: {features_file}")
        print(f"   Scores: {scores_file}")
        
        # Test API connection
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            try:
                # Health check
                response = await client.get("/api/health")
                if response.status_code != 200:
                    print("❌ API health check failed")
                    return False
                
                print("✅ API health check passed")
                
                # Submit job
                job_request = {
                    "pipeline_config": {
                        "input_file": str(features_file),
                        "scores_file": str(scores_file),
                        "output_folder": str(temp_path / "output"),
                        "columns_are_features": True,
                        "input_header": 0,
                        "input_index_column": 0,
                        "input_normalization": "robust",
                        "scores_header": 0,
                        "scores_index_column": None,
                        "interactive_plot": False,
                        "umap_trials": 1,
                        "hdbscan_trials": 1,
                        "optim_dict": "optim_dict_hcp",
                        "hdbscan_jobs": 2,
                        "optuna_trials": 2,
                        "prediction_optim_dict": "optim_dict_predict",
                        "prefix": "API_Test"
                    },
                    "job_name": "Simple API Test",
                    "description": "Testing API with dummy data"
                }
                
                print("📤 Submitting job...")
                response = await client.post("/api/v1/jobs/pipeline/full", json=job_request)
                
                if response.status_code != 201:
                    print(f"❌ Job submission failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False
                
                job_data = response.json()
                job_id = job_data['job_id']
                print(f"✅ Job submitted with ID: {job_id}")
                
                # Track progress for a few iterations
                print("📊 Tracking progress...")
                for i in range(5):
                    response = await client.get(f"/api/v1/jobs/{job_id}/status")
                    if response.status_code != 200:
                        print(f"❌ Status check failed: {response.status_code}")
                        return False
                    
                    status_data = response.json()
                    status = status_data['status']
                    progress = status_data.get('progress', 0.0)
                    current_stage = status_data.get('current_stage', 'N/A')
                    
                    print(f"   Status: {status}, Progress: {progress:.1%}, Stage: {current_stage}")
                    
                    if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                        print(f"✅ Job finished with status: {status}")
                        return status == "COMPLETED"
                    
                    await asyncio.sleep(5)
                
                print("✅ Job is running (stopped tracking after 5 checks)")
                return True
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                return False


if __name__ == "__main__":
    success = asyncio.run(test_api_with_dummy_data())
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)
