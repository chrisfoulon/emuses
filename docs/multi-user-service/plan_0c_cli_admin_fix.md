# Plan 0c: CLI Admin HTTP Client Architecture Fix

## Overview
Fix the async/sync architectural mismatch in CLI admin commands by replacing ServiceHTTPClient with synchronous httpx client, following TDD principles and modifying existing tests.

## Problem Statement
CLI admin commands (`add-user`, `list-users`, `system-status`, `set-quota`, `cancel-job`) are broken due to:
- ServiceHTTPClient methods return coroutines but are called synchronously
- StatusRenderer.status() method doesn't exist (already fixed)
- Parameter mismatches in ServiceHTTPClient constructor (already fixed)

## Current Issues Status
- ✅ **Issue #1**: CLI command invocation (`python -m emuses` → `python -m emuses.cli`) - FIXED
- ✅ **Issue #2**: ServiceHTTPClient parameter mismatch (`service_url`→`base_url`, `token`→`auth_token`) - FIXED  
- ✅ **Issue #3**: StatusRenderer.status() → console.status() using Rich library - FIXED
- ❌ **Issue #4**: Async/sync mismatch - ServiceHTTPClient async methods called synchronously - NEEDS FIX

## Solution Architecture

### Current (Broken) Pattern:
```python
client = ServiceHTTPClient(base_url=service_url, auth_token=token)
with console.status("Loading..."):
    response = client.get("/admin/users")  # Returns coroutine, not executed
```

### Target (Clean) Pattern:
```python
import httpx
headers = {"Authorization": f"Bearer {token}"} if token else {}
base_url = service_url or "http://localhost:8000"
with console.status("Loading..."):
    response = httpx.get(f"{base_url}/admin/users", headers=headers)  # Synchronous
```

## Implementation Tasks

### Task 1: Test Strategy Analysis ✅ COMPLETED
- **Locate existing CLI admin tests**: Found `/mnt/c/Users/Tolhsadum/PycharmProjects/emuses/tests/multi-user-service/test_admin_cli.py`
- **Analyze test patterns**: Tests mock FastAPI endpoints, not ServiceHTTPClient directly
- **Identify test modification needs**: Tests will need minimal changes since they test endpoints, not client

### Task 2: Create httpx Admin Client Helper 🔄 IN PROGRESS
- **Create simple admin client**: ✅ Implemented `make_admin_request()` helper function
- **Handle deployment modes**: ✅ Supports env vars and explicit params for URL/token
- **Error handling**: ✅ Created `AdminClientError` class matching ServiceClientError interface

### Task 3: Update Admin Commands (TDD) 🔄 PARTIALLY COMPLETED
- **Modify existing tests first**: ⏳ PENDING - need to update test expectations
- **Replace ServiceHTTPClient calls**: 🔄 Started - updated add-user command, need to finish other 4 commands
- **Maintain error handling**: ✅ Preserved error message patterns with AdminClientError
- **Preserve authentication logic**: ✅ Maintained env var and parameter-based auth

### Task 4: Integration Testing ⏳ PENDING
- **Test all admin commands**: Need to complete after implementation
- **Test error scenarios**: Need to verify after implementation 
- **Test deployment modes**: Need to test after implementation
- **Regression testing**: Need to verify after implementation

### Task 5: Documentation Updates ⏳ PENDING
- **Update technical context**: Need to document new httpx approach
- **Update user documentation**: No changes needed - same CLI interface
- **Update development docs**: Need to note async/sync separation pattern

## Current Progress Status (Session End)

### Completed Work:
1. **Added httpx synchronous HTTP client**: Created `make_admin_request()` helper function
2. **Error handling compatibility**: Created `AdminClientError` class matching ServiceClientError interface  
3. **Authentication preservation**: Maintained env var and parameter-based token authentication
4. **Partial command updates**: Updated add-user command to use httpx instead of ServiceHTTPClient

### Remaining Work for Next Session:
1. **Complete command updates**: Update remaining 4 admin commands (list-users, system-status, set-quota, cancel-job)
2. **Update tests**: Modify test expectations if needed (minimal changes expected)
3. **End-to-end testing**: Test all commands with real service
4. **Documentation**: Update context files with new architecture notes

## Success Criteria
- ✅ All 5 admin commands execute successfully
- ✅ Authentication works in all deployment modes  
- ✅ Error handling matches existing patterns
- ✅ All existing tests pass (modified as needed)
- ✅ No new async complexity in CLI admin commands
- ✅ Clean, maintainable httpx-based implementation

## Risk Mitigation
- **Feature parity**: Ensure new client has same capabilities as ServiceHTTPClient for admin operations
- **Error compatibility**: Match existing error message formats for user scripts
- **Auth compatibility**: Preserve existing token/authentication workflows
- **Testing coverage**: Modify existing tests to maintain coverage levels

## Files to Modify
- `emuses/cli/admin_commands.py` (main implementation)
- `tests/multi-user-service/test_admin_cli.py` (test modifications)
- `docs/multi-user-service/admin-guide.md` (if needed)
- `docs/multi-user-service/context_0c_interface.md` (architecture notes)

## TDD Approach
1. **Red**: Run existing tests to confirm they fail with current async/sync mismatch
2. **Green**: Modify tests to expect synchronous httpx client, implement httpx solution
3. **Refactor**: Clean up implementation while keeping tests passing
4. **Verify**: Ensure all admin functionality works end-to-end