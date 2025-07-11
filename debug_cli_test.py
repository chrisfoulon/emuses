#!/usr/bin/env python3
"""Debug script to understand the CLI integration test failure."""

import os
import tempfile
import shutil
import subprocess
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add the emuses directory to the path
sys.path.insert(0, str(Path(__file__).parent))

# Import the test class
from tests.integration.test_real_world_pipeline import RealWorldIntegrationTest

def main():
    """Debug the CLI integration test."""
    print("🔍 Debugging CLI integration test...")
    
    # Create test suite
    suite = RealWorldIntegrationTest(use_ci_params=True)
    
    try:
        # Setup environment
        print("\n1. Setting up test environment...")
        data_files = suite.setup_test_environment()
        
        print(f"   - Temp dir: {suite.temp_dir}")
        print(f"   - Output dir: {data_files['output_folder']}")
        print(f"   - Features train: {data_files['features_train']}")
        print(f"   - Labels train: {data_files['labels_train']}")
        
        # Check data files were created
        for key, path in data_files.items():
            if isinstance(path, Path) and path.suffix == '.csv':
                print(f"   - {key}: {path.exists()} ({path})")
                if path.exists():
                    df = pd.read_csv(path)
                    print(f"     Shape: {df.shape}")
        
        # Build command
        print("\n2. Building CLI command...")
        command_params = {**suite.params, **data_files}
        cmd = suite.CLI_COMMAND_TEMPLATE.format(**command_params)
        cmd = ' '.join(cmd.split())
        
        print(f"   Command: {cmd}")
        
        # Run command
        print("\n3. Running CLI command...")
        result = suite.run_cli_command(data_files)
        
        print(f"   Return code: {result.returncode}")
        if result.stdout:
            print(f"   STDOUT: {result.stdout[:500]}...")
        if result.stderr:
            print(f"   STDERR: {result.stderr[:500]}...")
        
        # Check output directory
        print("\n4. Checking output directory...")
        output_dir = data_files['output_folder']
        print(f"   Output dir exists: {output_dir.exists()}")
        
        if output_dir.exists():
            files = list(output_dir.iterdir())
            print(f"   Files in output dir: {len(files)}")
            for file in files:
                print(f"     - {file.name} ({'dir' if file.is_dir() else 'file'})")
        
        # Validate structure
        print("\n5. Validating output structure...")
        validations = suite.validate_output_structure(output_dir)
        for file, exists in validations.items():
            status = "✓" if exists else "✗"
            print(f"   {status} {file}")
        
        # Summary
        found_files = sum(validations.values())
        total_files = len(validations)
        print(f"\n📊 Summary: {found_files}/{total_files} expected files found")
        
        if found_files == 0:
            print("\n🚨 No expected files found! This suggests the CLI command failed or")
            print("   produced output in a different location/format than expected.")
            
            # Let's check if main.py exists and is executable
            main_script = Path(suite.params['script_path'])
            print(f"\n🔍 Checking main script: {main_script}")
            print(f"   Exists: {main_script.exists()}")
            if main_script.exists():
                print(f"   Is file: {main_script.is_file()}")
        
    except Exception as e:
        print(f"\n❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up temp directory: {suite.temp_dir}")
        suite.teardown_test_environment()

if __name__ == "__main__":
    main()
