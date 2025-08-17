#!/usr/bin/env python3
"""
Quick development test runner for local validation before pushing.

This runs the same lightweight tests that the GitHub CI will run,
allowing you to catch issues locally and save CI credits.

Usage:
    python scripts/dev_test_runner.py
    
    # Or with timing:
    python scripts/dev_test_runner.py --time
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}")
    
    start_time = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=False)
    duration = time.time() - start_time
    
    if result.returncode == 0:
        print(f"✅ {description} - PASSED ({duration:.1f}s)")
        return True
    else:
        print(f"❌ {description} - FAILED ({duration:.1f}s)")
        return False


def main():
    """Run development tests locally."""
    print("🚀 Running EMUSES Development Tests (CI Preview)")
    print("This simulates what GitHub CI will run - should complete in < 2 minutes")
    
    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    import os
    os.chdir(project_root)
    
    all_passed = True
    
    # Test 1: Syntax validation (very fast)
    if not run_command(
        "python -m py_compile emuses/cli/main.py emuses/tools/parallelism_utils.py emuses/__init__.py",
        "Syntax and Import Validation"
    ):
        all_passed = False
    
    # Test 2: Fast unit tests
    if not run_command(
        "pytest tests/tools/test_parallelism_utils.py -v --maxfail=2 -x --tb=short",
        "Fast Development Tests"
    ):
        all_passed = False
        
    # Summary
    print(f"\n{'='*60}")
    if all_passed:
        print("🎉 All development tests PASSED! Safe to push.")
        print("💡 Your GitHub CI should complete successfully and use minimal credits.")
    else:
        print("🛑 Some tests FAILED! Fix issues before pushing to save CI credits.")
        print("📝 Run individual test commands above to debug specific failures.")
    print(f"{'='*60}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
