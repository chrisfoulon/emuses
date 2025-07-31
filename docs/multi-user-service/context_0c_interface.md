# Multi-User EMUSES Service - Interface Context (Phase 0c)

## Phase Focus
**Domain**: CLI integration, deployment infrastructure, admin tools, background processing
**Scope**: Multi-mode CLI, HTTP authentication, Docker deployment, ProcessPoolExecutor, admin interface
**Prerequisites**: Plan 0b completion (workspace APIs, job management, quota system)

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

## Background Processing Architecture

### ProcessPoolExecutor Integration
**Worker Configuration**: Process pool sizing and worker management
**Job Queue**: Job queue management and task distribution
**Process Monitoring**: Worker health monitoring and cleanup

### Task Execution Patterns
**Pipeline Processing**: EMUSES pipeline execution in separate processes
**User Context**: User workspace isolation in background processes
**Status Tracking**: Task status tracking and progress reporting

### Task Management APIs
**Submission**: Task submission and queue management endpoints
**Control**: Task cancellation and cleanup logic
**Monitoring**: Process health monitoring and status reporting

## Production Infrastructure

### Docker Deployment Configuration
**Compose Files**: Production docker-compose.yml with PostgreSQL
**Service Containers**: API service containerization
**Networking**: nginx reverse proxy configuration

### Application Containerization
**Dockerfile**: API service Dockerfile with health checks
**Startup Scripts**: Application initialization and health validation
**Environment**: Production environment configuration templates

### Infrastructure Management
**Secrets Management**: Secure secrets and environment variable handling
**Monitoring**: Application monitoring and logging configuration
**Health Checks**: Service health validation and startup verification

## Admin Tools Architecture

### Admin API Endpoints
**User Management**: User creation, listing, updating, deletion endpoints
**Quota Management**: Quota adjustment and monitoring endpoints
**System Monitoring**: Job queue status and system health endpoints

### CLI Admin Commands
**User Operations**: `emuses admin add-user`, quota management commands
**System Control**: `emuses admin system-status`, job cancellation commands
**Help System**: Comprehensive help text and usage examples

### Research Environment Optimization
**CLI-First Design**: Admin tools optimized for CLI access
**Documentation**: Comprehensive usage examples and troubleshooting
**Workflow Integration**: Admin workflows suited for research environments

## Database Migration Completion

### Workspace Table Migrations
**Schema Completion**: Workspace and dataset table migrations
**Relationships**: Job table migrations with user relationships
**Constraints**: Database constraints and index optimization

### Migration Management
**CLI Integration**: Migration commands integrated into admin CLI
**Validation**: Migration validation and rollback capabilities
**Initialization**: Database initialization and setup scripts

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