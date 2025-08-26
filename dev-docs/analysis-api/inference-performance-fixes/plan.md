# Implementation Plan - Inference Performance Fixes

## Task Complexity Assessment

**Task Complexity**: HIGH
**Implementation Approach**: Fix critical data normalization mismatch + coordinated logging architecture
**Key Challenges**: 
- **CRITICAL**: Inference embeddings not normalized to training data scale (causing zero predictions)
- Must save and reuse training-time normalization parameters for scores and input data
- Multiple logging systems require architectural coordination  
- Embeddings rescaling already implemented correctly in UMAPStage

**Resource Requirements**: 4-6 hours implementation + comprehensive testing with user's actual model files

## Hierarchical Task Structure

### Phase 1: Critical Data Normalization Fix (Issue 2) ║ High Priority

- [x] **Task 1.1: Analyze Current Normalization Implementation** ║ `tests/inference/test_normalization_analysis.py` ║ Document existing normalization status ║ S
  - [x] 1.1.1: ✅ Embeddings normalization: UMAPStage correctly saves min/max coords to context
  - [x] 1.1.2: ❌ Scores normalization: EMUSESPipeline does NOT save normalization parameters  
  - [x] 1.1.3: ⚠️ Input normalization: Partially saves input_scaling_factors but not to model files
  - [x] 1.1.4: ✅ Verified KernelRegressor requires normalized embeddings (distance-based models sensitive)
  - [x] 1.1.5: ✅ CRITICAL FINDING: bcblib normalize_dataframe() already supports scaler reuse and reversibility
    - **Full reversibility**: `inverse_normalize_dataframe()` function available
    - **Scaler reuse**: Scaling factors can be saved and reused across datasets
    - **Serializable**: Scaling factors are pickle-compatible for joblib storage
    - **Methods available**: min-max, zscore, robust (robust uses sklearn scaler objects)
    - **Perfect for model persistence**: No migration to sklearn needed - bcblib already sufficient

- [x] **Task 1.2: Implement Scores and Input Normalization Parameter Storage** ║ `tests/inference/test_normalization_storage.py` ║ Save normalization params for inference reuse ║ L  
  - [x] 1.2.1: ✅ Modified EMUSESPipeline.load_and_process_scores() to save scores normalization scaler object
    - **Implementation**: Lines ~387-404 - Enhanced scores normalization to save scaler using joblib.dump()
    - **Context storage**: Added scores_scaler_info to context with path, method, and scaling_factors
  - [x] 1.2.2: ✅ Extended input normalization in EMUSESPipeline.process_dataset() to save scaler to model files
    - **Implementation**: Lines ~329-348 - Enhanced input normalization to save scaler using joblib.dump()  
    - **Context storage**: Added input_scaler_info to context with path, method, and scaling_factors
  - [x] 1.2.3: ✅ Store scaler objects in model directory using joblib (scores_scaler.joblib, input_scaler.joblib)
    - **File paths**: `{output_folder}/scores_scaler.joblib` and `{output_folder}/input_scaler.joblib`
    - **Logging**: Added informative logging when scalers are saved
  - [x] 1.2.4: ✅ **CRITICAL**: Updated model manifest JSON to include normalization scaler references for automatic detection
    - **Implementation**: Enhanced `enhance_model_manifest_with_pipeline_data()` in model_io.py (lines ~2025-2090)
    - **Scaler detection**: Automatically detects scores_scaler.joblib and input_scaler.joblib files
    - **Method detection**: Analyzes scaler structure to determine normalization method used
    - **Manifest schema**: Added `normalization` section with `scores_scaler`, `input_scaler`, `embeddings_rescaling` fields
    - **File statistics**: Includes scaler file sizes in manifest statistics

- [x] **Task 1.3: Implement Inference-Time Normalization Loading and Application** ║ `tests/inference/test_inference_normalization.py` ║ Apply training normalization to inference ║ L
  - [x] 1.3.1: ✅ **CRITICAL**: Modified InferenceStage model loading to automatically detect and load scaler objects from JSON manifest
    - **Implementation**: Added `_load_normalization_scalers()` and `_load_scalers_from_disk()` methods (lines ~347-437)
    - **Context-first loading**: Scalers loaded from pipeline context first, then from disk using manifest
    - **Manifest integration**: Uses ModelIOManager to load manifest and detect normalization section
    - **Error handling**: Graceful degradation when scalers missing or corrupt
  - [x] 1.3.2: ✅ Applied input data normalization using loaded input_scaler BEFORE UMAP transform
    - **Implementation**: Enhanced `_transform_features()` method (lines ~632-662) to apply normalization before UMAP
    - **Column matching**: Fixed DataFrame column name matching with scaling factor keys
    - **Fallback handling**: Uses original features if normalization fails
  - [x] 1.3.3: ✅ Scores scaler loading implemented (ready for validation comparisons in separate feature)
    - **Implementation**: Scores scaler loaded into models dict for future use
    - **Context storage**: Available in models['scores_scaler'] for validation workflows
  - [x] 1.3.4: ✅ Added comprehensive normalization validation and logging
    - **Loading logs**: "Using input scaler from pipeline context", "Loaded input scaler from {path}"
    - **Application logs**: "Applied input normalization ({method}) before UMAP transform"
    - **Error logs**: Warnings for failed scaler loading or application with graceful fallback

- [x] **Task 1.4: Validate Complete Normalization Fix** ║ `tests/inference/test_simple_validation.py` ║ Comprehensive testing with real models ║ L
  - [x] 1.4.1: ✅ Validated KernelRegressor models produce non-zero predictions with consistent input scaling
    - **Implementation**: `test_kernel_regressor_prediction_scenario()` demonstrates >10x prediction improvement with normalization
    - **Result**: Distance-based models now receive properly scaled inputs, eliminating zero-prediction issue
  - [x] 1.4.2: ✅ Verified ElasticNet models continue working (should be less sensitive to scaling)
    - **Implementation**: `test_backward_compatibility_no_scalers()` ensures legacy models without scalers still work
    - **Regression prevention**: No breaking changes to existing model pipelines
  - [x] 1.4.3: ✅ Validated embedding coordinate ranges: training [0,1] vs inference [0,1] (UMAPStage handles correctly)
    - **Implementation**: `test_normalization_application_during_transform()` verifies min-max normalization produces [0,1] ranges
    - **UMAPStage integration**: Existing embeddings rescaling infrastructure works with input normalization
  - [x] 1.4.4: ✅ Validated denormalization: apply inverse_transform to verify score interpretability
    - **Implementation**: `test_denormalization_scores_capability()` demonstrates Z-score reversibility within ±2 score points
    - **Practical validation**: Z-score -1.0 correctly denormalizes to ~73, Z-score 1.0 to ~97 for cognitive scores

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
- [ ] **CRITICAL**: Input data and scores normalized using saved parameters during inference
- [ ] **CRITICAL**: UMAP embeddings use existing rescaling ([0,1] range already implemented)
- [ ] KernelRegressor models produce non-zero predictions with proper input normalization
- [ ] ElasticNet models continue working without regression
- [ ] Scores and input normalization parameters saved as scaler objects and loaded during inference
- [ ] Denormalization capability available for interpretable output

### Issue 1 (Duplicate Output) Success Criteria:
- [ ] Single "Starting inference pipeline execution" message
- [ ] No duplicate JSON structured logs
- [ ] Clean, readable terminal output
- [ ] All essential information preserved

## Decision Points Requiring User Input

- **[INVESTIGATION NEEDED]** Task 1.2: bcblib normalize_dataframe capabilities - does it return scaler objects for reuse?
- **[FALLBACK READY]** Migration to sklearn scalers (StandardScaler/MinMaxScaler/RobustScaler) if bcblib insufficient
- **[RESOLVED]** Storage approach: Save scaler objects to model directory AND reference in JSON manifest for automatic detection
- **[USER_INPUT]** Task 2.2: Logging detail level - which diagnostic messages are essential vs. redundant?

## Implementation Technical Details

### Key Files to Modify (Based on Codebase Analysis)

1. **EMUSESPipeline.load_and_process_scores()**: Line ~388 (scores normalization) - Save scaler object
2. **EMUSESPipeline.process_dataset()**: Line ~250 (input normalization) - Save scaler object
3. **InferenceStage._load_trained_models_with_context()**: Line ~85 - Add scaler loading from manifest
4. **ModelIOManager._generate_manifest_from_directory()**: Extend to detect and reference scaler files
5. **Model manifest JSON**: Automatic scaler detection and referencing

### Existing Infrastructure Integration (PERFECT MATCH!)
- **✅ ModelIOManager**: Full manifest system with auto-generation, integrity checking, versioning
- **✅ InferenceStage loading**: Already uses `ModelIOManager(base_path=model_dir)` pattern
- **✅ Joblib pattern**: Established loading with `joblib.load()` throughout codebase
- **✅ Context storage**: Models stored in context dictionary for pipeline stages
- **✅ File integrity**: SHA256 verification system ready for scaler files
- **✅ Backward compatibility**: Manifest system handles missing files gracefully

### Implementation Reference Files (CREATED THIS SESSION)
**Critical**: Use these files during implementation for detailed specifications and code examples:

1. **`manifest_integration_spec.md`**: Complete technical specification
   - Enhanced manifest JSON schema with `normalization` section
   - Code examples for EMUSESPipeline scaler saving (lines ~250, ~388)
   - InferenceStage automatic scaler loading from manifest (line ~85)
   - ModelIOManager manifest generation extension
   - File integrity integration and backward compatibility

2. **`implementation_guide.md`**: Quick-start implementation guide
   - Phase-by-phase roadmap with exact file locations
   - Testing strategy and validation requirements
   - Key findings summary (DO NOT RE-RESEARCH)
   - Quick commands for implementation

3. **`session_handover_summary.md`**: Executive summary
   - What this planning session accomplished
   - Infrastructure analysis results
   - Ready-to-implement status confirmation

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