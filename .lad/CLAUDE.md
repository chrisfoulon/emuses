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

### Fixed Issues (August 2025)
**CLI Command Invocation**: The correct command is `python -m emuses.cli` not `python -m emuses`
- Root cause: Project structure has `emuses/cli/__main__.py` but no `emuses/__main__.py`
- Fixed in: testing-commands.md, admin-guide.md, research-workflows.md

**ServiceHTTPClient Parameter Mismatch**: Constructor expects `base_url` and `auth_token`, not `service_url` and `token`
- Root cause: API inconsistency between admin_commands.py and service_client.py
- Fixed in: admin_commands.py (all 5 instances)

**StatusRenderer Context Manager**: Used non-existent `status_renderer.status()` instead of Rich's `console.status()`
- Root cause: StatusRenderer class doesn't have status() context manager method
- Industry standard: Rich library's `console.status()` context manager
- Fixed in: admin_commands.py (replaced all instances, removed unused imports)

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
| Admin API Endpoints | ✅ Complete | User management, quota management, system monitoring endpoints with superuser auth | 2025-08-01 |
| Admin CLI Commands | ✅ Complete | Full CLI admin interface with comprehensive help, research workflows, and documentation | 2025-08-01 |
| Observability System | ✅ Complete | Prometheus metrics, Grafana dashboards, structured logging foundation | 2025-08-03 |
| Inference Pipeline System | ✅ Complete | InferenceStage, CLI command, API endpoint, comprehensive testing | 2025-08-05 |
| Model Registry System (Local Mode) | ✅ Complete | LocalModelRegistry, CLI commands, file-based discovery, comprehensive testing | 2025-08-06 |
| Model Registry System (Database Mode) | ✅ Complete | DatabaseModelRegistry, ModelPermissionManager, FastAPI endpoints, multi-user permissions | 2025-08-07 |

### Integration Decisions Log
*Historical decisions to guide future development*

| Feature | Decision | Strategy | Rationale | Session Date | Outcome |
|---------|----------|----------|-----------|--------------|---------|
| Workspace API Architecture | Single endpoints file | All workspace/dataset/job endpoints in one module | Maintain cohesion, shared auth patterns, easier testing | 2025-07-31 | ✅ Successfully implemented |
| User Isolation Strategy | Ownership validation helpers | Shared `_get_user_*` functions for consistent auth | DRY principle, consistent security boundaries | 2025-07-31 | ✅ Prevents code duplication |
| Job Cancellation Design | Soft delete (status=cancelled) | Mark jobs as cancelled vs hard delete | Audit trail preservation, better debugging | 2025-07-31 | ✅ Maintains data integrity |
| API Schema Strategy | Separate Create/Update/Read schemas | Different Pydantic models for each operation | Clear validation, proper response formatting | 2025-07-31 | ✅ Clean API design |
| Quota Management Integration | JobManager integration pattern | Quota validation integrated directly into job creation workflow | Automatic enforcement, consistent UX, fail-fast validation | 2025-07-31 | ✅ Seamless resource management |
| Model Registry Database Architecture | Single migration approach | Created unified migration for all model registry tables with existing user/workspace tables | Clean database schema, proper foreign keys, no migration conflicts | 2025-08-07 | ✅ Clean database design |
| Model Permission System Design | Multi-level access control | Four access levels (read/write/admin/owner) with explicit grants and implicit workspace/public permissions | Flexible permission model, workspace integration, ownership clarity | 2025-08-07 | ✅ Comprehensive access control |
| Database-Filesystem Coordination | Registry-managed storage | DatabaseModelRegistry coordinates between database records and filesystem storage | Data consistency, atomic operations, storage integrity | 2025-08-07 | ✅ Reliable storage management |

### Project Status Management

**CRITICAL**: Read and update `PROJECT_STATUS.md` at session start and completion.

**Status Location**: `PROJECT_STATUS.md` contains authoritative project status including:
- Completed features and implementation phases
- Outstanding work and pending tasks
- Next development priorities and roadmap
- Deployment readiness and project health metrics

**Session Protocol**:
1. **Start**: Read `PROJECT_STATUS.md` for current state
2. **Work**: Update TodoWrite for task tracking during session
3. **End**: Update `PROJECT_STATUS.md` with completed work and new pending items

### Pending Integration Tasks
*Cross-session work that needs completion*

- **CI/CD Task 4.2**: Multi-environment deployment automation (staging/production triggers)
- **model-registry Sub-Plan 3**: Cloud & Production Features Phase 3.2+ (Phase 3.1 cloud storage abstraction complete)

### Architecture Evolution Notes
*Key architectural changes that affect future integration decisions*

- **2025-07-31**: Consolidated workspace API endpoints into single module pattern - all related endpoints (workspaces, datasets, jobs) share common authentication and validation patterns
- **2025-07-31**: Established helper function pattern for user ownership validation - `_get_user_*` functions provide consistent security boundaries across all endpoints
- **2025-07-31**: Implemented soft delete pattern for job cancellation - preserves audit trail while marking resources as inactive
- **2025-07-31**: Adopted separate Pydantic schema pattern - distinct Create/Update/Read schemas improve API clarity and validation
- **2025-08-01**: Completed Docker production infrastructure - multi-stage builds, nginx reverse proxy, PostgreSQL with health checks, secrets management system
- **2025-08-01**: Implemented comprehensive database migration system - Alembic configuration, initial migrations for all models, migration management API with testing
- **2025-08-03**: Implemented lightweight observability system - Prometheus + Grafana approach over full OpenTelemetry to achieve <2% performance overhead for scientific workloads
- **2025-08-05**: Completed inference pipeline system - InferenceStage pipeline component, CLI integration (`emuses inference`), FastAPI endpoint (`POST /api/v1/inference`), comprehensive TDD testing with E2E workflow validation
- **2025-08-06**: **InferenceStage Architecture Rework** - Fixed architectural issues identified post-implementation: removed dual-mode complexity, implemented standard EMUSES stage pattern (context-based data access), added context-first model loading for performance optimization, enhanced HeatmapStage to store models in context, updated CLI to use proper EMUSESPipeline integration
- **2025-08-07**: **Model Registry Database Implementation** - Implemented comprehensive multi-user model registry with database backend: created unified Alembic migration for model registry tables, implemented multi-level permission system (read/write/admin/owner), database-filesystem coordination for atomic operations, comprehensive FastAPI endpoints with authentication integration, extensive test coverage (180+ tests), CLI enhancement with deployment mode detection
- **2025-08-07**: **Cloud Storage Abstraction Layer** - Implemented production-ready cloud storage backends for AWS S3, Azure Blob Storage, and Google Cloud Storage: validated implementations against official provider documentation, fixed signed URL generation patterns, added proper error handling with ClientError imports, comprehensive test coverage (14 tests), factory pattern for configuration-based provider instantiation

### Integration Anti-Patterns Avoided
*Documentation of duplicate implementations prevented*

- *No anti-patterns logged*

---
*Last updated by Claude Code LAD Framework*