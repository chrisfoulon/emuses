# Project Context for Claude Code LAD Framework

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
- Avoid excessive enthusiasm - use measured language
- Scientific tone: "This approach has merit" vs "That's a great idea!"
- State problems directly - honest criticism over hedging
- Acknowledge uncertainty: "I cannot verify this will work"
- Present trade-offs rather than unqualified endorsements
- Focus on accuracy over making user feel good

## Current Architecture Patterns

### Model Registry Integration (Phase 4.1 ✅)
- **Factory Pattern**: ModelRegistryFactory for cross-mode registry creation
- **Unified Interface**: BaseModelRegistry with consistent signatures across LOCAL/DATABASE/CLOUD
- **Flexible Parameters**: Methods support both old and new calling patterns
- **Auto-Detection**: Deployment mode detection with fallback logic

### Testing Strategy Guidelines
- **API Endpoints**: Integration testing (real app + mocked external deps)
- **Business Logic**: Unit testing (complete isolation + mocks)
- **Data Processing**: Unit testing (minimal deps + test fixtures)

### Token Optimization for Large Codebases
**Standard test commands:**
- **Large test suites**: Use `2>&1 | tail -n 100` for pytest to capture only final results
- **Coverage reports**: Use `tail -n 150` for comprehensive coverage summary
- **Targeted tests**: Single test runs (`pytest -xvs`) don't need redirection

**Long-running commands (>2 minutes):**
- **Pattern**: `<command> 2>&1 | tee full_output.txt | grep -iE "(warning|error|failed|exception)" | tail -n 30; echo "--- FINAL OUTPUT ---"; tail -n 100 full_output.txt`
- **Rationale**: Captures critical information while optimizing token usage

## Key Integration Decisions (Current Architecture)

| Component | Decision | Strategy | Impact |
|-----------|----------|----------|---------|
| Model Registry Factory | Single endpoints file | Unified interface across modes | Cross-mode compatibility ✅ |
| User Isolation Strategy | Ownership validation helpers | Shared `_get_user_*` functions | Consistent security boundaries ✅ |
| API Schema Strategy | Separate Create/Update/Read schemas | Different Pydantic models per operation | Clean API design ✅ |
| Registry Deployment Mode | Auto-detection with fallback | Factory pattern with mode validation | Seamless mode transitions ✅ |

## Active Development Context

**Current Branch**: `feature/model-registry`
**Active Phase**: Phase 4.2 - Cross-Mode Compatibility
**Next Implementation**: ModelMigrator class, export/import utilities, configuration management

**Recent Completion**: Phase 4.1 Unified Registry Interface
- ✅ ModelRegistryFactory with auto-detection
- ✅ BaseModelRegistry interface consistency
- ✅ LocalModelRegistry refactored (eliminated 200+ lines boilerplate)
- ✅ Enhanced CLI with cross-mode parameters
- ✅ 38/38 tests passing with backward compatibility

## Common Commands
- **CLI**: `python -m emuses.cli` (not `python -m emuses`)
- **Test Model Registry**: `pytest tests/model_registry/test_local_registry.py -xvs`
- **Test Integration**: `pytest tests/integration/test_unified_interface.py -xvs`
- **Coverage**: `pytest --cov=emuses --cov-report=term-missing`

---
*Last Updated: 2025-08-11 - Streamlined for token efficiency*
*Historical details archived in `docs/project-history/`*