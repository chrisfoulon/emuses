#!/usr/bin/env python3
"""
Test script to run the HCP real-world example using the actual FastAPI service.

This script demonstrates how to:
1. Connect to the running FastAPI service
2. Submit a full pipeline job via API using file paths
3. Track job progress in real-time
4. Download results when complete

The current implementation uses file paths (server-side files) since
file upload endpoints are not yet implemented in the API.
"""

import asyncio
import httpx
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

from tests.conftest import EXTERNAL_DATA_ROOT


def detect_and_convert_paths() -> Dict[str, Path]:
    """
    Locate the HCP dataset files.

    The dataset lives outside the repo and its mount point differs per machine and
    OS, so it is configured via the EMUSES_TEST_DATA_ROOT environment variable
    rather than hardcoded. Point it at the directory containing ``HCP_psy``.
    """
    if EXTERNAL_DATA_ROOT is None:
        raise OSError(
            "EMUSES_TEST_DATA_ROOT is not set; cannot locate the HCP dataset"
        )

    base_path = EXTERNAL_DATA_ROOT / "HCP_psy"

    return {
        'base_path': base_path,
        'features_file': base_path / "selected_columns_data.csv",
        'scores_file': base_path / "fluid_int_adj.csv"
    }


async def validate_files(paths: Dict[str, Path]) -> Dict[str, str]:
    """Validate that input files exist and return their paths.
    
    Since the current API expects file paths on the server, we use the files directly.
    """
    file_paths = {}
    
    # Validate features file
    print(">> Validating features file...")
    if not paths['features_file'].exists():
        raise Exception(f"Features file not found: {paths['features_file']}")
    print(f"   Found: {paths['features_file']}")
    file_paths['features_file'] = str(paths['features_file'])
    
    # Validate scores file
    print(">> Validating scores file...")
    if not paths['scores_file'].exists():
        raise Exception(f"Scores file not found: {paths['scores_file']}")
    print(f"   Found: {paths['scores_file']}")
    file_paths['scores_file'] = str(paths['scores_file'])
    
    return file_paths


async def submit_pipeline_job(client: httpx.AsyncClient, file_paths: Dict[str, str]) -> str:
    """Submit a full pipeline job via API."""
    
    # Output folder sits alongside the dataset, under the configured data root
    output_folder = str((detect_and_convert_paths()['base_path'] / "is_it_running2_api").resolve())
    
    job_request = {
        "pipeline_config": {
            "input_file": file_paths['features_file'],
            "scores_file": file_paths['scores_file'],
            "output_folder": output_folder,
            "columns_are_features": True,
            "input_header": 0,
            "input_index_column": 0,
            "input_normalization": "robust",
            "scores_header": 0,
            "scores_index_column": None,
            "interactive_plot": True,
            "umap_trials": 1,
            "hdbscan_trials": 1,
            "optim_dict": "optim_dict_hcp",
            "hdbscan_jobs": 16,
            "optuna_trials": 10,
            "prediction_optim_dict": "optim_dict_predict",
            "prefix": "HCP_API_Real_Test"
        },
        "job_name": "HCP Real-World API Test",
        "description": "Testing HCP dataset through real API endpoints"
    }
    
    print(">> Submitting pipeline job...")
    response = await client.post("/api/v1/jobs/pipeline/full", json=job_request)
    
    if response.status_code != 201:
        raise Exception(f"Failed to submit job: {response.text}")
    
    job_data = response.json()
    job_id = job_data['job_id']
    print(f"   Job submitted with ID: {job_id}")
    
    return job_id


async def track_job_progress(client: httpx.AsyncClient, job_id: str) -> bool:
    """Track job progress until completion."""
    
    print(">> Tracking job progress...")
    
    while True:
        response = await client.get(f"/api/v1/jobs/{job_id}/status")
        if response.status_code != 200:
            raise Exception(f"Failed to get job status: {response.text}")
        
        status_data = response.json()
        status = status_data['status']
        progress = status_data.get('progress', 0.0)
        current_stage = status_data.get('current_stage', 'N/A')
        
        print(f"   Status: {status}, Progress: {progress:.1%}, Stage: {current_stage}")
        
        if status == "COMPLETED":
            print("   Job completed successfully!")
            return True
        elif status == "FAILED":
            print(f"   Job failed: {status_data.get('message', 'No error message')}")
            return False
        elif status == "CANCELLED":
            print("   Job was cancelled")
            return False
        
        # Wait before next check
        await asyncio.sleep(10)


async def download_results(client: httpx.AsyncClient, job_id: str) -> None:
    """Download job results."""
    
    print(">> Downloading results...")
    
    # List available artifacts
    response = await client.get(f"/api/v1/jobs/{job_id}/artifacts")
    if response.status_code != 200:
        raise Exception(f"Failed to list artifacts: {response.text}")
    
    artifacts = response.json()['artifacts']
    print(f"   Found {len(artifacts)} artifacts:")
    
    for artifact in artifacts:
        print(f"   - {artifact['filename']} ({artifact['size']} bytes)")
    
    # Download key artifacts
    key_files = [
        'performance_summary_statistics.csv',
        'embeddings.npy',
        'heatmap_results.png'
    ]
    
    for filename in key_files:
        if any(artifact['filename'] == filename for artifact in artifacts):
            print(f"   Downloading {filename}...")
            response = await client.get(f"/api/v1/jobs/{job_id}/artifacts/{filename}")
            if response.status_code == 200:
                with open(f"downloaded_{filename}", 'wb') as f:
                    f.write(response.content)
                print(f"   Saved as downloaded_{filename}")
            else:
                print(f"   Failed to download {filename}: {response.text}")


async def main():
    """Main execution function."""
    
    print("🚀 HCP Real-World Example - Real API Test")
    print("=" * 60)
    
    # Check if FastAPI service is running
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        try:
            # Test health endpoint
            response = await client.get("/api/health")
            if response.status_code != 200:
                print("❌ FastAPI service is not running or not healthy")
                print("   Please start the service with: python -m emuses.foundation_fastapi_service.app")
                return False
            
            print("✅ FastAPI service is running and healthy")
            
            # Get input file paths
            paths = detect_and_convert_paths()
            
            # Validate files exist and get their paths
            file_paths = await validate_files(paths)
            print("✅ Input files validated")
            
            # Submit pipeline job using file paths
            job_id = await submit_pipeline_job(client, file_paths)
            
            # Track job progress
            success = await track_job_progress(client, job_id)
            
            if success:
                # Download results
                await download_results(client, job_id)
                print("\n✅ HCP real-world API test completed successfully!")
            else:
                print("\n❌ HCP real-world API test failed")
            
            return success
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
