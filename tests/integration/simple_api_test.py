"""
Simple API Test - Test the PipelineRunner directly without CLI comparison
"""

import asyncio
import tempfile
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

async def test_api_only():
    """Test just the API execution."""
    print("🧪 Testing API execution only...")
    
    try:
        # Import API components
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
        from emuses.foundation_fastapi_service.job_manager import JobManager
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            jobs_dir = temp_path / 'jobs'
            output_dir = temp_path / 'output'
            
            jobs_dir.mkdir()
            output_dir.mkdir()
            
            # Create job manager
            job_manager = JobManager(jobs_dir)
            job_id = str(job_manager.generate_job_id())
            
            # Create the job directory and initial status
            job_dir = job_manager.create_job_directory(job_id)
            job_manager.update_job_status(job_id, "SUBMITTED", message="Job created for API test")
            
            print(f"✅ Created job manager with job ID: {job_id}")
            print(f"✅ Created job directory: {job_dir}")
            
            # Create pipeline runner
            pipeline_runner = PipelineRunner(job_manager, pipeline_timeout=60)
            print("✅ Created pipeline runner")
            
            # Create minimal test context (make sure it's serializable)
            np.random.seed(42)
            context = {
                'input_matrix': np.random.randn(20, 10).tolist(),  # Convert to list for serialization
                'scores': np.random.randn(20, 2).tolist(),         # Convert to list for serialization
                'config': {
                    'output_folder': str(output_dir),               # Convert Path to string
                    'prefix': 'API_Test'
                }
            }
            
            print("✅ Created test context")
            print(f"   Input matrix shape: {np.array(context['input_matrix']).shape}")
            print(f"   Scores shape: {np.array(context['scores']).shape}")
            
            # Test execution
            print("🚀 Executing pipeline...")
            result_context = await pipeline_runner.execute_pipeline(job_id, context)
            
            print("✅ Pipeline execution completed!")
            print(f"   Result context keys: {list(result_context.keys())}")
            
            # Check job status
            job_status = job_manager.get_job_status(job_id)
            print(f"   Final job status: {job_status.get('status', 'unknown')}")
            
            return True
            
    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🧪 Simple API Test")
    print("=" * 30)
    
    success = asyncio.run(test_api_only())
    
    if success:
        print("\n🎉 API test completed successfully!")
    else:
        print("\n💥 API test failed!")
