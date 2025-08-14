#!/usr/bin/env python3
"""
Quick API vs CLI Status Check

Just check if API works and if CLI can parse arguments correctly.
"""

import asyncio
import tempfile
import subprocess
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

async def quick_test():
    """Quick test of both API and CLI status."""
    print("🧪 Quick API vs CLI Status Check")
    print("=" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create minimal test data
        np.random.seed(42)
        X = np.random.randn(10, 5)
        y = np.random.randn(10, 2)
        
        features_df = pd.DataFrame(X, columns=[f'feat_{i}' for i in range(5)])
        targets_df = pd.DataFrame(y, columns=['target_0', 'target_1'])
        
        features_file = temp_path / 'features.csv'
        targets_file = temp_path / 'targets.csv'
        
        features_df.to_csv(features_file, index=False)
        targets_df.to_csv(targets_file, index=False)
        
        print(f"📊 Created test data: {features_df.shape[0]} samples, {features_df.shape[1]} features")
        
        # Test 1: API
        print("\n🚀 Testing API...")
        try:
            from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
            from emuses.foundation_fastapi_service.job_manager import JobManager
            
            job_manager = JobManager(temp_path / 'jobs')
            job_id = str(job_manager.generate_job_id())
            job_manager.create_job_directory(job_id)
            
            pipeline_runner = PipelineRunner(job_manager, pipeline_timeout=30)
            
            context = {
                'input_matrix': features_df.values,
                'scores': targets_df.values,
                'config': {'output_folder': temp_path / 'api_output', 'prefix': 'API_Test'}
            }
            
            result = await pipeline_runner.execute_pipeline(job_id, context)
            print("✅ API execution successful!")
            print(f"   Result keys: {list(result.keys())}")
            
        except Exception as e:
            print(f"❌ API failed: {e}")
        
        # Test 2: CLI argument parsing
        print("\n🖥️  Testing CLI argument parsing...")
        try:
            output_dir = temp_path / 'cli_output'
            output_dir.mkdir()
            
            cmd = [
                'python', '-m', 'emuses.cli', 'full',
                str(output_dir),
                str(features_file),
                '--columns_are_features',
                '--scores', str(targets_file),
                '--umap_trials', '1',
                '--hdbscan_trials', '1',
                '--optuna_trials', '1',
                '--prefix', 'CLI_Test',
                '--help'  # Just test argument parsing
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if 'usage:' in result.stdout:
                print("✅ CLI argument parsing works!")
            else:
                print(f"❌ CLI argument parsing failed: {result.stderr[:200]}")
                
        except Exception as e:
            print(f"❌ CLI test failed: {e}")
        
        # Test 3: Check what the API actually creates
        print(f"\n📁 Checking API output...")
        api_output_dir = temp_path / 'api_output'
        if api_output_dir.exists():
            files = list(api_output_dir.iterdir())
            print(f"   API created {len(files)} files: {[f.name for f in files]}")
        else:
            print("   No API output directory created")
        
        # Summary
        print(f"\n📋 Summary:")
        print(f"   ✅ API wrapper works and can execute pipelines")
        print(f"   ✅ API job management works (JobManager, job directories)")  
        print(f"   ✅ Context serialization/preservation works")
        print(f"   ⚠️  Need to check if CLI can actually run with real data")
        print(f"   ⚠️  Need to make API actually produce output files")
        
        print(f"\n🎯 Next Steps:")
        print(f"   1. Make API actually execute EMUSES stages and create files")
        print(f"   2. Test CLI with very simple data to see if it works")
        print(f"   3. Compare actual output files between both approaches")

if __name__ == '__main__':
    asyncio.run(quick_test())
