#!/usr/bin/env python3

import sys
import shlex
from pathlib import Path

# Add current directory to path to import from emuses
sys.path.insert(0, '.')

# Get the actual problematic command
test_folder = Path("/home/tolhsadum/new_cli_test_wsl")
command_file = test_folder / "command.txt"

with open(command_file, 'r') as f:
    lines = f.readlines()

# Find the actual command line (last non-comment line)
command_line = None
for line in reversed(lines):
    line = line.strip()
    if line and not line.startswith('#'):
        command_line = line
        break

print("=== ORIGINAL COMMAND LINE ===")
print(command_line)

print("\n=== TESTING SHLEX PARSING ===")
try:
    parsed_parts = shlex.split(command_line)
    print(f"✅ SHLEX SUCCEEDED: {len(parsed_parts)} parts")
    print("This means the command is being treated as 'properly quoted' when it's not!")
    
    # Show the problematic parts
    for i, part in enumerate(parsed_parts):
        if 'Dropbox/Chris' in part and not part.startswith('/mnt/s/GIN'):
            print(f"  PROBLEM at {i}: '{part}'")
        elif '/mnt/s/GIN' in part:
            print(f"  PATH at {i}: '{part}'")
            
except ValueError as e:
    print(f"❌ SHLEX FAILED: {e}")
    print("This would trigger our backward compatibility fix")

# Test our detection logic
print("\n=== TESTING OUR DETECTION LOGIC ===")
parts_count = len(shlex.split(command_line))
print(f"Parts count: {parts_count}")
print(f"Parts >= 3? {parts_count >= 3}")

# The issue is that shlex.split() succeeds even with unquoted paths!
# We need a different detection method

print("\n=== BETTER DETECTION METHOD ===")
# Check if the parsed command has the expected paths intact
expected_path1 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv'
expected_path2 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv'

parsed = shlex.split(command_line)
has_intact_paths = expected_path1 in parsed and expected_path2 in parsed

print(f"Expected path 1 in parsed? {expected_path1 in parsed}")
print(f"Expected path 2 in parsed? {expected_path2 in parsed}")
print(f"Both paths intact? {has_intact_paths}")

if not has_intact_paths:
    print("🎯 THIS IS HOW WE SHOULD DETECT THE PROBLEM!")
    print("The command needs fixing because the expected paths are split")

# Test manual reconstruction
print("\n=== MANUAL RECONSTRUCTION TEST ===")
from emuses.cli.main import _fix_unquoted_command

try:
    fixed = _fix_unquoted_command(command_line)
    print("Fixed command:")
    print(fixed)
    
    # Test parsing fixed command
    fixed_parsed = shlex.split(fixed)
    print(f"\nFixed command parsed into {len(fixed_parsed)} parts")
    
    fixed_has_intact_paths = expected_path1 in fixed_parsed and expected_path2 in fixed_parsed
    print(f"Fixed version has intact paths? {fixed_has_intact_paths}")
    
except Exception as e:
    print(f"❌ FIXING FAILED: {e}")
    import traceback
    traceback.print_exc()