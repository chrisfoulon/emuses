# Feature Variables - Prediction Validity Reporting

## Core Feature Configuration
```bash
FEATURE_NAME="Prediction Validity Reporting"
FEATURE_SLUG="prediction-validity-reporting"
FEATURE_BRANCH="feature/prediction-validity-reporting"   # off main, after PR #10 merges
FEATURE_FOLDER="dev-docs/analysis-api/prediction-validity-reporting"
```

## Implementation Configuration
```bash
TASK_COMPLEXITY="MEDIUM-HIGH"
IMPLEMENTATION_APPROACH="Add a pre-flight power report before the target fan-out, a per-target mean-predictor floor inside the existing nested CV, and gated two-file ranking output. No change to how models are fitted or selected."
RESOURCE_REQUIREMENTS="4 phases, each independently landable. Phase 1-2 are hours; phase 3 needs a second-dataset replay before its default can change."
WORKING_MODE="accept-edits, NOT auto"   # see 'Working mode' in plan.md - this is scientific output
```

## Target Files
```bash
PRIMARY_TARGET_FILES="emuses/pipelines/heatmap_stage.py,emuses/tools/optuna_cv.py,emuses/cli/pipeline_options.py"
NEW_MODULE="emuses/tools/prediction_validity.py"
TEST_FILES="tests/unit/test_prediction_validity.py,tests/regression/test_validity_report.py"
VALIDATION_COMMAND="python scripts/dev_test_runner.py"
```

## Integration Points
```bash
INTEGRATION_STRATEGY="ENHANCE"
RELATED_COMPONENTS="HeatmapStage,nested_optuna_cv,_optimise_target,_generate_performance_csv_files,PipelineConfig"
EXISTING_INFRASTRUCTURE="joblib target fan-out,_seeds_from seed derivation,performance_summary context key,typer str-Enum option pattern"
```

## Rationale
```bash
RATIONALE_DOC="dev-docs/methodology/small_sample_prediction_validity.md"
AUDIT_NARRATIVE="dev-docs/issues/disconnectome_design_audit_2026_08.md"
STATUS_ITEMS="3d,3f,3g,3h,3i"
```
