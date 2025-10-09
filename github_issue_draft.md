# [Bug/Enhancement] Handle Optuna Parameter Space Conflicts During Resume

## Problem Description

When users run EMUSES on a previously trained model folder and change the `--prediction_optim_dict` parameter, the training crashes due to parameter space conflicts in Optuna studies.

### Steps to Reproduce
1. Run EMUSES training with `--prediction_optim_dict optim_dict_predict`
2. Let it complete some trials (creates SQLite study databases)
3. Rerun with `--prediction_optim_dict optim_dict_ae` (different parameter space)
4. Training crashes when Optuna tries to sample parameters that don't exist in the new space

### Expected Behavior
EMUSES should handle parameter space changes gracefully, either by:
- Creating new studies for the new parameter space, or  
- Providing clear options to the user about how to proceed

### Current Behavior
Application crashes with Optuna parameter sampling errors when trying to resume studies with incompatible parameter spaces.

## Root Cause

**Study Name Collision + Parameter Space Mismatch**:
- Study names remain the same: `f"{target_tag}_fold_{fold}"`
- But parameter space definition changes between optim dicts
- Optuna's `load_if_exists=True` tries to continue with incompatible parameters
- Results in sampling errors when new dict doesn't contain parameters from stored trials

**Code Locations**:
- Study creation: `emuses/tools/optuna_cv.py:166-182`
- Parameter loading: `emuses/pipelines/heatmap_stage.py:115-130`

## Proposed Solution

Implement **simple conflict detection and resolution**:

### Core Logic
1. **Detect conflicts early** in HeatmapStage initialization
2. **Check optim dict compatibility** before study creation
3. **Provide user-friendly resolution options**:
   - Create new timestamped study folder
   - Option to overwrite existing studies
   - Auto-handling for non-interactive/GUI modes

### Key Components
```python
# 1. Conflict detection
def check_optim_dict_compatibility(output_folder, new_optim_dict_name, target_tag):
    # Check for existing studies and compare optim dict names
    
# 2. Resolution handling (CLI + future GUI compatible)  
def handle_optim_dict_conflict(output_folder, new_optim_dict_name, context):
    # Provide appropriate options based on interaction mode
    
# 3. Metadata tracking
def save_optim_dict_metadata(output_folder, optim_dict_name):
    # Track which optim dict was used for future conflict detection
```

### Interaction Modes
- **CLI Interactive**: Prompt user with clear options
- **CLI Non-interactive**: Auto-create timestamped folder  
- **Future GUI**: Silent auto-handling with notification

### Benefits
- ✅ Prevents crashes completely
- ✅ Preserves user work (existing studies)
- ✅ GUI/CLI compatible design
- ✅ Early detection = fast feedback
- ✅ Simple implementation (low risk)

## Implementation Details

### Files to Modify
- `emuses/pipelines/heatmap_stage.py`: Add conflict detection
- `emuses/utils/`: New conflict resolution utilities  
- Tests: Add conflict scenario coverage

### Complexity: **Low**
- Small changes to existing pipeline flow
- No changes to core Optuna usage
- Minimal testing complexity

## Alternative Considered and Rejected

**Progressive Parameter Space Evolution**: Dynamically modify Optuna studies to support parameter space changes while preserving trials.

**Rejected because**:
- High implementation complexity (3x code, 5x testing)  
- Marginal performance gains (1-3% for significant complexity)
- Research software context prioritizes reliability over optimization sophistication
- EMUSES parameter spaces are relatively small (~8-12 parameters)

## Priority

**Medium** - Affects user experience when experimenting with different parameter spaces, but workaround exists (delete existing studies manually).

## Labels
- `bug` - crashes on parameter changes
- `enhancement` - improve user experience  
- `good first issue` - clear scope, well-defined solution

---

**Detailed analysis and technical specifications available in**: `docs/issues/optim_dict_resume_conflict.md`