# EMUSES Maintenance Registry

**Last Updated**: 2025-07-28  
**Session**: feat/parallelism-backend-conflicts LAD enhancement  
**Baseline**: 855 flake8 violations (established during LAD kickoff)

## Current Status

### High Priority Issues (Address First)
**Impact**: Likely bugs or functional problems requiring immediate attention

- [ ] **F821 (5 instances)**: Undefined names - potential runtime errors
  - `ClusteringStage` referenced but not defined
  - Other undefined variables in various files
- [ ] **E722 (3 instances)**: Bare except clauses - poor error handling
  - Need specific exception types for proper error handling
  - Risk of masking important errors

### Medium Priority Issues (Feature-Adjacent Cleanup)
**Impact**: Code quality and maintainability improvements

- [ ] **F811 (35 instances)**: Import redefinitions  *(2 fixed in heatmap_stage.py)*
  - Multiple imports of same module (e.g., 'os' redefinition)
  - Clean up import organization
- [ ] **F841 (6 instances)**: Unused variables  *(7 fixed: 3 in heatmap_stage.py, 4 in core pipeline files)*
  - Remaining instances in scripts/ and non-core tools/ files
  - Remove or utilize properly

### Low Priority Issues (Batch Processing)
**Impact**: Cosmetic improvements, can be automated

- [ ] **W293 (724 instances)**: Blank lines contain whitespace
  - Automated cleanup candidate
  - Consider pre-commit hooks
- [ ] **W291 (8 instances)**: Trailing whitespace
- [ ] **W292 (11 instances)**: No newline at end of file
- [ ] **F541 (6 instances)**: f-string missing placeholders  *(3 fixed in heatmap_stage.py, optuna_cv.py)*
- [ ] **E401 (1 instance)**: Multiple imports on one line

## Maintenance Workflow

### Boy Scout Rule Integration
When modifying files during feature development:
1. Check if file has maintenance items in this registry
2. Address high/medium priority items in files being modified
3. Update registry with completed work
4. Test changes before marking complete

### Systematic Cleanup Sessions
Use `04_maintenance_session.md` LAD prompt for dedicated maintenance work:
- Focus on high-impact items first
- Batch similar fixes by file or issue type
- Test thoroughly after each batch
- Update registry with progress

## Quality Trends

| Date | Session | Violations | Change | Notes |
|------|---------|------------|--------|-------|
| 2025-07-28 | LAD kickoff | 855 | baseline | Initial measurement during enhanced LAD setup |
| 2025-07-28 | Parallelism maintenance | ~847 | -8 | Fixed 2 F811, 3 F841, 3 F541 issues during feature maintenance |
| 2025-07-28 | Core pipeline cleanup | ~843 | -4 | Fixed 4 F841 unused variables in core pipeline files |

## Completed Maintenance Work

### Recently Completed
- [x] **2025-07-28**: Updated .flake8 to exclude .lad folder (LAD framework addition)
- [x] **2025-07-28**: Parallelism backend conflicts maintenance session
  - Fixed 2 F811 import redefinitions in `heatmap_stage.py` (ModelIOManager, optimize_ae_pretraining)
  - Fixed 3 F841 unused variables in `heatmap_stage.py` (embedding_train_coords, embedding_train_features, prediction_train_features)
  - Fixed 3 F541 f-string issues across `heatmap_stage.py` and `optuna_cv.py`
  - Verified parallelism utils integration in `stats_utils.py` and `optim_utils.py` (already completed)
  - Comprehensive test validation: 23/23 parallelism tests passing
  - Confirmed elimination of "setting n_jobs=1" warnings in production
- [x] **2025-07-28**: Core pipeline maintenance cleanup
  - Fixed 4 F841 unused variables in core pipeline files:
    - `emuses_pipeline.py`: embedding_test_indices
    - `umap_stage.py`: train_indices  
    - `UMAP_utils.py`: fig variable from plot function
    - `clustering_utils.py`: n_samples, max_cluster_size (dynamic range calculation)
  - Focused only on core pipeline components (excluded scripts/ and unused tools/)
  - All core pipeline stages import successfully after fixes

### Historical Maintenance
*No historical maintenance work logged*

## Impact Assessment

### Value Proposition
- **Bug Prevention**: F821 undefined names likely represent runtime errors
- **Code Quality**: Cleaner imports and error handling improve maintainability  
- **Developer Experience**: Reduced noise from cosmetic violations
- **Technical Debt**: Systematic reduction prevents accumulation

### Estimated Effort
- **High Priority**: ~30-45 minutes (5 F821 + 3 E722 issues)
- **Medium Priority**: ~60-90 minutes (50 import/variable cleanup issues)
- **Low Priority**: ~120-180 minutes (743+ cosmetic issues, good for automation)

## Notes for Future Sessions

### Patterns Observed
- High concentration of whitespace issues suggests need for automated formatting
- Import organization issues indicate potential for tooling (isort, black)
- Undefined names require careful analysis to avoid breaking changes

### Automation Opportunities
- Pre-commit hooks for whitespace/formatting issues
- Automated import sorting and organization
- Regular flake8 CI checks to prevent regression

---
*Maintained by LAD Framework - Update during each feature implementation session*