# Web GUI Implementation Plan

## Progress Update Requirements
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"
3. Run tests to verify completion
4. Only mark complete after successful testing

## Task Complexity Assessment

**Task Complexity**: MEDIUM

**Implementation Approach**:
Create new `emuses/gui/` module that wraps existing CLI functionality without modifying core code. Use Gradio 4.x for web interface with progressive disclosure (accordions) for ~97 parameters. Direct Python calls to existing async CLI functions.

**Key Challenges**:
1. Mapping 97 CLI parameters to appropriate Gradio components
2. Adapting ProgressTracker callbacks for real-time Gradio updates
3. Handling large file uploads (5GB+) efficiently
4. Managing long-running pipelines without timeouts (variable processing time)
5. Displaying results (plots, predictions) in browser

**Resource Requirements**:
- **Timeline**: 3-4 weeks (5 phases)
- **Team**: 1 Python developer familiar with EMUSES CLI
- **Dependencies**: Gradio 4.x, existing EMUSES modules
- **Testing**: Manual GUI testing + automated unit tests for adapters

---

## Phase 0: Setup & Foundation (2-3 days)

### Task 0.1: Environment Setup ║ tests/gui/test_setup.py ║ Install Gradio, create module structure ║ S

- [ ] 0.1.1: Install Gradio 4.x and verify compatibility with existing dependencies
  - Add `gradio>=4.0.0,<5.0.0` to setup.py
  - Test installation in development environment
  - Verify no dependency conflicts
- [ ] 0.1.2: Create GUI module structure
  - Create `emuses/gui/` directory
  - Create `emuses/gui/__init__.py`
  - Create `emuses/gui/components/` directory
  - Create `emuses/gui/adapters/` directory
  - Create `emuses/gui/utils/` directory
- [ ] 0.1.3: Write basic smoke test
  - Create `tests/gui/test_setup.py`
  - Test: Import gradio succeeds
  - Test: GUI module structure is accessible
  - Run: `pytest tests/gui/test_setup.py -xvs`

### Task 0.2: Basic Gradio Integration ║ tests/gui/test_basic_app.py ║ Verify Gradio can launch and interact with EMUSES ║ S

- [ ] 0.2.1: Create minimal "Hello World" Gradio app
  - Create `emuses/gui/app.py` with basic interface
  - Verify app launches successfully
  - Test browser opens and connects
- [ ] 0.2.2: Test async execution pattern
  - Create wrapper for async functions
  - Test Gradio queue functionality
  - Verify background execution works
- [ ] 0.2.3: Test EMUSES imports in GUI context
  - Import `emuses.cli.main._full_async`
  - Import `emuses.tools.local_model_registry.LocalModelRegistry`
  - Import `emuses.cli.rich_features.ProgressTracker`
  - Verify no import errors

---

## Phase 1: Core Pipeline Interface - MVP (4-5 days)

### Task 1.1: Parameter Mapper ║ tests/gui/adapters/test_parameter_mapper.py ║ Convert GUI inputs to CLI args ║ M

- [ ] 1.1.1: Create parameter mapper module
  - Create `emuses/gui/adapters/parameter_mapper.py`
  - Define `GUIParameterMapper` class
  - Implement `to_namespace()` method (GUI inputs → argparse.Namespace)
- [ ] 1.1.2: Implement required parameters mapping
  - Map: input_dataset (gr.File) → Path
  - Map: output_folder (gr.Textbox) → Path
  - Validate paths exist and are accessible
- [ ] 1.1.3: Implement basic optional parameters
  - Map: scores (gr.File) → Optional[Path]
  - Map: test_size (gr.Slider) → float
  - Map: input_normalization (gr.Dropdown) → InputNormalization enum
- [ ] 1.1.4: Write comprehensive unit tests
  - Test: Required parameters conversion
  - Test: Optional parameters with None values
  - Test: Path validation and error handling
  - Run: `pytest tests/gui/adapters/test_parameter_mapper.py -xvs`

### Task 1.2: Progress Adapter ║ tests/gui/adapters/test_progress_adapter.py ║ Adapt ProgressTracker to Gradio ║ M

- [ ] 1.2.1: Create progress adapter module
  - Create `emuses/gui/adapters/progress_adapter.py`
  - Define `GradioProgressAdapter` class
  - Implement callback wrapper for Gradio progress
- [ ] 1.2.2: Implement progress update mechanism
  - Convert ProgressTracker updates to Gradio format
  - Handle stage transitions
  - Support progress percentage (0.0-1.0)
- [ ] 1.2.3: Write unit tests
  - Test: Progress callback conversion
  - Test: Stage name display
  - Test: Progress value clamping (0.0-1.0)
  - Run: `pytest tests/gui/adapters/test_progress_adapter.py -xvs`

### Task 1.3: Pipeline Tab Component ║ tests/gui/components/test_pipeline_tab.py ║ Main full pipeline interface ║ L

- [ ] 1.3.1: Create pipeline tab module
  - Create `emuses/gui/components/pipeline_tab.py`
  - Define `create_pipeline_tab()` function
  - Return Gradio components for layout
- [ ] 1.3.2: Implement required parameters section
  - gr.File for input_dataset (label="Input Dataset", file_types=[".nii", ".nii.gz", ".jpg", ".png", ".csv"])
  - gr.Textbox for output_folder (label="Output Folder")
  - Always visible, no accordion
- [ ] 1.3.3: Implement basic optional parameters accordion
  - gr.Accordion(label="Basic Options", open=False)
  - gr.File for scores (optional)
  - gr.Slider for test_size (0.0-1.0, default=0.2)
  - gr.Dropdown for input_normalization (none, zscore, min-max, zero-max, robust)
- [ ] 1.3.4: Implement run button and status display
  - gr.Button("Run Full Pipeline")
  - gr.Textbox for status messages (read-only)
  - gr.Progress for progress bar
- [ ] 1.3.5: Wire up pipeline execution
  - Create async execution wrapper
  - Connect parameters to mapper
  - Connect progress to adapter
  - Handle errors with user-friendly messages
- [ ] 1.3.6: Write integration tests
  - Test: Component creation succeeds
  - Test: Parameter mapping integration
  - Test: Mock pipeline execution (no actual run)
  - Run: `pytest tests/gui/components/test_pipeline_tab.py -xvs`

### Task 1.4: Main App Entry Point ║ tests/gui/test_app_launch.py ║ Gradio app launch and navigation ║ M

- [ ] 1.4.1: Update `emuses/gui/app.py` with tabbed interface
  - Create main app with gr.TabbedInterface or gr.Blocks
  - Add "Full Pipeline" tab using create_pipeline_tab()
  - Add placeholder tabs for future features
- [ ] 1.4.2: Implement CLI entry point
  - Add `if __name__ == "__main__":` block
  - Support command-line args (--server-name, --server-port, --share)
  - Use `interface.queue()` for async support (NO default timeout)
  - Call `interface.launch()`
- [ ] 1.4.3: Test app launch
  - Test: App starts without errors
  - Test: Can access via browser at localhost:7860
  - Test: Tab navigation works
  - Manual test: Upload file, set parameters, click run (use small test dataset)

### Task 1.5: MVP Integration Testing ║ tests/gui/test_mvp_integration.py ║ End-to-end pipeline execution ║ L

- [ ] 1.5.1: Create integration test with mock data
  - Use MNIST dataset (small, fast)
  - Test full pipeline execution via GUI
  - Verify results saved to output folder
- [ ] 1.5.2: Test error handling
  - Invalid file upload
  - Missing output folder
  - Invalid parameter values
  - Verify user-friendly error messages
- [ ] 1.5.3: Test progress tracking
  - Verify progress updates during execution
  - Verify stage transitions
  - Verify completion message
- [ ] 1.5.4: Run comprehensive MVP tests
  - Run: `pytest tests/gui/ -xvs`
  - Fix any failures
  - Verify MVP acceptance criteria met

---

## Phase 2: Inference Interface (3-4 days)

### Task 2.1: Model Registry Integration ║ tests/gui/adapters/test_registry_adapter.py ║ Connect to LocalModelRegistry ║ M

- [ ] 2.1.1: Create registry adapter module
  - Create `emuses/gui/adapters/registry_adapter.py`
  - Define `ModelRegistryAdapter` class
  - Implement `list_models()` for GUI display
  - Implement `search_models()` for search functionality
  - Implement `get_model_info()` for detail view
- [ ] 2.1.2: Format model data for Gradio components
  - Convert model list to dropdown options
  - Format metadata for display (created_at, description, etc.)
  - Handle missing/optional fields gracefully
- [ ] 2.1.3: Write unit tests
  - Test: Model list retrieval
  - Test: Model search
  - Test: Model info formatting
  - Run: `pytest tests/gui/adapters/test_registry_adapter.py -xvs`

### Task 2.2: Inference Tab Component ║ tests/gui/components/test_inference_tab.py ║ Inference interface ║ L

- [ ] 2.2.1: Create inference tab module
  - Create `emuses/gui/components/inference_tab.py`
  - Define `create_inference_tab()` function
- [ ] 2.2.2: Implement model selection section
  - gr.Radio for selection mode (File Path / Registry ID)
  - gr.File for model path (conditional display)
  - gr.Dropdown for registry models (conditional display, populated from registry)
  - Display model metadata when selected
- [ ] 2.2.3: Implement data input section
  - gr.File for inference data upload
  - gr.Checkbox for validate mode
  - gr.Checkbox for verify model integrity
  - gr.Dropdown for output format (csv, npy)
- [ ] 2.2.4: Implement preprocessing options accordion
  - gr.Accordion(label="Preprocessing Options", open=False)
  - Data header, index column, normalization options
  - Match CLI preprocessing parameters
- [ ] 2.2.5: Implement execution and results
  - gr.Button("Run Inference")
  - gr.Textbox for status
  - gr.Dataframe for predictions preview (if CSV)
  - gr.File for results download
- [ ] 2.2.6: Wire up inference execution
  - Map parameters to inference command
  - Handle both file path and registry ID modes
  - Display predictions in interface
  - Provide download link for full results
- [ ] 2.2.7: Write integration tests
  - Test: Component creation
  - Test: Model selection (both modes)
  - Test: Mock inference execution
  - Run: `pytest tests/gui/components/test_inference_tab.py -xvs`

### Task 2.3: Inference Integration ║ tests/gui/test_inference_integration.py ║ End-to-end inference workflow ║ M

- [ ] 2.3.1: Test file path mode
  - Upload model from disk
  - Upload inference data
  - Execute inference
  - Verify results
- [ ] 2.3.2: Test registry ID mode
  - Select model from registry dropdown
  - Upload inference data
  - Execute inference
  - Verify results
- [ ] 2.3.3: Test validation mode
  - Enable validate flag
  - Provide scores for validation
  - Verify validation metrics displayed
- [ ] 2.3.4: Run inference tests
  - Run: `pytest tests/gui/test_inference_integration.py -xvs`

---

## Phase 3: Model Browser (2-3 days)

### Task 3.1: Model Browser Tab ║ tests/gui/components/test_models_tab.py ║ Registry management interface ║ M

- [ ] 3.1.1: Create models tab module
  - Create `emuses/gui/components/models_tab.py`
  - Define `create_models_tab()` function
- [ ] 3.1.2: Implement search and filter section
  - gr.Textbox for search query
  - gr.Button("Search")
  - gr.Dropdown for filter options (type, date range, etc.)
- [ ] 3.1.3: Implement model list display
  - gr.Dataframe for model list (name, description, created_at, type)
  - Clickable rows to view details
  - Sort by date, name, type
- [ ] 3.1.4: Implement model detail panel
  - Display full metadata when model selected
  - Show: name, description, created_at, model_type, performance metrics
  - Show: component details (UMAP, HDBSCAN, predictors)
  - gr.Button("Use in Inference") → switches to inference tab with model pre-selected
- [ ] 3.1.5: Implement model actions
  - gr.Button("Remove Model") with confirmation
  - gr.Button("Verify Integrity")
  - gr.Button("Export Provenance")
  - Display action results/errors
- [ ] 3.1.6: Write integration tests
  - Test: Model list display
  - Test: Search functionality
  - Test: Model detail view
  - Test: Model removal
  - Run: `pytest tests/gui/components/test_models_tab.py -xvs`

---

## Phase 4: Advanced Features & All Parameters (3-4 days)

### Task 4.1: Complete Parameter Mapping ║ tests/gui/adapters/test_all_parameters.py ║ Map all 97 CLI parameters ║ L

- [ ] 4.1.1: Map UMAP parameters accordion
  - gr.Accordion(label="UMAP Options", open=False)
  - n_neighbors, min_dist, n_components, metric, etc.
  - load_umap, load_embeddings options
  - umap_trials for optimization
- [ ] 4.1.2: Map clustering parameters accordion
  - gr.Accordion(label="Clustering Options", open=False)
  - min_cluster_size, min_samples
  - load_hdbscan option
  - hdbscan_trials, hdbscan_approx_min_span_tree
  - interactive_plot option
- [ ] 4.1.3: Map preprocessing parameters accordion
  - gr.Accordion(label="Preprocessing Options", open=False)
  - recursive_search, input_file_types, arg_separator
  - input_header, inputs_columns, input_index_column
  - columns_are_features, bids_filters
- [ ] 4.1.4: Map scores parameters accordion
  - gr.Accordion(label="Scores Options", open=False)
  - scores_header, scores_index_column
  - scores_are_rows, scores_column
  - classification, correlation_method
  - scores_normalization, filter_labelled_by_scores
- [ ] 4.1.5: Map prediction parameters accordion
  - gr.Accordion(label="Prediction Options", open=False)
  - optim_dict, prediction_optim_dict
  - prediction_models list
  - kernel_params, sigma, fwhm
- [ ] 4.1.6: Map output parameters accordion
  - gr.Accordion(label="Output Options", open=False)
  - prefix, show_plots
  - output_format options
- [ ] 4.1.7: Update parameter mapper to handle all parameters
  - Extend `to_namespace()` for all 97 parameters
  - Handle List[str] parameters (comma-separated)
  - Handle Optional parameters correctly
- [ ] 4.1.8: Write comprehensive parameter tests
  - Test each parameter group
  - Test parameter combinations
  - Test edge cases (empty lists, None values)
  - Run: `pytest tests/gui/adapters/test_all_parameters.py -xvs`

### Task 4.2: Configuration Presets ║ tests/gui/utils/test_presets.py ║ Save/load parameter configurations ║ M

- [ ] 4.2.1: Create presets module
  - Create `emuses/gui/utils/presets.py`
  - Define preset JSON schema
  - Implement save_preset(), load_preset()
- [ ] 4.2.2: Add preset UI components
  - gr.Dropdown for preset selection (with built-in presets)
  - gr.Button("Load Preset")
  - gr.Button("Save Current Config")
  - gr.Textbox for preset name (when saving)
- [ ] 4.2.3: Implement built-in presets
  - "Quick Test" (MNIST, minimal parameters)
  - "Full Analysis" (all stages, default parameters)
  - "Inference Only" (skip training stages)
- [ ] 4.2.4: Wire up preset loading
  - Load preset → populate all GUI fields
  - Save preset → capture current GUI state
  - Store presets in ~/.emuses/gui_presets/
- [ ] 4.2.5: Write tests
  - Test: Save preset
  - Test: Load preset
  - Test: Built-in presets exist and work
  - Run: `pytest tests/gui/utils/test_presets.py -xvs`

### Task 4.3: Result Visualization ║ tests/gui/components/test_results_display.py ║ Display plots and results ║ M

- [ ] 4.3.1: Create results display module
  - Create `emuses/gui/utils/result_formatter.py`
  - Implement plot loading and display
  - Support matplotlib figures → Gradio
  - Support plotly figures → Gradio
- [ ] 4.3.2: Add results panel to pipeline tab
  - gr.Accordion(label="Results", open=True)
  - gr.Gallery for multiple plots
  - gr.Dataframe for metrics/statistics
  - gr.File for downloadable outputs
- [ ] 4.3.3: Implement result auto-display
  - After pipeline completion, scan output folder
  - Load and display generated plots
  - Show summary statistics
  - Provide download links for all outputs
- [ ] 4.3.4: Write tests
  - Test: Plot loading (matplotlib, plotly)
  - Test: Result discovery from output folder
  - Test: Download link generation
  - Run: `pytest tests/gui/components/test_results_display.py -xvs`

### Task 4.4: Help & Documentation ║ No test file ║ Tooltips and help text ║ S

- [ ] 4.4.1: Add parameter tooltips
  - Use gr.components `info` parameter for tooltips
  - Extract help text from CLI parameter help strings
  - Add to all parameters
- [ ] 4.4.2: Add help tab
  - Create gr.Markdown tab with usage guide
  - Include quick start guide
  - Link to full documentation
  - Include troubleshooting tips
- [ ] 4.4.3: Add validation hints
  - Real-time validation feedback
  - Show expected formats for inputs
  - Display validation errors near relevant fields

---

## Phase 5: Testing, Polish & Deployment (2-3 days)

### Task 5.1: Cross-Platform Testing ║ No test file ║ Manual testing on Linux/Mac/Windows ║ M

- [ ] 5.1.1: Test on Linux
  - Install EMUSES + GUI
  - Run all interfaces (pipeline, inference, models)
  - Test file uploads (various formats and sizes)
  - Verify results display correctly
- [ ] 5.1.2: Test on macOS (if available)
  - Same tests as Linux
  - Verify path handling (no platform-specific issues)
- [ ] 5.1.3: Test on Windows (if available)
  - Same tests as Linux
  - Verify Windows path handling (backslashes, drive letters)
  - Test with WSL paths if applicable

### Task 5.2: Performance & Large File Testing ║ No test file ║ Verify handles large datasets ║ M

- [ ] 5.2.1: Test large file uploads
  - Upload 1GB NIfTI file
  - Upload 5GB dataset
  - Verify no timeout issues
  - Verify memory usage reasonable
- [ ] 5.2.2: Test long-running pipelines
  - Run pipeline on realistic dataset (30+ minutes)
  - Verify progress updates throughout
  - Verify no Gradio timeout (no default timeout set)
  - Verify memory cleanup after completion
- [ ] 5.2.3: Test concurrent users
  - Open 3-5 browser tabs
  - Start pipelines in each
  - Verify all execute without interference
  - Check for race conditions or deadlocks

### Task 5.3: Error Handling & Edge Cases ║ tests/gui/test_error_handling.py ║ Comprehensive error scenarios ║ M

- [ ] 5.3.1: Test invalid inputs
  - Invalid file formats
  - Non-existent paths
  - Invalid parameter values (negative numbers, etc.)
  - Verify user-friendly error messages
- [ ] 5.3.2: Test missing dependencies
  - Model file not found
  - Output folder not writable
  - Verify graceful degradation
- [ ] 5.3.3: Test pipeline failures
  - Simulate UMAP failure
  - Simulate clustering failure
  - Verify error reported to user
  - Verify partial results available if possible
- [ ] 5.3.4: Write error handling tests
  - Test each error scenario
  - Verify error messages are clear
  - Run: `pytest tests/gui/test_error_handling.py -xvs`

### Task 5.4: Documentation ║ No test file ║ User and deployment docs ║ M

- [ ] 5.4.1: Write user documentation
  - Create `docs/user_guide/gui_interface.md`
  - Quick start guide (5 minutes to first run)
  - Parameter reference
  - Common workflows
  - Troubleshooting section
- [ ] 5.4.2: Write deployment documentation
  - Create `docs/deployment/gui_deployment.md`
  - Local desktop usage: `python -m emuses.gui.app`
  - Lab server deployment: `--server-name 0.0.0.0 --server-port 7860`
  - Docker deployment instructions (if Docker support added)
  - Security considerations for shared deployment
- [ ] 5.4.3: Update main README
  - Add GUI section to README.md
  - Include screenshot/demo GIF (optional)
  - Link to GUI documentation

### Task 5.5: Code Quality & Cleanup ║ No test file ║ Linting, docstrings, final polish ║ S

- [ ] 5.5.1: Run Flake8 linting
  - Run: `flake8 emuses/gui/`
  - Fix all violations (max-complexity 10)
  - Ensure clean output
- [ ] 5.5.2: Add NumPy-style docstrings
  - Document all public functions and classes
  - Include Parameters, Returns, Examples sections
  - Verify docstring completeness
- [ ] 5.5.3: Run full test suite
  - Run: `pytest tests/gui/ -xvs`
  - Verify all tests pass
  - Check test coverage: `pytest tests/gui/ --cov=emuses/gui --cov-report=term-missing`
  - Aim for >80% coverage
- [ ] 5.5.4: Final integration test
  - Run full pipeline via GUI with realistic data
  - Run inference via GUI
  - Browse models via GUI
  - Verify all features working end-to-end

---

## Acceptance Criteria Mapping

### MVP Criteria (Week 1)
- [x] Task 1.3: Basic pipeline interface (full command) with file upload
- [x] Task 1.3.2: Required parameters: input dataset, output folder
- [x] Task 1.3.3: Basic optional parameters in expandable accordions
- [x] Task 1.3.5: Run button with async execution (no timeout)
- [x] Task 1.2: Real-time progress tracking
- [x] Task 1.3.5: Results download functionality
- [x] Task 5.3: Error handling with clear user messages
- [x] Task 5.1: Works on Linux, Mac, Windows without configuration changes

### Full Version Criteria (Weeks 2-3)
- [x] Task 4.1: All ~97 CLI parameters accessible via organized accordions
- [x] Task 2.2: Inference interface with model selection (file path or registry ID)
- [x] Task 3.1: Model browser interface (list, search, view metadata)
- [x] Task 4.2: Parameter presets for common workflows
- [x] Task 4.3: Results visualization (embeddings, heatmaps, clusters)
- [x] Task 4.2: Configuration save/load functionality
- [x] Task 4.4: Help text and tooltips for parameters
- [x] Task 4.3: Responsive design for different screen sizes (Gradio default)

### Quality Indicators
- [x] Task 1.3: < 100 lines of code for MVP interface
- [x] All phases: Zero platform-specific code (pure Python)
- [x] Task 5.1: Same behavior on Linux, Mac, Windows
- [x] Task 1.4.2: < 2 second startup time (Gradio default)
- [x] Gradio default: < 1 second response time for parameter changes
- [x] Task 5.2.1: Handles 5GB+ file uploads without issues
- [x] Task 5.2.3: Supports concurrent users (3-5 simultaneous jobs)
- [x] Task 5.3: Clear error messages for validation failures

---

## Risk Mitigation Tasks

### Large File Upload Failures
- **Mitigation**: Task 5.2.1 - Test with 5GB+ files
- **Strategy**: Use Gradio's built-in file handling (tested by community)

### Long-Running Job Issues
- **Mitigation**: Task 5.2.2 - Test 30+ minute pipelines
- **Strategy**: No default timeouts, Gradio queue handles background execution
- **Note**: Variable processing time depends on data, cannot enforce fixed timeout

### Parameter Validation Complexity
- **Mitigation**: Task 1.1 - Reuse CLI validation logic
- **Strategy**: Call existing validation functions, don't reimplement

### Cross-Platform Path Issues
- **Mitigation**: Task 5.1 - Test on all platforms
- **Strategy**: Use pathlib throughout, test with platform-specific paths

### Memory Issues with Large Datasets
- **Mitigation**: Task 5.2.2 - Monitor memory usage
- **Strategy**: Implement cleanup in pipeline completion callback

### User Confusion with Many Parameters
- **Mitigation**: Task 4.1 - Progressive disclosure with accordions
- **Strategy**: Required params visible, optional in logical groups

---

## Testing Strategy

### Unit Tests (Component-Aware)
- **Adapters** (Unit): parameter_mapper, progress_adapter, registry_adapter
- **Utils** (Unit): presets, result_formatter, validation
- **No business logic duplication**: Reuse existing CLI validation

### Integration Tests
- **Components** (Integration): pipeline_tab, inference_tab, models_tab
- **End-to-end** (Integration): mvp_integration, inference_integration, error_handling

### Manual Testing
- **Cross-platform**: Linux, Mac, Windows (Task 5.1)
- **Performance**: Large files, long pipelines, concurrent users (Task 5.2)
- **User workflows**: Complete workflows from upload to results download

### Coverage Target
- **Goal**: >80% coverage for new GUI code
- **Focus**: Adapters and utils (business logic wrappers)
- **Exclude**: UI layout code (Gradio components)

---

## Milestone Checkpoints

### Milestone 1: MVP Complete (End of Phase 1)
- [ ] Basic pipeline interface functional
- [ ] Can upload data and run full pipeline
- [ ] Progress tracking works
- [ ] Results downloadable
- **User Decision**: Review MVP, approve Phase 2 start

### Milestone 2: Core Features Complete (End of Phase 3)
- [ ] Inference interface functional
- [ ] Model browser functional
- [ ] All core workflows working
- **User Decision**: Approve advanced features or adjust scope

### Milestone 3: Feature Complete (End of Phase 4)
- [ ] All 97 parameters accessible
- [ ] Presets working
- [ ] Results visualization complete
- **User Decision**: Approve final testing phase

### Milestone 4: Production Ready (End of Phase 5)
- [ ] All tests passing
- [ ] Cross-platform verified
- [ ] Documentation complete
- [ ] Code quality standards met
- **User Decision**: Approve merge to main branch

---

## Implementation Notes

### No Core Code Modifications
- **Guaranteed**: All existing CLI and pipeline code remains unchanged
- **Pattern**: Thin wrapper that calls existing async functions
- **Validation**: Reuse existing CLI validation logic
- **Integration**: Import and call, don't duplicate

### No Default Timeouts
- **Rationale**: Processing time highly variable based on data size and complexity
- **Strategy**: Gradio queue handles long-running jobs without timeout
- **Implementation**: `interface.queue()` without max_size or default_concurrency_limit
- **User Control**: Users can cancel via browser if needed

### Gradio Queue Configuration
```python
# In emuses/gui/app.py
interface.queue(
    # NO max_size - allow unlimited queue
    # NO default_concurrency_limit - let Gradio manage
    # NO api_open - keep API closed for security
)
interface.launch(
    server_name=args.server_name,
    server_port=args.server_port,
    share=args.share
)
```

### Progress Tracking Without Timeout
```python
# Progress updates continue indefinitely until completion
def run_pipeline_with_progress(progress=gr.Progress()):
    # No timeout parameter
    for stage in stages:
        progress(stage.progress, desc=stage.name)
        # Continue until complete, regardless of time
```

---

**Plan Created**: 2025-10-08
**Branch**: feature/web-gui-gradio
**Next**: Begin Phase 0 implementation
