# Multi-User EMUSES Service - Foundation Plan (0a)

## Sub-Plan Overview
**Focus**: Authentication foundation, database models, core infrastructure
**Duration**: 3-4 days
**Dependencies**: None (foundation layer)
**Outputs**: User models, authentication system, database migrations

## Tasks

### Task 1: Create user models and database schema ║ `tests/multi-user-service/test_auth_models.py` ║ Add SQLAlchemy user models with FastAPI-Users integration ║ L ✅ COMPLETED
- [x] 1.1: Create User model extending SQLAlchemyBaseUserTableUUID
  - [x] 1.1.1: Add EMUSES-specific fields (organization, role, quotas)
  - [x] 1.1.2: Add usage tracking fields (storage, compute hours)
  - [x] 1.1.3: Add relationships to workspaces and jobs
- [x] 1.2: Create UserSettings model for preferences
  - [x] 1.2.1: Add default EMUSES configuration preferences
  - [x] 1.2.2: Add notification and UI preferences
- [x] 1.3: Create database configuration and connection setup
  - [x] 1.3.1: Add environment-based database URL configuration
  - [x] 1.3.2: Create async database session management
  - [x] 1.3.3: Add database initialization and health checks
  - [x] 1.3.4: Configure connection pooling for concurrent users (asyncpg pool)
  - [x] 1.3.5: Add database performance monitoring and query optimization

### Task 2: Implement JWT authentication backend ║ `tests/multi-user-service/test_auth_backend.py` ║ FastAPI-Users JWT authentication with secure token management ║ M ✅ COMPLETED
- [x] 2.1: Configure JWT authentication backend
  - [x] 2.1.1: Set up JWT secret key from environment
  - [x] 2.1.2: Configure token expiration and refresh policies
  - [x] 2.1.3: Add bearer transport configuration
- [x] 2.2: Create user manager with EMUSES-specific logic
  - [x] 2.2.1: Implement user registration validation
  - [x] 2.2.2: Add password complexity requirements
  - [x] 2.2.3: Create user quota initialization
  - [x] 2.2.4: Implement token rotation and refresh strategy
  - [x] 2.2.5: Add token blacklisting for logout/security events
- [x] 2.3: Set up FastAPI-Users instance
  - [x] 2.3.1: Configure authentication backends
  - [x] 2.3.2: Create user dependency functions
  - [x] 2.3.3: Add role-based access dependencies

### Task 3: Add authentication middleware to existing FastAPI app ║ `tests/multi-user-service/test_auth_middleware.py` ║ Integrate authentication with existing middleware stack ║ M ✅ COMPLETED
- [x] 3.1: Add authentication middleware after CORS
  - [x] 3.1.1: Position auth middleware correctly in stack
  - [x] 3.1.2: Preserve existing error handling patterns
  - [x] 3.1.3: Add authentication error handlers
- [x] 3.2: Create optional authentication dependency
  - [x] 3.2.1: Implement conditional authentication based on deployment mode
  - [x] 3.2.2: Add graceful degradation for local mode
  - [x] 3.2.3: Maintain backward compatibility
- [x] 3.3: Update existing endpoints with user context
  - [x] 3.3.1: Add user dependencies to protected endpoints
  - [x] 3.3.2: Preserve existing API signatures
  - [x] 3.3.3: Add user context to request processing

### Task 4: Create authentication endpoints ║ `tests/multi-user-service/test_auth_endpoints.py` ║ Registration, login, logout, and token management ║ S ✅ COMPLETED
- [x] 4.1: Add authentication routes from FastAPI-Users
  - [x] 4.1.1: Register JWT authentication router
  - [x] 4.1.2: Add user registration router
  - [x] 4.1.3: Configure route prefixes and tags
- [x] 4.2: Create simple authentication endpoints
  - [x] 4.2.1: Add token validation endpoint
  - [x] 4.2.2: Create basic user profile management
  - [x] 4.2.3: Add simple password reset functionality
- [x] 4.3: Implement simple user registration workflow
  - [x] 4.3.1: Add email validation and uniqueness checks
  - [x] 4.3.2: Create default workspace during registration
  - [x] 4.3.3: Initialize minimal user settings (n_jobs, optuna_trials defaults)

### Task 5A: Create initial database migrations ║ `tests/multi-user-service/test_initial_migrations.py` ║ Alembic migration setup before model testing ║ S ✅ COMPLETED
- [x] 5A.1: Set up Alembic configuration
  - [x] 5A.1.1: Create migration environment
  - [x] 5A.1.2: Configure database metadata detection
  - [x] 5A.1.3: Add migration script templates
- [x] 5A.2: Create initial user and auth table migrations
  - [x] 5A.2.1: Generate user table migrations
  - [x] 5A.2.2: Add authentication table migrations
  - [x] 5A.2.3: Create index and constraint migrations

### Task 5: Implement deployment mode configuration ║ `tests/multi-user-service/test_deployment_config.py` ║ Environment-based authentication enabling/disabling ║ S ✅ COMPLETED
- [x] 5.1: Create deployment configuration class
  - [x] 5.1.1: Add environment variable parsing for deployment modes
  - [x] 5.1.2: Configure authentication requirements per mode
  - [x] 5.1.3: Set up database connection configs
- [x] 5.2: Add configuration validation
  - [x] 5.2.1: Validate required environment variables
  - [x] 5.2.2: Check database connectivity in auth-required modes
  - [x] 5.2.3: Create configuration health checks

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

## Success Criteria & Validation Checkpoints ✅ ALL COMPLETED
- [x] **User models created and tested** - ✅ 3 model tests passing (User, UserSettings, table structure)
- [x] **JWT authentication system functional** - ✅ 6 auth backend tests passing (token generation, validation, user manager)
- [x] **Database migrations properly sequenced** - ✅ 6 migration tests passing (Alembic config, environment, initial migration)
- [x] **Authentication middleware integrated** - ✅ 7 middleware tests passing (FastAPI integration, conditional auth)
- [x] **Deployment modes configured** - ✅ 5 database config tests passing (local/multi-user/production modes)
- [x] **Foundation ready for workspace layer** - ✅ Context files updated with actual deliverables

**Integration Deliverables for Plan 0b:**
- User model definitions and database schemas (actual)
- Authentication middleware and user dependency functions (actual)
- Database connection and session management patterns (actual)
- JWT user validation and role-based access methods (actual)

## Next Steps
Upon completion and context updates, proceed to **Plan 0b: Workspace Isolation** which builds upon the authentication foundation established here.