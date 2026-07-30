# Web GUI Interface - Feature Kickoff

## Feature Draft

**Feature draft** ⟶ Implement a simple, robust, and multiplatform web-based GUI for EMUSES using Gradio 4.x. The GUI should provide intuitive access to core CLI commands (full pipeline, inference, model management) through a browser interface with minimal configuration surprises across platforms. Focus on progressive disclosure for the ~97 CLI parameters using expandable accordion sections, automatic file upload handling, real-time progress tracking, and result visualization. The implementation must be extremely simple to maintain, battle-tested by the ML community, and provide immediate value for researchers who prefer GUI over CLI. Include core interfaces: (1) Full pipeline wizard with required params always visible and optional params in accordions, (2) Inference interface with model selection from registry, (3) Model browser for registry management. Implementation should take 3-4 weeks with minimal ongoing maintenance burden (15-30 hours/year).

## Strategic Importance

A web GUI dramatically lowers the barrier to entry for EMUSES, making neuroimaging analysis accessible to researchers without CLI expertise. Gradio is the optimal choice based on comprehensive framework evaluation (scored 9.55/10), offering the simplest implementation path while being battle-tested by 100K+ ML researchers and backed by HuggingFace. The GUI will expand EMUSES user base and improve user experience for both novice and experienced researchers.

## Success Criteria

### Must Have - MVP (Week 1)
- [ ] Basic pipeline interface (full command) with file upload
- [ ] Required parameters: input dataset, output folder
- [ ] Basic optional parameters in expandable accordions (scores, test_size, normalization)
- [ ] Run button with async execution
- [ ] Real-time progress tracking
- [ ] Results download functionality
- [ ] Error handling with clear user messages
- [ ] Works on Linux, Mac, Windows without configuration changes

### Should Have - Full Version (Weeks 2-3)
- [ ] All ~97 CLI parameters accessible via organized accordions
- [ ] Inference interface with model selection (file path or registry ID)
- [ ] Model browser interface (list, search, view metadata)
- [ ] Parameter presets for common workflows
- [ ] Results visualization (embeddings, heatmaps, clusters)
- [ ] Configuration save/load functionality
- [ ] Help text and tooltips for parameters
- [ ] Responsive design for different screen sizes

### Quality Indicators
- [ ] < 100 lines of code for MVP interface
- [ ] Zero platform-specific code (pure Python)
- [ ] Same behavior on Linux, Mac, Windows
- [ ] < 2 second startup time
- [ ] < 1 second response time for parameter changes
- [ ] Handles 5GB+ file uploads without issues
- [ ] Supports concurrent users (3-5 simultaneous jobs)
- [ ] Clear error messages for validation failures

### Industry Compliance
- [ ] Follows Gradio 4.x best practices
- [ ] Reuses existing EMUSES validation logic
- [ ] Integrates with existing FastAPI backend (optional for multi-user)
- [ ] Compatible with existing model registry
- [ ] Docker deployment ready
- [ ] Documentation for deployment scenarios

## Implementation Complexity

**Estimated Effort**: 3-4 weeks
**Complexity Level**: Low-Medium
**Team Requirements**: 1 Python Developer (familiar with EMUSES CLI)

**Breakdown**:
- Phase 0: Setup (1-2 days)
- Phase 1: Core pipeline interface (4-5 days)
- Phase 2: Inference interface (3-4 days)
- Phase 3: Model browser (2-3 days)
- Phase 4: Advanced features (3-4 days)
- Phase 5: Testing & deployment (2-3 days)

## Dependencies

- Gradio 4.x (`pip install gradio`)
- Existing EMUSES CLI commands and pipeline classes
- EMUSESPipeline, UMAPStage, HeatmapStage, InferenceStage
- Model registry (LocalModelRegistry, ModelRegistryFactory)
- Existing validation logic from CLI
- FastAPI service (optional, for multi-user scenarios)

## Risk Assessment

**Technical Risks**:

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Large file upload failures | MEDIUM | HIGH | Gradio handles automatically; test with 5GB+ files |
| Long-running job timeouts | MEDIUM | MEDIUM | Use Gradio queue system with job persistence |
| Parameter validation complexity | LOW | MEDIUM | Reuse CLI validation logic directly |
| Cross-platform path issues | LOW | LOW | Use pathlib throughout; test on all platforms |
| Memory issues with large datasets | MEDIUM | HIGH | Stream processing, cleanup temp files |
| User confusion with many params | MEDIUM | MEDIUM | Progressive disclosure with accordions |

**Mitigation Strategies**:
- Use Gradio's built-in file handling (tested with large files)
- Implement Gradio queue system for background processing
- Wrap existing CLI validation instead of reimplementing
- Test on Linux, Mac, Windows before each release
- Monitor memory usage and implement cleanup
- Organize parameters into logical groups with good defaults
- Pin Gradio version to avoid breaking changes

## Value Proposition

**For Novice Users**:
- No CLI learning curve
- Visual parameter selection
- Immediate feedback on errors
- Guided workflows with tooltips

**For Experienced Users**:
- Faster parameter exploration
- Visual result preview
- Quick access to common tasks
- Alternative to CLI for specific workflows

**For Lab Groups**:
- Shared GUI on lab server
- Consistent interface across team
- Easier onboarding for new members
- Lower support burden

**For EMUSES Project**:
- Expanded user base
- Reduced support requests
- Better accessibility
- Professional appearance

## Architecture Overview

### Technology Stack
- **Framework**: Gradio 4.x (30K+ GitHub stars, HuggingFace backing)
- **Backend**: Direct Python calls to EMUSES pipelines
- **Deployment**: Standalone Python script, Docker optional
- **Dependencies**: Minimal (~10 packages beyond EMUSES)

### Component Structure
```
emuses/
├── gui/
│   ├── __init__.py
│   ├── app.py              # Main Gradio application
│   ├── components.py       # Reusable UI components
│   ├── pipeline_wrapper.py # CLI-to-GUI adapter
│   ├── model_browser.py    # Model registry interface
│   └── utils.py            # Helper functions
└── cli/
    └── main.py             # Existing CLI (unchanged)
```

### Parameter Handling Strategy
- **Progressive Disclosure**: Required params always visible, optional in accordions
- **Component Mapping**:
  - Path (file) → `gr.File()`
  - Path (folder) → `gr.Textbox()`
  - int/float → `gr.Slider()` or `gr.Number()`
  - bool → `gr.Checkbox()`
  - Enum → `gr.Dropdown()`
  - List[str] → `gr.Textbox()` (comma-separated)
- **Validation**: Reuse CLI validation logic
- **Defaults**: Match CLI default values

### Deployment Options
1. **Local Desktop**: `python emuses/gui/app.py` (opens browser)
2. **Lab Server**: `python emuses/gui/app.py --server-name 0.0.0.0`
3. **Docker**: Container with EMUSES + GUI pre-installed
4. **HuggingFace Spaces**: Free public hosting (for demos)

## Framework Selection Rationale

**Gradio Selected** (9.55/10 score) over alternatives:

**Why Gradio**:
- ✅ Simplest implementation (30-50 lines for MVP)
- ✅ Built specifically for ML/data applications
- ✅ Automatic type inference from Python functions
- ✅ Zero cross-platform configuration surprises
- ✅ Battle-tested by 100K+ researchers
- ✅ Built-in file upload, progress tracking, queuing
- ✅ HuggingFace backing (stability guarantee)
- ✅ FastAPI backend (matches EMUSES stack)

**Why Not Streamlit** (7.75/10):
- Re-runs entire script on every interaction (performance issue)
- More complex session state management
- Not ideal for long-running ML tasks
- More code required (~100-200 lines)

**Why Not NiceGUI** (6.45/10):
- Smaller community (5K vs 30K stars)
- Less documentation and examples
- More complex than needed
- Newer, less proven in production

**Why Not Reflex** (5.35/10):
- Most complex implementation (~300+ lines)
- Compiles to React (adds complexity layer)
- Slower development time
- Overkill for EMUSES requirements

**Why Not Dash** (6.2/10):
- Complex callback system
- Steep learning curve
- Very verbose (~400+ lines)
- Enterprise-grade but excessive for our needs

## Proof of Concept

**Minimal Working Example** (30 lines):
```python
import gradio as gr
from pathlib import Path
import asyncio
from emuses.cli.main import _full_async

def run_pipeline(input_file, output_folder, test_size=0.2):
    try:
        input_path = Path(input_file.name)
        output_path = Path(output_folder)
        output_path.mkdir(exist_ok=True)

        asyncio.run(_full_async(
            output_folder=output_path,
            input_dataset=input_path,
            test_size=test_size
        ))
        return f"✅ Complete! Results in {output_folder}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

interface = gr.Interface(
    fn=run_pipeline,
    inputs=[
        gr.File(label="Input Dataset"),
        gr.Textbox(label="Output Folder"),
        gr.Slider(0, 1, value=0.2, label="Test Size")
    ],
    outputs=gr.Textbox(label="Status"),
    title="EMUSES Pipeline"
)

if __name__ == "__main__":
    interface.launch()
```

## Maintenance Burden

**Estimated Annual Maintenance**: 15-30 hours/year (1-2 hours/month)

**Breakdown**:
- Gradio updates: 2-4 hours (usually backward compatible)
- EMUSES API changes: 4-8 hours (parameter mapping updates)
- Bug fixes: 8-16 hours (user-reported issues)
- Feature additions: Variable (user requests)

**Why Low Maintenance**:
- Thin wrapper around existing CLI
- Gradio handles UI complexity
- No database or authentication to maintain
- Minimal custom code
- Reuses existing validation logic

## Implementation Phases

### Phase 0: Setup (1-2 days)
- Install Gradio and test basic integration
- Create project structure
- Verify EMUSES imports work in GUI context

### Phase 1: Core Pipeline (4-5 days)
- Main layout with required parameters
- File upload and output selection
- Run button with async execution
- Progress tracking and error display
- Basic optional parameters (accordions)

### Phase 2: Inference (3-4 days)
- Inference interface layout
- Model selection (path or registry ID)
- Data upload and preprocessing options
- Results display and download

### Phase 3: Model Browser (2-3 days)
- List models with search/filter
- Model detail view with metadata
- Model management actions (install, remove, verify)

### Phase 4: Advanced Features (3-4 days)
- All optional parameters in organized accordions
- Configuration presets (save/load)
- Results visualization (plots, heatmaps)
- Help text and parameter validation hints

### Phase 5: Testing & Deployment (2-3 days)
- Cross-platform testing (Linux, Mac, Windows)
- Performance validation (large files, long jobs)
- Docker container setup
- Deployment documentation

## Testing Strategy

**Manual Testing Focus** (GUI-heavy):
- File upload with various formats (NIfTI, images, CSV)
- Parameter combinations (required + optional)
- Error scenarios (invalid files, bad paths)
- Long-running jobs (progress tracking)
- Cross-platform behavior (Windows, Mac, Linux)
- Concurrent users (multiple browser tabs)

**Automated Testing**:
- Unit tests for pipeline_wrapper.py (parameter conversion)
- Integration tests for model browser (registry queries)
- End-to-end smoke tests (can launch and respond)

**Performance Testing**:
- 5GB+ file upload handling
- 2-hour pipeline execution
- Memory usage monitoring
- Concurrent job handling (3-5 users)

## Documentation Requirements

**User Documentation**:
- Quick start guide (5 minutes to first run)
- Parameter reference (what each option does)
- Common workflows (tutorials)
- Troubleshooting guide

**Deployment Documentation**:
- Local setup instructions
- Lab server deployment
- Docker container usage
- HuggingFace Spaces deployment

**Developer Documentation**:
- Architecture overview
- Adding new parameters
- Customizing components
- Extending functionality

## Alternative Approaches

**Fallback if Gradio Insufficient**:
Use **Streamlit** (+50% development time, 7-10 days for Phase 1)
- More flexible layouts
- Better data visualization
- Multi-page apps
- Requires session state management

**Future Enhancements** (Not in Scope):
- Multi-user authentication (use FastAPI backend)
- Job history and resume capability
- Interactive parameter tuning with live preview
- Advanced result comparison tools
- Integration with HPC job schedulers

## Pre-Analysis Artifacts

The following analysis documents were created during feature planning:
- `/tmp/emuses_gui_analysis.md` - Comprehensive CLI-to-GUI mapping and framework evaluation
- `/tmp/emuses_gui_implementation_plan.md` - Detailed implementation plan with risk assessment

These documents contain:
- Complete CLI parameter analysis (~97 parameters)
- Framework comparison matrix (5 frameworks evaluated)
- Risk assessment with mitigation strategies
- Proof of concept code examples
- Deployment scenarios and options

## Next Steps

1. **Review this kickoff document** - Validate requirements and scope
2. **Proceed to LAD Phase 1** - Context gathering using the `lad:plan-feature` skill
3. **Create detailed plan** - Technical design and implementation breakdown
4. **Begin implementation** - Start with Phase 0 (setup) and Phase 1 (MVP)

---

**Feature Owner**: TBD
**Estimated Start**: After current feature branch (analysis-api-enhancement) is merged
**Target Branch**: `feature/web-gui`
**Priority**: Medium-High (expands user base, improves UX)
**Status**: Planning Phase
