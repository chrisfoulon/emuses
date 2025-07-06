#!/usr/bin/env python3
"""
Simple CLI vs API Test

A minimal test to compare CLI and API execution of EMUSES pipeline.
"""

import os
import sys
import tempfile
import subprocess
import asyncio
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def test_data(temp_dir):
    """Create test data files."""
    return create_test_data(temp_dir)


@pytest.fixture
def features_file(test_data):
    """Get the features file path."""
    return test_data[0]


@pytest.fixture
def targets_file(test_data):
    """Get the targets file path."""
    return test_data[1]


@pytest.fixture
def output_dir(temp_dir):
    """Create output directory."""
    output_path = temp_dir / 'output'
    output_path.mkdir(exist_ok=True)
    return output_path


def create_test_data(temp_dir):
    """Create minimal test data."""
    np.random.seed(42)
    
    # Small dataset for quick testing
    n_samples, n_features = 50, 20
    X = np.random.randn(n_samples, n_features)
    y = np.random.randn(n_samples, 2)
    
    features_df = pd.DataFrame(X, columns=[f'feat_{i}' for i in range(n_features)])
    targets_df = pd.DataFrame(y, columns=['target_0', 'target_1'])
    
    features_file = temp_dir / 'features.csv'
    targets_file = temp_dir / 'targets.csv'
    
    features_df.to_csv(features_file, index=False)
    targets_df.to_csv(targets_file, index=False)
    
    return features_file, targets_file


def test_cli_execution(features_file, targets_file, output_dir):
    """Test CLI execution."""
    print("🔧 Testing CLI execution...")
    
    cmd = [
        'python', 'emuses/scripts/main.py', 'full',
        str(features_file), str(targets_file),
        '--columns_are_features',
        '--input_header', '0',
        '--input_index_column', '0',
        '--scores', str(targets_file),
        '--scores_header', '0',
        '--scores_index_column', '0',
        '--umap_trials', '2',
        '--hdbscan_trials', '1',
        '--optuna_trials', '3',
        '--output_folder', str(output_dir),
        '--prefix', 'CLI_Test'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=project_root
        )
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout[:500] if result.stdout else '',
            'stderr': result.stderr[:500] if result.stderr else ''
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': 'Command timed out after 5 minutes'
        }
    except Exception as e:
        return {
            'success': False,
            'returncode': -1,
            'stdout': '',
            'stderr': f'Exception: {str(e)}'
        }


async def test_api_execution(features_file, targets_file, output_dir):
    """Test API execution."""
    print("🔧 Testing API execution...")
    
    try:
        # Import API components
        from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
        from emuses.foundation_fastapi_service.job_manager import JobManager
        
        # Create job manager
        jobs_dir = output_dir.parent / 'api_jobs'
        jobs_dir.mkdir(exist_ok=True)
        
        job_manager = JobManager(jobs_dir)
        job_id = str(job_manager.generate_job_id())
        
        # Create pipeline runner
        pipeline_runner = PipelineRunner(job_manager, pipeline_timeout=300)
        
        # Load data
        features_df = pd.read_csv(features_file)
        targets_df = pd.read_csv(targets_file)
        
        # Create minimal context
        context = {
            'input_matrix': features_df.values,
            'scores': targets_df.values,
            'config': {
                'output_folder': output_dir,
                'umap_trials': 2,
                'hdbscan_trials': 1,
                'optuna_trials': 3,
                'prefix': 'API_Test'
            }
        }
        
        # Execute
        result_context = await pipeline_runner.execute_pipeline(job_id, context)
        
        return {
            'success': True,
            'job_id': job_id,
            'context_keys': list(result_context.keys()),
            'message': 'API execution completed successfully'
        }
        
    except Exception as e:
        return {
            'success': False,
            'job_id': None,
            'context_keys': [],
            'message': f'API execution failed: {str(e)}'
        }


def compare_outputs(cli_output_dir, api_output_dir):
    """Compare output directories."""
    cli_files = set()
    api_files = set()
    
    if cli_output_dir.exists():
        cli_files = {f.name for f in cli_output_dir.iterdir() if f.is_file()}
    
    if api_output_dir.exists():
        api_files = {f.name for f in api_output_dir.iterdir() if f.is_file()}
    
    return {
        'cli_files': sorted(cli_files),
        'api_files': sorted(api_files),
        'common_files': sorted(cli_files.intersection(api_files)),
        'cli_only': sorted(cli_files - api_files),
        'api_only': sorted(api_files - cli_files)
    }


async def main():
    """Run the simple CLI vs API test."""
    print("🧪 Simple CLI vs API Test")
    print("=" * 40)
    
    # Create temporary directory
    with tempfile.TemporaryDirectory(prefix='cli_api_test_') as temp_dir:
        temp_path = Path(temp_dir)
        cli_output = temp_path / 'cli_output'
        api_output = temp_path / 'api_output'
        
        cli_output.mkdir()
        api_output.mkdir()
        
        try:
            # Create test data
            print("📊 Creating test data...")
            features_file, targets_file = create_test_data(temp_path)
            print(f"   Features: {features_file}")
            print(f"   Targets: {targets_file}")
            
            # Test CLI
            print("\n🖥️  Testing CLI...")
            cli_result = test_cli_execution(features_file, targets_file, cli_output)
            
            # Test API
            print("\n🚀 Testing API...")
            api_result = await test_api_execution(features_file, targets_file, api_output)
            
            # Compare results
            print("\n📊 Results:")
            print("-" * 20)
            
            print(f"CLI Success: {'✅' if cli_result['success'] else '❌'}")
            if not cli_result['success']:
                print(f"   Error: {cli_result['stderr']}")
            
            print(f"API Success: {'✅' if api_result['success'] else '❌'}")
            if not api_result['success']:
                print(f"   Error: {api_result['message']}")
            
            # Compare outputs
            comparison = compare_outputs(cli_output, api_output)
            print("\nFile Comparison:")
            print(f"   CLI files: {len(comparison['cli_files'])}")
            print(f"   API files: {len(comparison['api_files'])}")
            print(f"   Common: {len(comparison['common_files'])}")
            
            if comparison['common_files']:
                print(f"   Common files: {comparison['common_files']}")
            if comparison['cli_only']:
                print(f"   CLI only: {comparison['cli_only']}")
            if comparison['api_only']:
                print(f"   API only: {comparison['api_only']}")
            
            # Overall result
            print("\n🎯 Overall Result:")
            if cli_result['success'] and api_result['success']:
                print("✅ Both CLI and API executions successful!")
            elif cli_result['success']:
                print("⚠️  Only CLI execution successful")
            elif api_result['success']:
                print("⚠️  Only API execution successful")
            else:
                print("❌ Both executions failed")
                
        except Exception as e:
            print(f"💥 Test failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
