# Multi-User EMUSES Service - Interface Context (Phase 0c)

## Phase Focus
**Domain**: CLI integration, deployment infrastructure, admin tools, background processing
**Scope**: Multi-mode CLI, HTTP authentication, Docker deployment, ProcessPoolExecutor, admin interface
**Prerequisites**: Plan 0b completion (workspace APIs, job management, quota system)

## Plan 0c Completed Deliverables

**✅ CLI Multi-Mode Support (Tasks 10-11 COMPLETED)**:

**Task 10 - Deployment Mode Detection**: `emuses.multi_user_service.deployment_config`
- **Three Deployment Modes**: LOCAL (no auth), MULTI_USER (selective auth), PRODUCTION (full auth)
- **Environment Detection**: Via `EMUSES_DEPLOYMENT_MODE` with validation and fallback
- **Service Discovery**: Automatic service URL resolution per deployment mode
- **CLI Integration**: Automatic mode detection with configuration validation
- **Test Coverage**: 23/23 tests passing with comprehensive mode switching validation

**Task 11 - Authentication in HTTP Client**: `emuses.multi_user_service.token_manager` + `emuses.cli.service_client`
- **Token Management**: Secure JWT storage in `~/.emuses/token.json` with 0o600 permissions
- **Authentication Headers**: Automatic Bearer token injection in HTTP requests
- **CLI Parameters**: `--service-url` and `--token` parameters with deployment mode awareness
- **Session Persistence**: Token validation, expiry checks, and automatic token management
- **Test Coverage**: 15/15 tests passing with complete authentication flow validation

**CLI Command Examples**:
```bash
# Local mode (default) - no authentication required
emuses full output/ input/

# Multi-user mode with authentication
EMUSES_DEPLOYMENT_MODE=multi-user emuses full output/ input/ --token "jwt_token_here"

# Production mode with custom service URL
EMUSES_DEPLOYMENT_MODE=production emuses full output/ input/ --service-url "https://api.example.com" --token "jwt_token_here"
```

**Integration Points Completed**:
- FastAPI app integration with deployment mode detection
- Multi-user workspace endpoints integrated when service mode enabled
- HTTP client with automatic authentication header injection
- CLI parameter validation and deployment mode configuration

## Actual Integration Inputs from Plan 0b (COMPLETED)

**✅ Workspace API Contracts**: `emuses.multi_user_service.workspace_endpoints`
- **Workspace Management**: Complete CRUD operations with `POST/GET/PUT/DELETE /workspaces/` endpoints
- **Dataset Management**: Complete lifecycle with `POST/GET/PUT/DELETE /datasets/` endpoints  
- **Training Job Management**: User-scoped jobs with `POST/GET/PUT/DELETE /jobs/` endpoints
- **Quota Management**: Complete quota API with `GET /quota/status`, `POST /quota/admin/adjust`, `GET /quota/usage/history`, `GET/POST /quota/admin/*` endpoints
- **Authentication Integration**: All endpoints require FastAPI-Users authentication via `get_current_user()` dependency
- **Setup Function**: Single `setup_workspace_endpoints(app)` integrates all routers into FastAPI app

**✅ Multi-User Job Manager**: `emuses.multi_user_service.job_manager.MultiUserJobManager`
- **User-Scoped Operations**: `create_user_job()`, `list_user_jobs()`, `cancel_user_job()` with user context
- **Storage Isolation**: `create_user_storage_path()` with secure permissions (0o700) and user isolation
- **Ownership Validation**: `validate_job_ownership()` prevents cross-user access
- **Resource Tracking**: `update_user_resource_usage()`, `get_user_resource_usage()` for quota integration
- **Quota Validation**: Integrated quota checking in job creation workflow

**✅ Security Patterns**: `emuses.multi_user_service.auth` & `emuses.multi_user_service.middleware`
- **API Authentication**: FastAPI-Users with JWT tokens via `get_current_user()`, `get_current_active_user()`, `get_current_superuser()`
- **User Context Validation**: Helper functions `_get_user_workspace()`, `_get_user_dataset()`, `_get_user_training_job()` with 404 responses for unauthorized access
- **Data Access Control**: Complete user isolation with ownership validation across all endpoints
- **Conditional Authentication**: `get_conditional_auth_dependency()` for deployment-mode-aware authentication

## CLI Multi-Mode Architecture

### Deployment Mode Detection
**Three Modes**: Local (no auth), Multi-user (selective auth), Production (full auth)
**Environment Variables**: `EMUSES_DEPLOYMENT_MODE` detection and parsing
**Configuration Classes**: Mode-specific configuration and validation

### CLI Parameter Enhancement
**Authentication Parameters**: `--service` and `--token` parameter support
**Mode Validation**: Parameter validation per deployment mode
**Backward Compatibility**: Existing CLI workflows preserved

### Service Manager Extension
**Multi-Mode Support**: External service connection capabilities
**Health Checking**: Service health validation and monitoring
**Mode Switching**: Graceful deployment mode transitions

## HTTP Client Authentication Integration

### ServiceHTTPClient Extension
**Token Management**: JWT token header injection and refresh logic
**Authentication Errors**: Authentication error handling and recovery
**Session Persistence**: Token storage and validation across CLI calls

### Token Storage Strategy
**Secure Storage**: Token storage in `~/.emuses/token` with secure permissions
**Validation**: Token expiry checks and automatic refresh
**CLI Commands**: Login/logout CLI command implementation

### User Session Management
**Automatic Login**: Seamless login flows for CLI operations
**Session Persistence**: User context maintenance across CLI calls
**User Context Display**: User information display in CLI interfaces

## Background Processing Architecture (✅ COMPLETED - Task 14)

### ProcessPoolExecutor Integration
**✅ Worker Configuration**: Complete process pool with configurable worker count (max 32, defaults to CPU count + 4)
- **Process Pool Management**: BackgroundTaskManager with ProcessPoolExecutor configuration
- **Resource Limits**: Configurable memory limits per process (default 8GB), process timeout management
- **Security Isolation**: Spawn method for better process isolation, secure user context handling

**✅ Job Queue Management**: Complete task queue with user context isolation
- **Task Lifecycle**: PENDING → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED status flow
- **User Authorization**: Task ownership validation, user-scoped task operations
- **Concurrent Execution**: Multi-worker task processing with proper synchronization

**✅ Process Monitoring and Cleanup**: Complete health monitoring and resource management
- **Resource Monitoring**: Memory usage tracking, process health checks every 30 seconds
- **Automatic Cleanup**: Old completed tasks cleanup (24-hour retention), orphaned process cleanup
- **Process Limits**: Memory limit enforcement with automatic termination on excess usage

### Task Execution Patterns
**✅ Pipeline Processing**: Complete EMUSES pipeline execution in separate processes
- **Process Isolation**: User workspace isolation in background processes with secure permissions
- **Resource Tracking**: Job execution time tracking, storage usage measurement
- **Error Handling**: Comprehensive exception handling with proper status updates

**✅ User Context Integration**: Complete user workspace isolation
- **Storage Isolation**: User-scoped job directories with 0o700 permissions
- **Quota Integration**: Resource quota validation during task creation and execution
- **Ownership Validation**: Task ownership checks for all operations

**✅ Status Tracking**: Complete task status tracking and progress reporting
- **Real-time Updates**: Job status synchronization between task manager and job manager
- **Progress Monitoring**: Task progress tracking with detailed status messages
- **Result Storage**: Task execution results with resource usage summaries

### Task Management APIs (✅ COMPLETED)
**✅ Task Submission**: Complete task submission and queue management endpoints
- **POST /tasks/**: Task creation with pipeline configuration and quota validation
- **Background Submission**: Async task submission via FastAPI BackgroundTasks
- **Validation**: Config validation, user authorization, quota pre-checks

**✅ Task Control**: Complete task cancellation and lifecycle management
- **GET /tasks/**: User task listing with status filtering and pagination
- **GET /tasks/{id}**: Individual task status with user authorization
- **POST /tasks/{id}/cancel**: Task cancellation with process termination
- **GET /tasks/{id}/result**: Task execution results with resource usage

**✅ System Monitoring**: Complete process health monitoring and status reporting
- **GET /tasks/system/status**: System metrics (workers, task counts, resource limits)
- **Health Integration**: Task manager health checks via task_integration.py
- **Metrics Collection**: Process pool status, memory usage, task distribution

## Production Infrastructure

### Docker Deployment Configuration (✅ COMPLETED - Task 12)
**✅ Production Docker Compose**: `docker-compose.yml` with PostgreSQL 15, nginx 1.25, and API service
- **PostgreSQL Service**: Configured with health checks, secure authentication (scram-sha-256), and connection pooling
- **nginx Reverse Proxy**: SSL termination, rate limiting (10r/s API, 5r/s auth), security headers, WebSocket support
- **API Service**: Multi-user mode with user isolation, resource quotas, and background processing
- **Networking**: Custom bridge network (192.168.100.0/24) with service discovery and health dependencies

**✅ Application Containerization**: Multi-stage `Dockerfile` with security best practices
- **Multi-stage Build**: Builder stage for dependencies, production stage with minimal attack surface
- **Security**: Non-root user (emuses:emuses), secure file permissions, minimal base image (python:3.11-slim)
- **Health Checks**: Built-in health check via `/health` endpoint with 30s intervals
- **Startup Scripts**: Database migration, service initialization, graceful error handling

**✅ Environment Configuration**: Production-ready configuration management
- **Environment Templates**: `.env.production.template` with comprehensive production settings
- **Secrets Management**: `docker/secrets/` with generation script (`generate-secrets.sh`)
- **SSL Configuration**: `docker/ssl/` directory with certificate management documentation
- **Security**: Updated `.gitignore` to prevent secret leakage, secure file permissions

## Admin Tools Architecture (✅ COMPLETED - Task 15.1)

### Admin API Endpoints (✅ COMPLETED)
**✅ User Management**: Complete CRUD operations via `/admin/users/*` endpoints
- **POST /admin/users**: Create new user with organization and permissions
- **GET /admin/users**: List all users with pagination (skip/limit)
- **GET /admin/users/{id}**: Retrieve specific user by ID
- **PUT /admin/users/{id}**: Update user organization, active status, verification
- **DELETE /admin/users/{id}**: Delete user (admin only)

**✅ Quota Management**: Complete quota administration via `/admin/quota/*` endpoints
- **POST /admin/quota/adjust**: Adjust user quotas (storage_gb, concurrent_jobs, compute_hours)
- **GET /admin/quota/usage**: List quota usage for all users with detailed metrics
- **POST /admin/quota/reset**: Reset user quota to system defaults

**✅ System Monitoring**: Complete system health monitoring via `/admin/system/*` endpoints
- **GET /admin/system/status**: Overall system status with component health and metrics
- **GET /admin/system/job-queues**: Job queue status (pending, running, completed, failed counts)
- **GET /admin/system/health**: Detailed health checks (database, storage, tasks, resources)

### Authentication & Authorization
**✅ Superuser Authentication**: All admin endpoints require `get_current_superuser` dependency
**✅ Request/Response Schemas**: Complete Pydantic models with NumPy-style docstrings
**✅ Error Handling**: Proper HTTP status codes and exception handling
**✅ Integration**: Admin router integrated into FastAPI app via `setup_workspace_endpoints()`

### CLI Admin Commands (✅ COMPLETED - Task 15.2)
**✅ User Management Commands**: Complete user lifecycle management
- **`emuses admin add-user`**: Create new users with customizable quotas and organization settings
- **`emuses admin list-users`**: Display paginated user lists with status indicators
- **`emuses admin help`**: Comprehensive built-in help with workflows and troubleshooting

**✅ System Control Commands**: Complete system administration and monitoring
- **`emuses admin system-status`**: System health monitoring with detailed diagnostics
- **`emuses admin cancel-job`**: Emergency job cancellation with safety confirmations
- **`emuses admin set-quota`**: Dynamic quota management for storage, compute, and concurrent jobs

**✅ Authentication Integration**: Token-based admin authentication
- **Environment Variables**: `EMUSES_ADMIN_TOKEN` for secure token management
- **Command-line Options**: `--token` and `--service-url` for flexible deployment modes
- **Error Handling**: Rich console output with detailed error messages and troubleshooting guidance

### Research Environment Optimization (✅ COMPLETED - Task 15.3)
**✅ CLI-First Design**: Admin tools optimized for research environment CLI access
- **Typer Integration**: Modern CLI framework with rich console output and interactive features
- **Batch Operations**: Support for bulk user operations and scripted administration
- **Context-Aware Help**: Command-specific help with research workflow examples

**✅ Comprehensive Documentation**: Production-ready admin documentation suite
- **Usage Guide**: `docs/multi-user-service/admin-guide.md` with detailed examples and troubleshooting
- **Research Workflows**: `docs/multi-user-service/research-workflows.md` with semester management, project allocation, and compliance workflows
- **Interactive Help**: Built-in `emuses admin help` command with formatted guidance

**✅ Workflow Integration**: Admin workflows optimized for research environments
- **Academic Lifecycle**: Semester setup, cleanup, and user lifecycle management scripts
- **Resource Management**: Grant-based allocation, collaborative research setup, and quota management
- **Compliance Support**: Usage reporting, audit trails, and user activity monitoring

## Database Migration System (✅ COMPLETED - Task 13)

### Alembic Migration Infrastructure
**✅ Migration Environment**: Complete Alembic setup with `alembic.ini`, `env.py` configuration
- **Dynamic Database URLs**: Environment-based configuration supporting PostgreSQL/SQLite
- **Model Integration**: Automatic detection of SQLAlchemy models from `emuses.multi_user_service.models`
- **Sync/Async Compatibility**: Proper URL conversion for Alembic's synchronous operations

**✅ Initial Migration Generated**: `34df19297160_create_initial_tables_for_users_.py`
- **Users Table**: FastAPI-Users integration with EMUSES-specific fields (organization, role, quotas)
- **Workspaces Table**: User workspace isolation with storage path management
- **Datasets Table**: Dataset versioning with workspace relationships and integrity checking
- **Training Jobs Table**: User-scoped jobs with workspace association and resource tracking
- **Indexes & Constraints**: Foreign key relationships and performance indexes automatically generated

### Migration Management API
**✅ Migration Control Functions**: `emuses.multi_user_service.database`
- **`run_migrations(target="head")`**: Execute migrations to specified revision
- **`rollback_migration(target)`**: Rollback to specific migration revision
- **`get_migration_status()`**: Current revision, head revision, pending migrations status
- **`validate_database_schema()`**: Compare actual vs expected table structure

**✅ Database Operations**: 
- **`create_all_tables()`**: SQLAlchemy metadata-based table creation for development
- **`drop_all_tables()`**: Complete database reset capability
- **Environment Integration**: Automatic database URL detection and configuration

### Migration Testing & Validation
**✅ Comprehensive Test Suite**: 12/12 tests passing in `test_migrations.py`
- **Setup Tests**: Alembic configuration and directory structure validation
- **Table Tests**: All model tables created with correct columns and relationships
- **Migration Commands**: Upgrade, rollback, and status functionality testing
- **Consistency Tests**: Foreign key relationships and index validation
- **Management Functions**: All migration management API functions tested

**Database Compatibility**: SQLite (development/testing) and PostgreSQL (production) support

## Integration Deliverables for Next Phase

**This phase will provide:**
- Complete CLI interface with all deployment modes functional
- Fully integrated authentication system across all components
- Production deployment infrastructure with Docker configurations
- Background processing system with ProcessPoolExecutor integration
- Admin CLI tools with complete functionality

**Context Updates Required:**
Upon phase completion, update `context_0d_security.md` with actual:
- Complete system architecture documentation
- All integration points and interface contracts
- Attack surface analysis and security boundaries
- Performance characteristics and bottleneck analysis

## Testing and Validation Requirements

### CLI Integration Testing
**Mode Switching**: Deployment mode functionality validation
**Authentication**: CLI authentication flow testing
**Backward Compatibility**: Existing workflow preservation validation

### Infrastructure Testing
**Container Deployment**: Docker deployment and service validation
**Background Processing**: ProcessPoolExecutor functionality testing
**Admin Tools**: Admin CLI command functionality validation

### Integration Validation
**End-to-End**: Complete system workflow testing
**Cross-Component**: Authentication + workspace + CLI integration testing
**Performance**: System performance under load validation