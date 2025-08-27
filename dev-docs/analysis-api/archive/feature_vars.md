# Feature Variables

```bash
FEATURE_SLUG=inference-performance-fixes
PROJECT_NAME=EMUSES
FEATURE_DESCRIPTION="Fix two critical inference pipeline issues: (1) duplicated terminal output causing user experience problems, and (2) zero predictions in kernel models while elastic models work correctly"

# Problem Context
ISSUE_1_DESCRIPTION="Duplicated terminal output - multiple logging layers creating redundant messages, JSON logs, progress bars appearing multiple times"
ISSUE_1_SEVERITY="Medium - affects user experience, not functionality"
ISSUE_1_EVIDENCE="User reports 'there are still a lot of duplicate prints' after previous fixes"

ISSUE_2_DESCRIPTION="UPDATED 2025-08-27: Coordinate usage fix applied, remaining normalization enhancements needed for cross-validation denormalization"
ISSUE_2_SEVERITY="Medium - core functionality working, enhancements needed for complete user requirements"
ISSUE_2_EVIDENCE="Coordinate usage fix resolved zero predictions, need input scaler saving for labelled datasets and HeatmapStage raw prediction output"
ISSUE_2_ROOT_CAUSE="EMUSESPipeline is_labelled=True case doesn't save input scaler to joblib files, missing cross-validation denormalization"

# Solution Requirements
NO_BACKWARD_COMPATIBILITY="User explicitly stated no backward compatibility requirements"
NO_FALLBACK_ALLOWED="No fallback allowed for zero predictions - either works or throws error"
HIGH_CONFIDENCE_NEEDED="User requested proper LAD phases due to previous shallow analysis"
NORMALIZATION_CRITICAL="Must apply identical training-time normalization to inference embeddings"
TRAINING_PARAMS_REQUIRED="Must save/load normalization parameters from training for inference consistency"

# Environmental Context
MODEL_PATH_TEST="/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/model_registry_final_multi_target"
OUTPUT_PATH_TEST="/mnt/s/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/test_inference_pipeline"
VALIDATION_WORKING="Issue 3 (missing validation metrics) was successfully fixed"
```