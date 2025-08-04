# EMUSES Legacy Code Documentation

## Overview

This document identifies legacy code components that should be excluded from quality finalization analysis, based on user guidance and active usage patterns from CLI and modern API functionality.

## Exclusion Rationale

Legacy code components are excluded from quality metrics because:
1. They are not accessible through the modern CLI interface
2. They are not used by the FastAPI service endpoints
3. They represent deprecated functionality maintained for reference only
4. Including them would skew quality metrics for actively maintained code

## Confirmed Legacy Components

### 1. Complete Legacy Directories

#### `/emuses/scripts/` (All files are legacy)
**Status**: Complete exclusion from quality analysis
**Files**:
- `main.py` - Old CLI entry point (replaced by enhanced CLI)
- `run_optim_experiments.py` - Legacy experiment runner
- `streamlit_main.py` - Legacy Streamlit interface
- `viz_streamlit.py` - Legacy visualization interface

**Note**: These files import from pipelines but are not called by the modern CLI or API.

### 2. Legacy Functions in Active Files

#### `/emuses/pipelines/heatmap_stage.py`
**Active Component**: `HeatmapStage` class - Used by CLI and API
**Legacy Component**: `inspect_data_state()` function (lines 900+)
- Marked with TODO for removal
- Only used for debugging/development
- Has CLI parameter `--inspect_data_state` but deprecated functionality

**Quality Analysis Approach**: Include file but note that `inspect_data_state` function should be excluded from complexity/style metrics.

### 3. Mixed Legacy/Active Status Files

#### `/emuses/tools/stats_utils.py`
**Status**: Mostly legacy with some active functions
**User Guidance**: "mostly contains legacy code"
**Active Usage Found**:
- `compute_gwd_summary_test`, `train_and_test_model_per_label`, `optuna_model_selection`, `compute_gwd_summary`
- Used by: `prediction_stage.py`, `correlation_maps_utils.py`, `kernel_regression_utils.py`, `emuses_utils.py`

**Quality Analysis Approach**: 
- Include in test coverage analysis (functions are actively called)
- Apply lighter quality standards (focus on critical bugs, not style violations)
- Document as mixed legacy/active status

### 4. Confirmed Active Components (Not Legacy)

#### `/emuses/tools/` - Active Files
The following tools are actively used by the pipeline system and CLI:
- `parallelism_utils.py` - Direct CLI import, used by multiple stages
- `model_io.py` - Used by pipeline_config and pipeline stages
- `UMAP_utils.py` - Used by umap_stage.py
- `optim_utils.py` - Used by clustering and optimization
- `ae_utils.py`, `ae_optuna.py` - Autoencoder functionality
- `clustering_utils.py` - Used by UMAP_utils
- `data_preproc.py` - Used by inputs_utils and heatmap_stage
- `inputs_utils.py` - Used by emuses_pipeline and heatmap_stage
- `optuna_cv.py` - Used by heatmap_stage
- `kernel_regression_utils.py` - Used by heatmap_stage
- `correlation_maps_utils.py` - Used by kernel_regression_utils
- `models_utils.py` - Used by optuna_cv
- `features_utils.py` - Used by models_utils
- `emuses_utils.py` - Used by umap_stage
- `output_utils.py` - Used by kernel_regression_utils
- `visualisation.py` - Used by multiple stages

#### `/emuses/pipelines/` - All Active
All pipeline stage files are actively used by CLI and API:
- `emuses_pipeline.py` - Main pipeline orchestrator
- `heatmap_stage.py` - HeatmapStage class (excluding inspect_data_state function)
- `prediction_stage.py` - PredictionStage class
- `umap_stage.py` - UMAPStage class
- `pipeline_config.py` - Configuration management
- `pipeline_stage.py` - Base stage class

## Impact on Quality Analysis

### Adjusted Quality Metrics Scope

**Exclude from flake8 violation counts**:
- All files in `/emuses/scripts/`
- `inspect_data_state()` function in `heatmap_stage.py`

**Apply different standards**:
- `stats_utils.py` - Focus on critical bugs (F821, E722) rather than style violations
- Mixed legacy files - Lower priority for cosmetic fixes

**Focus quality efforts on**:
- All `/emuses/cli/` modules
- All `/emuses/api/` modules  
- All `/emuses/multi_user_service/` modules
- All `/emuses/observability/` modules
- Active `/emuses/tools/` modules
- Active functions in `/emuses/pipelines/` modules

### Revised Quality Baseline

With legacy code exclusions, the quality analysis should focus on approximately:
- **Modern CLI system** (~15 active files)
- **FastAPI service system** (~20 active files)
- **Multi-user service** (~15 active files)
- **Active tools** (~15 files)
- **Pipeline system** (~5 files, excluding legacy functions)

**Total active codebase**: ~70 files instead of full ~100+ file codebase

### Test Coverage Considerations

**Exclude from coverage requirements**:
- Legacy scripts (no CLI access paths)
- Deprecated functions (inspect_data_state)

**Include in coverage analysis**:
- Active functions in mixed files (specific functions from stats_utils.py)
- All pipeline classes and active methods

## Recommendations for Quality Finalization

1. **Immediate Priority**: Fix F821 undefined name violations in active code only
2. **Feature-specific review**: Apply LAD Step 03 to active components of completed features
3. **Legacy code**: Document current state but don't apply comprehensive quality standards
4. **Mixed files**: Focus on functions actively used by CLI/API, deprioritize legacy portions

## User Confirmation Needed

1. **stats_utils.py scope**: Should the specific active functions be treated as modern code for quality purposes?
2. **Legacy tolerance**: Is it acceptable to have higher violation counts in mixed legacy/active files?
3. **Test coverage**: Should legacy functions be completely excluded from coverage requirements?

---

*This documentation ensures quality finalization efforts focus on actively maintained code that impacts user experience and system reliability.*