# Web GUI Context - Codebase Integration Points

## Level 1: Plain English Summary

The EMUSES CLI is built with Typer and provides 5 main commands: `full` (complete pipeline), `umap` (dimensionality reduction), `heatmap` (visualization), `inference` (model application), and `models` (registry management). Each command has ~20-30 parameters that control data loading, preprocessing, UMAP configuration, clustering, prediction models, and output options.

The pipeline architecture uses a stage-based design where `EMUSESPipeline` orchestrates multiple stages (`UMAPStage`, `HeatmapStage`, `InferenceStage`) that share a common `context` dictionary. Progress tracking is handled by `ProgressTracker` and `StatusRenderer` using Rich library for terminal output.

The model registry (`LocalModelRegistry`) provides methods to `list_models()`, `search_models()`, `get_model_info()`, and `install_model()` with thread-safe operations and metadata indexing.

A FastAPI service exists (`foundation_fastapi_service`) that provides REST endpoints for job management and pipeline execution, with rate limiting, request size validation, and observability integration.

## Level 2: API Integration Table

| Symbol | Purpose | Inputs | Outputs | Side-effects |
|--------|---------|--------|---------|--------------|
| **CLI Commands** |
| `emuses.cli.main.full()` | Run complete EMUSES pipeline | 97 CLI params (input_dataset, output_folder, scores, etc.) | Pipeline results (embeddings, models, heatmaps) | Creates output folder, saves models/results to disk |
| `emuses.cli.main.umap()` | Train UMAP and generate embeddings | input_dataset, output_folder, UMAP params | UMAP model, embeddings (.npy) | Saves UMAP model to output folder |
| `emuses.cli.main.heatmap()` | Create correlation heatmaps | embeddings, scores, output_folder | Heatmap visualizations | Saves plots to disk |
| `emuses.cli.main.inference()` | Run inference on trained model | data, model (path or ID), output, validate flag | Predictions (CSV or NPY) | Saves predictions to output path |
| **Pipeline Classes** |
| `EMUSESPipeline.__init__()` | Initialize pipeline orchestrator | args (Namespace), inference_data (optional) | Configured pipeline instance | Creates output folder, saves random seeds |
| `EMUSESPipeline.add_stage()` | Add processing stage to pipeline | stage (PipelineStage instance) | None | Appends stage to self.stages list |
| `EMUSESPipeline.run()` | Execute all pipeline stages | progress_callback (optional) | None | Executes stages, updates context, saves results |
| `EMUSESPipeline.format_args()` | Load and preprocess input data | None (uses self.config) | None | Sets self.input_matrix, self.scores, etc. |
| **Pipeline Stages** |
| `UMAPStage.execute()` | Perform dimensionality reduction | context (shared pipeline data) | context (with embeddings, umap_model) | Saves UMAP model, embeddings, scaling params |
| `HeatmapStage.execute()` | Generate correlation heatmaps | context (embeddings, scores) | context (with plots) | Creates and saves heatmap visualizations |
| `InferenceStage.execute()` | Apply model to new data | context (model, inference data) | context (with predictions) | Saves predictions to CSV/NPY |
| **Model Registry** |
| `LocalModelRegistry.list_models()` | List all registered models | filters (dict, optional), filter_installed (bool) | List[Dict] (model metadata) | None (read-only) |
| `LocalModelRegistry.search_models()` | Search models by query | query (str), limit (int) | List[Dict] (matching models) | None (read-only) |
| `LocalModelRegistry.get_model_info()` | Get detailed model metadata | model_id (str) or model_name (str) | Dict (full model metadata) | None (read-only) |
| `LocalModelRegistry.install_model()` | Register model in registry | model_path (Path), model_name (str), metadata (dict) | str (model_id) | Creates model folder, saves metadata JSON |
| `LocalModelRegistry.remove_model()` | Remove model from registry | model_id (str) | None | Deletes model folder and updates index |
| **Progress Tracking** |
| `ProgressTracker.set_stages()` | Initialize stage tracking | stage_names (List[str]) | None | Creates StageInfo objects for each stage |
| `ProgressTracker.update()` | Update current stage progress | progress (float 0.0-1.0), message (str) | None | Updates current stage's progress value |
| `ProgressTracker.next_stage()` | Advance to next stage | None | None | Marks current stage complete, advances index |
| `StatusRenderer.render_status()` | Display progress in terminal | stages (List[StageInfo]) | None | Prints Rich-formatted progress bars |
| **FastAPI Service** |
| `/api/pipeline/full` (POST) | Execute full pipeline remotely | PipelineConfigRequest (JSON) | JobStatusResponse (job_id, status) | Creates background job, executes pipeline |
| `/api/inference` (POST) | Run inference via API | InferenceRequest (data, model_id) | InferenceResponse (predictions) | Loads model, runs inference, returns results |
| `/api/models/list` (GET) | List models via API | filters (query params) | List[ModelMetadata] | None (read-only) |
| `/api/jobs/{job_id}/status` (GET) | Check job status | job_id (UUID) | JobStatusResponse (status, progress, results) | None (read-only) |

## Level 3: Code Integration Snippets

### Calling Full Pipeline from GUI

```python
import asyncio
from pathlib import Path
from emuses.cli.main import _full_async
from argparse import Namespace

# Convert GUI inputs to args namespace
args = Namespace(
    output_folder=Path(output_folder),
    input_dataset=Path(input_dataset),
    scores=Path(scores_file) if scores_file else None,
    test_size=test_size,
    input_normalization=input_normalization,
    # ... ~90 more parameters
)

# Run pipeline asynchronously
asyncio.run(_full_async(
    output_folder=args.output_folder,
    input_dataset=args.input_dataset,
    scores=args.scores,
    # ... pass all parameters
))
```

### Progress Tracking Adapter for Gradio

```python
from emuses.cli.rich_features import ProgressTracker

# Create progress callback for Gradio
def create_progress_callback(gradio_progress):
    """Adapt EMUSES ProgressTracker to Gradio progress bar."""
    def progress_callback(stage_name, progress, message):
        # Update Gradio progress
        gradio_progress(progress, desc=f"{stage_name}: {message}")
    return progress_callback

# Use in pipeline execution
tracker = ProgressTracker()
tracker.set_stages(["Loading", "UMAP", "Clustering", "Heatmap"])
# Pass tracker.update as callback to pipeline
```

### Model Registry Integration

```python
from emuses.tools.local_model_registry import LocalModelRegistry
from pathlib import Path

# Initialize registry
registry = LocalModelRegistry()  # Uses default ~/.emuses/model_registry

# List models for GUI dropdown
models = registry.list_models(filter_installed=True)
model_options = [(m['name'], m['id']) for m in models]

# Get model details for display
model_id = selected_model  # from GUI selection
model_info = registry.get_model_info(model_id=model_id)
# Display: model_info['description'], model_info['created_at'], etc.

# Search models
query = search_text  # from GUI search box
results = registry.search_models(query=query, limit=20)
```

### File Upload Handling with Gradio

```python
import gradio as gr
from pathlib import Path

def process_uploaded_file(file):
    """Handle uploaded file from Gradio."""
    if file is None:
        return None

    # Gradio provides file object with .name attribute (temp path)
    file_path = Path(file.name)

    # For large files, Gradio automatically handles streaming
    # No need for custom chunking
    return file_path

# In Gradio interface
gr.File(label="Input Dataset", file_types=[".nii", ".nii.gz", ".jpg", ".png", ".csv"])
```

### Async Execution Pattern

```python
import gradio as gr
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=3)

def run_pipeline_sync(inputs):
    """Wrapper for async pipeline execution."""
    return asyncio.run(_execute_pipeline_async(inputs))

async def _execute_pipeline_async(inputs):
    """Actual async pipeline execution."""
    # Run pipeline
    result = await _full_async(**inputs)
    return result

# Gradio interface with queue for async
interface = gr.Interface(
    fn=run_pipeline_sync,
    inputs=[...],
    outputs=[...]
)
interface.queue()  # Enable queueing for async
interface.launch()
```

### FastAPI Integration (Optional Multi-User)

```python
import gradio as gr
import requests

API_BASE_URL = "http://localhost:8000"

def run_via_api(config):
    """Execute pipeline via FastAPI service."""
    response = requests.post(
        f"{API_BASE_URL}/api/pipeline/full",
        json=config
    )
    job_id = response.json()['job_id']

    # Poll for status
    while True:
        status_response = requests.get(
            f"{API_BASE_URL}/api/jobs/{job_id}/status"
        )
        status_data = status_response.json()

        if status_data['status'] == 'completed':
            return status_data['results']
        elif status_data['status'] == 'failed':
            raise Exception(status_data['error'])

        time.sleep(2)  # Poll every 2 seconds
```

## Maintenance Opportunities in Target Files

No target files have been created yet. This is a greenfield implementation in a new `emuses/gui/` module.

### Potential Maintenance While Implementing:
- **None identified** - This is new code in a new module
- Will follow existing code quality standards (Flake8, docstrings, type hints)
- Will reuse existing validation logic rather than duplicating

## Integration Points Summary

### Direct Python Integration
- **Primary approach**: Import and call existing CLI async functions
- **Advantages**: No duplication, inherits all validation and error handling
- **Disadvantages**: Must adapt ~97 parameters to GUI components

### FastAPI Service Integration (Optional)
- **Use case**: Multi-user deployments with authentication
- **Advantages**: Centralized execution, job queue, multi-user support
- **Disadvantages**: Additional complexity, requires service running

### Hybrid Approach (Recommended)
- **Single-user mode**: Direct Python calls for simplicity
- **Multi-user mode**: FastAPI integration for shared deployment
- **Implementation**: Detect if FastAPI service is available, fallback to direct calls

## Dependencies Required

### New Dependencies
```python
# Add to setup.py
install_requires=[
    # ... existing deps
    "gradio>=4.0.0,<5.0.0",  # Web UI framework
]
```

### Existing Dependencies (Reused)
- `typer` - CLI framework (for parameter validation)
- `rich` - Progress tracking (adapt for Gradio)
- `fastapi` - Optional API integration
- `uvicorn` - Optional API server
- All EMUSES pipeline dependencies

## Architecture Decisions

### GUI Module Structure
```
emuses/
├── gui/
│   ├── __init__.py          # Package init
│   ├── app.py               # Main Gradio application entry point
│   ├── components/          # Reusable UI components
│   │   ├── __init__.py
│   │   ├── pipeline_tab.py  # Full pipeline interface
│   │   ├── inference_tab.py # Inference interface
│   │   └── models_tab.py    # Model browser interface
│   ├── adapters/            # CLI-to-GUI adapters
│   │   ├── __init__.py
│   │   ├── parameter_mapper.py  # Convert GUI inputs to CLI args
│   │   ├── progress_adapter.py  # Adapt ProgressTracker to Gradio
│   │   └── result_formatter.py  # Format results for display
│   └── utils/               # Helper utilities
│       ├── __init__.py
│       ├── validation.py    # Input validation (reuse CLI logic)
│       └── file_utils.py    # File handling helpers
```

### Component Design Pattern
- **Progressive Disclosure**: Use `gr.Accordion()` for optional parameters
- **Tabbed Interface**: Separate tabs for full/umap/heatmap/inference/models
- **Real-time Validation**: Use Gradio's `.change()` events for parameter validation
- **Async Execution**: Use `gr.Interface.queue()` for long-running operations

## Testing Strategy

### Unit Tests
- `test_parameter_mapper.py` - Test GUI param to CLI args conversion
- `test_progress_adapter.py` - Test progress callback adaptation
- `test_validation.py` - Test input validation logic

### Integration Tests
- `test_pipeline_integration.py` - Test full pipeline execution via GUI
- `test_model_registry_integration.py` - Test model browser operations
- `test_inference_integration.py` - Test inference workflow

### Manual Testing
- File upload (various formats, sizes up to 5GB)
- Parameter combinations (required + optional)
- Error scenarios (invalid files, bad paths)
- Cross-platform (Linux, Mac, Windows)
- Concurrent users (multiple browser tabs)

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Gradio version changes break API | LOW | MEDIUM | Pin Gradio 4.x version in setup.py |
| Large file upload timeout | MEDIUM | HIGH | Test with 5GB+ files, use Gradio streaming |
| Parameter mapping errors | MEDIUM | MEDIUM | Comprehensive unit tests for all 97 params |
| Progress tracking mismatch | LOW | LOW | Adapt existing ProgressTracker callbacks |
| Memory issues with large datasets | MEDIUM | HIGH | Monitor memory, implement cleanup |
| Gradio queue deadlock | LOW | MEDIUM | Test concurrent execution, implement timeouts |

### Mitigation Strategies

1. **Version Pinning**: Lock Gradio to 4.x series in `setup.py`
2. **File Upload Testing**: Test with actual neuroimaging datasets (5GB+)
3. **Parameter Validation**: Reuse existing CLI validation logic
4. **Progress Adaptation**: Create thin adapter wrapper around ProgressTracker
5. **Memory Monitoring**: Implement cleanup in pipeline completion callback
6. **Queue Management**: Set reasonable timeouts, test with multiple users

---

**Context Gathered**: 2025-10-08
**Branch**: feature/web-gui-gradio
**Next**: Create comprehensive implementation plan (plan.md)
