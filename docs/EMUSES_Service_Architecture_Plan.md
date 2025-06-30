# EMUSES Service-Oriented Architecture Refactoring Plan

## Executive Summary

This document outlines a comprehensive plan to refactor EMUSES toward a service-oriented FastAPI architecture while maintaining backward compatibility and supporting three distinct user personas:

1. **Novice users** → GUI (Streamlit web interface)
2. **CLI users** → Enhanced command-line interface (Typer)  
3. **Developer users** → Programmatic API (FastAPI endpoints + Python SDK)

The plan follows an incremental approach that preserves existing functionality while gradually introducing new interface layers.

---

## 1. Current Architecture Analysis

### 1.1 Existing Core Components

Based on the current EMUSES codebase:

- **`EMUSESPipeline`** - Main orchestrator in `emuses/pipelines/emuses_pipeline.py`
- **`UMAPStage`** - UMAP embedding + HDBSCAN clustering with joint Optuna optimization in `emuses/pipelines/umap_stage.py`
- **`HeatmapStage`** - Multi-target prediction model optimization using nested cross-validation across multiple ML algorithms (kernel regression, random forest, elastic net) and feature engineering approaches (raw features, Gaussian width density, PCA variants) in `emuses/pipelines/heatmap_stage.py`
- **`PredictionStage`** - Inference stage (currently under rework) for both unlabeled data prediction and test set performance evaluation
- **`main.py`** - Current CLI interface in `emuses/scripts/main.py`

### 1.2 Current Data Flow and Outputs (Dry Run Analysis)

**Actual Pipeline Execution:**

```
CLI args → EMUSESPipeline.init() → Context Setup → Sequential Stage Execution
    ↓
Stage 0: Data Loading & Splitting
    • Input: features.csv, scores.csv
    • Output: train/test splits → context[embedding_train_features, prediction_train_labels, etc.]
    • Files: split_dataset/*.npy, random_seeds.json
    ↓
Stage 1: UMAPStage.run()
    • Input: context[embedding_train_features] 
    • Processing: Nested Optuna optimization (UMAP+HDBSCAN), embedding generation, rescaling
    • Output: context[embedding_train_coords, prediction_train_coords, clustering, models]
    • Files: best_umap_model.joblib, embeddings.npy, cluster_labels.npy
    ↓  
Stage 2: HeatmapStage.run()
    • Input: context[prediction_train_coords, prediction_train_labels]
    • Processing: Multi-target nested CV, model selection across feature types, performance tracking
    • Output: context[prediction_results] with CV scores per target
    • Files: target_*/optuna_*.db, performance_summary/*.csv, best_ae_model.joblib
    ↓
Stage 3: PredictionStage.run()  
    • Input: context[prediction_train_coords, prediction_test_coords, labels]
    • Processing: Feature engineering (GWD), final test evaluation
    • Output: Final test performance metrics
    • Files: prediction_models/*, prediction_performance.csv
```

**Key Finding**: The pipeline produces usable results at **multiple stages**, not just at the end:
1. **UMAPStage** produces 2D embeddings and clustering models
2. **HeatmapStage** produces comprehensive model performance evaluation via nested CV
3. **PredictionStage** adds final test set evaluation with additional feature engineering

**Current Optimization in HeatmapStage:**
The HeatmapStage performs sophisticated hyperparameter optimization using nested cross-validation with Optuna. For each target variable, it explores:

- **Model types**: Kernel regression, Random Forest, Elastic Net/Logistic regression, SVM
- **Feature engineering**: Raw coordinates, polynomial features, autoencoder features, combinations
- **Hyperparameters**: Kernel sigmas, regularization parameters, ensemble settings
- **Preprocessing**: Optional autoencoder pretraining for feature extraction

The optimization uses `nested_optuna_cv()` with parallel processing across targets via joblib. Each target gets its own Optuna study, generating comprehensive performance reports and model artifacts.

### 1.3 Key Observations and Current State

**Pipeline Architecture Strengths:**
- ✅ **Stage-based design with context passing works well** 
- ✅ **Heavy computation properly modularized** - Optuna optimization, parallel processing via joblib
- ✅ **Rich configuration system** - Search spaces defined in config files, proper random seed management
- ✅ **Comprehensive performance tracking** - Multiple CSV outputs with detailed metrics per target
- ✅ **Multiple output artifacts** - Each stage generates usable models, reports, and visualizations

**Missing/Incomplete Components (discovered via dry run):**
- ❌ **Effect size maps not generated** - Old visualization code commented out
- ❌ **Heatmap visualizations not produced** - Statistical mapping disabled  
- ⚠️ **ModelIOManager only partially implemented** - Inconsistent usage across stages
- ⚠️ **PredictionStage somewhat redundant** - Duplicates model selection already done in HeatmapStage
- ❌ **No service/API layer** - Only CLI interface available
- ❌ **No inference-only mode** - Must retrain models for new predictions
- ⚠️ **Prediction/inference stage needs clarification** - Current split between HeatmapStage and PredictionStage unclear

---

## 2. Target Architecture

### 2.1 Layer Overview

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Streamlit     │  │      Typer      │  │   FastAPI       │
│   (GUI)         │  │      (CLI)      │  │   (Web API)     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                    ┌─────────────────┐
                    │   EMUSES Core   │
                    │   Service API   │
                    └─────────────────┘
                               │
                    ┌─────────────────┐
                    │   Pipeline      │
                    │   Engine        │
                    └─────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │ UMAPStage   │  │HeatmapStage │  │PredictStage │
     └─────────────┘  └─────────────┘  └─────────────┘
```

### 2.2 Core Principles and Implementation Strategy

**Design Philosophy:**
1. **Pure core, thin interfaces** - All ML logic stays in current pipeline stages
2. **Stateless API layer** - FastAPI endpoints are pure functions over data  
3. **Shared data models** - Pydantic models for consistent data validation across interfaces
4. **Backward compatibility** - Current CLI and Python imports continue working unchanged
5. **Progressive enhancement** - Add capabilities without breaking existing workflows
6. **LAD-compatible** - Every feature addition should be a minimal, testable increment

**Implementation Approach (Following LAD Principles):**
- **One feature per branch** - Each increment gets its own git branch
- **Always keep pipeline runnable** - Never break the main `python main.py` functionality  
- **Minimal viable increments** - Start with basic endpoints, add complexity gradually
- **Test-driven additions** - Ensure new interfaces produce identical results to existing pipeline
- **Documentation-driven** - Update architecture plan as implementation proceeds

**Key Insight from Dry Run Analysis:**
The EMUSES pipeline already produces comprehensive, scientifically-valid results. The refactoring is primarily about **adding clean service interfaces** rather than rewriting core algorithms. This significantly reduces implementation risk and complexity.

### 2.3 Implementation Strategy

Following LAD principles, we implement the **smallest meaningful features** that each bring a new usable capability:

**Feature Hierarchy (Minimal Increments):**

**Tier 1: Foundation (Core service interfaces)**
- **Feature 1.1**: Basic FastAPI wrapper around UMAPStage  
- **Feature 1.2**: Add Pydantic models for UMAP request/response
- **Feature 1.3**: Background task support for long UMAP operations
- **Feature 1.4**: Enhanced Typer CLI (replace argparse with identical functionality)

**Tier 2: Missing Core Features (Restore existing capabilities)**  
- **Feature 2.1**: Restore heatmap visualizations (effect size maps, statistical maps)
- **Feature 2.2**: Complete ModelIOManager implementation for consistent model persistence
- **Feature 2.3**: Clarify PredictionStage role (inference vs evaluation split)

**Tier 3: Extended API Coverage**
- **Feature 3.1**: HeatmapStage FastAPI endpoints with progress tracking
- **Feature 3.2**: PredictionStage/InferenceStage FastAPI endpoints  
- **Feature 3.3**: Model loading and inference-only endpoints

**Tier 4: User Interfaces**
- **Feature 4.1**: Basic Streamlit interface for pipeline visualization
- **Feature 4.2**: Extended Streamlit interface for parameter tuning
- **Feature 4.3**: Model management and deployment features

**Implementation Questions for Future Developers:**

1. **Prediction vs Inference Stage Design:**
   - Should we keep PredictionStage as final test evaluation only?
   - Should we create a separate InferenceStage for new data prediction?
   - Or merge into a single stage with modes (evaluation vs inference)?

2. **Model Persistence Strategy:**
   - Complete ModelIOManager integration across all stages?
   - Standardize model artifact naming and metadata?
   - Add model versioning and experiment tracking?

3. **Feature Engineering Pipeline:**
   - Should GWD feature engineering be its own stage?
   - How to handle the autoencoder pretraining workflow?
   - Should feature engineering be configurable per endpoint?

4. **API Design Decisions:**
   - Synchronous vs asynchronous endpoints for long operations?
   - How to handle partial results and progress updates?
   - File upload vs direct data passing for large datasets?

---

## 3. Incremental Implementation Plan (LAD Approach)

> **📋 Implementation Reference**: See [LAD Implementation Guide](./LAD_Implementation_Guide.md) for detailed step-by-step instructions, feature descriptions, and context files for each LAD session.

### Foundation Principles
- **Always keep main pipeline functional** - `python main.py full` should always work
- **Each branch adds one working feature** - No half-implemented functionality
- **Backward compatibility maintained** - Existing scripts and notebooks continue working  
- **Test-driven development** - Verify new interfaces produce identical computational results

### Phase 0: Foundation Layer (1-2 weeks)

**Goal**: Add FastAPI layer that calls existing stages without changing core logic

> **📋 LAD Session 1**: See [LAD Implementation Guide - Session 1](./LAD_Implementation_Guide.md#lad-session-1-foundation-fastapi-service) for complete implementation details, context files, and feature description.

#### 3.1 Feature 1.1: Basic FastAPI-UMAPStage Integration

**Objective**: Create minimal FastAPI endpoint that calls `UMAPStage` directly

**Implementation approach**:
- **Keep `UMAPStage.run()` unchanged** - Call existing stage methods
- **Create thin service wrapper** - Handle request/response conversion only
- **Use existing context pattern** - FastAPI populates context like current CLI does

**Key questions for implementer**:
1. Should FastAPI service instantiate `UMAPStage` per request or reuse instances?
2. How to handle the `output_folder` parameter in API context vs file-based workflows?
3. Should we expose all UMAPStage parameters immediately or start with essential subset?

**Success criteria**: 
- Single `/umap/fit` endpoint that produces identical results to current CLI
- Full backward compatibility maintained
- ~90% code reuse from existing `UMAPStage`

#### 3.2 Feature 1.2: UMAP Request/Response Models

**Objective**: Add type-safe Pydantic models for UMAP operations

**Required models**:
```python
# Reference: emuses/pipelines/umap_stage.py UMAPStage.run()
class UMAPRequest(BaseModel):
    features: List[List[float]]  # Input feature matrix
    n_components: int = 2
    n_neighbors: int = 15
    min_dist: float = 0.1
    # ... other params from UMAPStage
    
class UMAPResponse(BaseModel):
    embeddings: List[List[float]]  # From context["embedding_train_coords"]
    cluster_labels: Optional[List[int]]  # From context["embedding_train_cluster_labels"] 
    model_path: str  # Path to saved UMAP model
    # ... other outputs from UMAPStage context
```

**Implementation notes**:
- Models should match exact outputs from `UMAPStage.run()` context updates
- See `emuses/pipelines/umap_stage.py` lines 230-251 for complete context outputs
- Handle numpy ↔ JSON serialization properly

#### 3.3 Feature 1.3: Background Task Infrastructure

**Objective**: Support long-running operations (Optuna optimization can take minutes/hours)

**Technical requirements**:
- Task queue system (Redis + Celery recommended for production)
- Progress tracking during Optuna trials
- Task cancellation support
- Result persistence and retrieval

**Key integration points**:
- Instrument `nested_optuna_cv()` in `emuses/tools/optuna_cv.py` for progress callbacks
- Handle joblib parallel processing with background tasks
- Maintain existing parallel processing capabilities (`--hdbscan_jobs`, etc.)

### Phase 1: Restore Missing Pipeline Features (1-2 weeks)

#### 3.4 Feature 2.1: Heatmap Visualizations

**Objective**: Restore heatmap generation that was removed during optimization focus

**Reference implementation**: 
- `emuses/tools/correlation_maps_utils.py` `run_heatmap_analysis()` (older version)
- Current `HeatmapStage` focuses on model optimization, missing actual heatmap plots

**Requirements**:
- Generate prediction heatmaps over embedding space
- Integrate with current `HeatmapStage` optimization results
- Support multiple targets (multi-column heatmaps)

#### 3.5 Feature 2.2: Effect Size Maps

**Objective**: Re-implement effect size calculations removed in pipeline evolution

**Reference functions**:
- `emuses/tools/stats_utils.py` `process_column()` and `input_matrix_stat_map()`
- These provide statistical analysis of feature importance

**Integration approach**:
- Add as optional stage or extend existing `HeatmapStage`
- Use results from optimized models to compute effect sizes
- Generate both statistical maps and visualization outputs

### Phase 2: PredictionStage Redesign (2-3 weeks)

#### 3.6 Feature 3.1: Inference vs Evaluation Modes

**Current issue**: `PredictionStage` needs rework to handle two distinct use cases

**Mode 1: Pure Inference**
- Input: Unlabeled data + trained models
- Output: Predictions only
- Use case: Production inference on new data

**Mode 2: Test Set Evaluation** 
- Input: Labeled test data + trained models  
- Output: Predictions + performance metrics + comparison reports
- Use case: Model validation and performance assessment

**Implementation decision needed**:
Should this be:
1. **Single stage with mode parameter**: `PredictionStage(mode="inference"|"evaluation")`
2. **Two separate stages**: `InferenceStage` + `EvaluationStage`

**Your preference?** This affects the FastAPI endpoint design significantly.

### Phase 3: API Completion (1-2 weeks)

#### 3.7 Feature 3.2: HeatmapStage API Integration

**Objective**: Add FastAPI endpoints for model training and optimization

**Complexity considerations**:
- `HeatmapStage` is the most complex stage (nested CV, multiple targets, parallel processing)
- Long-running operations (hours for full optimization)
- Multiple output artifacts per run

**API design questions**:
1. Should we expose per-target optimization as separate endpoints?
2. How to handle the extensive configuration from `emuses/config/optim_configs_predict.py`?
3. Should optimization progress be streamed or polled?

#### 3.8 Feature 3.3: Enhanced CLI with Typer

**Objective**: Replace argparse with Typer while maintaining exact functionality

**Timing**: **After** API is stable to avoid parallel interface changes
**Approach**: Direct parameter mapping from current `main.py` argparse to Typer
**Risk**: Lower priority to avoid disrupting working CLI during API development

### Phase 4: GUI Development (Deferred)

**Rationale**: Implement Streamlit GUI **only after** FastAPI is fully functional and stable

This ensures the GUI has a complete, tested API to integrate with rather than building against a moving target.

---

### Phase 1: Enhanced CLI with Typer (1 week)

**Goal**: Replace argparse with Typer while maintaining exact same functionality

#### 3.4 Typer CLI Implementation

```python
# emuses/cli/main.py
import typer
from typing import Optional
from pathlib import Path
from emuses.services.emuses_service import EMUSESService
from emuses.api.models import UMAPRequest, HeatmapRequest

app = typer.Typer(
    name="emuses",
    help="EMUSES: Embedding-based Multi-dimensional Unified Scalable Ensemble Scoring",
    add_completion=False
)

@app.command("run")
def run_pipeline(
    input_path: Path = typer.Argument(..., help="Path to input data"),
    label_dataset: Optional[Path] = typer.Option(None, help="Path to labeled dataset"),
    output_folder: Path = typer.Option("./results", help="Output directory"),
    task: str = typer.Option("regression", help="Task type: regression or classification"),
    n_components: int = typer.Option(2, help="UMAP number of components"),
    n_neighbors: int = typer.Option(15, help="UMAP number of neighbors"),
    optim_trials: int = typer.Option(50, help="Optuna optimization trials"),
    use_ae_pretrain: bool = typer.Option(False, help="Enable autoencoder pretraining"),
    random_state: int = typer.Option(42, help="Random seed for reproducibility"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """Run the complete EMUSES pipeline."""
    
    # Set up logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Initialize service
    service = EMUSESService(str(output_folder))
    
    # Load and validate data
    typer.echo(f"Loading data from {input_path}")
    # ... data loading logic
    
    # Run UMAP stage
    typer.echo("Running UMAP embedding...")
    umap_request = UMAPRequest(
        features=features.tolist(),
        n_components=n_components,
        n_neighbors=n_neighbors,
        random_state=random_state
    )
    umap_result = service.run_umap(umap_request)
    typer.echo(f"✓ UMAP completed in {umap_result.processing_time_ms:.1f}ms")
    
    # Run Heatmap stage
    typer.echo("Running heatmap optimization...")
    heatmap_request = HeatmapRequest(
        embeddings=umap_result.embeddings,
        labels=labels.tolist(),
        task=task,
        optim_trials=optim_trials,
        use_ae_pretrain=use_ae_pretrain,
        random_state=random_state
    )
    heatmap_result = service.run_heatmap(heatmap_request)
    typer.echo(f"✓ Heatmap optimization completed in {heatmap_result.processing_time_ms:.1f}ms")
    
    # Display results
    typer.echo("\n📊 Results Summary:")
    for target, scores in heatmap_result.cv_scores.items():
        mean_score = np.mean(scores)
        typer.echo(f"  {target}: {mean_score:.4f} ± {np.std(scores):.4f}")

@app.command("predict")
def predict(
    model_path: Path = typer.Argument(..., help="Path to trained model"),
    data_path: Path = typer.Argument(..., help="Path to prediction data"),
    output_path: Optional[Path] = typer.Option(None, help="Output predictions path")
):
    """Make predictions using trained EMUSES model."""
    # Implementation for prediction workflow

if __name__ == "__main__":
    app()
```

**Tasks**:
- [ ] Implement complete Typer CLI with all current argparse options
- [ ] Add shell completion support
- [ ] Maintain backward compatibility - old CLI should still work
- [ ] Add progress bars for long operations using `rich` integration
- [ ] Comprehensive testing to ensure identical behavior

---

### Phase 2: FastAPI Web Layer (2 weeks)

**Goal**: Add REST API endpoints that expose EMUSES functionality

#### 3.5 FastAPI Application

```python
# emuses/api/app.py
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uuid
from typing import Dict
import time

from emuses.api.models import UMAPRequest, UMAPResponse, HeatmapRequest, HeatmapResponse
from emuses.services.emuses_service import EMUSESService

app = FastAPI(
    title="EMUSES API",
    description="Embedding-based Multi-dimensional Unified Scalable Ensemble Scoring",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for GUI integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task tracking (use Redis in production)
tasks: Dict[str, Dict] = {}

@app.post("/umap/fit", response_model=UMAPResponse)
async def fit_umap(request: UMAPRequest):
    """Fit UMAP embedding model."""
    service = EMUSESService("/tmp/emuses_models")  # Configure as needed
    
    try:
        result = service.run_umap(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/heatmap/optimize", response_model=Dict[str, str])
async def optimize_heatmap(request: HeatmapRequest, background_tasks: BackgroundTasks):
    """Start heatmap optimization (long-running task)."""
    task_id = str(uuid.uuid4())
    
    # Store task info
    tasks[task_id] = {
        "status": "started",
        "progress": 0,
        "result": None,
        "error": None,
        "started_at": time.time()
    }
    
    # Add background task
    background_tasks.add_task(run_heatmap_background, task_id, request)
    
    return {"task_id": task_id, "status": "started"}

async def run_heatmap_background(task_id: str, request: HeatmapRequest):
    """Run heatmap optimization in background."""
    try:
        service = EMUSESService("/tmp/emuses_models")
        
        # Update progress periodically (implement progress tracking in service)
        tasks[task_id]["status"] = "running"
        tasks[task_id]["progress"] = 10
        
        # Run the actual optimization
        result = service.run_heatmap(request)
        
        # Store result
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["result"] = result.dict()
        
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of background task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return tasks[task_id]

@app.post("/data/upload")
async def upload_data(file: UploadFile = File(...)):
    """Upload and validate data file."""
    # Implementation for data upload and validation
    pass

@app.get("/models/{model_id}/download")
async def download_model(model_id: str):
    """Download trained model."""
    # Implementation for model download
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Tasks**:
- [ ] Implement core API endpoints for all pipeline stages
- [ ] Add file upload/download capabilities
- [ ] Implement proper background task management (consider Celery for production)
- [ ] Add authentication and rate limiting
- [ ] Comprehensive API documentation with examples
- [ ] Add health checks and monitoring endpoints

#### 3.6 Async and Progress Tracking

Since EMUSES operations can be long-running (Optuna optimization, large datasets), implement proper async handling:

```python
# emuses/services/async_service.py
import asyncio
from typing import Callable, Any
from dataclasses import dataclass

@dataclass
class ProgressUpdate:
    task_id: str
    stage: str
    progress: float  # 0.0 to 1.0
    message: str
    estimated_remaining_seconds: Optional[float] = None

class AsyncEMUSESService:
    """Async wrapper around EMUSESService with progress tracking."""
    
    async def run_heatmap_async(
        self, 
        request: HeatmapRequest,
        progress_callback: Callable[[ProgressUpdate], None] = None
    ) -> HeatmapResponse:
        """Run heatmap optimization with progress updates."""
        
        loop = asyncio.get_event_loop()
        
        # Wrap the synchronous service call
        def run_with_progress():
            # Implementation that calls progress_callback during optimization
            # This requires instrumenting the Optuna optimization loop
            pass
        
        result = await loop.run_in_executor(None, run_with_progress)
        return result
```

---

### Phase 3: Streamlit GUI (1 week)

**Goal**: Create intuitive web interface for novice users

#### 3.7 Streamlit Application

```python
# emuses/gui/app.py
import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import time
from pathlib import Path

# Configure page
st.set_page_config(
    page_title="EMUSES",
    page_icon="🔬",
    layout="wide"
)

# Session state initialization
if 'api_base_url' not in st.session_state:
    st.session_state.api_base_url = "http://localhost:8000"

def main():
    st.title("🔬 EMUSES: Embedding-based ML Analysis")
    st.markdown("*Unified platform for embedding, clustering, and prediction*")
    
    # Sidebar for navigation
    page = st.sidebar.selectbox(
        "Choose a workflow",
        ["🏠 Home", "📤 Upload Data", "🗺️ Generate Embeddings", "🎯 Train Predictors", "📊 Explore Results"]
    )
    
    if page == "🏠 Home":
        show_home_page()
    elif page == "📤 Upload Data":
        show_upload_page()
    elif page == "🗺️ Generate Embeddings":
        show_embedding_page()
    elif page == "🎯 Train Predictors":
        show_training_page()
    elif page == "📊 Explore Results":
        show_results_page()

def show_home_page():
    st.markdown("""
    ## Welcome to EMUSES
    
    EMUSES provides a complete pipeline for:
    - **Dimensionality reduction** using UMAP
    - **Clustering** with HDBSCAN
    - **Predictive modeling** with kernel regression
    - **Hyperparameter optimization** with Optuna
    
    ### Quick Start
    1. **Upload your data** using the Upload Data page
    2. **Generate embeddings** to visualize your data in 2D/3D
    3. **Train predictors** to build models on your embedded space
    4. **Explore results** with interactive visualizations
    """)

def show_upload_page():
    st.header("📤 Upload Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Feature Data")
        feature_file = st.file_uploader(
            "Upload feature matrix (CSV, NPY)",
            type=['csv', 'npy'],
            key="features"
        )
        
        if feature_file:
            if feature_file.name.endswith('.csv'):
                df = pd.read_csv(feature_file)
                st.write(f"Shape: {df.shape}")
                st.dataframe(df.head())
                features = df.values
            else:
                features = np.load(feature_file)
                st.write(f"Shape: {features.shape}")
                st.write(features[:5, :5])
            
            st.session_state.features = features
    
    with col2:
        st.subheader("Labels/Targets")
        label_file = st.file_uploader(
            "Upload target values (CSV, NPY)",
            type=['csv', 'npy'],
            key="labels"
        )
        
        if label_file:
            if label_file.name.endswith('.csv'):
                df = pd.read_csv(label_file)
                st.write(f"Shape: {df.shape}")
                st.dataframe(df.head())
                labels = df.values.flatten()
            else:
                labels = np.load(label_file)
                st.write(f"Shape: {labels.shape}")
                st.write(labels[:10])
            
            st.session_state.labels = labels
    
    # Data validation
    if 'features' in st.session_state and 'labels' in st.session_state:
        if len(st.session_state.features) == len(st.session_state.labels):
            st.success(f"✓ Data loaded: {len(st.session_state.features)} samples")
        else:
            st.error("❌ Features and labels must have same number of samples")

def show_embedding_page():
    st.header("🗺️ Generate Embeddings")
    
    if 'features' not in st.session_state:
        st.warning("Please upload feature data first")
        return
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("UMAP Parameters")
        n_components = st.slider("Dimensions", 2, 10, 2)
        n_neighbors = st.slider("Neighbors", 5, 100, 15)
        min_dist = st.slider("Min Distance", 0.0, 1.0, 0.1)
        metric = st.selectbox("Distance Metric", 
                             ["euclidean", "manhattan", "cosine", "correlation"])
        
        if st.button("Generate Embeddings", type="primary"):
            with st.spinner("Running UMAP..."):
                # Call FastAPI endpoint
                request_data = {
                    "features": st.session_state.features.tolist(),
                    "n_components": n_components,
                    "n_neighbors": n_neighbors,
                    "min_dist": min_dist,
                    "metric": metric,
                    "random_state": 42
                }
                
                try:
                    response = requests.post(
                        f"{st.session_state.api_base_url}/umap/fit",
                        json=request_data,
                        timeout=300
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.session_state.embeddings = np.array(result["embeddings"])
                        st.session_state.cluster_labels = result.get("cluster_labels")
                        st.success(f"✓ Embeddings generated in {result['processing_time_ms']:.1f}ms")
                    else:
                        st.error(f"API Error: {response.text}")
                        
                except requests.exceptions.RequestException as e:
                    st.error(f"Connection error: {e}")
    
    with col2:
        if 'embeddings' in st.session_state:
            st.subheader("Embedding Visualization")
            
            embeddings = st.session_state.embeddings
            
            if embeddings.shape[1] >= 2:
                # 2D visualization
                fig_data = {
                    'x': embeddings[:, 0],
                    'y': embeddings[:, 1]
                }
                
                # Color by labels if available
                if 'labels' in st.session_state:
                    fig_data['color'] = st.session_state.labels
                    fig = px.scatter(
                        fig_data, x='x', y='y', color='color',
                        title="UMAP Embeddings (colored by target)",
                        labels={'x': 'UMAP 1', 'y': 'UMAP 2'}
                    )
                else:
                    fig = px.scatter(
                        fig_data, x='x', y='y',
                        title="UMAP Embeddings",
                        labels={'x': 'UMAP 1', 'y': 'UMAP 2'}
                    )
                
                st.plotly_chart(fig, use_container_width=True)

def show_training_page():
    st.header("🎯 Train Predictors")
    
    if 'embeddings' not in st.session_state or 'labels' not in st.session_state:
        st.warning("Please generate embeddings and upload labels first")
        return
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Training Parameters")
        task_type = st.selectbox("Task Type", ["regression", "classification"])
        optim_trials = st.slider("Optimization Trials", 10, 200, 50)
        outer_folds = st.slider("Cross-validation Folds", 3, 10, 5)
        use_ae_pretrain = st.checkbox("Use Autoencoder Pretraining")
        
        if st.button("Start Training", type="primary"):
            with st.spinner("Starting optimization..."):
                # Start background task
                request_data = {
                    "embeddings": st.session_state.embeddings.tolist(),
                    "labels": st.session_state.labels.tolist(),
                    "task": task_type,
                    "optim_trials": optim_trials,
                    "outer_folds": outer_folds,
                    "use_ae_pretrain": use_ae_pretrain,
                    "random_state": 42
                }
                
                try:
                    response = requests.post(
                        f"{st.session_state.api_base_url}/heatmap/optimize",
                        json=request_data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.session_state.task_id = result["task_id"]
                        st.success("Training started! Check progress below.")
                    else:
                        st.error(f"API Error: {response.text}")
                        
                except requests.exceptions.RequestException as e:
                    st.error(f"Connection error: {e}")
    
    with col2:
        if 'task_id' in st.session_state:
            st.subheader("Training Progress")
            
            # Progress monitoring
            progress_placeholder = st.empty()
            
            if st.button("Check Progress"):
                try:
                    response = requests.get(
                        f"{st.session_state.api_base_url}/tasks/{st.session_state.task_id}"
                    )
                    
                    if response.status_code == 200:
                        task_info = response.json()
                        status = task_info["status"]
                        progress = task_info.get("progress", 0)
                        
                        with progress_placeholder.container():
                            st.write(f"Status: {status}")
                            st.progress(progress / 100)
                            
                            if status == "completed":
                                result = task_info["result"]
                                st.session_state.training_results = result
                                st.success("Training completed!")
                                
                                # Show performance summary
                                if "performance_summary" in result:
                                    st.write("Performance Summary:")
                                    st.json(result["performance_summary"])
                            elif status == "failed":
                                st.error(f"Training failed: {task_info.get('error', 'Unknown error')}")
                    
                except requests.exceptions.RequestException as e:
                    st.error(f"Connection error: {e}")

def show_results_page():
    st.header("📊 Explore Results")
    
    if 'training_results' not in st.session_state:
        st.warning("Please complete training first")
        return
    
    results = st.session_state.training_results
    
    # Performance visualization
    if "cv_scores" in results:
        st.subheader("Cross-validation Scores")
        
        scores_data = []
        for target, scores in results["cv_scores"].items():
            for fold, score in enumerate(scores):
                scores_data.append({
                    "Target": target,
                    "Fold": fold + 1,
                    "Score": score
                })
        
        df_scores = pd.DataFrame(scores_data)
        
        fig = px.box(df_scores, x="Target", y="Score", 
                     title="Cross-validation Performance by Target")
        st.plotly_chart(fig, use_container_width=True)
        
        # Summary statistics
        summary_stats = df_scores.groupby("Target")["Score"].agg(["mean", "std"]).round(4)
        st.dataframe(summary_stats)

if __name__ == "__main__":
    main()
```

**Tasks**:
- [ ] Implement complete Streamlit interface with all workflow steps
- [ ] Add real-time progress monitoring for long operations
- [ ] Create interactive visualizations with Plotly
- [ ] Add data validation and error handling
- [ ] Implement result download and sharing capabilities

---

### Phase 4: Production Readiness (1-2 weeks)

#### 3.8 Background Task Management

Replace in-memory task tracking with proper queue system:

```python
# emuses/api/tasks.py
from celery import Celery
from emuses.services.emuses_service import EMUSESService
from emuses.api.models import HeatmapRequest, HeatmapResponse

# Configure Celery
celery_app = Celery(
    "emuses",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task(bind=True)
def optimize_heatmap_task(self, request_data: dict):
    """Celery task for heatmap optimization."""
    try:
        request = HeatmapRequest(**request_data)
        service = EMUSESService("/app/models")
        
        # Update progress
        self.update_state(state="PROGRESS", meta={"progress": 10, "stage": "initialization"})
        
        result = service.run_heatmap(request)
        
        return {
            "status": "SUCCESS",
            "result": result.dict()
        }
    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise
```

#### 3.9 Authentication and Security

```python
# emuses/api/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Protected endpoints
@app.post("/heatmap/optimize")
async def optimize_heatmap(
    request: HeatmapRequest, 
    background_tasks: BackgroundTasks,
    current_user: str = Depends(verify_token)
):
    # Implementation with user context
```

#### 3.10 Database and Model Storage

```python
# emuses/api/database.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class TrainingJob(Base):
    __tablename__ = "training_jobs"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(36), unique=True, index=True)
    user_id = Column(String(100), index=True)
    status = Column(String(20), default="pending")
    parameters = Column(JSON)
    results = Column(JSON)
    model_paths = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)

class ModelArtifact(Base):
    __tablename__ = "model_artifacts"
    
    id = Column(Integer, primary_key=True)
    model_id = Column(String(36), unique=True, index=True)
    job_id = Column(Integer, ForeignKey("training_jobs.id"))
    model_type = Column(String(50))  # "umap", "heatmap", "prediction"
    file_path = Column(String(500))
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
```

**Tasks**:
- [ ] Set up Redis/PostgreSQL for production deployment
- [ ] Implement proper authentication and user management
- [ ] Add comprehensive logging and monitoring
- [ ] Create Docker containers for easy deployment
- [ ] Add API rate limiting and resource management

---

## 4. Migration Strategy

### 4.1 Backward Compatibility

During the entire migration:

1. **Current CLI continues working** - Old `main.py` with argparse stays functional
2. **Python imports unchanged** - Existing code using `from emuses.pipelines import EMUSESPipeline` works
3. **Results identical** - All refactoring preserves computational results
4. **Gradual adoption** - Users can adopt new interfaces when ready

### 4.2 Testing Strategy

```python
# tests/test_migration_compatibility.py
import pytest
import numpy as np
from emuses.pipelines.emuses_pipeline import EMUSESPipeline  # Old API
from emuses.services.emuses_service import EMUSESService      # New API

def test_identical_results():
    """Ensure new API produces identical results to old pipeline."""
    
    # Generate test data
    X = np.random.randn(100, 50)
    y = np.random.randn(100)
    
    # Old pipeline
    old_config = create_old_config()
    old_pipeline = EMUSESPipeline(old_config)
    old_results = old_pipeline.run(X, y)
    
    # New service API
    service = EMUSESService("/tmp/test")
    umap_request = UMAPRequest(features=X.tolist())
    heatmap_request = HeatmapRequest(embeddings=..., labels=y.tolist())
    
    new_umap_result = service.run_umap(umap_request)
    new_heatmap_result = service.run_heatmap(heatmap_request)
    
    # Compare results
    np.testing.assert_allclose(old_results.embeddings, new_umap_result.embeddings)
    np.testing.assert_allclose(old_results.cv_scores, new_heatmap_result.cv_scores)
```

### 4.3 Performance Benchmarks

Track performance throughout migration:
- Memory usage
- Processing time for standard datasets
- API response times
- Throughput under concurrent load

---

## 5. Deployment Architecture

### 5.1 Local Development

```yaml
# docker-compose.yml
version: '3.8'
services:
  emuses-api:
    build: ./emuses-api
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:pass@postgres:5432/emuses
    volumes:
      - ./models:/app/models
      - ./data:/app/data
  
  emuses-gui:
    build: ./emuses-gui
    ports:
      - "8501:8501"
    environment:
      - EMUSES_API_URL=http://emuses-api:8000
    depends_on:
      - emuses-api
  
  redis:
    image: redis:6
    ports:
      - "6379:6379"
  
  postgres:
    image: postgres:13
    environment:
      - POSTGRES_DB=emuses
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  celery-worker:
    build: ./emuses-api
    command: celery -A emuses.api.tasks worker --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres
    volumes:
      - ./models:/app/models

volumes:
  postgres_data:
```

### 5.2 Production Deployment

**Options**:
1. **Cloud Functions** - FastAPI on AWS Lambda/Google Cloud Functions for API
2. **Kubernetes** - Full container orchestration for high availability
3. **Cloud Run** - Serverless containers for auto-scaling
4. **Traditional VPS** - Docker Compose on virtual machines

---

## 6. Timeline and Resource Estimates

| Phase | Duration | Key Deliverables | Dependencies |
|-------|----------|------------------|--------------|
| 0: Foundation | 1-2 weeks | Pure functions, Pydantic models, Service layer | None |
| 1: Enhanced CLI | 1 week | Typer CLI with full feature parity | Phase 0 |
| 2: FastAPI Web Layer | 2 weeks | REST API, background tasks, documentation | Phase 0 |
| 3: Streamlit GUI | 1 week | Complete web interface for novices | Phase 2 |
| 4: Production Readiness | 1-2 weeks | Auth, database, deployment | Phase 2-3 |
| **Total** | **6-8 weeks** | Full service-oriented architecture | |

---

## 7. Success Metrics

### 7.1 Functional Metrics
- [ ] 100% backward compatibility maintained
- [ ] All current test cases pass
- [ ] Identical computational results across interfaces

### 7.2 Usability Metrics
- [ ] CLI users: Reduced command complexity, better help
- [ ] GUI users: Complete workflow possible without coding
- [ ] API users: < 1 hour to integrate EMUSES into existing systems

### 7.3 Performance Metrics
- [ ] API response time < 500ms for lightweight operations
- [ ] Background task progress updates every 10 seconds
- [ ] Support for concurrent users (10+ simultaneous training jobs)

### 7.4 Adoption Metrics
- [ ] Documentation with examples for all three interfaces
- [ ] Community feedback positive across all user types
- [ ] Successfully deployed in at least one production environment

---

## 8. Risk Assessment and Mitigation

### 8.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Breaking changes during refactoring | High | Medium | Comprehensive test suite, gradual migration |
| Performance degradation | Medium | Low | Benchmarking, profiling at each stage |
| Dependency conflicts | Medium | Medium | Virtual environments, careful version pinning |
| API design changes | Medium | Medium | Versioned APIs, deprecation notices |

### 8.2 Project Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Scope creep | Medium | High | Clear phase boundaries, incremental delivery |
| Resource constraints | High | Medium | Prioritize backward compatibility, MVP approach |
| User adoption slow | Medium | Medium | Maintain existing interfaces, gradual migration |

---

## 9. Conclusion

This plan provides a comprehensive roadmap for transforming EMUSES into a service-oriented architecture that serves all user types while maintaining scientific integrity and backward compatibility. The incremental approach minimizes risk while delivering value at each stage.

The key insight is that **EMUSES already has solid computational foundations** - this refactoring is primarily about **adding clean interfaces** rather than rewriting core algorithms. By following this plan, EMUSES will become a more accessible, maintainable, and scalable platform for embedding-based machine learning research and applications.

---

*Generated on: January 2025*
*Version: 1.0*
*Status: Planning Phase*
