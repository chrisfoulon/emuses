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