# Reasoning: Explicit Validation Flag Implementation

## Task Analysis
Implement `--validate` flag for explicit validation mode in the inference command.

## Current State
- Validation mode works automatically via label detection
- InferenceStage detects labels in context and switches modes
- Need to add explicit control via CLI flag

## Design Constraints
1. Must maintain backward compatibility
2. Should not break existing automatic detection
3. Flag should override automatic detection when provided
4. Must be consistent with existing CLI patterns

## Implementation Strategy

### 1. CLI Flag Addition
- Add `--validate` flag to inference command in `emuses/cli/main.py`
- Add to the inference function signature
- Pass through to the execution layer

### 2. InferenceStage Integration
- Add validate_mode parameter to config
- Update InferenceStage logic to check explicit flag first
- Maintain automatic detection as fallback

### 3. Testing Strategy
- Test explicit flag overrides automatic detection
- Test backward compatibility (no flag = automatic detection)
- Test edge cases (flag + no labels, flag + labels)

## Validation Steps
1. Find existing inference CLI command
2. Add validate flag following existing patterns
3. Update InferenceStage to respect flag
4. Write tests for new functionality
5. Verify no regression in existing tests

## Expected Outcomes
- Users can force validation mode with `--validate`
- Existing functionality unchanged
- Clear documentation of new flag