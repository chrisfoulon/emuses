# Analysis API Enhancement - Component Baseline

## Existing Components for Integration

### **Code Components**

#### **Analysis Functions** - Ready for API/CLI Exposure
- **Module**: `emuses.tools.kernel_regression_utils.run_kernel_heatmap_analysis` (location: `/emuses/tools/kernel_regression_utils.py:641`)
  - **Relevant functionality**: Kernel regression heatmap generation with ensemble predictions, uncertainty quantification, effect size mapping
  - **Integration approach**: Wrap with FastAPI endpoint and CLI command, preserve existing parameters and outputs
  - **Dependencies**: NumPy, scikit-learn, existing EMUSES utilities

- **Module**: `emuses.tools.correlation_maps_utils.run_heatmap_analysis` (location: `/emuses/tools/correlation_maps_utils.py:205`)  
  - **Relevant functionality**: Correlation-based heatmap analysis, point-biserial correlation, statistical analysis
  - **Integration approach**: Expose via API endpoint and CLI command with parameter validation
  - **Dependencies**: Existing clustering infrastructure, statistical utilities

#### **Model I/O Management** - Critical Missing Methods
- **Module**: `emuses.tools.model_io.ModelIOManager` (location: `/emuses/tools/model_io.py:113`)
  - **Relevant functionality**: Model saving, loading, manifest management ✅ | **MISSING**: install_model(), validate_model() ⚠️
  - **Integration approach**: Add missing methods to existing class, maintain compatibility with current usage
  - **Dependencies**: Existing manifest system, file hash utilities, JSON serialization

#### **Model Registry System** - Ready for Analysis Artifacts
- **Module**: `emuses.tools.local_model_registry.LocalModelRegistry` (location: `/emuses/tools/local_model_registry.py:502`)
  - **Relevant functionality**: Model installation, listing, metadata management with registry JSON index
  - **Integration approach**: Extend to support analysis artifact installation and discovery
  - **Dependencies**: ModelIOManager (currently blocked by missing methods)

#### **FastAPI Service Infrastructure** - Ready for Extension
- **Module**: `emuses.foundation_fastapi_service.app` (location: `/emuses/foundation_fastapi_service/app.py`)
  - **Relevant functionality**: Complete API service with middleware, authentication, error handling, artifact serving
  - **Integration approach**: Add analysis endpoints following existing patterns
  - **Dependencies**: Existing authentication system, rate limiting, CORS middleware

#### **CLI Command Framework** - Ready for Analysis Commands  
- **Module**: `emuses.cli.models_commands` (location: `/emuses/cli/models_commands.py`)
  - **Relevant functionality**: Model registry CLI commands with Typer integration, Rich console output
  - **Integration approach**: Add analysis command group following existing models command patterns
  - **Dependencies**: Existing security validation, path validation, Rich progress indicators

### **Data Structures**

#### **Model Registry Schema** - Ready for Analysis Artifacts
- **Data Model**: `ModelRegistry` (location: `/emuses/multi_user_service/models.py`)
  - **Schema/Format**: 
    ```python
    model_type = Column(String)      # Can store "analysis_artifact_kernel", "analysis_artifact_correlation"  
    tags = Column(JSON)              # Perfect for ["analysis", "heatmap", "effect_size"]
    model_path = Column(String)      # Filesystem path to analysis artifacts
    manifest_hash = Column(String)   # SHA-256 integrity verification
    workspace_id = Column(UUID)      # Multi-user workspace isolation
    ```
  - **Usage patterns**: Store trained models with metadata, support filtering and discovery
  - **Extension needs**: No schema changes required - existing fields support analysis artifacts

#### **Pipeline Configuration** - Pattern for Analysis Parameters
- **Data Model**: `PipelineConfig` (location: `/emuses/pipelines/pipeline_config.py`)
  - **Schema/Format**: Dataclass with comprehensive parameter validation, default handling
  - **Usage patterns**: Configuration validation, parameter transformation, environment-specific settings
  - **Extension needs**: Create `AnalysisConfig` following same patterns for complex parameter management

### **Infrastructure Components**

#### **Statistical Analysis Utilities** - Ready for Integration
- **Service**: `emuses.tools.stats_utils` 
  - **Current usage**: Effect size calculations, statistical testing, correlation analysis
  - **Integration points**: `input_matrix_stat_map()`, `calculate_correlation_grid()` functions
  - **Configuration**: Multiple test types supported (Cohen's d, Mann-Whitney, t-tests)

#### **Visualization Infrastructure** - Ready for Enhancement  
- **Service**: `emuses.tools.visualisation`
  - **Current usage**: Interactive plotting, embedding visualization, cluster analysis
  - **Integration points**: `plot_clustering_interactive_with_hover()` for HTML interactive plots
  - **Configuration**: Supports hover data, metadata integration, multiple visualization types

#### **Security and Validation System** - Ready for Analysis Endpoints
- **Service**: `emuses.cli.security`
  - **Current usage**: Path validation, directory traversal protection, filename sanitization
  - **Integration points**: `validate_path()`, `secure_filename()` functions
  - **Configuration**: Comprehensive security pattern for file operations and user input

#### **Artifact Serving Infrastructure** - Ready for Analysis Results
- **Service**: FastAPI artifact serving (location: `/foundation_fastapi_service/app.py`)
  - **Current usage**: Job artifact download with content-type detection and security
  - **Integration points**: Existing `GET /api/v1/jobs/{job_id}/artifacts/{filename}` pattern
  - **Configuration**: Permission-controlled access, path traversal protection, MIME type detection

### **Testing Infrastructure**

#### **API Testing Patterns** - Established for Analysis Endpoints
- **Framework**: pytest with AsyncClient for FastAPI testing
  - **Current usage**: Integration testing for pipeline APIs with real app and mocked dependencies
  - **Integration points**: Existing test fixtures, authentication mocking, response validation
  - **Configuration**: Test database, temporary file systems, async test execution

#### **CLI Testing Patterns** - Ready for Analysis Commands
- **Framework**: Typer CliRunner with filesystem mocking
  - **Current usage**: Model registry command testing with real filesystem operations
  - **Integration points**: Existing Rich console capture, progress indicator testing  
  - **Configuration**: Temporary directories, command output validation, exit code checking

#### **Integration Testing Infrastructure** - Comprehensive Coverage
- **Framework**: End-to-end testing with real data pipelines
  - **Current usage**: Complete workflow testing from input to artifact generation
  - **Integration points**: Test dataset fixtures, performance benchmarking, artifact validation
  - **Configuration**: Configurable test complexity, timeout handling, resource cleanup

## Integration Dependencies Map

### **Immediate Dependencies** (Sub-Plan 0A)
```
ModelIOManager.install_model() ←── LocalModelRegistry.install_model()
ModelIOManager.validate_model() ←── LocalModelRegistry validation workflow  
Fixed CI dependencies ←── All subsequent testing
```

### **Analysis API Dependencies** (Sub-Plan 0B)  
```
Working ModelIOManager ←── Analysis artifact installation
FastAPI infrastructure ←── Analysis endpoint implementation
CLI framework ←── Analysis command implementation
Analysis functions ←── API/CLI integration layer
```

### **Advanced Feature Dependencies** (Sub-Plan 0C)
```
Analysis artifacts ←── Inference visualization
Model registry integration ←── Advanced artifact access  
Working API/CLI ←── Research workflow tools
Comprehensive testing ←── Quality validation
```

## Component Readiness Assessment

### **✅ Production Ready - No Changes Needed**
- Analysis functions (`run_kernel_heatmap_analysis`, `run_heatmap_analysis`)
- FastAPI service infrastructure and middleware stack
- CLI command framework with Typer and Rich integration
- Model registry database schema and permissions system
- Statistical utilities and visualization functions
- Security validation and artifact serving systems

### **🔧 Enhancement Required - Extend Existing**  
- Model registry: Add analysis artifact support (use existing patterns)
- CLI commands: Add analysis command group (follow models command patterns)
- API endpoints: Add analysis endpoints (follow existing endpoint patterns)
- Configuration: Create AnalysisConfig (follow PipelineConfig patterns)

### **⚠️ Critical Missing - Must Implement**
- ModelIOManager.install_model() method (BLOCKING all model installation)
- ModelIOManager.validate_model() method (BLOCKING model validation)  
- CI pipeline dependency resolution (BLOCKING automated testing)

## Quality Metrics Baseline

### **Current Test Coverage**
- **Overall**: 47.1% line coverage (research software excellence level)
- **Critical Systems**: 70-100% coverage (Security, Model Registry core)
- **Total Tests**: 2,138 tests with 99.1% health status

### **Target Coverage for New Components**
- **ModelIOManager methods**: 95% coverage (critical infrastructure)
- **Analysis API endpoints**: 95% coverage (user-facing API)
- **CLI analysis commands**: 90% coverage (user experience critical)
- **Integration workflows**: 85% coverage (end-to-end validation)

### **Performance Baselines**
- **API Response Times**: <2s for simple requests, <30s for analysis jobs
- **CLI Command Responsiveness**: <1s for validation, progress indicators for long operations
- **Analysis Generation**: Configurable timeouts, background processing for large datasets
- **Artifact Storage**: Efficient file serving with caching and compression

This component baseline provides comprehensive guidance for integration with existing EMUSES infrastructure while identifying the critical ModelIOManager methods that must be implemented to unblock all subsequent development.