# Reasoning: Legacy CLI Cleanup

## Task Analysis  
Clean up deprecated CLI commands (clustering and prediction) from main.py

## Current State Analysis
Based on context, these commands need cleanup:
- `clustering` - Legacy command, functionality integrated into other stages
- `prediction` - Retired command, warning already displays

## Design Constraints
1. Must not break existing functionality
2. Should provide clear migration guidance to users
3. Commands should be removed cleanly without leaving dead code
4. Need to update help text and command listings

## Implementation Strategy

### 1. Identify Commands to Remove
- Find clustering and prediction command definitions
- Check for any dependencies or shared utilities
- Verify deprecation status

### 2. Safe Removal Process
- Remove command definitions
- Clean up imports that are no longer needed
- Update help documentation
- Ensure no regression in remaining commands

### 3. Testing Strategy
- Verify removed commands no longer appear in help
- Test remaining commands still work
- No import or runtime errors

## Expected Outcomes
- Cleaner CLI with only supported commands
- Reduced maintenance burden
- Clear command set for users