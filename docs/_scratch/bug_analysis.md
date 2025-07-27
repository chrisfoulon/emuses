# Bug Analysis - Phase 1 Critical Issues

## Issue #1: Rerun Command Still Failing

### Problem
The rerun command is still parsing paths with spaces incorrectly:
```
Error: Got unexpected extra arguments (Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv)
```

### Root Cause Analysis
Looking at the command.txt file:
```
/home/tolhsadum/miniforge3/envs/emuses/bin/emuses full /home/tolhsadum/new_cli_test_wsl /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv --columns_are_features --input_header 0 --input_index_column 0 --input_normalization robust --scores /mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/fluid_int_adj.csv --scores_header 0 --interactive_plot --umap_trials 1 --hdbscan_trials 1 --optuna_trials 10 --hdbscan_jobs 16
```

**The paths with spaces are NOT quoted in the saved command!**

This means our quoting fix in `save_command_to_output_folder()` is not working correctly.

### Investigation Needed
1. Check if the quoting function is being called
2. Verify the quoting logic works for these specific paths
3. Test the shlex.split behavior with unquoted vs quoted paths

## Issue #2: Database I/O Error on Network Drives

### Problem
SQLite fails with "disk I/O error" when output folder is on Dropbox/network drive:
```
sqlite3.OperationalError: disk I/O error
optuna.exceptions.StorageInternalError: An exception is raised during the commit
```

### Root Cause Analysis
- SQLite has known issues with network drives (Dropbox, SMB, NFS)
- SQLite requires POSIX-compliant file locking which network drives often don't support
- This affects Optuna's database storage in `/mnt/s/GIN Dropbox/...` paths

### Research Needed
1. How to detect network/cloud storage paths
2. Alternative storage strategies for Optuna on network drives
3. Fallback mechanisms or local temp storage options

## Impact Assessment
Both issues are **CRITICAL** user-facing bugs that prevent core functionality:
1. Rerun command fails for any path with spaces
2. Pipeline fails completely on network drives (common user scenario)

## Next Steps
1. Fix rerun quoting issue with proper testing
2. Research and implement network drive detection and fallback
3. Add comprehensive tests for both scenarios
4. Update LAD plans to reflect these as high-priority unsolved tasks