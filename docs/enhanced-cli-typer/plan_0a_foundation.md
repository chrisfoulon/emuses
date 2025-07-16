# Enhanced CLI Typer - Plan 0a: Foundation

## Sub-Plan Focus
Core CLI structure, backward compatibility analysis, and service integration foundation.

## Tasks (3 tasks, 15 sub-tasks)

- [x] Task 1 ║ tests/enhanced-cli-typer/test_argument_compatibility.py ║ Backward compatibility analysis and legacy CLI mapping ║ L
  - [x] 1.1 Map all legacy argparse arguments to Typer equivalents
  - [x] 1.2 Preserve argument validation rules and error messages  
  - [x] 1.3 Maintain exact command-line interface and exit codes
  - [x] 1.4 Test argument parsing edge cases and special values
  - [x] 1.5 Validate file path handling and cross-platform compatibility

- [x] Task 2 ║ tests/enhanced-cli-typer/test_cli_core.py ║ Core Typer CLI structure with security hardening ║ L
  - [x] 2.1 Create basic Typer application with modular command structure
  - [x] 2.2 Implement five main commands (full, umap, clustering, heatmap, prediction)
    - [x] 2.2.1 Create command signatures with proper argument parsing
    - [x] 2.2.2 Connect commands to EMUSESPipeline class
    - [x] 2.2.3 Add argument validation and conversion logic
    - [x] 2.2.4 Implement error handling and user feedback
  - [x] 2.3 Add argument parsing with Typer decorators and type hints
  - [x] 2.4 Implement secure path resolution with directory traversal protection
  - [x] 2.5 Add help text, command descriptions, and input sanitization
  - [x] 2.6 Integrate service client for pipeline execution
    - [x] 2.6.1 Add service client to command context
    - [x] 2.6.2 Implement service/local execution fallback
    - [x] 2.6.3 Add service health checking and startup

- [x] Task 3 ║ tests/enhanced-cli-typer/test_service_client.py ║ FastAPI service HTTP client with robust error handling ║ M
  - [x] 3.1 Create HTTP client class with connection pooling and circuit breaker
  - [x] 3.2 Implement job submission methods with API versioning support
  - [x] 3.3 Add job status polling with rate limiting and concurrent handling
  - [x] 3.4 Handle service startup/shutdown with offline fallback mode
  - [x] 3.5 Implement comprehensive error handling, retry logic, and timeout management
  - [x] 3.6 Integration with CLI commands (moved from Task 2.6)

## Dependencies
- **Prerequisites**: None (foundation layer)
- **Deliverables**: Working CLI with backward compatibility and robust service client
- **Context Updates**: Establishes CLI architecture patterns and service integration model

## Success Criteria
- ✅ 100% argument compatibility with legacy CLI validated (Task 1 complete)
- ✅ Secure CLI core with modular architecture (Task 2: FULLY FUNCTIONAL commands with pipeline integration)
- ✅ Robust service client with fallback mechanisms (Task 3 complete and INTEGRATED)
- ✅ All foundation tests passing with >90% coverage (Core functionality verified)

## Critical Issues RESOLVED ✅:
1. ✅ **CLI Commands are FUNCTIONAL**: All commands execute real pipelines with service/local fallback
2. ✅ **Service Client INTEGRATED**: ServiceHTTPClient used by all CLI commands with health checks
3. ✅ **Pipeline Integration COMPLETE**: Full connection to EMUSESPipeline class with proper argument mapping
4. ✅ **Rich Features INTEGRATED**: StatusRenderer, ProgressTracker used by CLI commands
