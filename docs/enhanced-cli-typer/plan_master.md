# Enhanced CLI with Typer - TDD Implementation Plan (Complete Master Plan)

- [x] Task 1 ║ tests/enhanced-cli-typer/test_argument_compatibility.py ║ Backward compatibility analysis and legacy CLI mapping ║ L
  - [x] 1.1 Map all legacy argparse arguments to Typer equivalents
  - [x] 1.2 Preserve argument validation rules and error messages  
  - [x] 1.3 Maintain exact command-line interface and exit codes
  - [x] 1.4 Test argument parsing edge cases and special values
  - [x] 1.5 Validate file path handling and cross-platform compatibility

- [x] Task 2 ║ tests/enhanced-cli-typer/test_cli_core.py ║ Core Typer CLI structure with security hardening ║ L
  - [x] 2.1 Create basic Typer application with modular command structure
  - [x] 2.2 Implement five main commands (full, umap, clustering, heatmap, prediction)
  - [x] 2.3 Add argument parsing with Typer decorators and type hints
  - [x] 2.4 Implement secure path resolution with directory traversal protection
  - [x] 2.5 Add help text, command descriptions, and input sanitization

- [ ] Task 3 ║ tests/enhanced-cli-typer/test_service_client.py ║ FastAPI service HTTP client with robust error handling ║ M
  - [x] 3.1 Create HTTP client class with connection pooling and circuit breaker
  - [x] 3.2 Implement job submission methods with API versioning support
  - [x] 3.3 Add job status polling with rate limiting and concurrent handling
  - [x] 3.4 Handle service startup/shutdown with offline fallback mode
  - [x] 3.5 Implement comprehensive error handling, retry logic, and timeout management

- [x] Task 4 ║ tests/enhanced-cli-typer/test_security_validation.py ║ Security testing and input validation ║ M
  - [x] 4.1 Test command injection prevention in path arguments
  - [x] 4.2 Validate file permissions and access controls
  - [x] 4.3 Test sanitization of user input in interactive mode
  - [x] 4.4 Validate secure handling of temporary files and process spawning
  - [x] 4.5 Test malicious CLI inputs and shell metacharacters

- [ ] Task 5 ║ tests/enhanced-cli-typer/test_rich_features.py ║ Rich UI features with performance optimization ║ M
  - [ ] 5.1 Implement Rich progress bars with stage-specific tracking
  - [ ] 5.2 Add colored output and status indicators with rate limiting
  - [ ] 5.3 Create table formatting for results summary
  - [ ] 5.4 Implement real-time progress updates with graceful degradation
  - [ ] 5.5 Add spinner animations and memory usage monitoring

- [ ] Task 6 ║ tests/enhanced-cli-typer/test_interactive_mode.py ║ Interactive mode with security and validation ║ M
  - [ ] 6.1 Create guided workflow prompts for common scenarios
  - [ ] 6.2 Implement parameter validation with security checks
  - [ ] 6.3 Add secure file picker with permission handling
  - [ ] 6.4 Create configuration templates for different use cases
  - [ ] 6.5 Implement interactive parameter review and confirmation

- [ ] Task 7 ║ tests/enhanced-cli-typer/test_shell_completion.py ║ Shell completion for bash, zsh, powershell ║ S
  - [ ] 7.1 Generate completion scripts for supported shells
  - [ ] 7.2 Implement command and argument completion
  - [ ] 7.3 Add file path completion for input arguments
  - [ ] 7.4 Test completion functionality across platforms

- [ ] Task 8 ║ tests/enhanced-cli-typer/test_performance_stress.py ║ Performance testing and resource monitoring ║ M
  - [ ] 8.1 Stress test with large synthetic datasets and memory profiling
  - [ ] 8.2 Test concurrent job submissions and high-throughput scenarios
  - [ ] 8.3 Validate HTTP client performance under load
  - [ ] 8.4 Test signal handling (CTRL+C) during long operations
  - [ ] 8.5 Benchmark against legacy CLI with incremental validation

- [ ] Task 9 ║ tests/enhanced-cli-typer/test_code_quality.py ║ Code quality and maintainability enforcement ║ S
  - [ ] 9.1 Enforce flake8 compliance with cyclomatic complexity ≤ 10
  - [ ] 9.2 Validate comprehensive docstring coverage
  - [ ] 9.3 Test modular architecture and dependency injection
  - [ ] 9.4 Verify minimum test coverage thresholds (>90%)
  - [ ] 9.5 Validate external dependency version compatibility

- [ ] Task 10 ║ tests/enhanced-cli-typer/test_integration.py ║ End-to-end integration and failure scenarios ║ L
  - [ ] 10.1 Test complete pipeline execution via new CLI
  - [ ] 10.2 Validate byte-level output compatibility with legacy CLI
  - [ ] 10.3 Test service failure scenarios and error handling
  - [ ] 10.4 Test unreachable endpoints, malformed responses, and timeouts
  - [ ] 10.5 Cross-platform testing (Linux, Windows, macOS)

## Current Progress Summary

## Current Progress Summary

### ✅ COMPLETED TASKS (23/50 subtasks, 46% complete)
- **Task 1**: COMPLETE ✅ - Backward compatibility analysis (17/17 tests passing)
- **Task 2**: COMPLETE ✅ - Core Typer CLI structure (19/19 tests passing) 
- **Task 3**: COMPLETE ✅ - Service HTTP client (37/37 tests passing, 5/5 subtasks complete)
  - ✅ 3.1: HTTP client with connection pooling and circuit breaker
  - ✅ 3.2: Job submission methods with API versioning support
  - ✅ 3.3: Job status polling with rate limiting and concurrent handling
  - ✅ 3.4: Service startup/shutdown with offline fallback mode
  - ✅ 3.5: Comprehensive error handling, retry logic, and timeout management

- **Task 4**: COMPLETE ✅ - Security testing and input validation (30/30 tests passing)
  - ✅ 4.1: Command injection prevention in path arguments
  - ✅ 4.2: File permissions and access controls validation
  - ✅ 4.3: User input sanitization for interactive mode
  - ✅ 4.4: Secure temporary file handling and process spawning
  - ✅ 4.5: Malicious CLI inputs and shell metacharacters testing

### 🔄 TEST STATUS: 103/103 TESTS PASSING (100% success rate)
- **test_argument_compatibility.py**: 17 tests ✅
- **test_cli_core.py**: 19 tests ✅ 
- **test_service_client.py**: 37 tests ✅
- **test_security_validation.py**: 30 tests ✅ (NEW - comprehensive security testing)
- **Remaining**: 6 tasks (27 subtasks) to implement

### 🎯 NEXT PRIORITY: Task 5 - Rich UI features with performance optimization

<details><summary>Review-Resolution Log</summary>

### Critical Issues Resolved
- **🚨 Dependency inversion** - RESOLVED: Moved compatibility analysis to Task 1 (was Task 3) to inform architectural decisions
- **🚨 Service availability assumption** - RESOLVED: Added offline fallback mode in Task 3.4 and comprehensive failure testing in Task 10.3-10.4
- **🚨 Insufficient negative tests** - RESOLVED: Added Task 4 (Security Validation) and expanded Task 10 with failure scenarios
- **🚨 Concurrency gaps** - RESOLVED: Added concurrent job testing in Task 3.3 and stress testing in Task 8.2

### Security Issues Addressed  
- **Command injection prevention** - NEW TASK 4: Dedicated security validation with input sanitization
- **Path traversal attacks** - ENHANCED: Task 2.4 now includes directory traversal protection
- **Malicious CLI inputs** - NEW: Task 4.5 tests shell metacharacters and injection attempts
- **File permission validation** - NEW: Task 4.2 validates secure file access

### Performance & Quality Issues Resolved
- **Performance regression risk** - NEW TASK 8: Dedicated performance testing with incremental validation
- **Missing stress tests** - RESOLVED: Task 8.1-8.3 covers large datasets and high-throughput scenarios  
- **Code quality enforcement** - NEW TASK 9: Comprehensive quality checks including complexity limits
- **Test isolation** - ENHANCED: Better separation between unit, integration, and stress tests

### Coverage Gaps Filled
- **Rate limiting tests** - ENHANCED: Task 3.3 and 5.2 include rate limiting validation
- **Signal handling** - NEW: Task 8.4 tests CTRL+C and graceful termination
- **Memory monitoring** - NEW: Task 5.5 and 8.1 include memory usage validation
- **API versioning** - ENHANCED: Task 3.2 includes API versioning support
- **Cross-platform validation** - MAINTAINED: Task 7.4 and 10.5 ensure multi-OS compatibility

### Resource & Dependency Issues
- **External dependency validation** - NEW: Task 9.5 verifies compatible versions
- **Connection pooling** - ENHANCED: Task 3.1 includes connection pooling and circuit breaker patterns
- **Modular architecture** - ENHANCED: Task 2.1 emphasizes modular command structure, Task 9.3 validates architecture

</details>

<details><summary>📝 Extended Details (for ChatGPT / humans)</summary>

### Rationale
<reasoning>The Enhanced CLI with Typer feature requires a comprehensive TDD approach with security-first design to ensure 100% backward compatibility while adding modern features. The plan now prioritizes compatibility analysis first (Task 1) to inform architectural decisions, followed by secure CLI core implementation (Task 2), then robust service integration (Task 3). Security validation (Task 4) is elevated to a dedicated task due to review feedback. Rich features (Task 5), interactive mode (Task 6), and shell completion (Task 7) add value without breaking existing workflows. Performance testing (Task 8) and code quality enforcement (Task 9) ensure production readiness. Finally, comprehensive integration testing (Task 10) validates the entire system with failure scenarios. This sequence ensures security and compatibility concerns are addressed early while building functionality incrementally.</reasoning>

### Resources
- Files to open: 
  - `emuses/scripts/main.py` (legacy CLI structure reference)
  - `emuses/foundation_fastapi_service/app.py` (API endpoints)
  - `emuses/foundation_fastapi_service/models.py` (request/response schemas)
  - `docs/enhanced-cli-typer_*.md` (implementation context)
- External APIs / libs: 
  - Typer (modern CLI framework)
  - Rich (terminal formatting and progress bars)
  - httpx (async HTTP client for service communication)
  - pytest (testing framework)
  - click (shell completion utilities)
  - psutil (resource monitoring)

### Risks & Mitigations
- 🚨 **Backward compatibility breakage** – Task 1 compatibility analysis informs all architectural decisions
- 🚨 **Security vulnerabilities** – Dedicated Task 4 for comprehensive security testing and input validation
- **Service startup complexity** – Task 3.4 implements robust service management with offline fallback mode
- **Performance regression** – Task 8 provides comprehensive performance validation with incremental benchmarking
- **Cross-platform compatibility** – Tasks 7.4 and 10.5 ensure multi-OS validation
- **Code quality degradation** – Task 9 enforces complexity limits and quality standards

### Acceptance-Checks
| Test file                                           | Assertion                                    | Metric                |
|-----------------------------------------------------|----------------------------------------------|-----------------------|
| tests/enhanced-cli-typer/test_argument_compatibility.py | 100% argument compatibility with legacy CLI | runtime ≤ 5s          |
| tests/enhanced-cli-typer/test_cli_core.py           | All commands parse arguments securely       | flake8 < 10           |
| tests/enhanced-cli-typer/test_service_client.py     | ✅ HTTP client handles all endpoints robustly | ✅ coverage > 90%     |
| tests/enhanced-cli-typer/test_security_validation.py | ✅ No security vulnerabilities detected      | ✅ 0 critical issues  |
| tests/enhanced-cli-typer/test_rich_features.py      | Progress bars work with performance limits  | visual + perf validation |
| tests/enhanced-cli-typer/test_interactive_mode.py   | Guided workflows complete securely          | user acceptance       |
| tests/enhanced-cli-typer/test_shell_completion.py   | Completion works on bash/zsh/powershell     | manual testing        |
| tests/enhanced-cli-typer/test_performance_stress.py | Handles large datasets without regression   | memory < 2GB, time < 2x legacy |
| tests/enhanced-cli-typer/test_code_quality.py       | Code quality standards enforced             | complexity ≤ 10, coverage > 90% |
| tests/enhanced-cli-typer/test_integration.py        | End-to-end pipeline produces identical results | byte-level comparison |

### Testing Strategy
**For each task, specify the appropriate testing approach:**
- **Task 1 (Compatibility)**: Unit testing with comprehensive argument mapping validation and edge case coverage
- **Task 2 (CLI Core)**: Unit testing with isolated Typer app testing and security-focused validation
- **Task 3 (Service Client)**: Integration testing with real HTTP client, mocked endpoints, and failure simulation
- **Task 4 (Security)**: Security testing with malicious input simulation and vulnerability scanning
- **Task 5 (Rich Features)**: Unit testing with mocked Rich components and performance validation
- **Task 6 (Interactive Mode)**: Unit testing with simulated user input and security validation
- **Task 7 (Shell Completion)**: Integration testing with real shell environments and cross-platform validation
- **Task 8 (Performance)**: Stress testing with large datasets, memory profiling, and benchmark comparison
- **Task 9 (Code Quality)**: Static analysis testing with complexity measurement and coverage validation
- **Task 10 (Integration)**: End-to-end testing with real service, failure scenarios, and compatibility validation

</details>
