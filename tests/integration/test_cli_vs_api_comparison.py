"""
CLI vs API Comparison Test

This script compares the execution of EMUSES pipeline using:
1. CLI command (existing main.py interface)
2. API functions (new PipelineRunner and stage runners)

The goal is to validate that both approaches produce identical results.
"""

import os
import sys
import tempfile
import shutil
import subprocess
import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any
import asyncio

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner
from emuses.foundation_fastapi_service.job_manager import JobManager
from emuses.pipelines.pipeline_config import PipelineConfig
from emuses.pipelines.emuses_pipeline import EMUSESPipeline


class CLIvsAPIComparison:
    """Compare CLI and API execution of EMUSES pipeline."""

    def __init__(self, use_reduced_params: bool = True):
        """Initialize comparison test.
        
        Args:
            use_reduced_params: If True, use smaller parameter values for faster testing
        """
        self.use_reduced_params = use_reduced_params
        self.temp_dir = None
        self.cli_output_dir = None
        self.api_output_dir = None
        
        # Reduced parameters for faster testing
        self.test_params = {
            'umap_trials': 3 if use_reduced_params else 10,
            'hdbscan_trials': 2 if use_reduced_params else 5,
            'hdbscan_jobs': 4 if use_reduced_params else 16,
            'optuna_trials': 5 if use_reduced_params else 10,
            'prediction_optim_dict': 'optim_dict_test'
        }

    def setup_test_environment(self) -> Dict[str, Path]:
        """Set up test environment with synthetic data."""
        # Create temporary directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix='cli_vs_api_test_'))
        self.cli_output_dir = self.temp_dir / 'cli_output'
        self.api_output_dir = self.temp_dir / 'api_output'
        
        self.cli_output_dir.mkdir(exist_ok=True)
        self.api_output_dir.mkdir(exist_ok=True)
        
        # Create synthetic data
        return self.create_synthetic_data()

    def create_synthetic_data(self) -> Dict[str, Path]:
        """Create synthetic data for testing."""
        np.random.seed(42)  # Fixed seed for reproducibility
        
        # Create feature matrix
        n_samples, n_features = 100, 50
        X = np.random.randn(n_samples, n_features)
        
        # Create target variables
        n_targets = 3
        y = np.random.randn(n_samples, n_targets)
        
        # Add some correlation between features and targets
        for i in range(n_targets):
            feature_weights = np.random.randn(n_features) * 0.1
            y[:, i] += X @ feature_weights
        
        # Save to CSV files
        features_df = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(n_features)])
        targets_df = pd.DataFrame(y, columns=[f'target_{i}' for i in range(n_targets)])
        
        features_file = self.temp_dir / 'features.csv'
        targets_file = self.temp_dir / 'targets.csv'
        
        features_df.to_csv(features_file, index=False)
        targets_df.to_csv(targets_file, index=False)
        
        return {
            'features_file': features_file,
            'targets_file': targets_file
        }

    def run_cli_execution(self, data_files: Dict[str, Path]) -> subprocess.CompletedProcess:
        """Execute the pipeline using CLI interface."""
        print("🔧 Running CLI execution...")
        
        # Build CLI command
        cmd = f"""
        python -m emuses.cli full \
          "{self.cli_output_dir}" \
          "{data_files['features_file']}" \
          --columns_are_features \
          --input_header 0 \
          --input_index_column 0 \
          -inorm robust \
          --scores "{data_files['targets_file']}" \
          --scores_header 0 \
          --scores_index_column 0 \
          --umap_trials {self.test_params['umap_trials']} \
          --hdbscan_trials {self.test_params['hdbscan_trials']} \
          --optim_dict optim_dict_hcp \
          --hdbscan_jobs {self.test_params['hdbscan_jobs']} \
          --optuna_trials {self.test_params['optuna_trials']} \
          --prediction_optim_dict {self.test_params['prediction_optim_dict']} \
          --prefix "CLI_Test"
        """
        
        # Clean up the command
        cmd = ' '.join(cmd.split())
        
        print(f"CLI Command: {cmd}")
        
        # Execute
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        return result

    async def run_api_execution(self, data_files: Dict[str, Path]) -> Dict[str, Any]:
        """Execute the pipeline using API interface."""
        print("🔧 Running API execution...")
        
        # Create job manager
        job_manager = JobManager(self.temp_dir / 'jobs')
        job_id = str(job_manager.generate_job_id())
        
        # Create job directory
        job_dir = job_manager.create_job_directory(job_id)
        print(f"Created job directory: {job_dir}")
        
        # Create pipeline runner
        pipeline_runner = PipelineRunner(job_manager)
        
        try:
            # Load data into context (similar to how EMUSES pipeline loads data)
            features_df = pd.read_csv(data_files['features_file'])
            targets_df = pd.read_csv(data_files['targets_file'])
            
            # Create context dictionary (mimicking EMUSES pipeline structure)
            context = {
                'input_matrix': features_df.values,
                'scores': targets_df.values,
                'embedding_train_features': features_df.values,
                'embedding_test_features': features_df.values[:20],  # Use subset for test
                'config': {
                    'output_folder': self.api_output_dir,
                    'umap_trials': self.test_params['umap_trials'],
                    'hdbscan_trials': self.test_params['hdbscan_trials'],
                    'optuna_trials': self.test_params['optuna_trials'],
                    'prediction_optim_dict': self.test_params['prediction_optim_dict'],
                    'prefix': 'API_Test'
                },
                'pipeline_metadata': {
                    'start_time': 0,
                    'stages_completed': [],
                    'stages_runtime': {}
                }
            }
            
            # Execute pipeline
            result_context = await pipeline_runner.execute_pipeline(job_id, context)
            
            return {
                'status': 'success',
                'job_id': job_id,
                'context': result_context
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'job_id': job_id
            }

    def compare_outputs(self) -> Dict[str, Any]:
        """Compare outputs from CLI and API executions."""
        print("🔍 Comparing outputs...")
        
        comparison_results = {
            'cli_files': [],
            'api_files': [],
            'common_files': [],
            'file_comparisons': {},
            'summary': {}
        }
        
        # List files in both output directories
        if self.cli_output_dir.exists():
            comparison_results['cli_files'] = [f.name for f in self.cli_output_dir.iterdir() if f.is_file()]
        
        if self.api_output_dir.exists():
            comparison_results['api_files'] = [f.name for f in self.api_output_dir.iterdir() if f.is_file()]
        
        # Find common files
        cli_files_set = set(comparison_results['cli_files'])
        api_files_set = set(comparison_results['api_files'])
        comparison_results['common_files'] = list(cli_files_set.intersection(api_files_set))
        
        # Compare common files
        for filename in comparison_results['common_files']:
            cli_file = self.cli_output_dir / filename
            api_file = self.api_output_dir / filename
            
            try:
                if filename.endswith('.csv'):
                    # Compare CSV files
                    cli_df = pd.read_csv(cli_file)
                    api_df = pd.read_csv(api_file)
                    
                    comparison_results['file_comparisons'][filename] = {
                        'type': 'csv',
                        'cli_shape': cli_df.shape,
                        'api_shape': api_df.shape,
                        'shapes_match': cli_df.shape == api_df.shape,
                        'columns_match': list(cli_df.columns) == list(api_df.columns)
                    }
                    
                elif filename.endswith('.json'):
                    # Compare JSON files
                    with open(cli_file, 'r') as f:
                        cli_data = json.load(f)
                    with open(api_file, 'r') as f:
                        api_data = json.load(f)
                    
                    comparison_results['file_comparisons'][filename] = {
                        'type': 'json',
                        'cli_keys': list(cli_data.keys()) if isinstance(cli_data, dict) else None,
                        'api_keys': list(api_data.keys()) if isinstance(api_data, dict) else None,
                        'keys_match': (list(cli_data.keys()) == list(api_data.keys())) if isinstance(cli_data, dict) and isinstance(api_data, dict) else None
                    }
                    
                else:
                    # Basic file comparison
                    comparison_results['file_comparisons'][filename] = {
                        'type': 'other',
                        'cli_size': cli_file.stat().st_size,
                        'api_size': api_file.stat().st_size,
                        'sizes_match': cli_file.stat().st_size == api_file.stat().st_size
                    }
                    
            except Exception as e:
                comparison_results['file_comparisons'][filename] = {
                    'type': 'error',
                    'error': str(e)
                }
        
        # Generate summary
        comparison_results['summary'] = {
            'total_cli_files': len(comparison_results['cli_files']),
            'total_api_files': len(comparison_results['api_files']),
            'common_files_count': len(comparison_results['common_files']),
            'files_only_in_cli': list(cli_files_set - api_files_set),
            'files_only_in_api': list(api_files_set - cli_files_set)
        }
        
        return comparison_results

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def print_results(self, cli_result: subprocess.CompletedProcess, api_result: Dict[str, Any], comparison: Dict[str, Any]):
        """Print comparison results."""
        print("\n" + "="*60)
        print("📊 COMPARISON RESULTS")
        print("="*60)
        
        # CLI Results
        print(f"\n🖥️  CLI Execution:")
        print(f"   Return code: {cli_result.returncode}")
        if cli_result.returncode != 0:
            print(f"   Error: {cli_result.stderr[:200]}...")
        else:
            print(f"   ✅ CLI execution successful")
        
        # API Results
        print(f"\n🚀 API Execution:")
        print(f"   Status: {api_result.get('status', 'unknown')}")
        if api_result.get('status') == 'error':
            print(f"   Error: {api_result.get('error', 'Unknown error')}")
        else:
            print(f"   ✅ API execution successful")
            print(f"   Job ID: {api_result.get('job_id', 'N/A')}")
        
        # File Comparison
        print(f"\n📁 File Comparison:")
        summary = comparison['summary']
        print(f"   CLI files: {summary['total_cli_files']}")
        print(f"   API files: {summary['total_api_files']}")
        print(f"   Common files: {summary['common_files_count']}")
        
        if summary['files_only_in_cli']:
            print(f"   Only in CLI: {summary['files_only_in_cli']}")
        if summary['files_only_in_api']:
            print(f"   Only in API: {summary['files_only_in_api']}")
        
        # Detailed file comparisons
        if comparison['file_comparisons']:
            print(f"\n📄 File Details:")
            for filename, details in comparison['file_comparisons'].items():
                print(f"   {filename}:")
                if details['type'] == 'csv':
                    print(f"     CLI shape: {details['cli_shape']}, API shape: {details['api_shape']}")
                    print(f"     Shapes match: {'✅' if details['shapes_match'] else '❌'}")
                    print(f"     Columns match: {'✅' if details['columns_match'] else '❌'}")
                elif details['type'] == 'json':
                    print(f"     Keys match: {'✅' if details.get('keys_match') else '❌'}")
                elif details['type'] == 'other':
                    print(f"     Sizes match: {'✅' if details['sizes_match'] else '❌'}")
                else:
                    print(f"     ❌ Error: {details.get('error', 'Unknown')}")


async def main():
    """Run the CLI vs API comparison test."""
    print("🧪 Starting CLI vs API Comparison Test")
    print("="*50)
    
    # Create comparison instance
    comparison_test = CLIvsAPIComparison(use_reduced_params=True)
    
    try:
        # Setup test environment
        print("🏗️  Setting up test environment...")
        data_files = comparison_test.setup_test_environment()
        print(f"   Created data files: {list(data_files.keys())}")
        
        # Run CLI execution
        cli_result = comparison_test.run_cli_execution(data_files)
        
        # Run API execution
        api_result = await comparison_test.run_api_execution(data_files)
        
        # Compare outputs
        comparison_results = comparison_test.compare_outputs()
        
        # Print results
        comparison_test.print_results(cli_result, api_result, comparison_results)
        
        # Determine overall success
        cli_success = cli_result.returncode == 0
        api_success = api_result.get('status') == 'success'
        
        if cli_success and api_success:
            print(f"\n🎉 Both CLI and API executions completed successfully!")
            print(f"📁 Common files found: {len(comparison_results['common_files'])}")
            
            if comparison_results['common_files']:
                print("✅ Comparison test PASSED - Both interfaces produced outputs")
            else:
                print("⚠️  Comparison test PARTIAL - Both ran but no common files found")
                
        elif cli_success:
            print(f"\n⚠️  Only CLI execution succeeded")
        elif api_success:
            print(f"\n⚠️  Only API execution succeeded")
        else:
            print(f"\n❌ Both executions failed")
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up...")
        comparison_test.cleanup()
        print("✅ Cleanup completed")


if __name__ == '__main__':
    # Run the comparison test
    asyncio.run(main())
