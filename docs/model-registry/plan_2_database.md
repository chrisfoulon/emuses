# Model Registry - Sub-Plan 2: Database & Multi-User Mode

## Implementation Overview

**Goal**: Implement database-backed model registry with multi-user permissions and API endpoints  
**Duration**: 1.5 weeks  
**Focus**: Database schema, permission system, FastAPI endpoints  
**Dependencies**: ✅ Sub-plan 1 foundation (LocalModelRegistry working)

## Progress Tracking Protocol
**CRITICAL**: After completing any task:
1. Mark checkbox [x] in this plan.md file immediately
2. Update TodoWrite status to "completed"  
3. Run tests to verify completion
4. Only mark complete after successful testing

## Task Breakdown

### Phase 2.1: Database Schema Implementation ║ tests/model_registry/test_database_schema.py ║ Database foundation ║ M

- [ ] **Task 2.1.1: Design and create database migration**
  - [ ] 2.1.1.a: Create Alembic migration for model registry tables
  - [ ] 2.1.1.b: Implement model_registry table with foreign keys to users/workspaces
  - [ ] 2.1.1.c: Add model_access table for permission management
  - [ ] 2.1.1.d: Create model_downloads table for usage tracking

- [ ] **Task 2.1.2: Create SQLAlchemy models**
  - [ ] 2.1.2.a: Add ModelRegistry model class in multi_user_service/models.py
  - [ ] 2.1.2.b: Add ModelAccess model for permissions
  - [ ] 2.1.2.c: Add ModelDownload model for analytics
  - [ ] 2.1.2.d: Configure relationships and constraints

- [ ] **Task 2.1.3: Implement database indexes and optimization**
  - [ ] 2.1.3.a: Add performance indexes for common queries
  - [ ] 2.1.3.b: Configure full-text search vectors
  - [ ] 2.1.3.c: Add database constraints for data integrity
  - [ ] 2.1.3.d: Test migration rollback functionality

### Phase 2.2: DatabaseModelRegistry Implementation ║ tests/model_registry/test_database_operations.py ║ Core database operations ║ L

- [ ] **Task 2.2.1: Create DatabaseModelRegistry class**
  - [ ] 2.2.1.a: Create emuses/tools/database_model_registry.py
  - [ ] 2.2.1.b: Implement constructor with database session and user context
  - [ ] 2.2.1.c: Add NumPy-style docstrings and comprehensive error handling
  - [ ] 2.2.1.d: Implement registry mode detection and initialization

- [ ] **Task 2.2.2: Implement model registration**
  - [ ] 2.2.2.a: Add register_model() method with database storage
  - [ ] 2.2.2.b: Coordinate filesystem storage with database metadata
  - [ ] 2.2.2.c: Generate unique model IDs and handle conflicts
  - [ ] 2.2.2.d: Update search vectors and metadata indexes

- [ ] **Task 2.2.3: Implement model querying and discovery**
  - [ ] 2.2.3.a: Add list_models() with permission filtering
  - [ ] 2.2.3.b: Implement search_models() with full-text search
  - [ ] 2.2.3.c: Add get_model() with detailed information
  - [ ] 2.2.3.d: Implement version resolution and filtering

### Phase 2.3: Permission System ║ tests/model_registry/test_permissions.py ║ Access control ║ M

- [ ] **Task 2.3.1: Create ModelPermissionManager class**
  - [ ] 2.3.1.a: Create emuses/tools/model_permission_manager.py
  - [ ] 2.3.1.b: Implement check_access() for permission validation
  - [ ] 2.3.1.c: Add grant_access() and revoke_access() methods
  - [ ] 2.3.1.d: Implement list_permissions() for access management

- [ ] **Task 2.3.2: Implement multi-level access control**
  - [ ] 2.3.2.a: Add owner-level permissions (full control)
  - [ ] 2.3.2.b: Implement workspace-level sharing
  - [ ] 2.3.2.c: Add public model access control
  - [ ] 2.3.2.d: Create permission inheritance and validation

- [ ] **Task 2.3.3: Security boundary enforcement**
  - [ ] 2.3.3.a: Add permission checks to all registry operations
  - [ ] 2.3.3.b: Implement user isolation and data protection
  - [ ] 2.3.3.c: Add audit logging for permission changes
  - [ ] 2.3.3.d: Create permission testing with edge cases

### Phase 2.4: FastAPI Endpoints ║ tests/foundation_fastapi_service/test_model_registry_endpoints.py ║ API interface ║ M

- [ ] **Task 2.4.1: Create model registry endpoints**
  - [ ] 2.4.1.a: Add model registry router to existing FastAPI app
  - [ ] 2.4.1.b: Implement GET /models for listing with filters
  - [ ] 2.4.1.c: Add GET /models/search for full-text search
  - [ ] 2.4.1.d: Create POST /models for model registration

- [ ] **Task 2.4.2: Implement model management endpoints**
  - [ ] 2.4.2.a: Add GET /models/{id} for detailed model information
  - [ ] 2.4.2.b: Implement PUT /models/{id} for metadata updates
  - [ ] 2.4.2.c: Add DELETE /models/{id} for model removal
  - [ ] 2.4.2.d: Create POST /models/{id}/download for download tracking

- [ ] **Task 2.4.3: Add permission management endpoints**
  - [ ] 2.4.3.a: Implement GET /models/{id}/access for permission listing
  - [ ] 2.4.3.b: Add POST /models/{id}/access for granting permissions
  - [ ] 2.4.3.c: Create DELETE /models/{id}/access/{user_id} for revocation
  - [ ] 2.4.3.d: Add admin endpoints for global model management

### Phase 2.5: CLI Integration Enhancement ║ tests/cli/test_database_mode_commands.py ║ Enhanced CLI ║ M

- [ ] **Task 2.5.1: Extend existing CLI commands for database mode**
  - [ ] 2.5.1.a: Update install command to support database registration
  - [ ] 2.5.1.b: Enhance list command with workspace and public filters
  - [ ] 2.5.1.c: Add search command for full-text registry search
  - [ ] 2.5.1.d: Update info command with permission and sharing details

- [ ] **Task 2.5.2: Add multi-user specific commands**
  - [ ] 2.5.2.a: Add share command for workspace model sharing
  - [ ] 2.5.2.b: Implement publish command for public model sharing
  - [ ] 2.5.2.c: Add workspace command for workspace-specific operations
  - [ ] 2.5.2.d: Create permissions command for access management

- [ ] **Task 2.5.3: Registry mode detection and configuration**
  - [ ] 2.5.3.a: Implement automatic registry backend selection
  - [ ] 2.5.3.b: Add configuration for database connection parameters
  - [ ] 2.5.3.c: Handle graceful fallback to local mode if database unavailable
  - [ ] 2.5.3.d: Add clear error messages for configuration issues

### Phase 2.6: Storage Coordination ║ tests/model_registry/test_storage_coordination.py ║ Filesystem integration ║ M

- [ ] **Task 2.6.1: Implement database-filesystem coordination**
  - [ ] 2.6.1.a: Create shared storage management for multi-user mode
  - [ ] 2.6.1.b: Implement atomic operations for database + filesystem
  - [ ] 2.6.1.c: Add integrity validation between database and files
  - [ ] 2.6.1.d: Create cleanup procedures for orphaned data

- [ ] **Task 2.6.2: Add model download and upload handling**
  - [ ] 2.6.2.a: Implement secure model upload with validation
  - [ ] 2.6.2.b: Add progress tracking for large model operations
  - [ ] 2.6.2.c: Create temporary staging area management
  - [ ] 2.6.2.d: Add download caching and optimization

### Phase 2.7: Testing & Integration ║ Comprehensive validation ║ Quality assurance ║ L

- [ ] **Task 2.7.1: Create comprehensive database test suite**
  - [ ] 2.7.1.a: Unit tests for DatabaseModelRegistry operations
  - [ ] 2.7.1.b: Permission system testing with various scenarios
  - [ ] 2.7.1.c: Database migration and rollback testing
  - [ ] 2.7.1.d: API endpoint testing with authentication

- [ ] **Task 2.7.2: Multi-user integration testing**
  - [ ] 2.7.2.a: Cross-user permission boundary testing
  - [ ] 2.7.2.b: Workspace isolation and sharing testing
  - [ ] 2.7.2.c: CLI command testing with database backend
  - [ ] 2.7.2.d: Storage coordination and integrity testing

- [ ] **Task 2.7.3: Update documentation and context**
  - [ ] 2.7.3.a: Document database schema and relationships
  - [ ] 2.7.3.b: Update API documentation with new endpoints
  - [ ] 2.7.3.c: Add CLI help and usage examples
  - [ ] 2.7.3.d: Create troubleshooting guide for database issues

## Testing Strategy

### Unit Testing
**Approach**: Test database operations in isolation with test database
- DatabaseModelRegistry CRUD operations with mocked dependencies
- Permission system logic with various access scenarios
- Search functionality with different query patterns
- API endpoint logic with authentication mocking

### Integration Testing  
**Approach**: Test full workflow with real database and authentication
- End-to-end model registration and discovery workflows
- Multi-user permission scenarios with real database
- API endpoints with real authentication system
- CLI commands with database backend integration

### Security Testing
**Approach**: Validate permission boundaries and data isolation
- Permission bypass attempt prevention
- User data isolation verification
- Malicious model upload protection
- Access control edge case validation

## Risk Assessment

### Technical Risks - MEDIUM
- **Database migration complexity**: New tables with foreign key constraints
- **Permission system complexity**: Multi-level access control logic
- **Storage coordination**: Maintaining database-filesystem consistency

### Implementation Risks - MEDIUM  
- **API endpoint integration**: Adding to existing FastAPI service structure
- **CLI mode detection**: Seamless switching between local and database modes
- **Search performance**: Full-text search optimization for large registries

### Security Risks - HIGH
- **Permission enforcement**: Critical security boundary implementation
- **Data isolation**: Preventing cross-user data leakage
- **Model validation**: Preventing malicious model uploads

## Success Criteria

### Functional Requirements
- [x] Database schema deployed and operational
- [x] Multi-user model registration with workspace isolation
- [x] Permission system with owner/workspace/public access levels
- [x] FastAPI endpoints with authentication integration
- [x] CLI commands work seamlessly with database backend

### Quality Requirements  
- [x] >90% test coverage for all database operations
- [x] Permission system passes security boundary tests
- [x] API performance meets response time requirements
- [x] Database queries optimized with proper indexing

### Integration Requirements
- [x] Foundation LocalModelRegistry patterns extended successfully
- [x] Existing authentication system integration operational
- [x] CLI commands maintain backward compatibility
- [x] Storage coordination maintains data integrity

## Milestone Checkpoints

**Checkpoint 2.A** (After Phase 2.2): Database operations working
**Checkpoint 2.B** (After Phase 2.4): API endpoints operational  
**Checkpoint 2.C** (After Phase 2.7): Multi-user testing complete

## Next Sub-Plan Integration

**Sub-Plan 3 Dependencies**:
- [x] Database registry with working CRUD operations
- [x] Permission system operational for access control
- [x] API endpoints established for cloud storage integration
- [x] Storage architecture ready for cloud abstraction layer

This database implementation provides the multi-user foundation that will be extended with cloud storage capabilities in sub-plan 3.