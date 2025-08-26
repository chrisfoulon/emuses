# Implementation Plan - Inference Performance Fixes

## Task Complexity Assessment

**Task Complexity**: HIGH  
**Implementation Approach**: Fix complete normalization pipeline inconsistency between training and inference
**Key Challenges**: 
- **CRITICAL**: EMUSESPipeline skips ALL normalization during inference mode (causing Object/Timedelta → UMAP failures)
- **CRITICAL**: No prediction denormalization - outputs not converted back to original score scale
- InferenceStage attempted duplicate normalization causing data type conflicts
- Multiple logging systems require architectural coordination

**Resource Requirements**: 4-6 hours implementation + comprehensive testing with user's actual model files

**ROOT CAUSE IDENTIFIED (COMPREHENSIVE ANALYSIS COMPLETE)**: EMUSESPipeline has multiple normalization issues causing cascade failures:

1. **Input normalization skipped**: Line ~321 logic `and not getattr(args, 'inference_mode', False)` completely skips normalization during inference
2. **Scores normalization skipped**: Line ~397 has identical logic skipping scores normalization during inference  
3. **No prediction denormalization**: Predictions not converted back to original score scale using scores scaler
4. **Data type conversion failure**: Timedelta/Object columns remain unconverted → UMAP fails

**RESULT**: KernelRegressor receives wrong input ranges ([7.8,11.5] instead of [0,1]) and produces zero predictions.

## Hierarchical Task Structure

### Phase 1: Critical Data Normalization Fix (Issue 2) ║ High Priority

⚠️  **PHASE 1 INCORRECTLY MARKED COMPLETE - ACTUAL IMPLEMENTATION NEEDED**

Previous analysis was incomplete. **Real issues requiring implementation**:

- [ ] **Task 1.1: Fix EMUSESPipeline Input Normalization Logic** ║ **CRITICAL IMPLEMENTATION** ║ L
  - [ ] 1.1.1: Modify line ~321 in `emuses_pipeline.py` - Remove `and not getattr(args, 'inference_mode', False)` from input normalization condition
  - [ ] 1.1.2: Add inference mode branch to load saved input_scaler.joblib and apply normalization using scaling_factors 
  - [ ] 1.1.3: Ensure Timedelta/Object columns properly converted to numeric during inference
  - [ ] 1.1.4: Save input scaler during training mode using joblib.dump()

- [ ] **Task 1.2: Fix EMUSESPipeline Scores Normalization Logic** ║ **CRITICAL IMPLEMENTATION** ║ L  
  - [ ] 1.2.1: Modify line ~397 in `load_and_process_scores()` - Same logic fix as input normalization
  - [ ] 1.2.2: Add inference mode branch to load saved scores_scaler.joblib during inference
  - [ ] 1.2.3: Save scores scaler during training mode using joblib.dump()

- [ ] **Task 1.3: Implement Prediction Denormalization in InferenceStage** ║ **NEW REQUIREMENT** ║ M
  - [ ] 1.3.1: Load scores scaler in InferenceStage from model files
  - [ ] 1.3.2: Apply inverse_normalize_dataframe() to predictions using scores scaler (NOT input scaler)
  - [ ] 1.3.3: Ensure predictions are in original raw score scale for user interpretation

- [ ] **Task 1.4: Validate Complete Fix with Real KernelRegressor Models** ║ End-to-end testing ║ M
  - [ ] 1.4.1: Test that KernelRegressor models no longer produce zero predictions
  - [ ] 1.4.2: Verify input ranges are correct ([0,1] for embeddings, normalized for inputs)  
  - [ ] 1.4.3: Confirm predictions are denormalized to meaningful score ranges
  - [ ] 1.4.4: Ensure no regression in ElasticNet model performance

### Phase 2: User Experience Fix (Issue 1) ║ Medium Priority

- [x] **Task 2.1: Analyze Duplicate Logging Sources** ║ `tests/cli/test_logging_coordination.py` ║ Map all logging output sources ║ S
  - [x] 2.1.1: ✅ Traced EMUSESPipeline JSON logging calls - extensive logger.info() usage for structured logging
  - [x] 2.1.2: ✅ Traced InferenceStage Rich console outputs - PRIMARY DUPLICATE: logger.info("Starting inference pipeline execution") at line 84
  - [x] 2.1.3: ✅ Traced CLI status_renderer messages - SECONDARY DUPLICATE: "Starting inference..." at main.py:1524
  - [x] 2.1.4: ✅ Identified exact duplicate pattern: CLI and InferenceStage both announce pipeline start to different audiences

- [x] **Task 2.2: Implement Coordinated Logging Architecture** ║ `tests/cli/test_unified_inference_output.py` ║ Single source of truth for inference output ║ M
  - [x] 2.2.1: ✅ Suppressed redundant InferenceStage logger message during CLI inference - added cli_inference_mode context flag
  - [x] 2.2.2: ✅ Consolidated CLI status messages with InferenceStage Rich output - removed redundant "Starting inference..." and "Initializing..." messages  
  - [x] 2.2.3: ✅ InferenceStage now serves as primary output channel - Rich progress and completion messages preserved
  - [x] 2.2.4: ✅ Essential diagnostic information preserved - success/error messages, validation metrics, and warnings maintained

- [x] **Task 2.3: Test Clean Output Experience** ║ `tests/cli/test_inference_output_quality.py` ║ Verify no duplicate messages remain ║ S
  - [x] 2.3.1: ✅ Ran full inference command and captured output - processed 1067 samples successfully
  - [x] 2.3.2: ✅ Validated no duplicate "Starting inference pipeline execution" - 0 messages found (FIXED!)
  - [x] 2.3.3: ✅ Verified minimal JSON structured logs - only 2 essential logs (pipeline init + random seeds)  
  - [x] 2.3.4: ✅ Confirmed all essential information still displayed - model loading, normalization, results, files saved

### Phase 3: Integration & Validation ║ High Priority

- [ ] **Task 3.1: Comprehensive Testing** ║ `tests/integration/test_inference_performance_fixes.py` ║ End-to-end validation ║ L
  - [ ] 3.1.1: Test user's exact command with fixes applied
  - [ ] 3.1.2: Verify validation metrics still work (no regression)
  - [ ] 3.1.3: Compare performance before/after fixes
  - [ ] 3.1.4: Test edge cases and error conditions

- [ ] **Task 3.2: Documentation Updates** ║ `docs/emuses/inference_stage.md` ║ Update inference documentation ║ S
  - [ ] 3.2.1: Document KernelRegressor error handling improvements
  - [ ] 3.2.2: Update troubleshooting guide for prediction failures
  - [ ] 3.2.3: Document logging architecture changes

## Progress Update Requirements

**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately  
2. Update TodoWrite status to "completed"
3. Run tests to verify completion
4. Only mark complete after successful testing

## Testing Strategy per Component Type

- **KernelRegressor Logic**: Unit testing with controlled weight sum scenarios
- **InferenceStage Integration**: Integration testing with real model files
- **CLI Output**: System testing with full command execution
- **Regression Prevention**: Compare outputs before/after changes

## Risk Assessment and Mitigation

### High Risk: Breaking ElasticNet Models
**Mitigation**: Comprehensive regression testing with all model types before deployment

### Medium Risk: Removing Essential Diagnostic Information  
**Mitigation**: Careful analysis of which messages are truly duplicates vs. valuable diagnostics

### Medium Risk: KernelRegressor Fix Complexity
**Mitigation**: Mathematical analysis of weight sum calculation and sigma parameter sensitivity

## Acceptance Criteria Mapping

### Issue 2 (Zero Predictions) Success Criteria:
- [ ] **CRITICAL**: EMUSESPipeline applies normalization during inference using saved scaler parameters (currently skipped)
- [ ] **CRITICAL**: Input data properly converted from Timedelta/Object → Numeric during inference  
- [ ] **CRITICAL**: Predictions denormalized using scores scaler to original score scale
- [ ] KernelRegressor models produce non-zero predictions with proper input normalization
- [ ] ElasticNet models continue working without regression  
- [ ] UMAP receives properly normalized numeric input ([0,1] embeddings already working)

### Issue 1 (Duplicate Output) Success Criteria:
- [x] ✅ Single "Starting inference pipeline execution" message (0 duplicate messages found)
- [x] ✅ No duplicate JSON structured logs (minimal essential logs only)
- [x] ✅ Clean, readable terminal output (Rich formatting preserved)
- [x] ✅ All essential information preserved (model loading, normalization, results display)

## Decision Points Requiring User Input

- **[INVESTIGATION NEEDED]** Task 1.2: bcblib normalize_dataframe capabilities - does it return scaler objects for reuse?
- **[FALLBACK READY]** Migration to sklearn scalers (StandardScaler/MinMaxScaler/RobustScaler) if bcblib insufficient
- **[RESOLVED]** Storage approach: Save scaler objects to model directory AND reference in JSON manifest for automatic detection
- **[USER_INPUT]** Task 2.2: Logging detail level - which diagnostic messages are essential vs. redundant?

## Implementation Technical Details (CORRECTED)

### Key Files to Modify (Actual Implementation Needed)

1. **EMUSESPipeline.process_dataset()**: Line ~321 - **FIX LOGIC**: Remove `and not getattr(args, 'inference_mode', False)` and add inference branch to load saved scaler
2. **EMUSESPipeline.load_and_process_scores()**: Line ~397 - **FIX LOGIC**: Same normalization skip issue, add inference branch to load scores scaler  
3. **InferenceStage**: **ADD**: Prediction denormalization using scores scaler after ensemble predictions computed
4. **BCBlib Integration**: Use existing `normalize_dataframe()` and `inverse_normalize_dataframe()` functions - no changes needed

### Existing Infrastructure Integration (PERFECT MATCH!)
- **✅ ModelIOManager**: Full manifest system with auto-generation, integrity checking, versioning
- **✅ InferenceStage loading**: Already uses `ModelIOManager(base_path=model_dir)` pattern
- **✅ Joblib pattern**: Established loading with `joblib.load()` throughout codebase
- **✅ Context storage**: Models stored in context dictionary for pipeline stages
- **✅ File integrity**: SHA256 verification system ready for scaler files
- **✅ Backward compatibility**: Manifest system handles missing files gracefully

### Implementation Reference Files (CREATED THIS SESSION)
**Critical**: Use these files during implementation for detailed specifications and code examples:

1. **`comprehensive_normalization_analysis.md`**: Complete root cause analysis
   - Detailed BCBlib function analysis with capabilities
   - Exact problem identification in EMUSESPipeline logic
   - Complete 4-phase solution plan with implementation details
   - Data flow analysis (training vs inference)

2. **`implementation_priority_plan.md`**: Concrete implementation roadmap
   - Priority ranking of tasks (Critical → High → Medium)
   - Specific code examples for each fix needed
   - Expected results after implementation
   - Line-by-line implementation guidance

3. **`emuses_pipeline_fix_plan.md`**: Focused EMUSESPipeline logic fix
   - Current vs correct logic comparison
   - Exact code changes needed for normalization consistency
   - Problem/solution summary for the core issue

### Available Normalization Methods (normalize_dataframe)
- Requires investigation of bcblib.tools.dataframe_filtering implementation
- May need migration to sklearn StandardScaler/MinMaxScaler/RobustScaler for reversibility
- Recommendation: Use sklearn scalers for guaranteed inverse_transform() support

### Storage Strategy (Integrated with Existing EMUSES Infrastructure)
- **✅ Embedding normalization**: Already implemented in UMAPStage (min/max coords saved)
- **Scores normalization**: Save scaler as `{model_dir}/scores_scaler.joblib` + manifest reference
- **Input normalization**: Save scaler as `{model_dir}/input_scaler.joblib` + manifest reference
- **Automatic manifest integration**: 
  - Extend `ModelIOManager._generate_manifest_from_directory()` to detect scaler files
  - Enhanced schema: `"normalization": {"scores_scaler": "scores_scaler.joblib", "input_scaler": "input_scaler.joblib", "scores_method": "standardscaler", "input_method": "minmaxscaler"}`
  - SHA256 integrity: Scaler files added to `file_integrity` section automatically
  - InferenceStage auto-loading: Detect normalization section, load scalers with joblib
  - Context integration: Store loaded scalers in context like `models['input_scaler']`
  - Perfect backward compatibility: Legacy models without scalers continue working unchanged

## Implementation Dependencies

1. **Task 1.1** must complete before **Task 1.2** (need analysis before implementation)
2. **Task 1.3** depends on **Task 1.2** completion (need saved scalers before loading)
3. **Task 2.1** can run in parallel with Phase 1
4. **Phase 3** requires both Phase 1 and 2 completion
5. **No backward compatibility constraints** - can modify existing models without migration

---

**Next Phase**: Implementation using LAD Phase 02 (Iterative Implementation)
**Estimated Completion**: 2-4 hours with comprehensive testing
**Quality Gate**: All KernelRegressor models must produce valid predictions before completion