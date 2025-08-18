# CLI Legacy Cleanup Implementation Plan

## Implementation Overview

Remove deprecated `clustering` and `prediction` commands from the EMUSES CLI to simplify the interface and reduce technical debt.

## Phase 1: Command Removal (4 hours)

### 1.1 Code Cleanup

#### Remove Deprecated Command Parsers
- [ ] Remove `clustering` subparser from `emuses/scripts/main.py` (lines ~428-441)
- [ ] Remove `prediction` subparser from `emuses/scripts/main.py` (lines ~467-485)
- [ ] Remove associated argument helper functions if no longer used
- [ ] Clean up unused imports and references

#### Update Command Logic
- [ ] Remove command handling logic for deprecated commands
- [ ] Update stage addition logic in main() function (lines ~520-542)
- [ ] Remove deprecated stage instantiation code
- [ ] Clean up conditional logic for removed commands

### 1.2 Help and Documentation Cleanup

#### CLI Help Updates
- [ ] Remove deprecated commands from CLI help output
- [ ] Update main help text to reflect current command set
- [ ] Ensure help text is accurate and consistent
- [ ] Test help output for all remaining commands

#### Code Documentation
- [ ] Remove deprecated command references from docstrings
- [ ] Update module-level documentation
- [ ] Clean up inline comments referencing removed commands
- [ ] Update function documentation as needed

### Implementation Tasks - Phase 1

#### Command Parser Cleanup
- [ ] Identify all code sections related to deprecated commands
- [ ] Remove subparser definitions and configurations
- [ ] Clean up argument parsing functions
- [ ] Test CLI parsing after removal

#### Logic Flow Cleanup
- [ ] Remove command routing for deprecated commands
- [ ] Clean up stage selection logic
- [ ] Remove unused conditional branches
- [ ] Simplify remaining command handling

## Phase 2: Testing and Validation (2 hours)

### 2.1 Functionality Testing

#### Remaining Commands Validation
- [ ] Test `emuses full` command functionality
- [ ] Test `emuses umap` command functionality
- [ ] Test `emuses heatmap` command functionality
- [ ] Verify all argument parsing works correctly

#### Error Handling
- [ ] Test error messages for invalid commands
- [ ] Ensure graceful handling of removed command usage
- [ ] Verify help system works correctly
- [ ] Test edge cases and argument validation

### 2.2 Regression Testing

#### Pipeline Integration
- [ ] Verify full pipeline still works correctly
- [ ] Test individual stage commands
- [ ] Ensure no breaking changes to existing workflows
- [ ] Validate output formats and file generation

#### Cross-Platform Testing
- [ ] Test CLI on Linux/macOS/Windows (if applicable)
- [ ] Verify path handling still works correctly
- [ ] Test with various argument combinations
- [ ] Ensure consistent behavior across platforms

### Implementation Tasks - Phase 2

#### Comprehensive Testing
- [ ] Create test cases for all remaining commands
- [ ] Test argument parsing and validation
- [ ] Verify error messages are appropriate
- [ ] Test help system functionality

#### Integration Validation
- [ ] Run full integration tests
- [ ] Verify pipeline functionality unchanged
- [ ] Test with real datasets and configurations
- [ ] Ensure backward compatibility maintained

## Phase 3: Documentation Updates (2 hours)

### 3.1 User-Facing Documentation

#### CLI Reference Updates
- [ ] Update CLI command documentation
- [ ] Remove deprecated command examples
- [ ] Add migration guidance for affected users
- [ ] Update command reference tables

#### Migration Guide
- [ ] Create migration guide for `clustering` command users
- [ ] Create migration guide for `prediction` command users  
- [ ] Document replacement workflows
- [ ] Provide example command conversions

### 3.2 Developer Documentation

#### Code Documentation
- [ ] Update inline code documentation
- [ ] Clean up function and class docstrings
- [ ] Update module-level documentation
- [ ] Remove outdated comments and references

#### API Documentation
- [ ] Update API documentation if affected
- [ ] Remove deprecated endpoint references
- [ ] Update code examples and samples
- [ ] Ensure consistency across documentation

### Implementation Tasks - Phase 3

#### Documentation Overhaul
- [ ] Audit all documentation for deprecated command references
- [ ] Update CLI help text and examples
- [ ] Create comprehensive migration guide
- [ ] Test documentation accuracy

#### User Communication
- [ ] Prepare changelog entries for deprecated commands
- [ ] Create user notification content
- [ ] Update README and getting started guides
- [ ] Ensure clear communication about changes

## Testing Strategy

### Functional Testing
- [ ] All remaining CLI commands work correctly
- [ ] Argument parsing functions as expected
- [ ] Help system displays accurate information
- [ ] Error handling provides clear guidance

### Regression Testing
- [ ] Existing workflows continue to function
- [ ] No performance degradation introduced
- [ ] Output formats remain consistent
- [ ] Pipeline integration unaffected

### User Experience Testing
- [ ] Migration guidance is clear and actionable
- [ ] Error messages guide users to correct commands
- [ ] Documentation accurately reflects current state
- [ ] New users can easily understand available commands

## Success Criteria

### Technical Validation
- [ ] Deprecated commands completely removed from codebase
- [ ] No references to removed commands remain in code
- [ ] All remaining commands function correctly
- [ ] Code complexity reduced through cleanup

### User Experience
- [ ] Clear migration path provided for affected users
- [ ] Simplified CLI interface with only active commands
- [ ] Accurate documentation reflecting current state
- [ ] Improved maintainability for future development

### Quality Standards
- [ ] No regressions introduced to existing functionality
- [ ] Comprehensive testing validates all changes
- [ ] Documentation updated and accurate
- [ ] Clean, maintainable codebase after cleanup

## Migration Strategy

### For `clustering` Command Users
```bash
# Old (deprecated):
emuses clustering /path/to/output --load_embeddings /path/to/embeddings

# New (recommended):
emuses heatmap /path/to/output /path/to/dataset --load_embeddings /path/to/embeddings
```

### For `prediction` Command Users  
```bash
# Old (deprecated):
emuses prediction /path/to/output /path/to/dataset

# New (recommended):
emuses heatmap /path/to/output /path/to/dataset
```

## Risk Mitigation

### User Impact
- **Workflow Disruption**: Clear migration guide and examples
- **Documentation Lag**: Comprehensive documentation update
- **Support Requests**: FAQ and troubleshooting section

### Technical Risks
- **Regression Introduction**: Comprehensive regression testing
- **Code Dependencies**: Careful dependency analysis before removal
- **Integration Issues**: Full integration test suite execution

---
*Created: 2025-08-06*
*Estimated Duration: 1 day (8 hours)*
*Priority: Low (Technical debt cleanup)*