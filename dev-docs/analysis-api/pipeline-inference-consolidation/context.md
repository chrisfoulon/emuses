# EMUSESPipeline Inference Mode Consolidation - Context Documentation

## Level 1: Plain English Summary

**Current Problem**: The EMUSES inference system has architectural duplication where `_execute_inference_locally` in CLI manually recreates EMUSESPipeline initialization logic, leading to double dataset processing and maintenance overhead.

**Key Components**:
- **EMUSESPipeline**: Main pipeline class with comprehensive initialization including random seed management, context setup, and dataset processing
- **InferenceStage**: Dedicated stage for running inference using trained models
- **_execute_inference_locally**: CLI function that duplicates pipeline initialization rather than using it efficiently
- **inference_mode flag**: Existing mechanism to skip training-specific operations (e.g., dataset splitting)

**Integration Strategy**: ENHANCE existing EMUSESPipeline to handle inference mode more efficiently, eliminating the need for manual initialization in CLI.

## Level 2: API Integration Table

| Symbol | Purpose | Inputs | Outputs | Side-effects |
|--------|---------|--------|---------|--------------|
| `EMUSESPipeline.__init__` | Full pipeline initialization | args (Namespace) | None | Creates output folder, saves random_seeds.json, processes datasets, sets up context |
| `EMUSESPipeline.process_dataset` | Dataset processing | dataset_identifier, is_labelled | input_matrix, dataset_type, output_format_info, scores | Updates paths_list, handles BIDS/image/NIfTI formats |
| `EMUSESPipeline.load_and_process_scores` | Score loading | expected_length | None | Updates self.scores, context["scores"] |
| `_execute_inference_locally` | CLI inference execution | config (dict), status_renderer | None | Creates EMUSESPipeline, processes data again, runs InferenceStage |
| `InferenceStage.run` | Model inference | context (dict) | results (dict) | Loads models, generates predictions, saves outputs |
| `PipelineConfig` | Configuration wrapper | args (Namespace) | PipelineConfig instance | Validates and structures arguments |

## Level 3: Code Integration Points

### Current Duplication Pattern
```python
# EMUSESPipeline.__init__ (automatic via format_args)
def format_args(self):
    self.input_matrix, self.dataset_type, self.output_format_info, scores = (
        self.process_dataset(self.config.input_dataset, is_labelled=False)
    )
    if scores is not None:
        self.scores = scores
    else:
        self.load_and_process_scores(expected_length=self.input_matrix.shape[0])

# _execute_inference_locally (manual duplication)
pipeline = EMUSESPipeline(args)  # Triggers format_args() above
input_matrix, dataset_type, output_format_info, scores = pipeline.process_dataset(config["data"])  # DUPLICATE!
if args.scores:
    pipeline.load_and_process_scores(expected_length=input_matrix.shape[0])  # DUPLICATE!
```

### Efficient Integration Pattern (Target)
```python
# EMUSESPipeline.__init__ (inference-aware)
def __init__(self, args, inference_data=None):
    if inference_data:
        # Lightweight initialization using pre-provided data
        self._setup_inference_mode(args, inference_data)
    else:
        # Full initialization with dataset processing
        self._setup_full_pipeline(args)

# _execute_inference_locally (simplified)
inference_data = {
    "input_path": config["data"],
    "scores_path": config.get("scores"),
    "model_path": config["model"]
}
pipeline = EMUSESPipeline(args, inference_data=inference_data)
# Pipeline context already contains processed data - no duplication
inference_stage = InferenceStage(pipeline.config)
results = inference_stage.run(pipeline.context)
```

### Existing Infrastructure to Leverage
```python
# inference_mode flag (already exists)
if not getattr(self.config, 'inference_mode', False):
    self.split_dataset()  # Skip in inference mode

# FastAPI conditional stage pattern (proven approach)
if config_dict.get("inference_stage_enabled", True):
    pipeline.add_stage(InferenceStage(pipeline.config))
```

## Maintenance Opportunities

### High Priority (None Found)
No critical maintenance issues (F821 undefined names, E722 bare except clauses) detected in target files.

### Medium Priority (Boy Scout Rule Opportunities)
- **emuses/cli/main.py**: Remove manual args object creation pattern once consolidation is complete
- **emuses/pipelines/emuses_pipeline.py**: Consider refactoring format_args() method for better separation of concerns
- Consider adding docstring improvements during refactoring

## Integration Points Summary

**Current Architecture**: CLI bypasses EMUSESPipeline's built-in dataset processing by calling methods manually after initialization

**Target Architecture**: EMUSESPipeline handles inference mode efficiently during initialization, CLI uses processed data from context

**Key Benefit**: Eliminates double dataset processing while preserving all inference-specific features (model_path, cli_inference_mode, validation support)

## ✅ Implementation Results (2025-08-30)

### Consolidation Successfully Completed

**Implemented Solution:**
- Enhanced `format_args()` to properly handle inference mode without bypassing critical bcblib processing
- Simplified CLI integration: set `inference_mode=True` and `model_path` on args, let existing logic handle everything
- Added inference context setup after dataset processing: `context["inference_features"] = self.input_matrix`

**Key Technical Decisions:**
- **Rejected bypass approach**: Initial attempt to bypass `format_args()` broke bcblib's essential data type conversion
- **Preserved existing inference_mode logic**: Lines 152-153, 337-399, 444-480 already had working inference specialization
- **Eliminated double processing**: Single pathway through `format_args()` handles both training and inference

**Validation Results:**
- ✅ **No double processing**: Single "Initializing pipeline" message, no duplicate dataset processing
- ✅ **Timedelta data processing fixed**: bcblib `spreadsheet_to_input_df` handles complex data types correctly
- ✅ **InferenceStage integration works**: Context contains `inference_features` with `shape=(1067, 116)`
- ✅ **Model loading successful**: UMAP, prediction models, scalers all load correctly
- ⚠️ **Remaining issue**: Timedelta objects reach UMAP transform causing `float() argument must be a string or a real number, not 'Timedelta'`

### New Issue: Timedelta Data Compatibility

**Current Problem**: After successful consolidation, inference fails at UMAP transform with Timedelta conversion error

**Root Cause Analysis Needed**:
- User reports this worked recently, suggesting a regression or environment change
- Data contains time strings (`'22:30:00'`, `'06:00:00'`) that become Timedelta objects
- `spreadsheet_to_input_df` processes these correctly, but they persist in final data matrix
- UMAP transform expects pure numeric data

**Investigation Required**:
1. Compare recent changes to data processing pipeline
2. Analyze why Timedelta objects survive data cleaning
3. Identify proper conversion strategy for mixed time/numeric data
4. Ensure solution maintains data integrity

## Related Analysis API Work

This consolidation builds on the recent Analysis API Enhancement work in `feature/analysis-api-enhancement`:
- Leverages the robust inference infrastructure established in Phase 6
- Complements the model registry improvements by streamlining inference pipeline architecture
- Addresses architectural debt identified during the comprehensive analysis API implementation