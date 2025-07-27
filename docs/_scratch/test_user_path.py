#!/usr/bin/env python3

import sys
from pathlib import Path

# Add current directory to path to import from emuses
sys.path.insert(0, '.')

from emuses.utils.network_drive_detection import (
    is_network_or_cloud_path, 
    setup_optuna_storage_safe
)

# Test the exact path that caused the user's problem
user_dropbox_path = Path("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/new_cli_test_wsl")

print("=== USER'S EXACT PATH TEST ===")
print(f"Path: {user_dropbox_path}")

# Test detection
is_network, reason = is_network_or_cloud_path(user_dropbox_path)
print(f"Detected as network/cloud: {is_network}")
print(f"Reason: {reason}")

if is_network:
    print("\n✅ GOOD: Path will be handled by our fix")
    
    # Test the Optuna storage setup
    try:
        storage_url = setup_optuna_storage_safe("umap_nested_optimization", user_dropbox_path)
        print(f"Storage URL that will be used: {storage_url}")
        
        # This should create a local temp directory instead of using the Dropbox path
        if "/tmp/" in storage_url and "emuses_sqlite_" in storage_url:
            print("✅ SUCCESS: SQLite database will use local temp storage")
            print("✅ This should prevent the 'disk I/O error' that the user experienced")
        else:
            print("❌ PROBLEM: SQLite database is still using the network path")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
else:
    print("❌ PROBLEM: Path not detected as network drive - fix won't activate")

print("\n=== COMPARISON WITH PROBLEM PATH ===")
# The specific path from the error log
problem_path = Path("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/new_cli_test_wsl_dropbox")
print(f"Error path: {problem_path}")

is_network_problem, reason_problem = is_network_or_cloud_path(problem_path)
print(f"Detected as network/cloud: {is_network_problem} ({reason_problem})")

if is_network_problem:
    print("✅ The error path would also be handled by our fix")
else:
    print("❌ The error path would NOT be handled - need to improve detection")

print("\n=== SIMULATION OF WHAT WILL HAPPEN ===")
print("When the user runs the pipeline with the Dropbox path:")
print("1. Our network drive detection will identify it as Dropbox cloud storage")
print("2. Instead of creating SQLite database in /mnt/s/GIN Dropbox/...")
print("3. It will create SQLite database in /tmp/emuses_sqlite_XXXXX/")
print("4. This prevents the 'sqlite3.OperationalError: disk I/O error'")
print("5. Pipeline results will still be saved to the original Dropbox folder")
print("6. User gets a clear explanation of what's happening")