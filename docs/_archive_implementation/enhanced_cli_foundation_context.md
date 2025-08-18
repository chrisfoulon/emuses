# Enhanced CLI Typer - Context 0a: Foundation

## Focus Areas
This context covers the foundation layer for the Enhanced CLI with Typer, focusing on core CLI structure, backward compatibility analysis, and service integration patterns.

## Key Components

### Legacy CLI Analysis
- **Argument Structure**: 40+ command-line arguments across 5 commands
- **Path Resolution**: Custom `resolve_path()` logic with URL decoding
- **Command Pattern**: Subcommand structure (full, umap, clustering, heatmap, prediction)
- **Validation Logic**: Extensive parameter validation and error handling

### Typer Migration Strategy
- **Compatibility First**: Task 1 ensures 100% argument compatibility
- **Modular Architecture**: Separate command modules to avoid monolithic structure
- **Type Safety**: Leverage Typer's type hints and validation
- **Security Hardening**: Protect against directory traversal and injection

### Service Integration Requirements
- **HTTP Client**: Connection pooling and circuit breaker patterns
- **API Versioning**: Support for graceful API evolution
- **Fallback Strategy**: Offline mode when service unavailable
- **Progress Tracking**: Real-time updates from background jobs

## Implementation Files
- **Target**: `emuses/cli/main.py` (new Typer CLI)
- **Reference**: `emuses/scripts/main.py` (legacy argparse CLI)
- **Service**: `emuses/foundation_fastapi_service/app.py` (API endpoints)
- **Tests**: `tests/enhanced-cli-typer/test_argument_compatibility.py` (✅ Complete)

## Completed Analysis (Task 1)
- **Legacy Parser Structure**: ✅ Complete mapping of 5 commands with 40+ arguments
- **Argument Categories**: ✅ 7 categories identified (positional, file_path, boolean, integer, choice, list, string)
- **Security Requirements**: ✅ Path traversal protection and input sanitization defined
- **Edge Cases**: ✅ Cross-platform paths, URL encoding, special identifiers tested
- **Compatibility Matrix**: ✅ Complete argument-to-Typer mapping documented

## Next Steps
- Task 2: Implement CLI core with modular command structure
- Task 3: Build service client with connection pooling

## Context Links
- Legacy CLI: `emuses/scripts/main.py` (reference implementation)
- FastAPI Service: `emuses/foundation_fastapi_service/app.py` (API endpoints)
