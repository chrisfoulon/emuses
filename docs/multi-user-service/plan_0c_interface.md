# Multi-User EMUSES Service - Interface and Infrastructure Plan (0c)

## Sub-Plan Overview
**Focus**: CLI integration, deployment infrastructure, admin tools, background processing
**Duration**: 2-3 days
**Dependencies**: Plan 0b (Workspace) - requires workspace APIs and job management
**Outputs**: Multi-mode CLI, production deployment, admin interface, background processing

## Tasks

### Task 10: Add deployment mode detection ║ `tests/multi-user-service/test_deployment_modes.py` ║ CLI support for three deployment modes ║ M
- [ ] 10.1: Implement deployment mode configuration
  - [ ] 10.1.1: Add environment variable detection
  - [ ] 10.1.2: Create mode-specific configuration classes
  - [ ] 10.1.3: Add service discovery for multi-user mode
- [ ] 10.2: Extend CLI parameter handling
  - [ ] 10.2.1: Add `--service` and `--token` parameters
  - [ ] 10.2.2: Implement parameter validation per mode
  - [ ] 10.2.3: Add backward compatibility checks
- [ ] 10.3: Update service manager for multi-mode
  - [ ] 10.3.1: Add external service connection support
  - [ ] 10.3.2: Implement service health checking
  - [ ] 10.3.3: Add graceful mode switching

### Task 11: Implement authentication in HTTP client ║ `tests/multi-user-service/test_auth_client.py` ║ Token management and authentication headers ║ S
- [ ] 11.1: Extend ServiceHTTPClient with authentication
  - [ ] 11.1.1: Add token header injection
  - [ ] 11.1.2: Implement token refresh logic
  - [ ] 11.1.3: Add authentication error handling
- [ ] 11.2: Create token storage and management
  - [ ] 11.2.1: Implement secure token storage (~/.emuses/token)
  - [ ] 11.2.2: Add token validation and expiry checks
  - [ ] 11.2.3: Create login/logout CLI commands
- [ ] 11.3: Add user session management
  - [ ] 11.3.1: Implement automatic login flows
  - [ ] 11.3.2: Add session persistence across CLI calls
  - [ ] 11.3.3: Create user context display in CLI

### Task 12: Create Docker deployment configurations ║ `tests/multi-user-service/test_docker_deployment.py` ║ Container orchestration for production ║ S
- [ ] 12.1: Create Docker compose files
  - [ ] 12.1.1: Add production docker-compose.yml
  - [ ] 12.1.2: Configure PostgreSQL service
  - [ ] 12.1.3: Add nginx reverse proxy configuration
- [ ] 12.2: Create application Dockerfiles
  - [ ] 12.2.1: Create API service Dockerfile
  - [ ] 12.2.2: Simplified deployment (no separate worker service needed)
  - [ ] 12.2.3: Add health check and startup scripts
- [ ] 12.3: Add environment configuration
  - [ ] 12.3.1: Create production environment templates
  - [ ] 12.3.2: Add secrets management
  - [ ] 12.3.3: Configure monitoring and logging

### Task 13: Add database migrations ║ `tests/multi-user-service/test_migrations.py` ║ Complete migration system for workspace models ║ S
- [ ] 13.1: Create workspace table migrations
  - [ ] 13.1.1: Add workspace and dataset table migrations
  - [ ] 13.1.2: Create job table migrations with user relationships
  - [ ] 13.1.3: Add quota and usage tracking table migrations
- [ ] 13.2: Add migration management
  - [ ] 13.2.1: Create migration CLI commands
  - [ ] 13.2.2: Add migration validation and rollback
  - [ ] 13.2.3: Implement database initialization scripts

### Task 14: Implement hybrid background task management ║ `tests/multi-user-service/test_background_tasks.py` ║ ProcessPoolExecutor integration for job processing ║ M
- [ ] 14.1: Set up ProcessPoolExecutor configuration
  - [ ] 14.1.1: Configure process pool with appropriate worker count
  - [ ] 14.1.2: Create job queue management
  - [ ] 14.1.3: Add process monitoring and cleanup
- [ ] 14.2: Create background task functions
  - [ ] 14.2.1: Implement pipeline execution in separate processes
  - [ ] 14.2.2: Add user context and workspace isolation
  - [ ] 14.2.3: Create task status tracking and reporting
- [ ] 14.3: Add task management APIs
  - [ ] 14.3.1: Task submission and status endpoints
  - [ ] 14.3.2: Task cancellation and cleanup logic
  - [ ] 14.3.3: Process health monitoring

### Task 15: Implement CLI admin tools ║ `tests/multi-user-service/test_admin_cli.py` ║ Simple API endpoints with CLI commands for admin tasks ║ S
- [ ] 15.1: Create admin API endpoints
  - [ ] 15.1.1: Add user management endpoints (create, list, update, delete)
  - [ ] 15.1.2: Add quota management endpoints
  - [ ] 15.1.3: Add system monitoring endpoints (job queues, health)
- [ ] 15.2: Create CLI admin commands
  - [ ] 15.2.1: Add `emuses admin add-user` command
  - [ ] 15.2.2: Add `emuses admin set-quota` command  
  - [ ] 15.2.3: Add `emuses admin system-status` command
  - [ ] 15.2.4: Add `emuses admin cancel-job` command for stuck jobs
- [ ] 15.3: Add admin documentation and help
  - [ ] 15.3.1: Create comprehensive help text for all admin commands
  - [ ] 15.3.2: Add usage examples and troubleshooting guide
  - [ ] 15.3.3: Document admin workflows for research environments

## Validation Strategy & Context Updates

**Real-Time Context Updates Required:**
- Each completed sub-task must update context files with **actual deliverables** (not planned)
- Validation checkpoints after each sub-task verify implementation matches plan
- Context files maintained with verified actual deliverables throughout implementation

**Completion Validation Process:**
- Tasks cannot be marked complete without verifying they work as intended
- Manual verification of CLI mode switching and authentication integration
- End-to-end testing of deployment infrastructure and admin tools

**Context Evolution Responsibilities:**
Upon completion of this phase, update the following context files with actual deliverables:
- `context_0d_security.md` - Add complete system architecture, all integration points, attack surface documentation
- Document actual CLI authentication flows, deployment configurations, background processing implementations

## Success Criteria & Validation Checkpoints
- [ ] **CLI supports all three deployment modes** - Verify with actual mode switching and functionality tests
- [ ] **Authentication integrated in HTTP client** - Verify with actual token handling and refresh tests
- [ ] **Docker deployment configurations ready** - Verify with actual deployment and container tests
- [ ] **Database migrations complete** - Verify with actual migration execution and rollback tests
- [ ] **Background processing operational** - Verify with actual ProcessPoolExecutor job processing tests
- [ ] **Admin CLI tools functional** - Verify with actual admin command execution and validation tests
- [ ] **Production infrastructure ready for security validation** - Verify complete system integration tests

**Integration Deliverables for Plan 0d:**
- Complete CLI interface with all deployment modes (actual)
- Fully integrated authentication system across all components (actual)
- Production deployment infrastructure with Docker configurations (actual)
- Background processing system with ProcessPoolExecutor integration (actual)
- Admin CLI tools with complete functionality (actual)
- Full system ready for comprehensive security and performance testing (actual)

## Integration Points
**From Plan 0b**: Workspace APIs, job management, quota system (actual implementations)
**To Plan 0d**: Complete system ready for security testing and validation (actual implementations)

## Next Steps
Upon completion and context updates, proceed to **Plan 0d: Security and Testing** which provides comprehensive security validation, performance testing, and documentation for the complete system.