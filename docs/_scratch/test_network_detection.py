#!/usr/bin/env python3

import sys
from pathlib import Path

# Add current directory to path to import from emuses
sys.path.insert(0, '.')

from emuses.utils.network_drive_detection import (
    is_network_or_cloud_path, 
    get_sqlite_safe_location,
    setup_optuna_storage_safe,
    validate_sqlite_compatibility
)

# Test paths
test_paths = [
    Path("/home/tolhsadum/new_cli_test_wsl"),  # Local path
    Path("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/new_cli_test_wsl"),  # Dropbox path
    Path("/tmp/test"),  # Definitely local
    Path("/mnt/c/Users/test"),  # WSL mount (might be considered network)
]

print("=== NETWORK DRIVE DETECTION TEST ===")

for path in test_paths:
    print(f"\nTesting: {path}")
    
    # Test detection
    is_network, reason = is_network_or_cloud_path(path)
    print(f"  Is network/cloud: {is_network}")
    if is_network:
        print(f"  Reason: {reason}")
    
    # Test safe location
    safe_location, is_relocated, explanation = get_sqlite_safe_location(path)
    print(f"  Safe location: {safe_location}")
    print(f"  Is relocated: {is_relocated}")
    if explanation:
        print(f"  Explanation: {explanation}")
    
    # Test Optuna storage setup
    print(f"  Testing Optuna storage setup...")
    try:
        storage_url = setup_optuna_storage_safe("test_study", path)
        print(f"  Storage URL: {storage_url}")
    except Exception as e:
        print(f"  ❌ Optuna setup failed: {e}")

print("\n=== SQLITE COMPATIBILITY TEST ===")

# Test SQLite compatibility on different paths
for path in test_paths:
    if path.exists() or str(path).startswith('/tmp'):
        print(f"\nTesting SQLite compatibility: {path}")
        try:
            is_compatible, error_msg = validate_sqlite_compatibility(path)
            if is_compatible:
                print(f"  ✅ SQLite compatible")
            else:
                print(f"  ❌ SQLite incompatible: {error_msg}")
        except Exception as e:
            print(f"  ❌ Test failed: {e}")
    else:
        print(f"\nSkipping SQLite test for non-existent path: {path}")

print("\n=== SPECIFIC DROPBOX TEST ===")
# Test the specific problematic path
dropbox_path = Path("/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/new_cli_test_wsl_dropbox")
print(f"Testing specific Dropbox path: {dropbox_path}")

is_network, reason = is_network_or_cloud_path(dropbox_path)
print(f"Detected as network/cloud: {is_network} ({reason})")

if is_network:
    safe_location, is_relocated, explanation = get_sqlite_safe_location(dropbox_path)
    print(f"Safe SQLite location: {safe_location}")
    print(f"User explanation: {explanation}")
    
    # Test creating the safe location
    try:
        storage_url = setup_optuna_storage_safe("test_dropbox_study", dropbox_path)
        print(f"Generated storage URL: {storage_url}")
        
        # Extract the directory from the URL
        if "sqlite:///" in storage_url:
            db_path = Path(storage_url.replace("sqlite:///", ""))
            db_dir = db_path.parent
            print(f"SQLite database directory: {db_dir}")
            print(f"Directory exists: {db_dir.exists()}")
    except Exception as e:
        print(f"❌ Failed to create safe storage: {e}")
        import traceback
        traceback.print_exc()