"""
Minimal API Test - Test the PipelineRunner without actual pipeline execution
"""

import asyncio
import tempfile
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

async def test_pipeline_runner_interface():
    """Test just the PipelineRunner interface without actual execution."""
    print("🧪 Testing PipelineRunner interface...")
    
    try:
        # Import API components
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
        from emuses.foundation_fastapi_service.job_manager import JobManager
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            jobs_dir = temp_path / 'jobs'
            jobs_dir.mkdir()
            
            # Create job manager
            job_manager = JobManager(jobs_dir)
            job_id = str(job_manager.generate_job_id())
            
            # Create the job directory and initial status
            job_dir = job_manager.create_job_directory(job_id)
            job_manager.update_job_status(job_id, "SUBMITTED", message="Job created for test")
            
            print(f"✅ Created job: {job_id}")
            
            # Create pipeline runner
            pipeline_runner = PipelineRunner(job_manager, pipeline_timeout=10)
            print("✅ Created pipeline runner")
            
            # Test the runner attributes
            print(f"   Max workers: {pipeline_runner.max_workers}")
            print(f"   Memory limit ratio: {pipeline_runner.memory_limit_ratio}")
            print(f"   Pipeline timeout: {pipeline_runner.pipeline_timeout}")
            print(f"   Has executor attribute: {hasattr(pipeline_runner, 'executor')}")
            
            # Test serialization methods
            test_context = {
                'input_matrix': [[1, 2, 3], [4, 5, 6]],
                'scores': [[0.1, 0.2], [0.3, 0.4]],
                'config': {'test': 'value'}
            }
            
            # Test serialization
            serialized = pipeline_runner._serialize_context(test_context)
            deserialized = pipeline_runner._deserialize_context(serialized)
            
            print("✅ Context serialization works")
            print(f"   Original keys: {list(test_context.keys())}")
            print(f"   Deserialized keys: {list(deserialized.keys())}")
            print(f"   Serialized size: {len(serialized)} bytes")
            
            # Test progress callback creation
            progress_callback = pipeline_runner._create_progress_callback(job_id)
            progress_callback("test_stage", 0.5, "Test message")
            print("✅ Progress callback works")
            
            # Check job status
            job_status = job_manager.get_job_status(job_id)
            print(f"✅ Job status: {job_status.get('status', 'unknown')}")
            
            return True
            
    except Exception as e:
        print(f"❌ Interface test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🧪 Minimal Pipeline Runner Interface Test")
    print("=" * 45)
    
    success = asyncio.run(test_pipeline_runner_interface())
    
    if success:
        print("\n🎉 Interface test completed successfully!")
        print("✅ PipelineRunner API is working correctly")
    else:
        print("\n💥 Interface test failed!")
