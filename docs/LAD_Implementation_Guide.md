# EMUSES LAD Implementation Guide

> **Purpose**: Detailed implementation roadmap using the LAD (LLM-Assisted Development) framework for the EMUSES service-oriented architecture refactoring.

This guide provides step-by-step instructions for each LAD session, including specific feature descriptions, context files, and implementation priorities aligned with the [EMUSES Service Architecture Plan](./EMUSES_Service_Architecture_Plan.md).

---

## LAD Session Overview

| Session | Branch Name | Duration | Focus | Merge Target | Dependencies |
|---------|-------------|----------|-------|--------------|--------------|
| 1 | `feat/foundation-fastapi-service` | 1-2 weeks | Core service layer + UMAPStage API | `main` | None |
| 2 | `feat/enhanced-cli-typer` | 1 week | Typer CLI replacement | `main` | Session 1 merged |
| 3 | `feat/fastapi-web-layer` | 2 weeks | Complete REST API | `main` | Session 1 merged |
| 4 | `feat/streamlit-gui` | 1 week | Web interface | `main` | Session 3 merged |
| 5 | `feat/production-readiness` | 1-2 weeks | Auth, database, deployment | `main` | Sessions 3-4 merged |

---

## LAD Session 1: Foundation FastAPI Service

### **Current Implementation Status** 🚀

**Session 1 Progress**: ✅ **Pipeline Runner COMPLETED** - Real EMUSES pipeline execution implemented and validated

**Key Achievements**:
- ✅ **Task 4 (Pipeline Runner)**: Real EMUSES pipeline execution with context setup for prediction keys
- ✅ **CLI vs API Validation**: Integration test confirms API executes identical pipeline to CLI
- ✅ **Production Ready**: All EMUSES stages create expected artifacts (models, embeddings, plots, metrics)
- ✅ **Context Management**: Proper setup of prediction_train_features and prediction_train_labels
- ✅ **Background Execution**: ProcessPoolExecutor with resource limits and timeout handling

**Implementation Details**:
- **PipelineRunner**: `/emuses/foundation_fastapi_service/pipeline_runner.py` - Real stage execution
- **Context Setup**: Fixed prediction context keys to match EMUSESPipeline expectations
- **Integration Tests**: `/tests/integration/test_cli_vs_api_comparison.py` - Validates API/CLI equivalence
- **Unit Tests**: `/tests/foundation-fastapi-service/test_pipeline_runner.py` - Real execution validation

**Next Steps**: Continue with remaining LAD Session 1 tasks (API endpoints, security validation, etc.)

---

### **Feature Draft (for `00_feature_kickoff.md`)**

```markdown
**Feature draft** ⟶ Create a FastAPI service layer that wraps the existing EMUSES pipeline stages (EmbeddingStage for joint UMAP+HDBSCAN optimization, HeatmapStage for multi-target prediction, PredictionStage for inference) without modifying their core logic. The service should provide REST endpoints that accept Pydantic-validated requests containing optimization configurations (not individual parameters), call the existing stage.run() methods with proper context setup, and return structured responses. The EmbeddingStage performs joint UMAP+HDBSCAN optimization using Optuna nested trials and parameter dictionaries from config files. Include background task support for long-running operations like hyperparameter optimization. Must maintain 100% backward compatibility - existing CLI and Python imports continue working unchanged. The service acts as a thin translation layer between HTTP requests and the current pipeline context pattern, reusing 90%+ of existing computational code.
```

### **Context Files to Open Before Starting**

```bash
# Core pipeline files (for understanding existing architecture)
emuses/pipelines/emuses_pipeline.py
emuses/pipelines/umap_stage.py
emuses/pipelines/heatmap_stage.py
emuses/pipelines/prediction_stage.py
emuses/pipelines/pipeline_stage.py
emuses/pipelines/pipeline_config.py

# Configuration and utilities
emuses/config/optim_configs.py        # CRITICAL: Joint UMAP+HDBSCAN optimization configs
emuses/config/optim_configs_predict.py
emuses/tools/optim_utils.py
emuses/tools/model_io.py
emuses/tools/UMAP_utils.py            # Joint optimization implementation

# Current CLI for reference
emuses/scripts/main.py

# Architecture documentation
docs/EMUSES_Service_Architecture_Plan.md
docs/LAD_Implementation_Guide.md
```

### **Key Implementation Requirements**

1. **Service Layer Structure**:
   ```
   emuses/
   ├── services/
   │   ├── __init__.py
   │   ├── emuses_service.py          # Main service coordinator
   │   ├── embedding_service.py       # EmbeddingStage wrapper (joint UMAP+HDBSCAN)
   │   ├── heatmap_service.py         # HeatmapStage wrapper (multi-target optimization)
   │   └── prediction_service.py      # PredictionStage wrapper
   ├── api/
   │   ├── __init__.py
   │   ├── models.py                  # Pydantic request/response models
   │   ├── app.py                     # FastAPI application
   │   └── dependencies.py           # Common API dependencies
   ```

2. **Pydantic Models to Define**:
   ```python
   # Core models based on existing stage inputs/outputs and context pattern
   class EmbeddingStageRequest(BaseModel):
       """Request for joint UMAP+HDBSCAN embedding and clustering optimization."""
       features: List[List[float]]  # Input feature matrix
       test_features: Optional[List[List[float]]] = None  # Optional test data
       optim_config: Dict = None  # Optuna optimization configuration (uses default if None)
       n_trials: int = 50  # Number of UMAP optimization trials  
       hdbscan_trials: int = 20  # Number of HDBSCAN trials per UMAP trial
       random_state: Optional[int] = None
       # Configuration parameters from PipelineConfig
       umap_jobs: Optional[int] = 1
       hdbscan_jobs: Optional[int] = 1
       prefix: str = ""

   class EmbeddingStageResponse(BaseModel):
       """Response from joint UMAP+HDBSCAN optimization with context outputs."""
       # Main outputs (matches context updates from UMAPStage.run())
       train_embeddings: List[List[float]]  # context["embedding_train_coords"]
       test_embeddings: Optional[List[List[float]]] = None  # context["embedding_test_coords"]
       cluster_labels: List[int]  # context["embedding_train_cluster_labels"]
       
       # Model artifacts
       umap_model_path: str  # Path to saved UMAP model
       clusterer_model_path: str  # Path to saved HDBSCAN model
       
       # Scaling information for new data transformation
       min_coords: List[float]  # context["embedding_train_min_coords"]
       max_coords: List[float]  # context["embedding_train_max_coords"]
       
       # Processing metadata
       processing_time_ms: float
       optimization_history: Optional[Dict] = None  # Optuna study results

   class HeatmapStageRequest(BaseModel):
       """Request for multi-target prediction model optimization."""
       embeddings: List[List[float]]  # From EmbeddingStage output
       labels: Union[List[float], List[List[float]]]  # Single or multi-target
       task: str = "regression"  # "regression" or "classification"
       
       # Optimization configuration
       optim_config: Dict = None  # From emuses/config/optim_configs_predict.py
       outer_folds: int = 5  # Cross-validation folds
       optim_trials: int = 60  # Optuna trials per fold
       
       # Feature engineering options
       use_ae_pretrain: bool = False
       feature_types: List[str] = ["raw"]  # e.g., ["raw", "polynomial", "autoencoder"]
       
       random_state: Optional[int] = None

   class HeatmapStageResponse(BaseModel):
       """Response from multi-target model optimization."""
       # Performance results (matches context["prediction_results"])
       cv_scores: Dict[str, List[float]]  # Target -> fold scores
       best_models: Dict[str, str]  # Target -> model type
       performance_summary: Dict[str, Any]  # Detailed metrics per target
       
       # Model artifacts
       model_paths: Dict[str, str]  # Target -> model file path
       
       # Optimization metadata
       processing_time_ms: float
       optimization_studies: Dict[str, Any]  # Optuna study summaries per target
   ```

3. **Background Task Infrastructure**:
   - Use FastAPI BackgroundTasks for initial implementation
   - Prepare for Celery migration in production phase
   - Implement progress tracking hooks in Optuna optimization loops

### **Critical Design Decisions for Implementer**

1. **Context Pattern Preservation**: The service must populate the same context dictionary that the current pipeline uses. Study how `EMUSESPipeline.run()` creates and passes context between stages - especially the context updates in `UMAPStage.run()` lines 230-251.

2. **Optimization Configuration Handling**: EMUSES uses nested dictionaries for parameter optimization, not individual parameters. The service must:
   - Accept `optim_config` dictionaries (from `emuses/config/optim_configs.py`)
   - Handle the default `optim_dict_default` if no config provided
   - Support custom optimization configurations for advanced users

3. **Joint UMAP+HDBSCAN Architecture**: The `UMAPStage` is actually an embedding transformer that jointly optimizes UMAP and HDBSCAN. The service should:
   - Expose this as `/embedding/fit` not `/umap/fit`
   - Return both embeddings and cluster labels
   - Handle the nested Optuna optimization (UMAP trials × HDBSCAN trials)

4. **Output Folder Handling**: FastAPI endpoints shouldn't require file system outputs. Consider:
   - In-memory model storage with download endpoints
   - Temporary directories for intermediate files
   - Optional persistent storage configuration

5. **Error Handling**: Wrap all stage exceptions in HTTP-appropriate responses while preserving scientific error information and Optuna study details.

### **Success Criteria Checklist**

- [ ] `/embedding/fit` endpoint produces identical embeddings and cluster labels to CLI
- [ ] `/heatmap/optimize` endpoint produces identical CV scores to CLI  
- [ ] Optimization configurations work with both default and custom `optim_dict` settings
- [ ] Joint UMAP+HDBSCAN optimization preserves the nested Optuna trial structure
- [ ] Background tasks work for long-running optimization operations
- [ ] All existing Python imports continue working
- [ ] `python main.py` CLI remains functional
- [ ] Context dictionary passing matches existing pipeline behavior
- [ ] Comprehensive test suite comparing API vs CLI results

---

## LAD Session 2: Enhanced CLI with Typer

### **Feature Draft (for `00_feature_kickoff.md`)**

```markdown
**Feature draft** ⟶ Replace the current argparse-based CLI in main.py with a modern Typer interface while maintaining exact functional parity. The new CLI should provide identical command-line arguments, produce identical outputs, and support all existing workflows. Add rich progress bars, better help text, and shell completion. The CLI should internally call the new FastAPI service layer for consistency across interfaces. All existing scripts and documentation using the current CLI syntax must continue working without modification. Include subcommands for different workflows (full pipeline, umap-only, predict-only) and add interactive parameter prompts for novice users.
```

### **Context Files to Open Before Starting**

```bash
# Current CLI implementation
emuses/scripts/main.py

# Service layer from Session 1
emuses/services/emuses_service.py
emuses/api/models.py

# Configuration files
emuses/config/optim_configs.py
emuses/config/optim_configs_predict.py

# Documentation
docs/EMUSES_Service_Architecture_Plan.md
.copilot-instructions.md
```

### **Implementation Structure**

```
emuses/
├── cli/
│   ├── __init__.py
│   ├── main.py              # New Typer-based CLI
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── pipeline.py      # Full pipeline commands
│   │   ├── umap.py          # UMAP-specific commands
│   │   ├── predict.py       # Prediction commands
│   │   └── utils.py         # CLI utilities
│   └── prompts.py           # Interactive prompts
```

### **Key Features to Implement**

1. **Command Structure**:
   ```bash
   emuses run [options]           # Full pipeline (backward compatible)
   emuses umap [options]          # UMAP embedding only
   emuses heatmap [options]       # Model optimization only
   emuses predict [options]       # Prediction/inference only
   emuses interactive             # Guided workflow for novices
   ```

2. **Rich Integration**:
   - Progress bars for long operations
   - Colored output and status indicators
   - Table formatting for results summary
   - Interactive parameter selection

3. **Backward Compatibility Testing**:
   - All existing command-line invocations must work identically
   - Preserve exact output format for scripting compatibility
   - Maintain exit codes and error messages

### **Critical Implementation Notes**

- **Service Integration**: CLI should call the FastAPI service internally for consistency
- **Configuration Loading**: Preserve existing config file loading behavior
- **Logging Setup**: Maintain current logging configuration and output patterns
- **Performance**: CLI should not introduce overhead compared to direct pipeline calls

---

## LAD Session 3: FastAPI Web Layer

### **Feature Draft (for `00_feature_kickoff.md`)**

```markdown
**Feature draft** ⟶ Build a complete REST API exposing all EMUSES functionality through HTTP endpoints. Include file upload/download for datasets and models, background task management with progress tracking, and comprehensive OpenAPI documentation. Support both synchronous (quick operations) and asynchronous (long optimization runs) workflows. The API should handle large datasets efficiently, provide detailed error handling, and include health checks. All endpoints must produce scientifically identical results to the existing pipeline while adding web-native features like CORS, request validation, and structured error responses. Include model versioning, experiment tracking, and multi-user workspace support.
```

### **Context Files to Open Before Starting**

```bash
# Service layer foundation
emuses/services/emuses_service.py
emuses/api/models.py
emuses/api/app.py

# Pipeline stages for reference
emuses/pipelines/umap_stage.py
emuses/pipelines/heatmap_stage.py
emuses/pipelines/prediction_stage.py

# Configuration
emuses/config/optim_configs.py
emuses/config/optim_configs_predict.py

# Architecture plan
docs/EMUSES_Service_Architecture_Plan.md
```

### **API Endpoint Structure**

```
GET    /                          # API info and health check
GET    /health                    # Health check endpoint

# Data management
POST   /data/upload               # Upload datasets (CSV, NPY)
GET    /data/validate             # Validate dataset format
POST   /data/preprocess           # Data preprocessing and splitting

# Embedding endpoints (joint UMAP+HDBSCAN optimization)
POST   /embedding/fit             # Fit embedding model with joint optimization (synchronous for small data)
POST   /embedding/fit-async       # Fit embedding model (asynchronous for large datasets)
POST   /embedding/transform       # Transform new data with existing model
GET    /embedding/models/{model_id} # Download embedding model bundle (UMAP + HDBSCAN)

# Heatmap/prediction optimization endpoints  
POST   /heatmap/optimize          # Start multi-target optimization (asynchronous)
POST   /heatmap/fit               # Quick model fitting (synchronous)
GET    /heatmap/results/{job_id}  # Get optimization results

# Prediction endpoints
POST   /predict/inference         # Pure inference on new data
POST   /predict/evaluate          # Test set evaluation
GET    /predict/models/{model_id} # Download prediction models

# Task management
GET    /tasks/{task_id}           # Get task status and progress
DELETE /tasks/{task_id}           # Cancel running task
GET    /tasks                     # List user's tasks

# Model management
GET    /models                    # List available models
GET    /models/{model_id}         # Get model metadata
DELETE /models/{model_id}         # Delete model
```

### **Key Implementation Features**

1. **File Upload Handling**:
   ```python
   @app.post("/data/upload")
   async def upload_dataset(
       features: UploadFile = File(...),
       labels: Optional[UploadFile] = File(None),
       dataset_name: str = Form(...)
   ):
       # Validate file formats (CSV, NPY)
       # Store in user workspace
       # Return dataset metadata
   ```

2. **Joint Embedding Optimization**:
   ```python
   @app.post("/embedding/fit")
   async def fit_embedding(request: EmbeddingStageRequest):
       """Synchronous embedding for small datasets."""
       service = EMUSESService("/tmp/models")
       result = service.run_embedding_stage(request)
       return result

   @app.post("/embedding/fit-async")
   async def fit_embedding_async(
       request: EmbeddingStageRequest,
       background_tasks: BackgroundTasks
   ):
       """Asynchronous embedding for large datasets with Optuna optimization."""
       task_id = str(uuid.uuid4())
       background_tasks.add_task(run_embedding_optimization, task_id, request)
       return {"task_id": task_id, "status": "started"}
   ```

3. **Background Task Management**:
   ```python
   @app.post("/heatmap/optimize")
   async def start_optimization(
       request: HeatmapStageRequest,
       background_tasks: BackgroundTasks
   ):
       task_id = str(uuid.uuid4())
       background_tasks.add_task(run_heatmap_optimization, task_id, request)
       return {"task_id": task_id, "status": "started"}
   ```

3. **Progress Tracking**:
   - Instrument Optuna callbacks for real-time progress
   - WebSocket endpoints for live progress streaming
   - Estimated time remaining calculations

4. **Error Handling**:
   ```python
   class EMUSESException(HTTPException):
       def __init__(self, detail: str, scientific_context: Dict = None):
           super().__init__(status_code=422, detail=detail)
           self.scientific_context = scientific_context
   ```

### **Testing Requirements**

- **Load Testing**: Support multiple concurrent optimization jobs
- **Data Validation**: Comprehensive input validation and error messages
- **Result Consistency**: API results must match CLI results exactly
- **Documentation**: Auto-generated OpenAPI docs with examples

---

## LAD Session 4: Streamlit GUI

### **Feature Draft (for `00_feature_kickoff.md`)**

```markdown
**Feature draft** ⟶ Create an intuitive Streamlit web interface that allows novice users to run complete EMUSES workflows without coding. The GUI should guide users through data upload, parameter selection, training monitoring, and results visualization. Include interactive plots (embeddings, performance metrics), real-time progress tracking for long operations, and result download capabilities. The interface communicates with the FastAPI backend and should gracefully handle errors, provide helpful guidance, and offer both quick-start and advanced parameter tuning modes. Add workflow templates for common use cases and educational tooltips explaining machine learning concepts.
```

### **Context Files to Open Before Starting**

```bash
# FastAPI backend to integrate with
emuses/api/app.py
emuses/api/models.py

# Example data and workflows
data/FSL_HCP1065_FA_1mm.nii.gz  # Sample dataset
clean_run.ipynb                  # Example notebook workflow

# Configuration for parameter defaults
emuses/config/optim_configs.py
emuses/config/optim_configs_predict.py

# Architecture documentation
docs/EMUSES_Service_Architecture_Plan.md
```

### **GUI Application Structure**

```
emuses/
├── gui/
│   ├── __init__.py
│   ├── app.py                 # Main Streamlit application
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── upload.py          # Data upload and validation
│   │   ├── embedding.py       # UMAP parameter tuning
│   │   ├── training.py        # Model training interface
│   │   ├── results.py         # Results visualization
│   │   └── help.py            # Help and tutorials
│   ├── components/
│   │   ├── __init__.py
│   │   ├── data_viz.py        # Data visualization components
│   │   ├── parameter_tuning.py # Parameter input widgets
│   │   ├── progress.py        # Progress monitoring
│   │   └── file_handlers.py   # File upload/download utilities
│   └── templates/
│       ├── workflows/         # Predefined workflow templates
│       └── examples/          # Example datasets and configs
```

### **User Experience Design**

1. **Guided Workflow**:
   ```
   Home → Upload Data → Configure UMAP → Generate Embeddings → 
   Configure Training → Monitor Progress → Explore Results → Download Models
   ```

2. **Parameter Assistance**:
   - Tooltips with ML concept explanations
   - Recommended parameter ranges based on dataset size
   - "Quick Start" vs "Advanced" parameter modes
   - Template workflows for common use cases

3. **Real-time Feedback**:
   ```python
   # Progress monitoring with auto-refresh
   if st.button("Check Progress"):
       with st.spinner("Fetching progress..."):
           response = requests.get(f"{API_URL}/tasks/{task_id}")
           progress = response.json()["progress"]
           st.progress(progress / 100)
           
           if progress == 100:
               st.success("Training completed!")
               st.session_state.results = response.json()["result"]
   ```

4. **Visualization Components**:
   - Interactive UMAP embedding plots (Plotly)
   - Performance metric dashboards
   - Hyperparameter optimization history
   - Cross-validation results analysis

### **Educational Features**

1. **Workflow Templates**:
   - "Neuroimaging Analysis" - for brain data
   - "Time Series Prediction" - for temporal data
   - "Classification Task" - for categorical outcomes
   - "Exploratory Analysis" - for data exploration

2. **Interactive Tutorials**:
   - Built-in example datasets
   - Step-by-step guided workflows
   - Parameter sensitivity demonstrations
   - Model interpretation tools

### **Technical Requirements**

- **API Integration**: All operations via FastAPI backend calls
- **Session Management**: Persistent state across page navigation
- **Error Handling**: User-friendly error messages with suggestions
- **Performance**: Efficient handling of large datasets and visualizations

---

## LAD Session 5: Production Readiness

### **Feature Draft (for `00_feature_kickoff.md`)**

```markdown
**Feature draft** ⟶ Add production-grade features to the EMUSES service: JWT authentication, user management, persistent task storage with Redis/PostgreSQL, proper error handling and logging, API rate limiting, and container-based deployment. Include model versioning, experiment tracking, and multi-user support. Provide Docker configurations, database migrations, and deployment guides for cloud platforms. Maintain high availability, support concurrent users, and add monitoring/metrics collection while preserving all existing functionality and performance characteristics. Include backup/restore capabilities and security audit features.
```

### **Context Files to Open Before Starting**

```bash
# Complete API from previous sessions
emuses/api/app.py
emuses/services/emuses_service.py
emuses/gui/app.py

# Configuration files
emuses/config/optim_configs.py
requirements.txt
setup.py

# Documentation
docs/EMUSES_Service_Architecture_Plan.md
docs/LAD_Implementation_Guide.md
```

### **Production Infrastructure Components**

1. **Authentication System**:
   ```python
   # emuses/api/auth.py
   - JWT token-based authentication
   - User registration and management
   - Role-based access control (admin, user, readonly)
   - API key management for programmatic access
   ```

2. **Database Schema**:
   ```sql
   -- Core tables for production deployment
   users (id, username, email, password_hash, role, created_at)
   workspaces (id, user_id, name, description, created_at)
   datasets (id, workspace_id, name, file_path, metadata)
   training_jobs (id, workspace_id, status, parameters, results, created_at)
   models (id, job_id, model_type, file_path, metadata, version)
   ```

3. **Container Configuration**:
   ```yaml
   # docker-compose.prod.yml
   services:
     api:
       build: ./emuses-api
       environment:
         - DATABASE_URL=postgresql://...
         - REDIS_URL=redis://...
         - JWT_SECRET_KEY=...
     worker:
       build: ./emuses-api
       command: celery worker
     redis:
       image: redis:6-alpine
     postgres:
       image: postgres:13-alpine
     nginx:
       image: nginx:alpine
       volumes:
         - ./nginx.conf:/etc/nginx/nginx.conf
   ```

4. **Monitoring and Logging**:
   ```python
   # Structured logging
   - Request/response logging
   - Performance metrics (execution time, memory usage)
   - Error tracking and alerting
   - Health check endpoints
   - Prometheus metrics integration
   ```

### **Deployment Configurations**

1. **Local Development** (`docker-compose.dev.yml`)
2. **Staging Environment** (`docker-compose.staging.yml`)
3. **Production Environment** (`docker-compose.prod.yml`)
4. **Cloud Deployment** (Kubernetes manifests, Terraform configs)

### **Security Features**

- **API Rate Limiting**: Prevent abuse and ensure fair resource usage
- **Input Validation**: Comprehensive data validation and sanitization
- **Audit Logging**: Track all user actions and data access
- **Backup Strategy**: Automated database and model artifact backups

---

## Branching Strategy

### **Recommended Approach: Independent Feature Branches**

Each LAD session gets its own feature branch that merges directly to `main`:

```
main
├── feat/foundation-fastapi-service     # LAD Session 1 → merge to main
├── feat/enhanced-cli-typer            # LAD Session 2 → merge to main  
├── feat/fastapi-web-layer             # LAD Session 3 → merge to main
├── feat/streamlit-gui                 # LAD Session 4 → merge to main
└── feat/production-readiness          # LAD Session 5 → merge to main
```

**Why this approach works:**
- ✅ **Pure LAD methodology** - Each session is focused and independent
- ✅ **Clean rollback capability** - Can abandon/restart any session
- ✅ **Manageable PR scope** - Each PR is reviewable and testable
- ✅ **Continuous integration** - Main branch always has working, integrated code
- ✅ **Parallel development** - Could work on multiple sessions simultaneously

### **Session Dependencies**

While branches are independent, sessions have logical dependencies:
- **Session 2** (CLI) depends on **Session 1** (service layer)
- **Session 3** (API) builds on **Session 1** (service layer)  
- **Session 4** (GUI) depends on **Session 3** (API endpoints)
- **Session 5** (production) enhances **Sessions 3-4**

**Dependency Management:**
1. Complete and merge each session before starting dependent sessions
2. Always start new sessions from latest `main` to get previous session changes
3. Run integration tests after each merge to catch dependency issues

## Implementation Workflow for Each Session

### **Pre-Session Setup**

1. **Sync with Main Branch**:
   ```bash
   git checkout main
   git pull origin main  # Get latest changes from previous sessions
   ```

2. **Create Feature Branch**:
   ```bash
   git checkout -b feat/foundation-fastapi-service  # Use session-specific name
   ```

3. **Open Context Files**: Open all files listed in the session's "Context Files" section in VS Code

4. **Review Documentation**: Ensure Copilot has access to:
   - `.copilot-instructions.md`
   - `docs/EMUSES_Service_Architecture_Plan.md`
   - This LAD implementation guide (especially the session-specific sections)

### **LAD Session 1 - Ready-to-Use Context Package**

**Copy-paste this complete context package into your new LAD discussion:**

```markdown
**Feature draft** ⟶ Create a FastAPI service layer that wraps the existing EMUSES pipeline stages (EmbeddingStage for joint UMAP+HDBSCAN optimization, HeatmapStage for multi-target prediction, PredictionStage for inference) without modifying their core logic. The service should provide REST endpoints that accept Pydantic-validated requests containing optimization configurations (not individual parameters), call the existing stage.run() methods with proper context setup, and return structured responses. The EmbeddingStage performs joint UMAP+HDBSCAN optimization using Optuna nested trials and parameter dictionaries from config files. Include background task support for long-running operations like hyperparameter optimization. Must maintain 100% backward compatibility - existing CLI and Python imports continue working unchanged. The service acts as a thin translation layer between HTTP requests and the current pipeline context pattern, reusing 90%+ of existing computational code.

**Implementation Requirements from LAD Analysis:**

**Service Layer Structure:**
```
emuses/
├── services/
│   ├── __init__.py
│   ├── emuses_service.py          # Main service coordinator
│   ├── embedding_service.py       # EmbeddingStage wrapper (joint UMAP+HDBSCAN)
│   ├── heatmap_service.py         # HeatmapStage wrapper (multi-target optimization)
│   └── prediction_service.py      # PredictionStage wrapper
├── api/
│   ├── __init__.py
│   ├── models.py                  # Pydantic request/response models
│   ├── app.py                     # FastAPI application
│   └── dependencies.py           # Common API dependencies
```

**Critical Design Decisions:**
1. **Context Pattern Preservation**: Service must populate the same context dictionary that current pipeline uses. Study how `EMUSESPipeline.run()` creates and passes context between stages - especially context updates in `UMAPStage.run()` lines 230-251.

2. **Optimization Configuration Handling**: EMUSES uses nested dictionaries for parameter optimization, not individual parameters. Accept `optim_config` dictionaries from `emuses/config/optim_configs.py`, handle default `optim_dict_default` if none provided.

3. **Joint UMAP+HDBSCAN Architecture**: `UMAPStage` performs joint optimization of UMAP and HDBSCAN. Expose as `/embedding/fit` not `/umap/fit`, return both embeddings and cluster labels, handle nested Optuna optimization (UMAP trials × HDBSCAN trials).

4. **Background Task Infrastructure**: Use FastAPI BackgroundTasks for initial implementation, prepare for Celery migration in production phase.

**Pydantic Models to Define:**
- `EmbeddingStageRequest` with features, test_features, optim_config, n_trials, hdbscan_trials, random_state, umap_jobs, hdbscan_jobs, prefix
- `EmbeddingStageResponse` with train_embeddings, test_embeddings, cluster_labels, umap_model_path, clusterer_model_path, min_coords, max_coords, processing_time_ms, optimization_history
- `HeatmapStageRequest` with embeddings, labels, task, optim_config, outer_folds, optim_trials, use_ae_pretrain, feature_types, random_state
- `HeatmapStageResponse` with cv_scores, best_models, performance_summary, model_paths, processing_time_ms, optimization_studies

**Success Criteria:**
- `/embedding/fit` endpoint produces identical embeddings and cluster labels to CLI
- `/heatmap/optimize` endpoint produces identical CV scores to CLI  
- Optimization configurations work with both default and custom `optim_dict` settings
- All existing Python imports continue working
- `python emuses/scripts/main.py` CLI remains functional
- Context dictionary passing matches existing pipeline behavior

**Context Files for Exploration:**
- emuses/pipelines/emuses_pipeline.py
- emuses/pipelines/umap_stage.py
- emuses/pipelines/heatmap_stage.py
- emuses/pipelines/prediction_stage.py
- emuses/pipelines/pipeline_stage.py
- emuses/pipelines/pipeline_config.py
- emuses/config/optim_configs.py
- emuses/config/optim_configs_predict.py
- emuses/tools/optim_utils.py
- emuses/tools/model_io.py
- emuses/tools/UMAP_utils.py
- emuses/scripts/main.py
- docs/LAD_Implementation_Guide.md

Please implement according to this architectural guidance while exploring the codebase to understand current patterns and ensure 100% compatibility.
```

**Current Status:**
- Branch: `feat/foundation-fastapi-service`
- All planning work committed to main
- Ready for LAD Session 1 implementation
- Start a new VS Code discussion with the context package above

---

## Integration Testing & Real-World Validation

### **Real-World CLI Command for Integration Testing**

The following command represents a comprehensive real-world use case that should be used as a gold standard for integration testing across all LAD sessions. This command exercises the complete EMUSES pipeline with realistic data paths and optimization parameters:

```bash
# Real-world integration test command  
python "emuses/scripts/main.py" full \
  "/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/is_it_running" \
  "/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm robust \
  --scores "/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/specific_columns_data.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --hdbscan_jobs 16 \
  --optuna_trials 10 \
  --prediction_optim_dict optim_dict_test
```

### **Original Real-World Command (Verified Working)**

The following is the exact command that was provided as a reference for integration testing:

```bash
python "/home/chrisfoulon/neuro_apps/emuses/emuses/scripts/main.py" full \
  "/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/is_it_running" \
  "/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/selected_columns_data.csv" \
  --columns_are_features \
  --input_header 0 \
  --input_index_column 0 \
  -inorm robust \
  --scores "/gamma/GIN Dropbox/Chris Foulon/EMUSE/HCP_psy/specific_columns_data.csv" \
  --scores_header 0 \
  --scores_index_column 0 \
  --interactive_plot \
  --umap_trials 1 \
  --hdbscan_trials 1 \
  --optim_dict optim_dict_hcp \
  --hdbscan_jobs 16 \
  --prediction_optim_dict optim_dict_predict
```

**Debugging Notes:**
- ✅ **Command Structure**: Verified correct - uses `full` subcommand with proper positional arguments
- ✅ **File Paths**: Properly quoted to handle spaces in directory names
- ✅ **Arguments**: All parameters validated against the CLI parser
- ⚠️ **Dependencies**: Requires the `PipelineConfig` bug fix (output_folder vs output_folder_path)
- ✅ **Real Data**: Uses actual HCP psychology datasets with proper formatting

This command demonstrates:
- **Full Pipeline**: Uses the `full` subcommand for complete processing
- **Real Data**: Processing actual HCP psychology data
- **Feature Configuration**: `--columns_are_features` indicates CSV columns are features
- **Normalization**: Uses robust normalization (`-inorm robust`)
- **Optimization**: Limited trials for testing (`--umap_trials 1 --hdbscan_trials 1`)
- **Parallel Processing**: High job count (`--hdbscan_jobs 16`) for performance
- **Custom Configurations**: Uses specific optimization dictionaries

### **Integration Test Requirements for Each LAD Session**

**Session 1 (Foundation FastAPI Service):**
- The FastAPI service must produce identical results to the CLI command above
- All intermediate files, models, and outputs must match exactly
- Performance metrics and optimization histories must be preserved
- Test should run within reasonable time limits (< 30 minutes for CI)

**Session 2 (Enhanced CLI with Typer):**
- New Typer CLI must accept identical parameters and produce identical outputs
- All existing argument parsing and validation must be preserved
- Shell completion and help text must be comprehensive
- Backward compatibility with existing scripts must be maintained

**Session 3 (FastAPI Web Layer):**
- REST API endpoints must handle the same data and parameters
- File upload/download must support the CSV formats in the test command
- Background task processing must handle the optimization workload
- API responses must include all outputs from the CLI version

**Session 4 (Streamlit GUI):**
- Web interface must support uploading the same CSV files
- Parameter configuration must match the CLI arguments
- Results visualization must display all outputs from the test command
- Download functionality must provide identical files to CLI

**Session 5 (Production Readiness):**
- The production service must handle the full optimization workload
- Authentication and authorization must not interfere with processing
- Database storage must preserve all results and metadata
- Deployment must support the computational requirements

### **Integration Test Data Characteristics**

Based on the file paths, this test uses:
- **Training Features**: `/features_train.csv` - High-dimensional feature matrix
- **Test Features**: `/features_test.csv` - Hold-out test data
- **Training Labels**: `/labels_train.csv` - Multi-target regression/classification labels
- **Test Labels**: `/labels_test.csv` - Hold-out test labels
- **Output Directory**: Structured output with all artifacts

### **Performance Benchmarks**

The integration test should establish baseline performance metrics:
- **UMAP Optimization**: 10 trials × 5 HDBSCAN trials = 50 total evaluations
- **Heatmap Optimization**: 3 outer folds × 10 trials = 30 cross-validation runs
- **Prediction Inference**: Full test set evaluation
- **Resource Usage**: Memory, CPU, and disk I/O profiles
- **Processing Time**: End-to-end pipeline duration

### **Validation Criteria**

For each LAD session, the integration test must verify:
1. **Numerical Consistency**: All floating-point outputs match within tolerance
2. **File Structure**: Output directory structure and file naming conventions
3. **Model Artifacts**: Saved models can be loaded and used for inference
4. **Optimization Results**: Optuna study histories and best parameters
5. **Performance Metrics**: CV scores, prediction accuracy, and error rates
6. **Metadata Preservation**: All processing metadata and configuration

### **Automated Testing Integration**

```bash
# Example integration test runner
pytest tests/integration/test_real_world_pipeline.py::test_full_pipeline_compatibility -v --tb=short
```

This integration test should be:
- **Executable in CI/CD**: Automated on every LAD session merge
- **Deterministic**: Use fixed random seeds for reproducibility
- **Comprehensive**: Cover all major code paths and edge cases
- **Fast**: Optimized for CI environments (reduced trial counts if needed)
- **Documented**: Clear failure modes and debugging instructions

**Current Status:**
- Branch: `feat/foundation-fastapi-service`
- All planning work committed to main
- Ready for LAD Session 1 implementation
- Start a new VS Code discussion with the context package above
