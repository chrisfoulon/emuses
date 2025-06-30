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

### **Context Package for Copilot**

For each LAD session, provide this complete context package to Copilot:

```markdown
**Feature draft** ⟶ [Include the session's feature draft from above]

**Implementation Requirements from LAD Analysis:**

[Include these sections from the guide for the specific session:]
- Key Implementation Requirements
- Critical Design Decisions for Implementer  
- Pydantic Models/API Structure (if applicable)
- Success Criteria Checklist

**Context Files for Exploration:**
[List the context files from the session's "Context Files to Open" section]

Please implement according to this architectural guidance while exploring the codebase to understand current patterns and ensure 100% compatibility.
```

**Why this approach works:**
- **Leverages our analysis** - Copilot gets the benefit of our architectural research
- **Prevents rediscovery time** - No need to re-understand joint UMAP+HDBSCAN optimization
- **Ensures correct design** - API structure and service layer match EMUSES patterns
- **Still allows exploration** - Copilot examines code files for implementation details
- **Maintains LAD flexibility** - Copilot can ask questions and suggest improvements

### **LAD Workflow Steps**

1. **Feature Kickoff** (`00_feature_kickoff.md`):
   - Provide the complete context package (see above)
   - Let Copilot ask clarifying questions
   - Provide additional context as needed

2. **Context Gathering** (`01_context_gathering.md`):
   - Generate multi-level documentation
   - Review current codebase understanding

3. **Plan Feature** (`02_plan_feature.md`):
   - Create detailed implementation checklist
   - Ensure test-driven development approach

4. **Implementation Loop** (`04_implement_next_task.md`):
   - Implement each checklist item
   - Run tests after each change
   - Commit with conventional commit messages

5. **Code Review** (`05_code_review_package.md` + `06_self_review_with_chatgpt.md`):
   - Generate comprehensive review bundle
   - Address feedback and issues

### **Success Validation for Each Session**

- **Backward Compatibility**: Existing CLI and Python imports work unchanged
- **Result Consistency**: New interfaces produce identical computational results
- **Test Coverage**: Comprehensive test suite with good coverage
- **Documentation**: Updated docs and examples
- **Performance**: Maintain or improve existing performance characteristics

### **Between-Session Integration**

- **After each session merge**:
  ```bash
  # Merge completed session
  git checkout main
  git merge feat/foundation-fastapi-service
  git push origin main
  
  # Run full integration tests
  python -m pytest tests/integration/
  python main.py --help  # Verify CLI still works
  ```

- **Before starting new session**:
  ```bash
  # Start from latest main
  git checkout main
  git pull origin main
  
  # Verify all existing functionality
  python -m pytest tests/
  
  # Create new session branch
  git checkout -b feat/enhanced-cli-typer
  ```

- **Mid-session integration issues**: 
  - If Session 1 needs hotfixes while Session 2 is in progress:
    ```bash
    # From Session 2 branch
    git checkout main
    git checkout -b hotfix/session1-fix
    # Make fix, PR to main
    # Then rebase Session 2 onto updated main
    git checkout feat/enhanced-cli-typer
    git rebase main
    ```

### **Session Completion Checklist**

Before merging each session to main:

- [ ] All LAD checklist items completed
- [ ] Comprehensive test suite passes
- [ ] Backward compatibility verified (existing CLI works)
- [ ] Performance benchmarks show no regression
- [ ] Documentation updated
- [ ] Code review completed (using LAD review bundle)
- [ ] Integration with previous sessions tested

---

## Additional Context for Copilot

### **EMUSES Domain-Specific Knowledge**

1. **Scientific Computing Context**:
   - EMUSES is neuroimaging analysis software
   - Results must be reproducible and scientifically valid
   - Performance matters for large brain datasets
   - Users range from novice researchers to ML experts

2. **Pipeline Architecture Understanding**:
   - Context dictionary pattern for stage communication
   - Optuna-based hyperparameter optimization
   - Joblib for parallel processing
   - Multiple output artifacts per stage

3. **Key Dependencies and Constraints**:
   - Python 3.11 target
   - NumPy/SciPy scientific computing stack
   - Scikit-learn for ML algorithms
   - UMAP-learn for dimensionality reduction
   - Optuna for hyperparameter optimization

### **Code Quality Standards**

- **Type Hints**: Use throughout (already established in codebase)
- **Docstring Format**: NumPy-style docstrings (per `.copilot-instructions.md`)
- **Error Handling**: Preserve scientific error context
- **Testing**: pytest with good coverage of edge cases
- **Performance**: Profile memory usage for large datasets

### **Implementation Priorities**

1. **Correctness First**: Results must match existing pipeline exactly
2. **Backward Compatibility**: Never break existing user workflows
3. **Scientific Integrity**: Preserve all statistical and ML validity
4. **Usability**: Each interface serves its target user type well
5. **Performance**: Maintain or improve existing performance characteristics

This guide provides the comprehensive context needed for successful LAD-driven implementation of the EMUSES service architecture refactoring.

### **Context Package for Copilot**

For each LAD session, provide this complete context package to Copilot:

```markdown
**Feature draft** ⟶ [Include the session's feature draft from above]

**Implementation Requirements from LAD Analysis:**

[Include these sections from the guide for the specific session:]
- Key Implementation Requirements
- Critical Design Decisions for Implementer  
- Pydantic Models/API Structure (if applicable)
- Success Criteria Checklist

**Context Files for Exploration:**
[List the context files from the session's "Context Files to Open" section]

Please implement according to this architectural guidance while exploring the codebase to understand current patterns and ensure 100% compatibility.
```

**Why this approach works:**
- **Leverages our analysis** - Copilot gets the benefit of our architectural research
- **Prevents rediscovery time** - No need to re-understand joint UMAP+HDBSCAN optimization
- **Ensures correct design** - API structure and service layer match EMUSES patterns
- **Still allows exploration** - Copilot examines code files for implementation details
- **Maintains LAD flexibility** - Copilot can ask questions and suggest improvements
