# Multi-User EMUSES Service - Foundation Context (Phase 0a)

## Phase Focus
**Domain**: Authentication foundation, database models, core infrastructure
**Scope**: User models, JWT authentication, database setup, middleware integration
**Prerequisites**: None (foundation layer)

## Key Integration Points from Existing Codebase

### FastAPI Service Integration
**Current State**: Single-user FastAPI service with middleware stack
**Integration Target**: Add authentication middleware after CORS
**Pattern**: `app.add_middleware()` calls in `foundation_fastapi_service/app.py:15-20`

### Database Architecture
**Current State**: No user persistence, file-based storage
**Integration Target**: PostgreSQL with SQLAlchemy async patterns
**Connection Point**: Environment-aware configuration extending existing patterns

### Job Manager Extension Point
**Current State**: `JobManager` class in `foundation_fastapi_service/job_manager.py`
**Extension Strategy**: Create `MultiUserJobManager` extending existing class
**User Context**: Add optional `user_id` parameter to constructor

### CLI Service Integration
**Current State**: Service-oriented CLI with auto-start in `cli/main.py`
**Integration Target**: Add authentication parameter handling
**Pattern**: Extend `_convert_typer_args_to_service_config()` function

## Authentication Architecture Patterns

### FastAPI-Users Integration
**Strategy**: Use FastAPI-Users for battle-tested authentication
**Components**: User model, authentication backend, middleware integration
**Security**: JWT tokens with environment-based secrets

### Database Models Design
**User Model**: Extend `SQLAlchemyBaseUserTableUUID` for EMUSES-specific fields
**Relationships**: User → Workspaces → Jobs hierarchy
**Constraints**: Email uniqueness, role-based access patterns

### Middleware Stack Integration
**Position**: Authentication middleware after CORS, before rate limiting
**Conditional**: Environment-based authentication enabling/disabling
**Compatibility**: Preserve existing error handling patterns

## Deployment Mode Configuration

### Three-Mode Strategy
- **Local Mode**: No authentication, existing behavior preserved
- **Multi-User Mode**: Selective authentication, monitoring open
- **Production Mode**: Full authentication, complete isolation

### Environment Configuration
**Variables**: `EMUSES_DEPLOYMENT_MODE`, `DATABASE_URL`, `JWT_SECRET`
**Validation**: Required variables per deployment mode
**Health Checks**: Database connectivity validation

## Database Migration Strategy

### Alembic Integration
**Setup**: Migration environment with metadata detection
**Sequencing**: User tables before workspace tables
**Rollback**: Migration validation and rollback capabilities

### Connection Pooling
**Implementation**: asyncpg connection pool for concurrent users
**Configuration**: Environment-based pool sizing
**Monitoring**: Connection pool performance tracking

## Security Patterns

### JWT Token Management
**Generation**: Secure token generation with rotation
**Validation**: Token expiration and refresh policies
**Storage**: Secure token storage patterns for CLI

### Password Security
**Hashing**: bcrypt password hashing
**Complexity**: Password complexity requirements
**Validation**: Email validation and uniqueness checks

## Integration Deliverables for Next Phase

**This phase will provide:**
- User model definitions and database schemas
- Authentication middleware and user dependency functions
- Database connection and session management patterns
- JWT user validation and role-based access methods
- Deployment mode configuration classes

**Context Updates Required:**
Upon phase completion, update `context_0b_workspace.md` with actual:
- User model API contracts and relationships
- Authentication patterns and middleware integration
- Database access methods and session management
- JWT validation and user context injection patterns