# Model Registry - Sub-Plan 1: Foundation & Local Mode

## Implementation Overview

**Goal**: Implement local file-based model registry with CLI integration  
**Duration**: 1 week  
**Focus**: Foundation classes and local mode functionality  

## Progress Tracking Protocol
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"  
3. Run tests to verify completion
4. Only mark complete after successful testing

## Task Breakdown

### Phase 1.1: Foundation Classes ║ tests/model_registry/test_local_registry.py ║ Core registry functionality ║ L

- [x] **Task 1.1.1: Create LocalModelRegistry class**
  - [x] 1.1.1.a: Create `emuses/tools/local_model_registry.py` module
  - [x] 1.1.1.b: Implement constructor with directory initialization
  - [x] 1.1.1.c: Add NumPy-style docstrings and type hints
  - [x] 1.1.1.d: Create basic directory structure (~/.emuses/models/)

- [x] **Task 1.1.2: Implement model installation**
  - [x] 1.1.2.a: Add `install_model()` method with ModelIOManager integration
  - [x] 1.1.2.b: Implement model validation using existing manifest system
  - [x] 1.1.2.c: Add model copying with verification
  - [x] 1.1.2.d: Handle installation conflicts and versioning

- [x] **Task 1.1.3: Implement registry index management**
  - [x] 1.1.3.a: Design registry.json schema for model metadata
  - [x] 1.1.3.b: Implement index reading and writing operations
  - [x] 1.1.3.c: Add index update triggers for model operations
  - [x] 1.1.3.d: Implement index validation and repair functionality

### Phase 1.2: Model Discovery ║ tests/model_registry/test_model_discovery.py ║ Query and filter operations ║ M

- [x] **Task 1.2.1: Implement model listing**
  - [x] 1.2.1.a: Add `list_models()` method with filter support
  - [x] 1.2.1.b: Implement filtering by name, version, tags, model_type
  - [x] 1.2.1.c: Add sorting and pagination for large registries
  - [x] 1.2.1.d: Handle registry corruption gracefully

- [x] **Task 1.2.2: Implement model information retrieval**
  - [x] 1.2.2.a: Add `get_model_info()` method for detailed metadata
  - [x] 1.2.2.b: Implement version resolution (latest, specific, semver)
  - [x] 1.2.2.c: Include file system information (size, permissions)
  - [x] 1.2.2.d: Add manifest integrity verification

### Phase 1.3: CLI Integration ║ tests/cli/test_models_commands.py ║ User interface commands ║ M

- [x] **Task 1.3.1: Create models command group**
  - [x] 1.3.1.a: Add `models` Typer app to existing CLI structure
  - [x] 1.3.1.b: Implement command group with proper help documentation  
  - [x] 1.3.1.c: Add shell completion support for models commands
  - [x] 1.3.1.d: Ensure no conflicts with existing CLI commands

- [x] **Task 1.3.2: Implement install command**
  - [x] 1.3.2.a: Add `install` command with path validation
  - [x] 1.3.2.b: Implement progress indicators for large model installations
  - [x] 1.3.2.c: Add `--name` option for custom naming
  - [x] 1.3.2.d: Include `--force` option for overwrite handling

- [x] **Task 1.3.3: Implement discovery commands**  
  - [x] 1.3.3.a: Add `list` command with filtering options
  - [x] 1.3.3.b: Add `info` command for detailed model information
  - [x] 1.3.3.c: Implement table formatting for model lists
  - [x] 1.3.3.d: Add JSON output format option

### Phase 1.4: Model Management ║ tests/model_registry/test_model_management.py ║ Maintenance operations ║ M

- [x] **Task 1.4.1: Implement model removal**
  - [x] 1.4.1.a: Add `remove_model()` method with safety checks
  - [x] 1.4.1.b: Implement registry cleanup after removal
  - [x] 1.4.1.c: Add confirmation prompts for destructive operations
  - [x] 1.4.1.d: Handle removal of symlinks and references

- [x] **Task 1.4.2: Implement registry maintenance**
  - [x] 1.4.2.a: Add `update_index()` method for registry scanning
  - [x] 1.4.2.b: Implement orphaned entry cleanup
  - [x] 1.4.2.c: Add registry validation and repair
  - [x] 1.4.2.d: Include storage usage reporting

### Phase 1.5: Error Handling & Security ║ tests/model_registry/test_security.py ║ Robust operation ║ M

- [x] **Task 1.5.1: Implement comprehensive error handling**
  - [x] 1.5.1.a: Handle filesystem permission errors gracefully
  - [x] 1.5.1.b: Add proper error messages for invalid models
  - [x] 1.5.1.c: Implement recovery from corrupted registry files
  - [x] 1.5.1.d: Add logging for all registry operations

- [x] **Task 1.5.2: Implement security measures**
  - [x] 1.5.2.a: Integrate with existing CLI security validation
  - [x] 1.5.2.b: Add path traversal protection for model installations  
  - [x] 1.5.2.c: Validate model manifests for security issues
  - [x] 1.5.2.d: Implement storage quota awareness

### Phase 1.6: Testing & Documentation ║ Comprehensive validation ║ Quality assurance ║ L

- [x] **Task 1.6.1: Create comprehensive test suite**
  - [x] 1.6.1.a: Unit tests for LocalModelRegistry class
  - [x] 1.6.1.b: Integration tests for CLI commands
  - [x] 1.6.1.c: File system operation tests
  - [x] 1.6.1.d: Error handling and edge case tests

- [x] **Task 1.6.2: Update documentation**
  - [x] 1.6.2.a: Update context.md with actual implementation details
  - [x] 1.6.2.b: Add CLI help documentation for models commands
  - [x] 1.6.2.c: Create usage examples and common workflows
  - [x] 1.6.2.d: Document troubleshooting for common issues

## Testing Strategy

### Unit Testing
**Approach**: Test LocalModelRegistry in isolation with mocked filesystem
- Registry operations (install, list, remove)
- Index management and validation
- Error handling for edge cases
- Version resolution and conflict detection

### Integration Testing  
**Approach**: Test CLI commands with real filesystem operations
- End-to-end model installation workflows
- CLI command integration with registry
- Cross-platform compatibility testing
- Security validation with malicious inputs

### Component Testing
**Approach**: Test registry integration with existing components
- ModelIOManager integration for manifest validation
- CLI security integration for path validation  
- File system permissions and ownership
- Registry corruption recovery and repair

## Risk Assessment

### Technical Risks - LOW
- **Filesystem operations**: Standard Python pathlib operations
- **ModelIOManager integration**: ✅ Existing and tested interface  
- **CLI integration**: ✅ Established Typer patterns

### Implementation Risks - MEDIUM
- **Registry corruption**: Multiple processes accessing same index file
- **Storage management**: Handling large models and disk space  
- **Cross-platform compatibility**: Path handling differences

### Security Risks - LOW  
- **Path validation**: ✅ Existing CLI security functions available
- **Model validation**: ✅ ModelIOManager provides manifest validation
- **File permissions**: Standard filesystem permission model

## Success Criteria

### Functional Requirements
- [x] Install models from local filesystem paths  
- [x] List installed models with filtering and search
- [x] Display detailed model information and metadata
- [x] Remove models with registry cleanup
- [x] Maintain consistent registry index

### Quality Requirements  
- [x] >90% test coverage for all new components
- [x] Flake8 compliance with NumPy-style docstrings
- [x] No regressions in existing CLI functionality
- [x] Comprehensive error handling and recovery

### Integration Requirements
- [x] Seamless integration with existing ModelIOManager
- [x] CLI commands follow established security patterns  
- [x] Compatible with inference pipeline model loading
- [x] Ready for database integration in sub-plan 2

## Milestone Checkpoints

**Checkpoint 1.A** (After Phase 1.2): Core registry functionality working
**Checkpoint 1.B** (After Phase 1.4): CLI integration complete  
**Checkpoint 1.C** (After Phase 1.6): Testing and quality validation complete

## Next Sub-Plan Integration

**Sub-Plan 2 Dependencies**:
- [x] LocalModelRegistry class with working model operations
- [x] Registry index schema established for database integration
- [x] CLI command patterns established for API endpoint design
- [x] Model metadata structure defined for database schema

This foundation establishes the core registry functionality that will be extended with database operations and multi-user features in subsequent sub-plans.