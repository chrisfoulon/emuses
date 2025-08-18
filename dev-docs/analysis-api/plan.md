# Analysis API Enhancement - Implementation Plan

## Implementation Overview

**Goal**: Expose existing effect size map analysis functions through API endpoints and CLI commands  
**Duration**: 2-3 days (implementation + testing + documentation)  
**Focus**: API endpoint development, CLI integration, configuration enhancement, testing and validation  
**Dependencies**: ✅ Existing analysis functions, FastAPI infrastructure, CLI framework

## Progress Tracking Protocol
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"  
3. Run validation tests to verify completion
4. Test API endpoints and CLI commands with realistic data

## Task Breakdown

### Phase A.1: API Endpoint Development ║ FastAPI endpoint implementation ║ API foundation ║ M

**Objective**: Create FastAPI endpoints that expose both `run_kernel_heatmap_analysis()` and `run_heatmap_analysis()` functions with comprehensive parameter validation and response handling.

### Task A.1.1: Request/Response Model Development ║ Pydantic model creation ║ API schema ║ S

- [ ] **Subtask A.1.1.a: Base request model creation**
  - [ ] Create `AnalysisRequestBase` with common parameters (embeddings, scores_vectors, input_matrix, grid_size, etc.)
  - [ ] Add parameter validation with appropriate constraints (grid_size range, valid effect_size_test values)
  - [ ] Implement input data validation (array dimensions, data type consistency)
  - [ ] Add comprehensive docstring documentation for all parameters

- [ ] **Subtask A.1.1.b: Function-specific request models**
  - [ ] Create `KernelAnalysisRequest` extending base model with kernel-specific parameters
  - [ ] Create `CorrelationAnalysisRequest` extending base model with correlation-specific parameters  
  - [ ] Add specialized validation for each function's unique requirements
  - [ ] Implement parameter default values matching existing function defaults

- [ ] **Subtask A.1.1.c: Response model development**
  - [ ] Create `AnalysisResponse` model with analysis results, output paths, and metadata
  - [ ] Add `AnalysisError` model for comprehensive error reporting
  - [ ] Implement response validation and formatting
  - [ ] Add execution metadata (timing, warnings, parameter validation results)

- [ ] **Subtask A.1.1.d: Data serialization handling**
  - [ ] Implement efficient serialization for large numpy arrays
  - [ ] Add support for file upload/download patterns for large datasets
  - [ ] Create parameter validation for data consistency (matching array dimensions)
  - [ ] Add memory usage estimation and limits

### Task A.1.2: Endpoint Implementation ║ FastAPI endpoint creation ║ Core API ║ M

- [ ] **Subtask A.1.2.a: Kernel analysis endpoint**
  - [ ] Create `/analysis/kernel-heatmap/` POST endpoint
  - [ ] Implement parameter mapping from request model to function parameters
  - [ ] Add comprehensive error handling with informative error messages
  - [ ] Integrate with existing `run_kernel_heatmap_analysis()` function

- [ ] **Subtask A.1.2.b: Correlation analysis endpoint**
  - [ ] Create `/analysis/correlation-heatmap/` POST endpoint  
  - [ ] Implement parameter mapping from request model to function parameters
  - [ ] Add correlation-specific validation (clustering requirements)
  - [ ] Integrate with existing `run_heatmap_analysis()` function

- [ ] **Subtask A.1.2.c: Analysis status and management endpoints**
  - [ ] Create `/analysis/{analysis_id}/status/` GET endpoint for long-running analyses
  - [ ] Add `/analysis/{analysis_id}/results/` GET endpoint for result retrieval
  - [ ] Implement analysis result caching and cleanup
  - [ ] Add analysis history and metadata endpoints

- [ ] **Subtask A.1.2.d: Error handling and validation**
  - [ ] Implement comprehensive input validation with clear error messages
  - [ ] Add parameter constraint validation (valid ranges, required combinations)
  - [ ] Create detailed error responses with suggested solutions
  - [ ] Add logging and monitoring for analysis operations

### Task A.1.3: Integration Testing ║ API endpoint validation ║ Quality assurance ║ S

- [ ] **Subtask A.1.3.a: Unit testing for request/response models**
  - [ ] Test parameter validation with valid and invalid inputs
  - [ ] Validate data serialization and deserialization
  - [ ] Test error handling and response formatting
  - [ ] Verify parameter default value application

- [ ] **Subtask A.1.3.b: Integration testing for endpoints**
  - [ ] Test both analysis endpoints with realistic neuroimaging data
  - [ ] Validate analysis result accuracy against direct function calls
  - [ ] Test error handling with malformed requests
  - [ ] Verify output artifact integration with `save_statistical_maps()`

- [ ] **Subtask A.1.3.c: Performance and scalability testing**  
  - [ ] Test endpoint performance with varying data sizes
  - [ ] Validate memory usage and resource management
  - [ ] Test concurrent analysis request handling
  - [ ] Verify timeout and resource limit handling

**Expected Deliverables**:
- `emuses/api/models/analysis.py` - Pydantic models for analysis requests/responses
- `emuses/api/endpoints/analysis.py` - FastAPI endpoint implementations
- `tests/api/test_analysis_endpoints.py` - Comprehensive endpoint testing
- API documentation with request/response examples

### Phase A.2: CLI Command Integration ║ Command-line interface development ║ CLI enhancement ║ M

**Objective**: Add CLI commands that provide command-line access to analysis functions with parameter file support and help integration.

### Task A.2.1: CLI Command Structure Development ║ Click command implementation ║ CLI foundation ║ M

- [ ] **Subtask A.2.1.a: Base command group creation**
  - [ ] Create `emuses analysis` command group for all analysis operations
  - [ ] Add comprehensive help text and usage examples
  - [ ] Implement consistent parameter naming with API endpoints
  - [ ] Add global analysis options (output directory, verbosity, etc.)

- [ ] **Subtask A.2.1.b: Kernel analysis CLI command**
  - [ ] Create `emuses analysis kernel-heatmap` command
  - [ ] Implement parameter mapping from CLI arguments to function parameters
  - [ ] Add file input support for embeddings, scores, and input matrix
  - [ ] Support both individual parameters and configuration file input

- [ ] **Subtask A.2.1.c: Correlation analysis CLI command**
  - [ ] Create `emuses analysis correlation-heatmap` command
  - [ ] Implement correlation-specific parameter handling
  - [ ] Add clustering configuration support
  - [ ] Integrate with existing CLI help system

- [ ] **Subtask A.2.1.d: Parameter file support**
  - [ ] Add YAML/JSON configuration file support for complex parameter sets
  - [ ] Implement parameter validation and default value handling
  - [ ] Create configuration file templates and examples
  - [ ] Add configuration validation and error reporting

### Task A.2.2: CLI Integration and User Experience ║ CLI usability enhancement ║ User interface ║ S

- [ ] **Subtask A.2.2.a: Help system integration**
  - [ ] Add detailed help text for all analysis commands
  - [ ] Create parameter descriptions with examples and valid ranges
  - [ ] Add usage examples and common workflow patterns
  - [ ] Integrate with existing EMUSES CLI help system

- [ ] **Subtask A.2.2.b: Output management and reporting**
  - [ ] Implement progress reporting for long-running analyses
  - [ ] Add result summary and success confirmation
  - [ ] Create verbose mode with detailed execution information
  - [ ] Add output path validation and creation

- [ ] **Subtask A.2.2.c: Error handling and user guidance**
  - [ ] Implement comprehensive error handling with clear messages
  - [ ] Add parameter validation with suggested corrections
  - [ ] Create troubleshooting guidance for common issues
  - [ ] Add dry-run mode for parameter validation without execution

### Task A.2.3: CLI Testing and Validation ║ Command-line testing ║ Quality assurance ║ S

- [ ] **Subtask A.2.3.a: CLI command testing**
  - [ ] Test all CLI commands with various parameter combinations
  - [ ] Validate file input handling and parameter parsing
  - [ ] Test configuration file loading and validation
  - [ ] Verify help system integration and documentation

- [ ] **Subtask A.2.3.b: Integration testing with analysis functions**
  - [ ] Test CLI commands produce identical results to direct function calls
  - [ ] Validate output artifact creation and organization
  - [ ] Test error handling and user message quality
  - [ ] Verify integration with existing EMUSES CLI framework

**Expected Deliverables**:
- `emuses/cli/analysis.py` - CLI command implementations
- `docs/analysis-api/cli_reference.md` - CLI command documentation
- `tests/cli/test_analysis_commands.py` - CLI command testing
- Configuration file templates and examples

### Phase A.3: Configuration Integration ║ Pipeline configuration enhancement ║ Configuration management ║ S

**Objective**: Integrate analysis capabilities with existing EMUSES pipeline configuration system and enable configurable effect size map generation.

### Task A.3.1: Configuration Schema Enhancement ║ Configuration model updates ║ Config management ║ S

- [ ] **Subtask A.3.1.a: Analysis configuration schema**
  - [ ] Add analysis configuration section to main EMUSES config schema
  - [ ] Define default parameters for both analysis functions
  - [ ] Add enable/disable flags for analysis features
  - [ ] Create environment-specific configuration templates

- [ ] **Subtask A.3.1.b: Pipeline integration configuration**
  - [ ] Add configuration flags for automatic effect size map generation
  - [ ] Integrate analysis configuration with existing pipeline stages
  - [ ] Add output directory and artifact management configuration
  - [ ] Create configuration validation and migration support

### Task A.3.2: Pipeline Enhancement ║ Existing workflow integration ║ Feature integration ║ S

- [ ] **Subtask A.3.2.a: Heatmap stage enhancement**
  - [ ] Add optional effect size analysis to existing heatmap stage
  - [ ] Implement configuration-driven analysis execution
  - [ ] Add analysis result integration with stage outputs
  - [ ] Maintain backward compatibility with existing workflows

- [ ] **Subtask A.3.2.b: Configuration documentation**
  - [ ] Document all new configuration options with examples
  - [ ] Add configuration best practices and recommendations
  - [ ] Create migration guide for existing configurations
  - [ ] Add configuration validation and troubleshooting guide

**Expected Deliverables**:
- Updated configuration schema with analysis options
- Enhanced pipeline integration with optional analysis
- Configuration documentation and migration guide

### Phase A.4: Testing and Documentation ║ Comprehensive validation and documentation ║ Quality assurance ║ L

**Objective**: Comprehensive testing of all components and complete documentation for API and CLI usage.

### Task A.4.1: Comprehensive Testing ║ Full system validation ║ Quality validation ║ M

- [ ] **Subtask A.4.1.a: End-to-end testing**
  - [ ] Test complete workflows from API request to artifact output
  - [ ] Validate CLI commands produce correct analysis results
  - [ ] Test configuration integration with existing pipelines
  - [ ] Verify all output formats and artifact integration

- [ ] **Subtask A.4.1.b: Error handling and edge case testing**
  - [ ] Test all error conditions with appropriate error messages
  - [ ] Validate parameter boundary conditions and limits
  - [ ] Test memory and resource management with large datasets
  - [ ] Verify graceful handling of malformed inputs

- [ ] **Subtask A.4.1.c: Performance and reliability testing**
  - [ ] Benchmark API endpoint performance with realistic datasets
  - [ ] Test CLI command performance and resource usage
  - [ ] Validate analysis result consistency and reproducibility
  - [ ] Test concurrent usage and resource contention

### Task A.4.2: Documentation Development ║ User and developer documentation ║ Knowledge transfer ║ M

- [ ] **Subtask A.4.2.a: API documentation**
  - [ ] Create comprehensive API reference with request/response examples
  - [ ] Add usage examples for both analysis endpoints
  - [ ] Document error handling and troubleshooting
  - [ ] Create integration examples for external applications

- [ ] **Subtask A.4.2.b: CLI documentation** 
  - [ ] Write complete CLI reference for all analysis commands
  - [ ] Add usage examples and common workflow patterns
  - [ ] Create parameter reference with descriptions and examples
  - [ ] Document configuration file usage and templates

- [ ] **Subtask A.4.2.c: User guide integration**
  - [ ] Add analysis API section to main EMUSES user guide
  - [ ] Create workflow examples showing analysis integration
  - [ ] Document best practices for analysis parameter selection
  - [ ] Add troubleshooting guide for common analysis issues

**Expected Deliverables**:
- Complete test suite with >90% coverage for new functionality
- Comprehensive API reference documentation
- Complete CLI reference and user guide
- Integration examples and best practices documentation

## Testing Strategy

### Component Testing Approach
- **API Endpoints**: Integration testing with FastAPI TestClient using realistic neuroimaging data
- **CLI Commands**: End-to-end testing with subprocess calls and output validation
- **Analysis Functions**: Validate wrapped functions produce identical results to direct calls
- **Configuration**: Test configuration loading, validation, and pipeline integration

### Quality Assurance Gates
- **Functional Correctness**: All analysis results match direct function call results
- **Error Handling**: Comprehensive error testing with clear, actionable error messages
- **Performance**: API and CLI performance meets acceptable standards for analysis operations
- **Documentation**: Complete documentation with working examples for all functionality
- **Integration**: Seamless integration with existing EMUSES workflows and output systems

## Risk Assessment

### Technical Risks - LOW
- **Function Compatibility**: Analysis functions are mature and stable with well-defined interfaces
- **Parameter Complexity**: Large parameter sets managed through structured request models
- **Performance**: Memory usage and execution time managed through appropriate limits

### Implementation Risks - LOW  
- **API Design**: Clear parameter mapping from existing function signatures
- **CLI Integration**: Following established EMUSES CLI patterns
- **Configuration**: Building on existing configuration management system

### Mitigation Strategies
- **Incremental Development**: Build and test each component independently
- **Validation First**: Comprehensive parameter validation prevents analysis failures
- **Documentation Driven**: Clear documentation and examples reduce adoption barriers
- **Backward Compatibility**: All changes maintain existing functionality

## Success Criteria

### Functional Requirements
- [ ] API endpoints successfully expose both analysis functions with full parameter support
- [ ] CLI commands provide command-line access to analysis functions with help integration
- [ ] Configuration integration enables optional analysis in existing pipelines
- [ ] All functionality maintains existing analysis function behavior and output quality

### Quality Requirements  
- [ ] >90% test coverage for all new API and CLI functionality
- [ ] Comprehensive error handling with clear, actionable error messages
- [ ] API performance meets standards for typical neuroimaging analysis datasets
- [ ] Complete documentation with working examples for all features

### User Experience Requirements
- [ ] Intuitive API interface with clear parameter names and validation
- [ ] CLI commands follow existing EMUSES patterns and conventions
- [ ] Configuration options are well-documented with clear defaults
- [ ] Error messages provide specific guidance for resolution

## Integration with EMUSES Development

### Leverages Existing Work
- **Analysis Functions**: Mature `run_kernel_heatmap_analysis()` and `run_heatmap_analysis()` functions
- **API Infrastructure**: Established FastAPI framework and request/response patterns
- **CLI Framework**: Existing Click-based command system and help integration
- **Artifact Pipeline**: Proven `save_statistical_maps()` output management system

### Feeds Into Future Work
- **Enhanced Research Workflows**: Better analysis access supports advanced neuroimaging research
- **API Expansion**: Pattern for exposing additional analysis functions through consistent API
- **External Integration**: API enables integration with external research tools and workflows
- **User Experience**: Enhanced analysis capabilities improve overall EMUSES research value

This implementation plan provides a systematic approach to exposing existing analysis capabilities through modern API and CLI interfaces while maintaining all current functionality and integration patterns.