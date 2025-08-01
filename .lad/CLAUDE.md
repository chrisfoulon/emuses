# Project Context for Claude Code LAD Framework

## Architecture Overview
*Auto-updated by LAD workflows - current system understanding*

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

## Project Structure Patterns
*Learned from exploration - common patterns and conventions*

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
| User Authentication System | ✅ Complete | FastAPI-Users JWT auth, user dependencies | 2025-07-31 |
| Workspace Models | ✅ Complete | User, Workspace, Dataset, TrainingJob models | 2025-07-31 |
| MultiUserJobManager | ✅ Complete | User-scoped storage, job isolation, quota tracking | 2025-07-31 |
| Workspace API Endpoints | ✅ Complete | Full CRUD REST APIs with authentication | 2025-07-31 |
| Dataset API Endpoints | ✅ Complete | Dataset lifecycle management with workspace integration | 2025-07-31 |
| Training Job API Endpoints | ✅ Complete | User-scoped job management with status tracking | 2025-07-31 |
| Quota Management System | ✅ Complete | Complete resource validation, usage tracking, and administrative tools | 2025-07-31 |
| CLI Multi-Mode Support | ✅ Complete | LOCAL/MULTI_USER/PRODUCTION modes with authentication | 2025-08-01 |
| Docker Production Infrastructure | ✅ Complete | docker-compose.yml, Dockerfile, nginx, PostgreSQL, secrets management | 2025-08-01 |
| Database Migration System | ✅ Complete | Alembic configuration, initial migrations, management API, comprehensive testing | 2025-08-01 |
| Background Task Management | ✅ Complete | ProcessPoolExecutor integration, user context isolation, task lifecycle management | 2025-08-01 |

### Integration Decisions Log
*Historical decisions to guide future development*

| Feature | Decision | Strategy | Rationale | Session Date | Outcome |
|---------|----------|----------|-----------|--------------|---------|
| Workspace API Architecture | Single endpoints file | All workspace/dataset/job endpoints in one module | Maintain cohesion, shared auth patterns, easier testing | 2025-07-31 | ✅ Successfully implemented |
| User Isolation Strategy | Ownership validation helpers | Shared `_get_user_*` functions for consistent auth | DRY principle, consistent security boundaries | 2025-07-31 | ✅ Prevents code duplication |
| Job Cancellation Design | Soft delete (status=cancelled) | Mark jobs as cancelled vs hard delete | Audit trail preservation, better debugging | 2025-07-31 | ✅ Maintains data integrity |
| API Schema Strategy | Separate Create/Update/Read schemas | Different Pydantic models for each operation | Clear validation, proper response formatting | 2025-07-31 | ✅ Clean API design |
| Quota Management Integration | JobManager integration pattern | Quota validation integrated directly into job creation workflow | Automatic enforcement, consistent UX, fail-fast validation | 2025-07-31 | ✅ Seamless resource management |

### Pending Integration Tasks
*Cross-session work that needs completion*

- **Admin CLI Tools**: Create administrative CLI commands and endpoints (Task 15)

### Architecture Evolution Notes
*Key architectural changes that affect future integration decisions*

- **2025-07-31**: Consolidated workspace API endpoints into single module pattern - all related endpoints (workspaces, datasets, jobs) share common authentication and validation patterns
- **2025-07-31**: Established helper function pattern for user ownership validation - `_get_user_*` functions provide consistent security boundaries across all endpoints
- **2025-07-31**: Implemented soft delete pattern for job cancellation - preserves audit trail while marking resources as inactive
- **2025-07-31**: Adopted separate Pydantic schema pattern - distinct Create/Update/Read schemas improve API clarity and validation
- **2025-08-01**: Completed Docker production infrastructure - multi-stage builds, nginx reverse proxy, PostgreSQL with health checks, secrets management system
- **2025-08-01**: Implemented comprehensive database migration system - Alembic configuration, initial migrations for all models, migration management API with testing

### Integration Anti-Patterns Avoided
*Documentation of duplicate implementations prevented*

- *No anti-patterns logged*

---
*Last updated by Claude Code LAD Framework*