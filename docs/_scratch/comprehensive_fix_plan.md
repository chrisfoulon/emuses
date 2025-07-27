# Comprehensive Fix Plan for Critical Issues

## Issue 1: Rerun Command Parsing (CRITICAL)

### Root Cause
- **OLD command files**: Created before our quoting fix lack proper quoting for paths with spaces
- **Parsing failure**: `shlex.split()` splits unquoted paths on spaces
- **Backward compatibility**: Need to handle both old (unquoted) and new (quoted) command files

### Solution Strategy
1. **Smart parsing**: Detect if command file uses quoted paths or not
2. **Fallback logic**: If parsing fails, try heuristic reconstruction
3. **Path detection**: Use regex to identify file paths and regroup split parts
4. **Validation**: Verify paths exist before executing

### Implementation Plan
- Modify `load_command_from_folder()` with backward-compatible parsing
- Add heuristic path reconstruction for unquoted commands
- Add validation that reconstructed paths exist on filesystem
- Update tests to cover both old and new command file formats

## Issue 2: SQLite Network Drive Error (CRITICAL)

### Root Cause
- **SQLite limitation**: Cannot handle file locking on network drives (Dropbox, SMB, NFS)
- **Optuna storage**: Uses SQLite by default, fails on cloud-synced folders
- **Disk I/O error**: `sqlite3.OperationalError: disk I/O error` on network drives

### Solution Strategy
1. **Network drive detection**: Identify when output folder is on network/cloud storage
2. **Local temp storage**: Use local temp directory for SQLite database
3. **Database relocation**: Move SQLite files to local storage, symlink or copy back
4. **Alternative storage**: For network drives, use in-memory SQLite with periodic dumps

### Implementation Plan
- Add network drive detection utility (check for `/mnt/`, Dropbox paths, UNC paths)
- Modify Optuna storage setup to use local temp for databases
- Add cleanup logic to copy study results back to output folder
- Provide user warnings and guidance about network drive limitations

## Issue 3: Testing and Validation

### Test Coverage Needed
1. **Rerun backward compatibility**: Test with old command file formats
2. **Path edge cases**: Unicode, very long paths, special characters
3. **Network drive scenarios**: Test detection and fallback behavior
4. **Cross-platform**: Ensure solutions work on Windows, Linux, macOS

### Integration Strategy
- Update existing tests to cover both old and new formats
- Add specific tests for network drive scenarios
- Mock filesystem operations for reliable testing
- Validate end-to-end workflows with both issues

## Priority and Timeline
1. **IMMEDIATE**: Fix rerun parsing with backward compatibility (30 min)
2. **HIGH**: Implement network drive detection and fallback (60 min)  
3. **IMPORTANT**: Comprehensive testing (45 min)
4. **QUALITY**: Update documentation and LAD plans (15 min)

Total estimated time: 2.5 hours

## Success Criteria
- [x] Old command files work with rerun command
- [x] New command files continue to work correctly  
- [x] Network drive paths automatically use local SQLite storage
- [x] Clear user messaging about storage location choices
- [x] All existing functionality preserved
- [x] Cross-platform compatibility maintained