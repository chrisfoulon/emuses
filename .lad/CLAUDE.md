# Project Context for Claude Code LAD Framework

## Architecture Overview
*Auto-updated by LAD workflows - current system understanding*

## Project Mission
**EMUSES** is a predictive modeling tool for neuroimaging research enabling:
- **Individual Researchers**: Local model development and analysis
- **Research Labs**: Collaborative model sharing with workspace isolation  
- **Scientific Community**: Public model registry with peer review and benchmarking

## Status Maintenance Protocol
**CRITICAL**: Always read and update `PROJECT_STATUS.md` when:
- Starting new development sessions
- Completing major tasks or features
- Moving between development phases

**Current Status**: See `PROJECT_STATUS.md` for authoritative project status and next priorities.

## Code Style Requirements
- **Docstrings**: NumPy-style required for all functions/classes
- **Linting**: Flake8 compliance (max-complexity 10)
- **Testing**: TDD approach, component-aware strategies
- **Coverage**: 90%+ target for new code

## Communication Guidelines
**Objective, European-Style Communication**:
- **Avoid excessive enthusiasm**: Replace "brilliant!", "excellent!", "perfect!" with measured language
- **Scientific tone**: "This approach has merit" instead of "That's a great idea!"
- **Honest criticism**: State problems directly - "This approach has significant limitations" vs hedging
- **Acknowledge uncertainty**: "I cannot verify this will work" vs "This should work fine"
- **Balanced perspectives**: Present trade-offs rather than unqualified endorsements
- **Focus on accuracy**: Prioritize correctness over making user feel good about ideas

## Maintenance Integration Protocol
**Technical Debt Management**:
- **Boy Scout Rule**: Leave code cleaner than found when possible
- **Maintenance Registry**: Track and prioritize technical debt systematically
- **Impact-based cleanup**: Focus on functional issues before cosmetic ones
- **Progress tracking**: Update both TodoWrite and plan.md files consistently

## Testing Strategy Guidelines
- **API Endpoints**: Integration testing (real app + mocked external deps)
- **Business Logic**: Unit testing (complete isolation + mocks)
- **Data Processing**: Unit testing (minimal deps + test fixtures)

## Test Coverage Enhancement Strategy (Evidence-Based)

### Current Achievement: Research Software Excellence
- **Coverage**: 47.1% line coverage - **EXCEEDS research software standards** (30-60% typical)
- **Critical Systems**: 70-100% coverage (Security, Model Registry, Integration)
- **Standards Compliance**: NIH research software guidelines met with focus on reproducibility

### Future Production Enhancement Targets
- **Overall Target**: 60% coverage (balanced for scientific software context)
- **Critical Components**: 80%+ coverage (Security/Auth, Model Registry Core, Data Pipelines)
- **Standard Components**: 60% coverage (CLI, Configuration, Utilities)
- **Priority**: After HeatmapStage development and comprehensive feature testing

### Evidence-Based Rationale
- **Research Analysis**: Comprehensive review of NIH, academic research, and industry standards
- **EMUSES Context**: Neuroimaging research tool (discovery focus, not safety-critical)
- **Resource Balance**: Quality over quantity approach for solo programmer efficiency
- **Implementation Strategy**: Systematic improvement plan documented in model registry plan

## Current Architecture Patterns

### Model Registry Integration (Phase 4.1 ✅)
- **Factory Pattern**: ModelRegistryFactory for cross-mode registry creation
- **Unified Interface**: BaseModelRegistry with consistent signatures across LOCAL/DATABASE/CLOUD
- **Flexible Parameters**: Methods support both old and new calling patterns
- **Auto-Detection**: Deployment mode detection with fallback logic

## Project Structure Patterns
*Learned from exploration - common patterns and conventions*

### Documentation Organization
- **docs/**: User-facing documentation (API_REFERENCE.md, USER_GUIDE.md, model-registry user guides)
- **dev-docs/**: Internal development documentation (project plans, contexts, issue tracking)

## Current Feature Progress
*TodoWrite integration status and cross-session state*

## Quality Metrics Baseline
- Test count: *tracked across sessions*
- Coverage: *baseline and current*
- Complexity: *monitored for regression*

## Common Gotchas & Solutions
*Accumulated from previous implementations*

### Token Optimization for Large Codebases
**Standard test commands:**
- **Large test suites**: Use `2>&1 | tail -n 100` for pytest commands to capture only final results/failures
- **Coverage reports**: Use `tail -n 150` for comprehensive coverage output to include summary
- **Keep targeted tests unchanged**: Single test runs (`pytest -xvs`) don't need redirection

**Long-running commands (>2 minutes):**
- **Pattern**: `<command> 2>&1 | tee full_output.txt | grep -iE "(warning|error|failed|exception|fatal|critical)" | tail -n 30; echo "--- FINAL OUTPUT ---"; tail -n 100 full_output.txt`
- **Use cases**: Package installs, builds, data processing, comprehensive test suites, long compilation
- **Benefits**: Captures warnings/errors from anywhere in output, saves full output for detailed review, prevents token explosion
- **Case-insensitive**: Catches `ERROR`, `Error`, `error`, `WARNING`, `Warning`, `warning`, etc.

**Rationale**: Large codebases can generate massive output consuming significant Claude Pro allowance. Enhanced pattern ensures critical information isn't missed while optimizing token usage.

## Integration Patterns
*How components typically connect in this codebase*

## Cross-Session Integration Tracking
*Maintained across LAD sessions to prevent duplicate implementations*

### Active Implementations
*Current state of system components and their integration readiness*

| Component | Status | Integration Points | Last Updated |
|-----------|--------|--------------------|--------------|
| Model Registry Factory | Production Ready | Cross-mode compatibility | 2025-08-19 |
| Progressive Disclosure Docs | Complete | MkDocs Material integration | 2025-08-19 |
| FastAPI Documentation Serving | Production Ready | Development environment integration | 2025-08-19 |

### Integration Decisions Log
*Historical decisions to guide future development*

| Feature | Decision | Strategy | Rationale | Session Date | Outcome |
|---------|----------|----------|-----------|--------------|---------|
| Model Registry Factory | Single endpoints file | Unified interface across modes | Cross-mode compatibility | 2025-08-17 | Cross-mode compatibility ✅ |
| User Isolation Strategy | Ownership validation helpers | Shared `_get_user_*` functions | Consistent security boundaries | 2025-08-17 | Consistent security boundaries ✅ |
| API Schema Strategy | Separate Create/Update/Read schemas | Different Pydantic models per operation | Clean API design | 2025-08-17 | Clean API design ✅ |
| Registry Deployment Mode | Auto-detection with fallback | Factory pattern with mode validation | Seamless mode transitions | 2025-08-17 | Seamless mode transitions ✅ |
| Caching Strategy | In-memory cache with TTL/LRU | ModelRegistryCache with user isolation | Query performance optimization | 2025-08-17 | Query performance optimization ✅ |
| Storage Management UX | Enhanced visibility and reporting | StorageManager with model breakdown and suggestions | Improved user awareness | 2025-08-17 | Improved user awareness ✅ |
| Database Query Optimization | Strategic indexes + performance monitoring | DatabaseIndexOptimizer with 9 composite indexes | Query performance optimization | 2025-08-17 | Query performance optimization ✅ |

### Pending Integration Tasks
*Cross-session work that needs completion*

- Analysis API Enhancement: Expose `run_kernel_heatmap_analysis()` and `run_heatmap_analysis()` functions

### Architecture Evolution Notes
*Key architectural changes that affect future integration decisions*

- Progressive disclosure documentation system established with MkDocs Material
- Clear separation of user-facing docs/ vs internal dev-docs/ established
- LAD framework compliance restored with static guidelines vs dynamic project tracking

### Integration Anti-Patterns Avoided
*Documentation of duplicate implementations prevented*

- Mixed static guidelines with dynamic project tracking in LAD CLAUDE.md (resolved 2025-08-19)
- Incorrect docs/ references for internal development documentation (resolved 2025-08-19)

---
*Last updated by Claude Code LAD Framework - 2025-08-19*