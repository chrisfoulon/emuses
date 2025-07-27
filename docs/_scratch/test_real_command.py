#!/usr/bin/env python3

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add current directory to path to import from emuses
sys.path.insert(0, '.')

from emuses.cli.main import save_command_to_output_folder

# Simulate the exact command that failed
test_argv = [
    '/home/tolhsadum/miniforge3/envs/emuses/bin/emuses',
    'full',
    '/home/tolhsadum/new_cli_test_wsl',
    '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv',
    '--columns_are_features',
    '--input_header',
    '0',
    '--input_index_column',
    '0',
    '--input_normalization',
    'robust',
    '--scores',
    '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv',
    '--scores_header',
    '0',
    '--interactive_plot',
    '--umap_trials',
    '1',
    '--hdbscan_trials',
    '1',
    '--optuna_trials',
    '10',
    '--hdbscan_jobs',
    '16'
]

print("=== TESTING REAL COMMAND SAVING ===")
print(f"Original argv: {test_argv[:3]}...{test_argv[-3:]}")

# Create temporary directory
with tempfile.TemporaryDirectory() as temp_dir:
    output_folder = Path(temp_dir)
    
    # Mock sys.argv with our test command
    with patch('sys.argv', test_argv):
        save_command_to_output_folder(output_folder)
    
    # Read the saved command
    command_file = output_folder / "command.txt"
    with open(command_file, 'r') as f:
        content = f.read()
    
    print(f"=== SAVED COMMAND CONTENT ===")
    print(content)
    
    # Extract just the command line (last line)
    lines = content.strip().split('\n')
    command_line = lines[-1]
    
    print(f"=== COMMAND LINE ===")
    print(command_line)
    
    # Test parsing
    import shlex
    print(f"=== PARSING TEST ===")
    try:
        parsed = shlex.split(command_line)
        print(f"Parsed into {len(parsed)} parts")
        
        # Check for the problem paths
        for i, part in enumerate(parsed):
            if 'Dropbox/Chris' in part and not part.startswith('/mnt/s/GIN'):
                print(f"❌ PROBLEM at {i}: '{part}' - path was split!")
            elif '/mnt/s/GIN Dropbox/Chris' in part:
                print(f"✅ GOOD at {i}: '{part}' - path preserved")
        
        # Check if the paths are intact
        path1 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv'
        path2 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv'
        
        if path1 in parsed and path2 in parsed:
            print("✅ Both paths preserved correctly!")
        else:
            print("❌ Paths were corrupted:")
            if path1 not in parsed:
                print(f"  Missing: {path1}")
            if path2 not in parsed:
                print(f"  Missing: {path2}")
        
    except Exception as e:
        print(f"❌ Parse error: {e}")