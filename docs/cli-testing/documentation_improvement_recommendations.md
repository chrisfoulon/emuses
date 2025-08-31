# Documentation Clarity Issues Identified

## Overview
During CLI testing, several areas where documentation could be clearer were identified. These don't represent bugs but rather opportunities to improve user understanding.

## Issue 0: Documentation/Implementation Mismatch - CRITICAL

### Problem: Command Name Error
**Critical Error Found**: Documentation references `emuses prediction` but the actual command is `emuses inference`.

### Evidence
- **CLI_REFERENCE.md mentions**: `prediction` command
- **Actual CLI shows**: `inference` command in help output
- **Status**: Complete mismatch - documentation is incorrect

### Impact  
- **High**: Users following documentation will get command not found errors
- **Confusing**: Creates doubt about documentation reliability  
- **Workflow breaking**: Prevents users from completing inference tasks

### Immediate Action Required
1. **Update CLI_REFERENCE.md** - Replace all `prediction` references with `inference`
2. **Search entire docs** for other `prediction` command references  
3. **Verify command examples** work with actual CLI
4. **Add note about name change** if this was a recent change

## Issue 1: Model Registry Workflow Confusion

### Problem
The relationship between different registry operations is not clearly documented:

1. **`emuses full`** creates models but doesn't automatically register them
2. **`emuses models install`** registers models into the default registry 
3. **`emuses models list`** shows models from the default registry (not necessarily local files)

### User Confusion Points
- Users might expect `emuses full` output to automatically appear in `emuses models list`
- The `--registry` parameter behavior is not intuitive:
  - When used with `install`, where does it actually install the model?
  - When used with `list`, does it show models from that specific registry?

### Documentation Improvement Recommendations
1. **Clear workflow diagrams** showing model creation → installation → listing
2. **Explicit explanation** of default vs custom registries
3. **Examples** showing the complete workflow from training to listing
4. **Parameter documentation** clarifying exactly what `--registry` does for each command

## Issue 2: Output Redirection Requirements

### Problem  
CLI commands don't show output in some terminal configurations without explicit redirection (`2>&1`).

### User Impact
- Commands appear to "hang" or do nothing
- Users may think the CLI is broken
- No indication that the command is actually working

### Documentation Improvement Recommendations
1. **Troubleshooting section** in docs explaining output capture
2. **Example commands** showing proper redirection syntax
3. **Terminal compatibility notes** for different environments

## Issue 3: Registry Location Confusion

### Problem
It's not clear where models are stored by default vs when custom paths are used.

### Questions Raised During Testing
- Where is the "default registry" located?
- How do local registries (created by `emuses full`) relate to the global registry?
- Can you have multiple registries? How do you switch between them?

### Documentation Improvement Recommendations
1. **Registry concepts explained** in a dedicated section
2. **File system layout** showing where different types of data are stored
3. **Multi-registry workflows** if they're supported

## Issue 4: Command Dependencies

### Problem
Some commands depend on others but this isn't clearly documented.

### Examples Found
- `emuses models install` requires model files created by `emuses full`
- Admin commands require a service to be running
- Some model commands might require specific model types

### Documentation Improvement Recommendations  
1. **Prerequisite sections** for each command
2. **Error message improvements** pointing to missing dependencies
3. **Workflow tutorials** showing command sequences

## Issue 5: Parameter Documentation Gaps

### Problem
Some parameter behaviors discovered during testing weren't obvious from documentation.

### Examples
- What file formats does `emuses models install` accept?
- How does `--force` work with model installation?
- What are the valid values for optimization dictionaries?

### Documentation Improvement Recommendations
1. **Complete parameter reference** with examples
2. **Format specifications** for input files  
3. **Validation error examples** showing what goes wrong and why

## Testing Value

These documentation issues were only discoverable through systematic CLI testing:
- **Real user workflow simulation** revealed confusion points
- **Cross-command testing** showed dependency relationships
- **Error condition testing** highlighted missing guidance

This demonstrates the value of comprehensive CLI testing beyond just functional verification.

## Recommendations for Documentation Team

1. **User journey mapping** - trace through complete workflows from new user perspective
2. **Error message audit** - ensure all error messages provide actionable guidance
3. **Cross-reference validation** - ensure CLI docs match actual command behavior  
4. **Terminal compatibility testing** - verify examples work in different environments

These improvements would significantly enhance user experience without requiring code changes.
