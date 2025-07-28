# EMUSES Documentation Summary

This document provides a comprehensive overview of all documentation created for the EMUSES core pipeline and its utilities. The documentation follows the `.lad/` toolkit conventions with a three-level nested structure for progressive disclosure.

## Documentation Structure

### Core Pipeline Documentation (`docs/emuses/`)

#### 1. Main Script (`main.md`)
- **Purpose**: CLI orchestrator and pipeline entry point
- **Key Features**: Argument parsing, stage coordination, output management
- **Integration**: Entry point for all EMUSES workflows

#### 2. Core Pipeline (`emuses_pipeline.md`)
- **Purpose**: EMUSESPipeline class with data management and stage execution
- **Key Features**: Stage orchestration, context management, configuration handling
- **Integration**: Central coordinator for all pipeline stages

#### 3. UMAP Stage (`umap_stage.md`)
- **Purpose**: UMAP dimensionality reduction with nested clustering optimization
- **Key Features**: Bayesian optimization, HDBSCAN integration, model persistence
- **Integration**: Primary dimensionality reduction stage

#### 4. Heatmap Stage (`heatmap_stage.md`)
- **Purpose**: Enhanced prediction pipeline with feature engineering
- **Key Features**: Nested CV, Optuna optimization, autoencoder pretraining
- **Integration**: Core prediction and modeling stage

#### 5. Prediction Stage (`prediction_stage.md`)
- **Purpose**: Enhanced/classic pipeline modes with feature engineering
- **Key Features**: Multiple feature types, hyperparameter optimization, robust evaluation
- **Integration**: Final modeling and evaluation stage

### Utility Documentation (`docs/emuses/utils/`)

#### 1. Feature Engineering (`features_utils.md`)
- **Purpose**: sklearn-compatible transformers for sophisticated feature generation
- **Key Components**:
  - `RawCoords`: Pass-through transformer for baseline features
  - `GWD`: Gaussian-weighted distance features with configurable aggregation
  - `PCAGWD`: PCA compression of GWD features with variance threshold selection
  - `KernelPCAGWD`: Non-linear compression via Kernel PCA on precomputed RBF kernels
  - `CorrFilter`: Correlation-based feature selection with leakage prevention
- **Integration**: Used throughout prediction pipeline for feature engineering

#### 2. Model I/O Management (`model_io.md`)
- **Purpose**: Comprehensive model persistence with versioning and metadata tracking
- **Key Components**:
  - `ModelIOManager`: Centralized model saving/loading with fallback mechanisms
  - `ModelMetadata`: Enhanced metadata with Optuna study tracking and CV info
  - `ModelArtifact`: Container for model + metadata + filepath
- **Integration**: Used by all pipeline stages for robust model persistence

#### 3. UMAP Utilities (`umap_utils.md`)
- **Purpose**: UMAP optimization with Bayesian search and clustering integration
- **Key Components**:
  - `train_and_save_umap_with_bayesian_search`: Single UMAP optimization
  - `train_and_save_umap_optim_with_nested_clustering`: UMAP+HDBSCAN joint optimization
  - `evaluate_embedding_statistics`: Comprehensive embedding quality metrics
  - `load_umap_model`: Robust model loading with multiple fallback strategies
- **Integration**: Core functionality for UMAPStage and embedding generation

#### 4. Statistics and Modeling (`stats_utils.md`)
- **Purpose**: Advanced prediction pipeline with nested CV and comprehensive modeling
- **Key Components**:
  - `new_pipeline_test`: Enhanced prediction pipeline with feature engineering
  - `create_cluster_representative_maps`: Statistical cluster analysis with effect sizes
  - `filter_nan_rows`: Robust data cleaning for machine learning
  - Multiple model training functions with hyperparameter optimization
- **Integration**: Core functionality for HeatmapStage and PredictionStage

#### 5. Clustering Utilities (`clustering_utils.md`)
- **Purpose**: HDBSCAN optimization with comprehensive quality metrics
- **Key Components**:
  - `inner_optimize_hdbscan`: Bayesian hyperparameter optimization for clustering
  - `evaluate_clustering_metrics`: Multiple clustering quality metrics (persistence, DBCV, noise ratio)
  - `compute_cluster_persistence`: Cluster stability measurement
  - `load_hdbscan_model`: Robust model loading with fallback mechanisms
- **Integration**: Used by UMAPStage for nested clustering optimization

#### 6. Data Preprocessing (`data_preproc.md`)
- **Purpose**: Data cleaning, normalization, and quality assurance
- **Key Components**:
  - `normalize_input_matrix`: Min-max normalization for consistent scaling
  - `rescale_image_array`: Image resolution standardization with memory efficiency
  - `normalise_colours_in_array`: Pixel value normalization for ML compatibility
  - `filter_nan_rows`: Missing value handling with mask tracking
  - `validate_input_data`: Comprehensive data quality validation
- **Integration**: Essential preprocessing for all pipeline stages

## Documentation Conventions

### Three-Level Structure

Each documentation file follows the `.lad/` toolkit conventions with progressive disclosure:

#### Level 1: Visible Summary
- Overview paragraph with purpose and key capabilities
- Immediately visible to users for quick understanding
- Highlights integration points and main use cases

#### Level 2: Collapsible API Table
- Comprehensive function/class reference in tabular format
- Shows inputs, outputs, and side effects for each component
- Organized for quick lookup and interface understanding

#### Level 3: Detailed Code Walk-through
- In-depth code examples with NumPy-style docstrings
- Implementation details and mathematical foundations
- Integration patterns and error handling
- Real-world usage examples and best practices

### Consistent Format

All documentation follows consistent formatting:
- **Purpose statements**: Clear, concise descriptions of functionality
- **Parameter documentation**: Complete type hints and descriptions
- **Return value documentation**: Detailed output specifications
- **Integration notes**: How components fit into the broader pipeline
- **Error handling**: Common issues and resolution strategies
- **Examples**: Practical usage patterns and code snippets

## Key Features Documented

### Advanced Capabilities
- **Bayesian Optimization**: Optuna-based hyperparameter search across all stages
- **Nested Cross-Validation**: Proper model evaluation with inner/outer CV loops
- **Feature Engineering**: Multiple sophisticated feature representations
- **Model Persistence**: Versioned artifacts with comprehensive metadata
- **Fallback Mechanisms**: Robust loading with compatibility checking
- **Parallel Processing**: Efficient multi-core utilization throughout pipeline
- **Service Architecture**: FastAPI-based REST API with automatic local/remote execution
- **Job Management**: Background processing with progress tracking and artifact management
- **Resilient Client**: Circuit breaker, retry logic, and connection pooling for robust service communication

### Integration Patterns
- **Stage Coordination**: How pipeline stages communicate and share data
- **Context Management**: Standardized data passing between components
- **Configuration Handling**: Flexible parameter specification and validation
- **Error Propagation**: Consistent error handling and logging across stages
- **Progress Tracking**: User feedback and monitoring capabilities

### Quality Assurance
- **Data Validation**: Comprehensive input data quality checking
- **Reproducibility**: Consistent random seeding and deterministic algorithms
- **Memory Management**: Efficient handling of large datasets
- **Performance Monitoring**: Timing and resource usage tracking
- **Result Validation**: Output quality checks and statistical validation

## Usage Patterns

### For Pipeline Users
- Start with core pipeline documentation to understand overall workflow
- Reference utility documentation for specific functionality
- Use examples and integration patterns for implementation guidance

### For Developers
- Detailed API documentation for extending functionality
- Implementation patterns for adding new stages or utilities
- Error handling and testing guidance

### For Researchers
- Mathematical foundations and algorithmic details
- Parameter tuning guidance and best practices
- Performance characteristics and computational complexity

### API Service Documentation (`docs/emuses/`)

#### 1. API Service (`api_service.md`)
- **Purpose**: Comprehensive REST API reference for EMUSES service
- **Key Features**:
  - Complete endpoint documentation with request/response examples
  - Authentication, rate limiting, and security patterns
  - Job management lifecycle (submit, monitor, cancel, artifacts)
  - File upload system with validation and storage
  - Error handling patterns and standardized responses
- **Integration**: Central API reference for service-based EMUSES execution

#### 2. CLI Service Integration (`cli_service_integration.md`)
- **Purpose**: CLI-to-service integration patterns and client usage
- **Key Features**:
  - Auto-start local service and remote service connection modes
  - Robust HTTP client with circuit breaker and retry logic
  - Progress monitoring and real-time job status updates
  - Offline fallback and graceful degradation patterns
  - Security considerations and path validation
- **Integration**: Bridges CLI interface with service architecture

#### 3. Service Deployment (`service_deployment.md`)
- **Purpose**: Production deployment guide for EMUSES service
- **Key Features**:
  - Local development setup and containerized deployment
  - Kubernetes, Docker Compose, and cloud platform configurations
  - Load balancing, SSL/TLS, and security hardening
  - Monitoring, logging, and performance optimization
  - Troubleshooting and maintenance procedures
- **Integration**: Complete deployment reference for all environments

## File Organization

```
docs/emuses/
├── main.md                    # CLI entry point
├── emuses_pipeline.md         # Core pipeline orchestrator
├── umap_stage.md             # UMAP dimensionality reduction
├── heatmap_stage.md          # Enhanced prediction pipeline
├── prediction_stage.md       # Feature engineering and modeling
├── api_service.md            # FastAPI service comprehensive reference
├── cli_service_integration.md # CLI-service integration patterns
├── service_deployment.md     # Service deployment and configuration
└── utils/
    ├── features_utils.md     # Feature engineering transformers
    ├── model_io.md          # Model persistence system
    ├── umap_utils.md        # UMAP optimization utilities
    ├── stats_utils.md       # Statistical modeling utilities
    ├── clustering_utils.md  # HDBSCAN clustering utilities
    └── data_preproc.md      # Data preprocessing utilities
```

## Commit History

All documentation was committed using Conventional Commits format:

1. **Core Pipeline Modules** (5 commits):
   - `docs(emuses): add multi-level docs for main.py`
   - `docs(emuses): add multi-level docs for emuses_pipeline.py`
   - `docs(emuses): add multi-level docs for umap_stage.py`
   - `docs(emuses): add multi-level docs for heatmap_stage.py`
   - `docs(emuses): add multi-level docs for prediction_stage.py`

2. **Utility Modules** (1 consolidated commit):
   - `docs(emuses): add multi-level docs for core utility modules`

## Next Steps

The documentation provides a complete reference for the EMUSES pipeline. Future enhancements could include:

- **Interactive Examples**: Jupyter notebooks demonstrating key workflows
- **API Reference**: Auto-generated API documentation from docstrings
- **Performance Benchmarks**: Computational complexity and scaling analysis
- **Tutorial Series**: Step-by-step guides for common use cases
- **Troubleshooting Guide**: Common issues and resolution strategies

This comprehensive documentation ensures that users, developers, and researchers have complete information about the EMUSES pipeline functionality, implementation patterns, and best practices.
