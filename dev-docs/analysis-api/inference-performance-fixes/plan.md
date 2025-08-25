# Implementation Plan - Inference Performance Fixes

## Task Complexity Assessment

**Task Complexity**: HIGH
**Implementation Approach**: Fix critical data normalization mismatch + coordinated logging architecture
**Key Challenges**: 
- **CRITICAL**: Inference embeddings not normalized to training data scale (causing zero predictions)
- Must preserve training-time normalization parameters and apply to inference data
- Multiple logging systems require architectural coordination
- Complex embedding processing pipeline needs normalization integration

**Resource Requirements**: 4-6 hours implementation + comprehensive testing with user's actual model files

## Hierarchical Task Structure

### Phase 1: Critical Data Normalization Fix (Issue 2) ║ High Priority

- [ ] **Task 1.1: Research Existing Normalization Infrastructure** ║ `tests/inference/test_normalization_research.py` ║ Discover current normalization approach ║ M
  - [ ] 1.1.1: Find where embedding normalization happens during training pipeline
  - [ ] 1.1.2: Identify if normalization parameters are saved to model files
  - [ ] 1.1.3: Check UMAP stage outputs and downstream processing
  - [ ] 1.1.4: Analyze how ElasticNet models handle unnormalized data vs KernelRegressor

- [ ] **Task 1.2: Implement Training-Time Normalization Parameter Storage** ║ `tests/inference/test_normalization_storage.py` ║ Ensure normalization params are saved ║ L  
  - [ ] 1.2.1: Modify training pipeline to save embedding normalization parameters (min/max/mean/std)
  - [ ] 1.2.2: Store normalization parameters in model manifest or separate file
  - [ ] 1.2.3: Ensure backward compatibility with existing trained models
  - [ ] 1.2.4: Add validation that normalization parameters are correctly saved

- [ ] **Task 1.3: Implement Inference-Time Normalization Application** ║ `tests/inference/test_inference_normalization.py` ║ Apply training normalization to inference ║ L
  - [ ] 1.3.1: Load normalization parameters during inference
  - [ ] 1.3.2: Apply identical training-time normalization to inference embeddings
  - [ ] 1.3.3: Ensure normalization applied AFTER UMAP transform, BEFORE model prediction
  - [ ] 1.3.4: Add diagnostic logging for normalization parameters and ranges

- [ ] **Task 1.4: Validate Complete Normalization Fix** ║ `tests/inference/test_normalization_validation.py` ║ Comprehensive testing with real models ║ L
  - [ ] 1.4.1: Test all KernelRegressor models produce non-zero predictions
  - [ ] 1.4.2: Verify ElasticNet models still work correctly (no regression)
  - [ ] 1.4.3: Compare embedding ranges: training [0,1] vs normalized inference [0,1]
  - [ ] 1.4.4: Validate distance calculations now work correctly for KernelRegressor

### Phase 2: User Experience Fix (Issue 1) ║ Medium Priority

- [ ] **Task 2.1: Analyze Duplicate Logging Sources** ║ `tests/cli/test_logging_coordination.py` ║ Map all logging output sources ║ S
  - [ ] 2.1.1: Trace EMUSESPipeline JSON logging calls
  - [ ] 2.1.2: Trace InferenceStage Rich console outputs
  - [ ] 2.1.3: Trace CLI status_renderer messages  
  - [ ] 2.1.4: Identify specific duplicate message patterns

- [ ] **Task 2.2: Implement Coordinated Logging Architecture** ║ `tests/cli/test_unified_inference_output.py` ║ Single source of truth for inference output ║ M
  - [ ] 2.2.1: Suppress redundant EMUSESPipeline JSON logs during inference
  - [ ] 2.2.2: Consolidate CLI status messages with InferenceStage Rich output
  - [ ] 2.2.3: Ensure InferenceStage remains primary output channel
  - [ ] 2.2.4: Preserve essential diagnostic information

- [ ] **Task 2.3: Test Clean Output Experience** ║ `tests/cli/test_inference_output_quality.py` ║ Verify no duplicate messages remain ║ S
  - [ ] 2.3.1: Run full inference command and capture output
  - [ ] 2.3.2: Validate no duplicate "Starting inference pipeline execution"
  - [ ] 2.3.3: Verify no duplicate JSON structured logs
  - [ ] 2.3.4: Confirm all essential information still displayed

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
- [ ] **CRITICAL**: Inference embeddings normalized to same scale as training ([0,1] range)
- [ ] KernelRegressor models produce non-zero predictions (not due to weight_sum=0)
- [ ] ElasticNet models continue working without regression
- [ ] Training-time normalization parameters correctly saved and loaded
- [ ] Identical normalization applied to inference as was applied to training data

### Issue 1 (Duplicate Output) Success Criteria:
- [ ] Single "Starting inference pipeline execution" message
- [ ] No duplicate JSON structured logs
- [ ] Clean, readable terminal output
- [ ] All essential information preserved

## Decision Points Requiring User Input

- **[USER_INPUT]** Task 1.2: Normalization parameter storage location - model manifest vs separate normalization file?
- **[USER_INPUT]** Task 1.3: Backward compatibility - how to handle existing models without saved normalization parameters?
- **[USER_INPUT]** Task 2.2: Logging detail level - which diagnostic messages are essential vs. redundant?

## Implementation Dependencies

1. **Task 1.1** must complete before **Task 1.2** (need root cause before fix)
2. **Task 1.3** depends on **Task 1.2** completion (need fix before validation)
3. **Task 2.1** can run in parallel with Phase 1
4. **Phase 3** requires both Phase 1 and 2 completion

---

**Next Phase**: Implementation using LAD Phase 02 (Iterative Implementation)
**Estimated Completion**: 2-4 hours with comprehensive testing
**Quality Gate**: All KernelRegressor models must produce valid predictions before completion