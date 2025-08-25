# Feature Variables

```bash
FEATURE_SLUG=inference-performance-fixes
PROJECT_NAME=EMUSES
FEATURE_DESCRIPTION="Fix two critical inference pipeline issues: (1) duplicated terminal output causing user experience problems, and (2) zero predictions in kernel models while elastic models work correctly"

# Problem Context
ISSUE_1_DESCRIPTION="Duplicated terminal output - multiple logging layers creating redundant messages, JSON logs, progress bars appearing multiple times"
ISSUE_1_SEVERITY="Medium - affects user experience, not functionality"
ISSUE_1_EVIDENCE="User reports 'there are still a lot of duplicate prints' after previous fixes"

ISSUE_2_DESCRIPTION="CRITICAL: Data normalization mismatch - inference embeddings not normalized to training data scale, causing KernelRegressor models to fail"
ISSUE_2_SEVERITY="Critical - affects data accuracy, KernelRegressor models completely non-functional"
ISSUE_2_EVIDENCE="Training embeddings: [0,1] range, Inference embeddings: [1.5-13] range, Distance ~8-12 causes weight_sum=0"
ISSUE_2_ROOT_CAUSE="Missing post-UMAP normalization in inference pipeline - embeddings must match training scale"

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