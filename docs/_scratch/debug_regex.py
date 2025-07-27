#!/usr/bin/env python3

import re

# The actual command line from the file
command_line = "/home/tolhsadum/miniforge3/envs/emuses/bin/emuses full /home/tolhsadum/new_cli_test_wsl /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv --columns_are_features --input_header 0 --input_index_column 0 --input_normalization robust --scores /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv --scores_header 0 --interactive_plot --umap_trials 1 --hdbscan_trials 1 --optuna_trials 10 --hdbscan_jobs 16"

print("=== ORIGINAL COMMAND ===")
print(command_line)

# Current regex pattern
pattern = r'(/mnt/s/GIN)\s+(Dropbox/[^/\s]+)\s+(Foulon/[^/\s]+/[^/\s]+/[^/\s]+/[^\s]+\.csv)'

print(f"\n=== TESTING REGEX PATTERN ===")
print(f"Pattern: {pattern}")

matches = re.findall(pattern, command_line)
print(f"Matches found: {len(matches)}")
for i, match in enumerate(matches):
    print(f"  Match {i}: {match}")

# Test with a more flexible pattern
flexible_pattern = r'(/mnt/s/GIN)\s+(Dropbox/\S+)\s+(Foulon/\S+\.csv)'
print(f"\n=== TESTING FLEXIBLE PATTERN ===")
print(f"Pattern: {flexible_pattern}")

flexible_matches = re.findall(flexible_pattern, command_line)
print(f"Matches found: {len(flexible_matches)}")
for i, match in enumerate(flexible_matches):
    print(f"  Match {i}: {match}")

# Let's try to see what the actual text looks like around the problem areas
print(f"\n=== ANALYZING PROBLEM AREAS ===")
parts = command_line.split()
for i, part in enumerate(parts):
    if '/mnt/s/GIN' in part or 'Dropbox/Chris' in part or 'selected_columns_data.csv' in part or 'fluid_int_adj.csv' in part:
        context_start = max(0, i-2)
        context_end = min(len(parts), i+3)
        context = parts[context_start:context_end]
        print(f"  Context around '{part}' (index {i}): {context}")

# Test an even simpler approach - just look for the specific broken parts
print(f"\n=== SIMPLE REPLACEMENT APPROACH ===")

# Replace the specific broken patterns we know about
fixed = command_line
fixed = re.sub(r'/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data\.csv', 
               '"/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv"', fixed)
fixed = re.sub(r'/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj\.csv', 
               '"/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv"', fixed)

print("Fixed command:")
print(fixed)

# Test parsing
import shlex
try:
    parsed = shlex.split(fixed)
    print(f"\nParsed into {len(parsed)} parts")
    
    expected_path1 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv'
    expected_path2 = '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv'
    
    has_path1 = expected_path1 in parsed
    has_path2 = expected_path2 in parsed
    
    print(f"Has path 1? {has_path1}")
    print(f"Has path 2? {has_path2}")
    
    if has_path1 and has_path2:
        print("✅ SUCCESS!")
    else:
        print("❌ Still not working")
        
except Exception as e:
    print(f"❌ Parsing failed: {e}")