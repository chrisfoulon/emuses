# Optuna Parameter Space Conflict During Resume - Analysis and Solution

## Problem Summary

When users run EMUSES on a previously trained model folder and change the `--prediction_optim_dict` parameter, the training crashes due to parameter space conflicts in Optuna studies.

## Context

### How EMUSES Resume Works
- EMUSES uses Optuna's `load_if_exists=True` to resume optimization studies
- Each target gets its own study: `f"{target_tag}_fold_{fold}"`
- Studies are stored in SQLite databases (with network-safe locations)
- When rerunning, Optuna automatically loads existing trials and continues

### Why Changing Optim Dict Crashes
The crash occurs because:

1. **Study Name Collision**: Same study names are reused regardless of parameter changes
2. **Parameter Space Mismatch**: New optim dict creates incompatible parameter suggestions
3. **Optuna Validation Failure**: Optuna tries to sample parameters that don't exist in the new dictionary

### Code Locations
- **HeatmapStage** (`heatmap_stage.py:115-130`): Loads optim dict from CLI args
- **Nested CV** (`optuna_cv.py:166-182`): Creates study with `load_if_exists=True`
- **Study Storage** (`network_drive_detection.py:162-201`): SQLite database management

### Conflict Examples
```python
# Original study has these trials:
"feat_type": "kpca_gwd"  # From optim_dict_predict

# New optim dict only allows:
"feat_type": {"choices": ["raw_only", "ae"]}  # From optim_dict_ae

# → Optuna fails when trying to continue with incompatible space
```

## Proposed Solution: Simple Conflict Detection

### Approach
When `--prediction_optim_dict` parameter changes, automatically create new studies instead of attempting to resume.

### Implementation Strategy

#### 1. Early Detection (in HeatmapStage)
```python
def check_optim_dict_compatibility(output_folder, new_optim_dict_name, target_tag):
    """Check if optim dict change requires new studies"""
    
    # Look for existing studies
    study_pattern = f"optuna_{target_tag}_fold_*.db"
    existing_studies = list(Path(output_folder).glob(f"databases/{study_pattern}"))
    
    if not existing_studies:
        return True  # No existing studies, safe to proceed
    
    # Check if same optim dict name used previously
    metadata_file = output_folder / "optim_dict_history.json"
    if metadata_file.exists():
        previous_dict = load_json(metadata_file).get("prediction_optim_dict")
        if previous_dict == new_optim_dict_name:
            return True  # Same dict, safe to resume
    
    # Different optim dict detected - need new studies
    return False
```

#### 2. Conflict Resolution (CLI/GUI Compatible)
```python
def handle_optim_dict_conflict(output_folder, new_optim_dict_name, context):
    """Handle optim dict conflicts with appropriate user interaction"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if context.get("gui_mode", False):
        # GUI mode: automatically use timestamped folder
        new_output = Path(output_folder).parent / f"{Path(output_folder).name}_{timestamp}"
        logger.info(f"Parameter space changed. Creating new study in: {new_output}")
        return str(new_output)
    
    elif context.get("interactive", True):
        # CLI interactive mode: prompt user
        print(f"⚠️  Parameter space conflict detected!")
        print(f"   Previous studies used different optimization parameters")
        print(f"   Options:")
        print(f"   1. Create new timestamped study: {output_folder}_{timestamp}")
        print(f"   2. Overwrite existing studies (lose previous progress)")
        
        choice = input("Choose option (1/2) [1]: ").strip() or "1"
        
        if choice == "2":
            # Remove existing studies
            cleanup_existing_studies(output_folder)
            return output_folder
        else:
            # Create timestamped folder
            new_output = f"{output_folder}_{timestamp}"
            return new_output
    
    else:
        # Non-interactive mode: auto-create timestamped study
        new_output = f"{output_folder}_{timestamp}"
        logger.info(f"Non-interactive mode: Creating new study in {new_output}")
        return new_output
```

#### 3. Study Metadata Tracking
```python
def save_optim_dict_metadata(output_folder, optim_dict_name):
    """Save optim dict metadata for future conflict detection"""
    metadata = {
        "prediction_optim_dict": optim_dict_name,
        "created_at": datetime.now().isoformat(),
        "emuses_version": get_emuses_version()
    }
    
    metadata_file = Path(output_folder) / "optim_dict_history.json"
    save_json(metadata_file, metadata)
```

### Timing and Integration Points

#### Early Detection in Pipeline Flow
```python
# In HeatmapStage.__init__ or early in run()
if not check_optim_dict_compatibility(self.config.output_folder, 
                                     context["cli_args"]["prediction_optim_dict"],
                                     "target_0"):
    # Handle conflict before any optimization starts
    new_output_folder = handle_optim_dict_conflict(
        self.config.output_folder,
        context["cli_args"]["prediction_optim_dict"], 
        context
    )
    # Update config with new output folder
    self.config.output_folder = new_output_folder
```

### Benefits

1. **Prevents crashes**: No more parameter space conflicts
2. **User control**: Clear options for handling conflicts  
3. **GUI compatible**: Works without user input prompts
4. **Simple implementation**: Minimal code changes
5. **Preserves work**: Option to keep existing studies or create new ones
6. **Early detection**: Fast feedback before optimization starts

### Implementation Complexity: Low
- Small changes to HeatmapStage initialization
- Helper functions for conflict detection
- Metadata tracking system
- No changes to Optuna usage patterns

## Alternative Considered: Progressive Optimization

We considered implementing dynamic parameter space evolution (progressive refinement), but rejected it due to:
- **High complexity**: 3x implementation burden, 5x testing complexity
- **Marginal gains**: 1-3% performance improvement for significant complexity
- **Research context**: Users prefer reliability over optimization sophistication
- **Parameter space size**: EMUSES has relatively small parameter spaces (~8-12 active parameters)

## Files to Modify

1. `emuses/pipelines/heatmap_stage.py`: Add conflict detection logic
2. `emuses/tools/optuna_cv.py`: Optional - add metadata saving
3. `emuses/utils/`: New utility functions for conflict handling
4. Tests: Add test cases for conflict scenarios

## Testing Strategy

1. **Unit tests**: Conflict detection logic
2. **Integration tests**: Full pipeline with parameter changes
3. **Manual testing**: CLI and future GUI scenarios
4. **Edge cases**: Network storage, concurrent runs, corrupted metadata

---

## Conclusion

This solution addresses the immediate crash issue while maintaining simplicity and user control. The implementation is straightforward and provides a foundation for future GUI integration.