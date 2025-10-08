# Feature Variables - Web GUI with Gradio

## Core Variables
```bash
FEATURE_SLUG=web-gui-gradio
PROJECT_NAME=EMUSES
FEATURE_DESCRIPTION="Implement a simple, robust, and multiplatform web-based GUI for EMUSES using Gradio 4.x"
```

## Requirements

### Inputs
- User-uploaded datasets (NIfTI files, images, CSV data)
- Configuration parameters from GUI controls (~97 CLI parameters)
- Model paths or registry IDs
- Output directory paths

### Outputs
- Interactive web interface accessible via browser
- Real-time progress tracking during pipeline execution
- Results visualization (embeddings, heatmaps, clustering plots)
- Downloadable output files (models, predictions, visualizations)
- Error messages with actionable feedback

### Constraints
- Must work identically on Linux, Mac, Windows (zero platform-specific code)
- Minimal maintenance burden (15-30 hours/year)
- Thin wrapper around existing CLI (no business logic duplication)
- Handles 5GB+ file uploads
- Supports 2+ hour pipeline executions
- < 100 lines for MVP interface
- < 2 second startup time
- Reuses existing EMUSES validation logic

### Acceptance Criteria

#### MVP (Week 1)
- [ ] Basic pipeline interface (full command) launches in browser
- [ ] Required parameters (input dataset, output folder) functional
- [ ] Basic optional parameters in expandable accordions (scores, test_size, normalization)
- [ ] Run button executes pipeline asynchronously
- [ ] Real-time progress updates displayed to user
- [ ] Results available for download after completion
- [ ] Clear error messages for validation failures
- [ ] Works without configuration on Linux, Mac, Windows

#### Full Version (Weeks 2-3)
- [ ] All ~97 CLI parameters accessible via organized accordions
- [ ] Inference interface with model selection (file path or registry ID)
- [ ] Model browser interface (list, search, view metadata)
- [ ] Parameter presets for common workflows
- [ ] Results visualization (embeddings, heatmaps, clusters)
- [ ] Configuration save/load functionality
- [ ] Help text and tooltips for all parameters
- [ ] Responsive design for different screen sizes

#### Quality Indicators
- [ ] < 100 lines of code for MVP interface
- [ ] Zero platform-specific code (pure Python)
- [ ] < 2 second startup time
- [ ] < 1 second response time for parameter changes
- [ ] Handles 5GB+ file uploads without issues
- [ ] Supports concurrent users (3-5 simultaneous jobs)

## Planning Variables

### Task Complexity
**MEDIUM** - Feature implementation with GUI framework integration

### Implementation Approach
Thin wrapper pattern using Gradio 4.x to expose existing EMUSES CLI functionality through web interface. Progressive disclosure for parameters using accordions. Direct calls to existing pipeline classes rather than duplicating logic.

### Key Challenges
1. **Parameter Mapping**: Converting ~97 CLI parameters to appropriate Gradio components
2. **File Upload Handling**: Managing large file uploads (5GB+) efficiently
3. **Progress Tracking**: Adapting CLI progress callbacks for real-time web updates
4. **Async Execution**: Running long pipelines without blocking web interface
5. **Result Visualization**: Displaying plots and results in browser

### Resource Requirements
- **Timeline**: 3-4 weeks
- **Team**: 1 Python developer familiar with EMUSES CLI
- **Dependencies**: Gradio 4.x, existing EMUSES pipelines, model registry
- **Testing**: Manual GUI testing + automated unit tests for wrappers

## Component Integration Points

### Existing Components to Integrate
- `emuses.cli.main` - CLI commands and validation logic
- `emuses.pipelines.emuses_pipeline.EMUSESPipeline` - Core pipeline orchestration
- `emuses.pipelines.umap_stage.UMAPStage` - Dimensionality reduction
- `emuses.pipelines.heatmap_stage.HeatmapStage` - Visualization
- `emuses.pipelines.inference_stage.InferenceStage` - Model inference
- `emuses.tools.model_registry.LocalModelRegistry` - Model management
- `emuses.foundation_fastapi_service.app` - Optional multi-user backend

### Integration Strategy
**ENHANCE** - Add new GUI layer that wraps existing CLI functionality
- Create new `emuses/gui/` module
- No modifications to existing CLI or pipeline code
- Reuse validation, execution, and registry logic
- Optional: integrate with FastAPI service for multi-user scenarios

### Deprecation Plan
None - GUI complements CLI, does not replace it

### Compatibility Requirements
- GUI must produce identical results to CLI for same parameters
- No breaking changes to existing EMUSES APIs
- Must work with current model registry format
- Should integrate with existing FastAPI endpoints (optional)

## Architecture Overview

### New Module Structure
```
emuses/
├── gui/
│   ├── __init__.py
│   ├── app.py              # Main Gradio application
│   ├── components.py       # Reusable UI components (accordions, file inputs)
│   ├── pipeline_wrapper.py # CLI-to-GUI parameter adapter
│   ├── model_browser.py    # Model registry interface
│   └── utils.py            # Helper functions (validation, formatting)
```

### Deployment Options
1. **Local Desktop**: `python -m emuses.gui.app` (opens browser)
2. **Lab Server**: `python -m emuses.gui.app --server-name 0.0.0.0 --server-port 7860`
3. **Docker**: Container with EMUSES + GUI pre-installed
4. **HuggingFace Spaces**: Free public hosting (for demos)

## Framework Selection

### Gradio 4.x (Selected - 9.55/10)
- ✅ Simplest implementation (30-50 lines for MVP)
- ✅ Built for ML/data applications
- ✅ Zero cross-platform configuration surprises
- ✅ Battle-tested by 100K+ researchers
- ✅ Built-in file upload, progress tracking, queuing
- ✅ HuggingFace backing (stability)
- ✅ FastAPI backend (matches EMUSES stack)

### Alternatives Considered
- **Streamlit** (7.75/10): Re-runs entire script on interaction, more complex state management
- **NiceGUI** (6.45/10): Smaller community, less proven
- **Reflex** (5.35/10): Complex React compilation, overkill
- **Dash** (6.2/10): Verbose callback system, steep learning curve

---

**Created**: 2025-10-08
**Branch**: feature/web-gui-gradio
**Status**: Planning Phase
