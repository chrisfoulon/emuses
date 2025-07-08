#!/usr/bin/env python3
"""
Test script to run the HCP real-world example using the current FastAPI service.

This script works with the current API implementation that expects file paths
instead of file uploads. This is suitable for server-side execution where
files are already available on the server filesystem.
"""

import asyncio
import httpx
import json
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional


def detect_and_convert_paths() -> Dict[str, Path]:
    """Detect OS and convert paths from the original Linux command to appropriate format."""
    system = platform.system().lower()
    
    if system == "windows":
        base_path = Path("S:/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy")
    elif system == "linux" or system == "darwin":
        base_path = Path("/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy")
    else:
        raise OSError(f"Unsupported operating system: {system}")
    
    return {
        'features_file': base_path / "selected_columns_data.csv",
        'scores_file': base_path / "fluid_int_adj.csv",
        'output_folder': base_path / "is_it_running2_api"
    }


async def submit_pipeline_job(client: httpx.AsyncClient, paths: Dict[str, Path]) -> str:
    """Submit a full pipeline job via API using file paths."""
    
    job_request = {
        "pipeline_config": {
            "input_file": str(paths['features_file']),
            "scores_file": str(paths['scores_file']),
            "output_folder": str(paths['output_folder']),
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
    
    download_dir = Path("downloaded_results")
    download_dir.mkdir(exist_ok=True)
    
    for filename in key_files:
        if any(artifact['filename'] == filename for artifact in artifacts):
            print(f"   Downloading {filename}...")
            response = await client.get(f"/api/v1/jobs/{job_id}/artifacts/{filename}")
            if response.status_code == 200:
                output_path = download_dir / filename
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"   Saved as {output_path}")
            else:
                print(f"   Failed to download {filename}: {response.text}")


async def main():
    """Main execution function."""
    
    print("🚀 HCP Real-World Example - Real API Test")
    print("=" * 60)
    
    # Check if FastAPI service is running
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        try:
            # Test health endpoint
            response = await client.get("/api/health")
            if response.status_code != 200:
                print("❌ FastAPI service is not running or not healthy")
                print("   Please start the service with:")
                print("   cd /home/chrisfoulon/neuro_apps/emuses")
                print("   python -m uvicorn emuses.foundation_fastapi_service.app:app --host 0.0.0.0 --port 8000")
                return False
            
            print("✅ FastAPI service is running and healthy")
            
            # Get input file paths
            paths = detect_and_convert_paths()
            
            # Validate files exist
            for key, path in paths.items():
                if key != 'output_folder' and not path.exists():
                    print(f"❌ File not found: {path}")
                    return False
            
            print("✅ Input files validated")
            
            # Submit pipeline job
            job_id = await submit_pipeline_job(client, paths)
            
            # Track progress
            success = await track_job_progress(client, job_id)
            
            if success:
                await download_results(client, job_id)
                print("\n✅ HCP API test completed successfully!")
            else:
                print("\n❌ HCP API test failed")
            
            return success
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
