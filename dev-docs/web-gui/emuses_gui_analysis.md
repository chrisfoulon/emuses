# EMUSES GUI Analysis & Planning Notes

## Executive Summary

**Date**: 2025-10-08
**Analysis Focus**: Mapping CLI commands to potential GUI implementation
**Key Finding**: Legacy Streamlit GUI exists but is archived. No current GUI plans in active roadmap.

---

## Current CLI Commands - Core Analysis Pipeline

### 1. `full` Command - Complete Pipeline
**Location**: `emuses/cli/main.py:524`
**Purpose**: Run the complete EMUSES analysis pipeline

**Key Parameters**:
- `output_folder` (required)
- `input_dataset` (required) - Images (jpg), NIfTI, or MNIST
- `scores` (optional) - Labels/target data
- `label_dataset` (optional) - Separate labeled dataset
- Input preprocessing: normalization, file search, BIDS filters
- UMAP configuration: n_neighbors, min_dist, n_components
- Clustering: HDBSCAN min_cluster_size, min_samples
- Prediction: model types, optimization parameters
- Output: correlation maps, heatmaps, embeddings

**GUI Potential**: **HIGH** - This is the main entry point for researchers
- Could be a wizard-style interface
- Form-based parameter input
- Progress tracking with rich output
- Result visualization

---

### 2. `umap` Command - Dimensionality Reduction
**Location**: `emuses/cli/main.py:1712`
**Purpose**: Train UMAP and get embeddings

**Key Parameters**:
- `output_folder` (required)
- `input_dataset` (required)
- Simplified interface - delegates to full pipeline internally

**GUI Potential**: **MEDIUM** - Subset of full pipeline
- Could be integrated into full GUI
- Useful for iterative UMAP parameter tuning
- Embedding visualization would be valuable

---

### 3. `heatmap` Command - Visualization
**Location**: `emuses/cli/main.py:1752`
**Purpose**: Create correlation heatmaps

**Key Parameters**:
- `output_folder` (required)
- `input_dataset` (required)
- Simplified interface

**GUI Potential**: **HIGH** - Visual output is GUI-friendly
- Interactive heatmap exploration
- Parameter tweaking with live preview
- Export options for publications

---

### 4. `inference` Command - Model Application
**Location**: `emuses/cli/main.py:1792`
**Purpose**: Run inference on trained models

**Key Parameters**:
- `output` (required) - Output path
- `data` (required) - Input data
- `model` OR `model_id` - Model source (path or registry)
- `validate` - Validation mode flag
- `verify` - Model integrity check
- `output_format` - csv or npy
- Preprocessing parameters (headers, columns, etc.)

**GUI Potential**: **VERY HIGH** - Critical for model deployment
- Model selection interface (browse or registry)
- Data upload/selection
- Real-time validation feedback
- Results visualization
- Batch processing interface

---

### 5. `models` Command Group - Model Registry
**Location**: `emuses/cli/models_commands.py`
**Purpose**: Model registry management

**Subcommands** (based on file analysis):
- Model listing/search
- Model information retrieval
- Model verification
- Citation generation
- Provenance export

**GUI Potential**: **VERY HIGH** - Perfect for GUI
- Model browser/explorer
- Search and filter interface
- Model cards with metadata
- Dependency graphs
- Download/share functionality

---

## Legacy GUI Evidence

### Streamlit Implementation (Archived)
**Location**: `legacy_archive/scripts/streamlit_main.py`
**Date**: Archived (pre-Typer CLI migration)

**Capabilities**:
- Web-based interface using Streamlit
- Command selection: full, umap, clustering, heatmap, prediction
- Sidebar parameter configuration
- Real-time progress tracking
- Pipeline execution from GUI

**Key Components**:
```python
st.title("EMUSES Pipeline Web Interface")
command = st.sidebar.selectbox("Select Command", ["full", "umap", "clustering", "heatmap", "prediction"])
# Parameter collection based on command
# Execute button -> run pipeline
```

**Why Archived**:
- Likely incompatible with current Typer-based CLI
- Parameters may have changed significantly
- May not support new features (model registry, inference, etc.)

---

## Project Planning Documents - GUI References

### Search Results Summary
- **61 markdown files** mention "streamlit", "GUI", "graphical", "web interface", or "dashboard"
- Most mentions are in:
  - Documentation restructuring plans
  - User guide references
  - Model registry integration plans
  - Multi-user service documentation

### Key Findings:

#### 1. No Active GUI Feature Plans
**Status**: Not found in active roadmap
- DEFERRED_FEATURES.md: Only mentions HIPAA compliance
- No standalone GUI development plan
- Multi-user service is API-based (not GUI)

#### 2. Documentation Focus
Most GUI mentions are about:
- User guide improvements (not actual GUI)
- Web-based documentation (MkDocs Material)
- API documentation for building interfaces

#### 3. Multi-User Service is REST API
**Location**: `dev-docs/multi-user-service/`
- FastAPI-based service
- REST endpoints for model management
- Authentication/authorization
- Could be consumed by future GUI

#### 4. Model Registry Integration
**Location**: `dev-docs/model-registry/`
- Database-backed model storage
- REST API endpoints available
- Could power model browser GUI

---

## CLI-to-GUI Interaction Patterns

### Current CLI Architecture
```
User (CLI)
    ↓
emuses.cli.main (Typer)
    ↓
Pipeline Classes (EMUSESPipeline, UMAPStage, etc.)
    ↓
Results (files on disk)
```

### Potential GUI Architecture
```
User (Browser/Desktop App)
    ↓
GUI Framework (Streamlit/Gradio/Custom Web)
    ↓
Option A: Direct Pipeline Calls
    └→ emuses.pipelines.* (same as CLI)

Option B: REST API Layer
    └→ FastAPI Service
        └→ emuses.pipelines.*

Option C: Hybrid
    ├→ Direct calls for simple operations
    └→ API for multi-user/remote scenarios
```

---

## GUI Implementation Options Analysis

### Option 1: Streamlit Revival
**Pros**:
- Rapid development
- Python-native
- Good for data science apps
- Previous implementation exists (archived)

**Cons**:
- Not ideal for production deployment
- Limited customization
- Slower than custom web apps
- Requires Python runtime

**Effort**: 2-3 weeks
**Best For**: Research/academic users, prototyping

---

### Option 2: Gradio Interface
**Pros**:
- Simpler than Streamlit
- Great for ML model interfaces
- Auto-generates API endpoints
- Easy sharing/deployment

**Cons**:
- Less flexible than Streamlit
- Limited for complex workflows
- Mainly for model inference

**Effort**: 1-2 weeks
**Best For**: Inference-focused interface, demos

---

### Option 3: Custom Web App (React/Vue + FastAPI)
**Pros**:
- Full control over UX
- Production-ready
- Fast, responsive
- Mobile-friendly possible
- Integrates with existing FastAPI service

**Cons**:
- Longer development time
- Requires frontend expertise
- More maintenance

**Effort**: 6-8 weeks
**Best For**: Production deployment, multi-user scenarios

---

### Option 4: Jupyter Extension/Widget
**Pros**:
- Integrates into existing workflows
- Interactive notebooks
- Good for exploratory analysis

**Cons**:
- Limited to Jupyter environment
- Not standalone application

**Effort**: 3-4 weeks
**Best For**: Notebook-based researchers

---

## Command Mapping to GUI Components

### High-Priority GUI Features

#### 1. Pipeline Wizard (full command)
**Components**:
- Step 1: Data Selection
  - File browser for input_dataset
  - Optional scores file upload
  - Data format detection
- Step 2: Preprocessing
  - Normalization options (dropdown)
  - File search options (checkboxes)
  - Column/feature mapping (if spreadsheet)
- Step 3: UMAP Configuration
  - Sliders for n_neighbors, min_dist
  - Preview of parameter effects
- Step 4: Clustering
  - HDBSCAN parameter inputs
  - Preview cluster estimates
- Step 5: Prediction (optional)
  - Model type selection
  - Optuna optimization toggle
- Step 6: Execution
  - Progress bar with stage indicators
  - Log output (collapsible)
- Step 7: Results
  - Visualization gallery
  - Download options
  - Rerun with modifications

---

#### 2. Inference Interface (inference command)
**Components**:
- Model Selection Panel
  - Tab 1: Local Models (file browser)
  - Tab 2: Registry Models (searchable list)
  - Model card display (metadata, performance)
- Data Input Panel
  - File upload/selection
  - Data format preview
  - Preprocessing options
- Configuration Panel
  - Validation mode toggle
  - Output format selection
  - Verify integrity checkbox
- Execution & Results
  - Run inference button
  - Real-time progress
  - Results table/visualization
  - Download predictions

---

#### 3. Model Browser (models commands)
**Components**:
- Search & Filter Bar
  - Text search
  - Filter by: type, date, performance, tags
- Model Grid/List View
  - Thumbnail/icon
  - Model name, description
  - Key metrics
  - Actions: view, download, cite
- Model Detail View
  - Full metadata
  - Provenance graph
  - Performance metrics
  - Citation generator
  - Download options
  - Verification status
- Model Actions
  - Run inference
  - View results
  - Export provenance
  - Generate citation

---

#### 4. Results Visualization (heatmap + general)
**Components**:
- Visualization Gallery
  - Heatmaps (interactive)
  - Embedding plots (3D/2D)
  - Cluster visualizations
  - Performance metrics
- Interactive Controls
  - Zoom, pan, rotate
  - Color scheme selection
  - Threshold sliders
  - Export options (PNG, SVG, PDF)
- Comparison View
  - Side-by-side comparisons
  - Difference maps
  - Statistical overlays

---

## Technical Implementation Considerations

### Backend Integration

#### Current CLI Async Pattern
```python
@app.command()
def full(...):
    save_command_to_output_folder(output_folder)
    asyncio.run(_full_async(...))
```

#### GUI Backend Pattern
```python
# For Streamlit/Gradio
def gui_run_full(params):
    # Convert GUI params to CLI args
    args = convert_gui_to_args(params)
    # Run in thread to avoid blocking
    result = run_in_executor(asyncio.run, _full_async(**args))
    return result

# For FastAPI-backed GUI
@app.post("/api/pipeline/full")
async def api_run_full(config: PipelineConfig):
    job_id = create_job()
    background_tasks.add_task(run_pipeline, job_id, config)
    return {"job_id": job_id, "status": "queued"}
```

---

### Progress Tracking

**CLI Uses**: Rich progress bars, StatusRenderer
**GUI Needs**: WebSocket or SSE for real-time updates

```python
# Pattern for GUI progress
class GUIProgressTracker:
    def __init__(self, websocket_or_queue):
        self.output = websocket_or_queue

    def update(self, stage, progress, message):
        self.output.send({
            "stage": stage,
            "progress": progress,
            "message": message
        })
```

---

### File Management

**CLI**: Direct file system access
**GUI Challenges**:
- File upload size limits
- Temporary storage
- Cloud storage integration
- Permission management

**Solutions**:
- Chunked uploads for large files
- Background processing
- S3/Azure integration (already in codebase)
- User workspace isolation

---

## Integration with Existing Infrastructure

### Multi-User Service Integration
**Current Status**: FastAPI service exists
**Endpoint**: `emuses/foundation_fastapi_service/app.py`

**GUI Could Leverage**:
- `/api/models/*` - Model registry endpoints
- `/api/pipeline/*` - Pipeline execution (if added)
- `/auth/*` - Authentication
- `/workspaces/*` - Multi-user workspaces

**Benefits**:
- Shared authentication
- Centralized model registry
- Job queue management
- Resource allocation

---

### Model Registry Integration
**Current Status**: Production-ready, comprehensive
**Location**: `emuses/tools/model_registry/`

**GUI Integration Points**:
```python
from emuses.tools.model_registry import ModelRegistry

# In GUI backend
registry = ModelRegistry(registry_dir)
models = registry.list_models(filter_installed=True)
model_info = registry.get_model_info(model_id)
registry.install_model(model_path, model_id)
```

**GUI Features Enabled**:
- Browse installed models
- Search/filter models
- View model metadata
- Install from registry
- Verify integrity
- Generate citations

---

## User Workflows to Support

### Workflow 1: First-Time Researcher
**Goal**: Run first analysis with minimal configuration

**GUI Flow**:
1. Welcome screen with quick start button
2. Load sample data OR upload own data
3. Click "Run Default Analysis"
4. Watch progress
5. Explore results with guided tour
6. Export results
7. Learn about customization

**Required Commands**: `full` (with sane defaults)

---

### Workflow 2: Iterative Parameter Tuning
**Goal**: Find optimal UMAP/clustering parameters

**GUI Flow**:
1. Load previous results or data
2. Adjust parameters with sliders
3. See parameter effect preview
4. Run analysis (fast if possible)
5. Compare results side-by-side
6. Save best configuration

**Required Commands**: `umap`, `full` (with parameter grid)

---

### Workflow 3: Model Application
**Goal**: Use trained model on new data

**GUI Flow**:
1. Browse model registry
2. Select model (view metadata)
3. Upload new data
4. Configure preprocessing to match training
5. Run inference
6. View predictions
7. Download results

**Required Commands**: `inference`, `models list`, `models info`

---

### Workflow 4: Multi-User Collaboration
**Goal**: Share models and results across team

**GUI Flow**:
1. Login to workspace
2. Browse shared models
3. Run analysis with shared model
4. Save results to workspace
5. Share results with team
6. Comment/annotate results

**Required**: Multi-user service integration, authentication

---

## Data from Planning Documents

### Documentation Restructuring Plans
**Finding**: Focus on improving written docs, not GUI
**Relevance**: Good documentation will help GUI design
- USER_GUIDE.md (15,000 words) - Maps to GUI features
- CLI_REFERENCE.md (10,000 words) - Parameter reference
- API_REFERENCE.md (8,000 words) - Backend integration guide

### Model Registry Integration
**Finding**: Comprehensive model management system
**Relevance**: Core feature for GUI
- Database-backed registry
- Cloud storage support
- Verification and provenance
- Citation generation

### Multi-User Service
**Finding**: REST API for multi-user scenarios
**Relevance**: Backend for collaborative GUI
- Authentication (FastAPI-users)
- Workspaces
- Job queuing
- Resource management

### Observability Integration
**Finding**: Prometheus metrics, structured logging
**Relevance**: GUI monitoring/debugging
- Performance metrics for GUI
- Usage analytics
- Error tracking

---

## Recommended GUI Implementation Approach

### Phase 1: Prototype (2-3 weeks)
**Goal**: Validate GUI concept with researchers

**Technology**: Streamlit (rapid prototyping)
**Features**:
- Pipeline wizard (full command)
- Basic inference interface
- Results visualization

**Success Criteria**:
- 5-10 users test and provide feedback
- Identify critical missing features
- Validate workflow assumptions

---

### Phase 2: Production MVP (6-8 weeks)
**Goal**: Production-ready GUI for single-user scenarios

**Technology**: React + FastAPI OR Gradio Pro
**Features**:
- Complete pipeline wizard
- Inference interface with model browser
- Results gallery with interactive viz
- Model registry browser
- File management
- Configuration presets

**Success Criteria**:
- Can replace CLI for common workflows
- Performance acceptable for large datasets
- Deployable on researcher workstations

---

### Phase 3: Multi-User (4-6 weeks additional)
**Goal**: Collaborative platform

**Technology**: Extend Phase 2 with multi-user backend
**Features**:
- Authentication and workspaces
- Shared models and results
- Job queue with priorities
- Resource management
- Commenting/annotations

**Success Criteria**:
- Lab groups can collaborate
- Scales to 10-50 concurrent users
- Admin controls for resources

---

## Gap Analysis

### What's Missing for GUI

#### Technical Gaps:
1. **Job Queue System** - Long-running analyses need background processing
2. **WebSocket/SSE Support** - Real-time progress updates
3. **File Upload Management** - Handle large neuroimaging files
4. **Result Caching** - Avoid re-computation for parameter tweaks
5. **API Endpoints** - REST API for all CLI commands (partially exists)

#### User Experience Gaps:
1. **Parameter Presets** - Common configurations for different use cases
2. **Data Validation** - Check data format before running
3. **Interactive Previews** - Show parameter effects before full run
4. **Result Comparison** - Side-by-side analysis comparisons
5. **Export Flexibility** - Multiple format options, publication-ready

#### Documentation Gaps:
1. **GUI Design Guide** - User interaction patterns
2. **API Documentation** - Complete REST API reference for GUI builders
3. **Deployment Guide** - How to deploy GUI in different scenarios
4. **User Personas** - Detailed user needs for different researcher types

---

## Conclusion & Recommendations

### Key Findings:
1. ✅ **Strong CLI Foundation** - Well-structured, async-ready
2. ✅ **Legacy GUI Exists** - Streamlit implementation (archived)
3. ✅ **Backend Ready** - FastAPI service, model registry, storage
4. ❌ **No Active GUI Plans** - Not in current roadmap
5. ⚠️ **Some Gaps** - Job queue, real-time updates needed

### Recommended Next Steps:

#### Short Term (1-2 weeks):
1. **Restore Streamlit GUI** - Update for current CLI
2. **User Research** - Interview 5-10 target users
3. **Feature Prioritization** - Which commands need GUI most?

#### Medium Term (1-2 months):
1. **MVP Development** - Focus on inference + model browser
2. **FastAPI Endpoints** - Complete REST API for GUI
3. **Alpha Testing** - Deploy to small user group

#### Long Term (3-6 months):
1. **Production GUI** - React/Vue if justified by usage
2. **Multi-User Features** - If collaboration demand exists
3. **Advanced Features** - Interactive parameter tuning, comparison tools

### Priority Ranking:
1. **HIGHEST**: Inference interface + Model browser (immediate value)
2. **HIGH**: Pipeline wizard for full command (main workflow)
3. **MEDIUM**: Results visualization gallery
4. **LOW**: Advanced parameter tuning (experts can use CLI)

---

**Analysis Complete**: 2025-10-08
**Analyst**: Claude Code
**Document**: `/tmp/emuses_gui_analysis.md`
