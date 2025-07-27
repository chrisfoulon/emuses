#!/usr/bin/env python3

import shlex

# Simulate the problematic command
test_argv = [
    '/home/tolhsadum/miniforge3/envs/emuses/bin/emuses',
    'full',
    '/home/tolhsadum/new_cli_test_wsl',
    '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv',
    '--columns_are_features',
    '--scores',
    '/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv'
]

def quote_argument_cross_platform(arg: str) -> str:
    """The current implementation from main.py"""
    # If argument doesn't need quoting, return as-is
    if not any(char in arg for char in [' ', '\t', '\n', '"', "'", '\\', '&', '|', ';', '<', '>', '(', ')', '$', '`']):
        return arg
    
    # For arguments that need quoting, use double quotes
    # Handle any existing double quotes and backslashes properly
    escaped_arg = arg.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped_arg}"'

print("=== ORIGINAL ARGS ===")
for i, arg in enumerate(test_argv):
    print(f"{i}: {arg}")

print("\n=== QUOTED ARGS ===")
quoted_args = [quote_argument_cross_platform(arg) for arg in test_argv]
for i, arg in enumerate(quoted_args):
    print(f"{i}: {arg}")

command = ' '.join(quoted_args)
print(f"\n=== FULL COMMAND ===")
print(command)

print(f"\n=== PARSING RESULT ===")
try:
    parsed = shlex.split(command)
    print(f"Parsed into {len(parsed)} parts:")
    for i, part in enumerate(parsed):
        print(f"  {i}: {part}")
        
    # Check if original args match parsed args
    print(f"\n=== ROUNDTRIP VERIFICATION ===")
    if parsed == test_argv:
        print("✅ PERFECT: Original args == Parsed args")
    else:
        print("❌ MISMATCH: Original args != Parsed args")
        print(f"Original: {len(test_argv)} args")
        print(f"Parsed:   {len(parsed)} args")
        
        for i, (orig, parsed_arg) in enumerate(zip(test_argv, parsed)):
            if orig != parsed_arg:
                print(f"  Diff at {i}: '{orig}' != '{parsed_arg}'")
        
except Exception as e:
    print(f"❌ Parse error: {e}")

# Test the specific problem case
print(f"\n=== TESTING REAL COMMAND FROM FILE ===")
real_command = "/home/tolhsadum/miniforge3/envs/emuses/bin/emuses full /home/tolhsadum/new_cli_test_wsl /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv --columns_are_features --input_header 0 --input_index_column 0 --input_normalization robust --scores /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv --scores_header 0 --interactive_plot --umap_trials 1 --hdbscan_trials 1 --optuna_trials 10 --hdbscan_jobs 16"

try:
    real_parsed = shlex.split(real_command)
    print(f"Real command parsed into {len(real_parsed)} parts:")
    for i, part in enumerate(real_parsed):
        print(f"  {i}: {part}")
        
    # Look for the problem
    problem_found = False
    for part in real_parsed:
        if "Dropbox/Chris" in part and not part.startswith("/mnt/s/GIN"):
            print(f"❌ FOUND PROBLEM: '{part}' - path was split!")
            problem_found = True
    
    if not problem_found:
        print("✅ No obvious path splitting detected")
        
except Exception as e:
    print(f"❌ Real command parse error: {e}")