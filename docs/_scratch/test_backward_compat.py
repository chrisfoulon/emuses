#!/usr/bin/env python3

import sys
from pathlib import Path

# Add current directory to path to import from emuses
sys.path.insert(0, '.')

from emuses.cli.main import load_command_from_folder

# Test with the real command file that has unquoted paths
test_folder = Path("/home/tolhsadum/new_cli_test_wsl")

print("=== TESTING BACKWARD COMPATIBILITY FIX ===")
print(f"Testing with folder: {test_folder}")

try:
    # Load the command using our new backward-compatible function
    fixed_command = load_command_from_folder(test_folder)
    
    print(f"=== FIXED COMMAND ===")
    print(fixed_command)
    
    # Test parsing the fixed command
    import shlex
    print(f"\n=== PARSING FIXED COMMAND ===")
    try:
        parsed = shlex.split(fixed_command)
        print(f"Successfully parsed into {len(parsed)} parts:")
        
        # Look for the paths that were previously split
        path1 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv'
        path2 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv'
        
        if path1 in parsed and path2 in parsed:
            print("✅ SUCCESS: Both paths preserved correctly!")
            print(f"  Found: {path1}")
            print(f"  Found: {path2}")
        else:
            print("❌ PARTIAL: Some paths might still be split")
            for i, part in enumerate(parsed):
                if 'Dropbox' in part or 'HCP_psy' in part:
                    print(f"  {i}: {part}")
        
        # Test if this would work with the rerun command logic
        print(f"\n=== TESTING RERUN LOGIC ===")
        # Remove executable path (emuses or absolute path) from the beginning
        command_parts = shlex.split(fixed_command)
        if command_parts and ('emuses' in command_parts[0] or command_parts[0].startswith('/')):
            command_parts = command_parts[1:]  # Remove first element (executable path)
        
        print(f"Command parts for rerun: {len(command_parts)} parts")
        print(f"  Command: {command_parts[0] if len(command_parts) > 0 else 'MISSING'}")
        print(f"  Output folder: {command_parts[1] if len(command_parts) > 1 else 'MISSING'}")
        print(f"  Input dataset: {command_parts[2] if len(command_parts) > 2 else 'MISSING'}")
        
        # Check for problematic split parts
        problematic_parts = [part for part in command_parts 
                           if 'Dropbox/Chris' in part and not part.startswith('/mnt/s/GIN')]
        if problematic_parts:
            print(f"❌ STILL FOUND SPLIT PARTS: {problematic_parts}")
        else:
            print("✅ NO SPLIT PARTS DETECTED!")
        
    except Exception as e:
        print(f"❌ PARSING FAILED: {e}")
        
except Exception as e:
    print(f"❌ LOADING FAILED: {e}")
    import traceback
    traceback.print_exc()