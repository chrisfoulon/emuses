# InferenceStage CLI Parameter Fix - Implementation Plan

## Task Complexity Assessment

**Task Complexity**: MEDIUM  
**Implementation Approach**: Add missing typer.Option parameters to inference command and enhance args object creation  
**Key Challenges**: Ensuring comprehensive parameter coverage, maintaining CLI consistency, proper parameter validation  
**Resource Requirements**: 6-10 hours across 3 phases, validation with real failing test cases

## Progress Update Requirements
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"
3. Run tests to verify completion
4. Only mark complete after successful testing

## Hierarchical Task Structure

### Phase 1: Critical Parameters (HIGH PRIORITY) ║ 2-4 hours ║ Fix User's Blocking Issue ║ M ✅ COMPLETED

- [x] **Task 1.1**: Add Core Preprocessing Parameters to Inference CLI ║ `tests/cli/test_inference_preprocessing_params.py` ║ Add the 5 critical parameters to fix header/index column processing ║ M
  - [x] 1.1.1: Add input_header parameter with proper typing and help text
  - [x] 1.1.2: Add input_index_column parameter with proper typing and help text
  - [x] 1.1.3: Add scores_header parameter with proper typing and help text
  - [x] 1.1.4: Add scores_index_column parameter with proper typing and help text
  - [x] 1.1.5: Add scores parameter for validation mode support

- [x] **Task 1.2**: Enhance Args Object Creation ║ `tests/cli/test_inference_args_creation.py` ║ Pass new parameters through to EMUSESPipeline args object ║ M
  - [x] 1.2.1: Update _execute_local_inference to accept new parameters from config
  - [x] 1.2.2: Set preprocessing parameters in args object creation
  - [x] 1.2.3: Add parameter validation for preprocessing options
  - [x] 1.2.4: Test args object has all required preprocessing parameters

- [x] **Task 1.3**: Core Integration Testing ║ `tests/cli/test_inference_integration.py` ║ Verify parameter passing works end-to-end ║ M
  - [x] 1.3.1: Create test CSV files with headers and index columns
  - [x] 1.3.2: Test inference command with new preprocessing parameters
  - [x] 1.3.3: Verify EMUSESPipeline receives parameters correctly
  - [x] 1.3.4: Test user's specific failing case scenario

- [x] **Task 1.4**: EMERGENCY FIX - Inference Mode Architecture ║ N/A ║ Fix pipeline initialization error for inference ║ H
  - [x] 1.4.1: Add inference_mode flag to PipelineConfig
  - [x] 1.4.2: Modify EMUSESPipeline to skip dataset splitting in inference mode
  - [x] 1.4.3: Update CLI inference to set inference_mode=True automatically
  - [x] 1.4.4: Add missing columns_are_features and input_normalization parameters

### Phase 2: Common Use Cases (MEDIUM PRIORITY) ║ 2-3 hours ║ Extend for Frequent Scenarios ║ M

- [x] **Task 2.1**: Add Data Normalization Parameters ║ `tests/cli/test_inference_normalization.py` ║ Support input and scores normalization options ║ M ✅ COMPLETED
  - [x] 2.1.1: Add input_normalization parameter with enum validation
  - [x] 2.1.2: Add columns_are_features parameter for data interpretation  
  - [x] 2.1.3: Add inputs_columns parameter for column selection
  - [x] 2.1.4: Test normalization parameter integration

- [x] **Task 2.2**: Add Classification Support ║ `tests/cli/test_inference_classification.py` ║ Support classification vs regression mode switching ║ S ✅ COMPLETED
  - [x] 2.2.1: Add classification parameter for mode switching
  - [x] 2.2.2: Update args object creation with classification parameter
  - [x] 2.2.3: Test classification parameter functionality
  - [x] 2.2.4: Verify classification mode works with inference pipeline

### Phase 3: Advanced Parameters (LOWER PRIORITY) ║ 3-4 hours ║ Complete Parameter Coverage ║ L ✅ COMPLETED

- [x] **Task 3.1**: Add Advanced Scores Processing ║ `tests/cli/test_inference_advanced_scores.py` ║ Complete scores/labels preprocessing parameter support ║ S ✅ COMPLETED
  - [x] 3.1.1: Add scores_normalization parameter with enum validation
  - [x] 3.1.2: Add correlation_method parameter with enum validation
- [x] **Task 3.1.X**: Clean Up Correlation Method Parameter ║ Remove correlation_method (not used in inference) ║ Cleanup subtask ║ S ✅ COMPLETED
  - [x] 3.1.X.1: Remove correlation_method from inference CLI parameters
  - [x] 3.1.X.2: Remove correlation_method from docstring and help text  
  - [x] 3.1.X.3: Remove correlation_method from args object creation
  - [x] 3.1.X.4: Test removal doesn't break existing inference functionality
  - [x] 3.1.3: Add scores_are_rows parameter for data orientation
  - [x] 3.1.4: Add scores_column parameter for column selection
  - [x] 3.1.5: Add filter_labelled_by_scores parameter for data filtering

- [x] **Task 3.2**: Add Advanced Input Processing ║ `tests/cli/test_inference_advanced_input.py` ║ Complete input data preprocessing parameter support ║ S ✅ COMPLETED
  - [x] 3.2.1: Add recursive_search parameter for file discovery
  - [x] 3.2.2: Add input_file_types parameter for file filtering
  - [x] 3.2.3: Add arg_separator parameter for parsing configuration
  - [x] 3.2.4: Add bids_filters parameter for BIDS dataset handling

- [x] **Task 3.3**: Comprehensive Parameter Validation ║ `tests/cli/test_inference_comprehensive.py` ║ Full parameter validation and edge case testing ║ M ✅ COMPLETED
  - [x] 3.3.1: Test all parameter combinations work correctly
  - [x] 3.3.2: Test parameter validation and error handling
  - [x] 3.3.3: Test parameter help text and CLI documentation
  - [x] 3.3.4: Performance test with various parameter configurations

### CRITICAL SECURITY FIX ║ 1 hour ║ Data Privacy Protection ║ H ✅ COMPLETED

- [x] **Task 4.0**: Remove Default Output Behavior ║ `tests/cli/test_inference_output_required.py` ║ CRITICAL: Prevent data privacy leaks ║ H
  - [x] 4.0.1: Make --output parameter REQUIRED (no default value)
  - [x] 4.0.2: Remove all default output folder logic from _inference_async
  - [x] 4.0.3: Update CLI help to emphasize --output is required
  - [x] 4.0.4: Test that inference command fails without --output specified
  - [x] 4.0.5: Update error message to guide users to specify output folder

### Quality Assurance & Documentation ║ 1-2 hours ║ Final Validation ║ M

- [x] **Task 4.1**: Code Quality Validation ║ `tests/cli/test_inference_quality.py` ║ Ensure code meets quality standards ║ S ✅ COMPLETED
  - [x] 4.1.1: Run flake8 on modified files and fix any issues
  - [x] 4.1.2: Add NumPy-style docstrings to any new functions
  - [x] 4.1.3: Verify test coverage meets 90%+ target for new code
  - [x] 4.1.4: Run full test suite to prevent regressions

- [x] **Task 4.2**: Documentation Updates ║ N/A ║ Update CLI help and usage documentation ║ S ✅ COMPLETED
  - [x] 4.2.1: Verify CLI help text is clear and helpful for new parameters
  - [x] 4.2.2: Update context.md with actual implementation details
  - [x] 4.2.3: Document parameter usage patterns and examples
  - [x] 4.2.4: Add troubleshooting guide for common preprocessing issues

## Milestone Checkpoints

**Checkpoint A** (After Task 1.4): User's blocking issue should be resolved ✅ ACHIEVED
- User can run inference with --input_header and --input_index_column
- No more "No numeric data remaining" errors for files with headers
- Core functionality working end-to-end
- **BONUS**: Fixed inference mode architecture issue that was causing "'NoneType' object is not subscriptable" errors
- **SUCCESS**: User's complete command now works: 1067 samples processed successfully across 8 prediction targets

**Checkpoint B** (After Task 2.2): Common use cases supported  
- Normalization parameters available for users
- Classification mode supported
- Most frequent user scenarios covered

**Checkpoint C** (After Task 3.3): Complete parameter coverage
- All preprocessing parameters available in inference CLI
- Full parity with EMUSESPipeline preprocessing capabilities
- Comprehensive parameter validation and testing

## Testing Strategy

**Component Type**: CLI Command Integration
**Primary Strategy**: Integration testing with real CSV files and parameter validation

**Test Categories**:
1. **Parameter Addition Tests**: Verify new CLI parameters are accepted and validated
2. **Args Object Tests**: Verify parameters are correctly passed to EMUSESPipeline
3. **Integration Tests**: End-to-end testing with real data files requiring preprocessing
4. **Edge Case Tests**: Invalid parameters, missing files, malformed data
5. **Regression Tests**: Ensure existing inference functionality unchanged

**Test Data Requirements**:
- CSV files with headers in first row
- CSV files with index columns
- CSV files requiring normalization
- Malformed CSV files for error testing
- Existing model directories for inference testing

## Risk Assessment and Mitigation

**Low Risk Areas**:
- Parameter definitions (reusing tested patterns from full CLI)
- Basic integration (well-understood args object pattern)
- No architectural changes required

**Medium Risk Areas**:
- Parameter validation complexity increases with each phase
- Comprehensive testing across all parameter combinations
- Maintaining consistency with full CLI parameter behavior

**HIGH RISK - DATA PRIVACY CONCERN** ⚠️:
- **Default output folder behavior is dangerous for data privacy**
- When using `--model-id` (registry models), default output might be in `~/.emuses/` or model directory
- Users could accidentally include inference results when sharing models
- **CRITICAL FIX REQUIRED**: Make output folder argument REQUIRED, remove all defaults

**Mitigation Strategies**:
- Implement phases incrementally to isolate issues
- Test each parameter addition individually before combining
- Reference existing full CLI implementation for consistency
- Use user's actual failing case as primary validation test
- **PRIORITY**: Remove default output folder behavior to prevent data privacy leaks

## Acceptance Criteria Mapping

1. **User can specify header row**: Task 1.1.1 (input_header parameter)
2. **User can specify index column**: Task 1.1.2 (input_index_column parameter)  
3. **User can specify scores file formatting**: Tasks 1.1.3-1.1.4 (scores_header, scores_index_column)
4. **No preprocessing failures**: Tasks 1.2-1.3 (proper parameter passing and integration)
5. **Maintains existing functionality**: Task 4.1 (regression prevention)
6. **Clear CLI help and documentation**: Task 4.2 (user guidance)

## Implementation Notes

**Parameter Consistency**: All new parameters should match exactly the naming, typing, and help text patterns from the full CLI command to maintain user experience consistency.

**Args Object Pattern**: The args object creation pattern should be enhanced rather than replaced to minimize risk and maintain compatibility with existing InferenceStage integration.

**Validation Strategy**: Each phase should be immediately tested with the user's original failing case to ensure the problem is being solved progressively.

**Documentation Integration**: Context.md should be updated after each major task completion to reflect actual implementation rather than planned implementation.