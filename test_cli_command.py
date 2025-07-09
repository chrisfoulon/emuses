#!/usr/bin/env python3
"""
Test script to run the EMUSES CLI command with synthetic data.
"""

import tempfile
import pandas as pd
import numpy as np
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.fixture
def test_data():
    """Create synthetic test data that matches the expected format."""
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix='emuses_test_'))
    
    # Create synthetic features data (CSV with features as columns)
    np.random.seed(42)
    n_samples = 100
    n_features = 50
    
    # Create features data
    features_data = np.random.randn(n_samples, n_features)
    features_df = pd.DataFrame(
        features_data,
        columns=[f'feature_{i}' for i in range(n_features)]
    )
    features_df.index = [f'sample_{i}' for i in range(n_samples)]
    
    features_file = temp_dir / 'features.csv'
    features_df.to_csv(features_file, index=True)
    
    # Create synthetic scores data
    n_targets = 3
    scores_data = np.random.randn(n_samples, n_targets)
    scores_df = pd.DataFrame(
        scores_data,
        columns=[f'target_{i}' for i in range(n_targets)]
    )
    scores_df.index = [f'sample_{i}' for i in range(n_samples)]
    
    scores_file = temp_dir / 'scores.csv'
    scores_df.to_csv(scores_file, index=True)
    
    # Create output directory
    output_dir = temp_dir / 'output'
    output_dir.mkdir(exist_ok=True)
    
    yield temp_dir, features_file, scores_file, output_dir
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def features_file(test_data):
    """Return features file path"""
    return test_data[1]


@pytest.fixture
def scores_file(test_data):
    """Return scores file path"""
    return test_data[2]


@pytest.fixture
def output_dir(test_data):
    """Return output directory path"""
    return test_data[3]


def create_test_data():
    """Legacy function - use test_data fixture instead"""
    pass


def test_emuses_command(features_file, scores_file, output_dir):
    """Test the EMUSES command with synthetic data."""
    
    # Build the command
    cmd = [
        sys.executable, 
        'emuses/scripts/main.py',
        'full',
        str(output_dir),  # output_folder
        str(features_file),  # input_dataset
        '--columns_are_features',
        '--input_header', '0',
        '--input_index_column', '0',
        '-inorm', 'robust',
        '--scores', str(scores_file),
        '--scores_header', '0',
        '--scores_index_column', '0',
        '--interactive_plot',
        '--umap_trials', '1',
        '--hdbscan_trials', '1',
        '--optim_dict', 'optim_dict_default',  # Use default instead of optim_dict_hcp
        '--hdbscan_jobs', '2',  # Reduce from 16 to 2 for testing
        '--prediction_optim_dict', 'optim_dict_predict'
    ]
    
    print("🚀 Running EMUSES command:")
    print(' '.join(cmd))
    print()
    
    # Run the command
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=Path.cwd(),
            timeout=300  # 5 minute timeout
        )
        
        print(f"Return code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        
        return result.returncode == 0, result
        
    except subprocess.TimeoutExpired:
        print("❌ Command timed out after 5 minutes")
        return False, None
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False, None

def main():
    """Main test function."""
    
    print("🔬 Testing EMUSES CLI command with synthetic data...")
    print("=" * 60)
    
    try:
        # Create test data
        print("📊 Creating synthetic test data...")
        temp_dir, features_file, scores_file, output_dir = create_test_data()
        
        print(f"✅ Test data created in: {temp_dir}")
        print(f"  Features file: {features_file}")
        print(f"  Scores file: {scores_file}")
        print(f"  Output directory: {output_dir}")
        print()
        
        # Test the command
        success, result = test_emuses_command(features_file, scores_file, output_dir)
        
        if success:
            print("✅ EMUSES command executed successfully!")
            
            # Check output files
            print("\n📁 Checking output files:")
            output_files = list(output_dir.rglob('*'))
            for f in output_files:
                if f.is_file():
                    print(f"  {f.relative_to(output_dir)}")
        else:
            print("❌ EMUSES command failed")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if 'temp_dir' in locals():
            import shutil
            shutil.rmtree(temp_dir)
            print(f"\n🧹 Cleaned up temporary directory: {temp_dir}")

if __name__ == "__main__":
    main()
