# Multi-User EMUSES Service - Foundation Plan (0a)

## Sub-Plan Overview
**Focus**: Authentication foundation, database models, core infrastructure
**Duration**: 3-4 days
**Dependencies**: None (foundation layer)
**Outputs**: User models, authentication system, database migrations

## Tasks

### Task 1: Create user models and database schema ║ `tests/multi-user-service/test_auth_models.py` ║ Add SQLAlchemy user models with FastAPI-Users integration ║ L
- [ ] 1.1: Create User model extending SQLAlchemyBaseUserTableUUID
  - [ ] 1.1.1: Add EMUSES-specific fields (organization, role, quotas)
  - [ ] 1.1.2: Add usage tracking fields (storage, compute hours)
  - [ ] 1.1.3: Add relationships to workspaces and jobs
- [ ] 1.2: Create UserSettings model for preferences
  - [ ] 1.2.1: Add default EMUSES configuration preferences
  - [ ] 1.2.2: Add notification and UI preferences
- [ ] 1.3: Create database configuration and connection setup
  - [ ] 1.3.1: Add environment-based database URL configuration
  - [ ] 1.3.2: Create async database session management
  - [ ] 1.3.3: Add database initialization and health checks
  - [ ] 1.3.4: Configure connection pooling for concurrent users (asyncpg pool)
  - [ ] 1.3.5: Add database performance monitoring and query optimization

### Task 2: Implement JWT authentication backend ║ `tests/multi-user-service/test_auth_backend.py` ║ FastAPI-Users JWT authentication with secure token management ║ M
- [ ] 2.1: Configure JWT authentication backend
  - [ ] 2.1.1: Set up JWT secret key from environment
  - [ ] 2.1.2: Configure token expiration and refresh policies
  - [ ] 2.1.3: Add bearer transport configuration
- [ ] 2.2: Create user manager with EMUSES-specific logic
  - [ ] 2.2.1: Implement user registration validation
  - [ ] 2.2.2: Add password complexity requirements
  - [ ] 2.2.3: Create user quota initialization
  - [ ] 2.2.4: Implement token rotation and refresh strategy
  - [ ] 2.2.5: Add token blacklisting for logout/security events
- [ ] 2.3: Set up FastAPI-Users instance
  - [ ] 2.3.1: Configure authentication backends
  - [ ] 2.3.2: Create user dependency functions
  - [ ] 2.3.3: Add role-based access dependencies

### Task 3: Add authentication middleware to existing FastAPI app ║ `tests/multi-user-service/test_auth_middleware.py` ║ Integrate authentication with existing middleware stack ║ M
- [ ] 3.1: Add authentication middleware after CORS
  - [ ] 3.1.1: Position auth middleware correctly in stack
  - [ ] 3.1.2: Preserve existing error handling patterns
  - [ ] 3.1.3: Add authentication error handlers
- [ ] 3.2: Create optional authentication dependency
  - [ ] 3.2.1: Implement conditional authentication based on deployment mode
  - [ ] 3.2.2: Add graceful degradation for local mode
  - [ ] 3.2.3: Maintain backward compatibility
- [ ] 3.3: Update existing endpoints with user context
  - [ ] 3.3.1: Add user dependencies to protected endpoints
  - [ ] 3.3.2: Preserve existing API signatures
  - [ ] 3.3.3: Add user context to request processing

### Task 4: Create authentication endpoints ║ `tests/multi-user-service/test_auth_endpoints.py` ║ Registration, login, logout, and token management ║ S
- [ ] 4.1: Add authentication routes from FastAPI-Users
  - [ ] 4.1.1: Register JWT authentication router
  - [ ] 4.1.2: Add user registration router
  - [ ] 4.1.3: Configure route prefixes and tags
- [ ] 4.2: Create simple authentication endpoints
  - [ ] 4.2.1: Add token validation endpoint
  - [ ] 4.2.2: Create basic user profile management
  - [ ] 4.2.3: Add simple password reset functionality
- [ ] 4.3: Implement simple user registration workflow
  - [ ] 4.3.1: Add email validation and uniqueness checks
  - [ ] 4.3.2: Create default workspace during registration
  - [ ] 4.3.3: Initialize minimal user settings (n_jobs, optuna_trials defaults)

### Task 5A: Create initial database migrations ║ `tests/multi-user-service/test_initial_migrations.py` ║ Alembic migration setup before model testing ║ S
- [ ] 5A.1: Set up Alembic configuration
  - [ ] 5A.1.1: Create migration environment
  - [ ] 5A.1.2: Configure database metadata detection
  - [ ] 5A.1.3: Add migration script templates
- [ ] 5A.2: Create initial user and auth table migrations
  - [ ] 5A.2.1: Generate user table migrations
  - [ ] 5A.2.2: Add authentication table migrations
  - [ ] 5A.2.3: Create index and constraint migrations

### Task 5: Implement deployment mode configuration ║ `tests/multi-user-service/test_deployment_config.py` ║ Environment-based authentication enabling/disabling ║ S
- [ ] 5.1: Create deployment configuration class
  - [ ] 5.1.1: Add environment variable parsing for deployment modes
  - [ ] 5.1.2: Configure authentication requirements per mode
  - [ ] 5.1.3: Set up database connection configs
- [ ] 5.2: Add configuration validation
  - [ ] 5.2.1: Validate required environment variables
  - [ ] 5.2.2: Check database connectivity in auth-required modes
  - [ ] 5.2.3: Create configuration health checks

## Validation Strategy & Context Updates

**Real-Time Context Updates Required:**
- Each completed sub-task must update context files with **actual deliverables** (not planned)
- Validation checkpoints after each sub-task verify implementation matches plan
- Context files maintained with verified actual deliverables throughout implementation

**Completion Validation Process:**
- Tasks cannot be marked complete without verifying they work as intended
- Manual verification of each deliverable against success criteria
- Integration testing at each major milestone

**Context Evolution Responsibilities:**
Upon completion of this phase, update the following context files with actual deliverables:
- `context_0b_workspace.md` - Add actual user model APIs, authentication patterns, database access methods
- Document actual JWT implementation details, middleware integration patterns, deployment configuration

## Success Criteria & Validation Checkpoints
- [ ] **User models created and tested** - Verify with actual model tests passing
- [ ] **JWT authentication system functional** - Verify with actual token generation/validation tests
- [ ] **Database migrations properly sequenced** - Verify with actual migration execution
- [ ] **Authentication middleware integrated** - Verify with actual middleware tests in FastAPI stack
- [ ] **Deployment modes configured** - Verify with actual deployment mode switching tests
- [ ] **Foundation ready for workspace layer** - Verify integration contracts documented in context

**Integration Deliverables for Plan 0b:**
- User model definitions and database schemas (actual)
- Authentication middleware and user dependency functions (actual)
- Database connection and session management patterns (actual)
- JWT user validation and role-based access methods (actual)

## Next Steps
Upon completion and context updates, proceed to **Plan 0b: Workspace Isolation** which builds upon the authentication foundation established here.