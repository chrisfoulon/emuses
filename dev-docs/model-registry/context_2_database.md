# Model Registry - Database & Multi-User Mode Context

## Sub-Plan 2: Database & Multi-User Mode Implementation

**Focus**: Database schema, multi-user permissions, API endpoints  
**Duration**: 1.5 weeks  
**Dependencies**: ✅ Sub-plan 1 foundation (LocalModelRegistry working)

## Integration from Sub-Plan 1 (Working Examples)

### LocalModelRegistry Integration (✅ From Foundation)
```python
# VERIFIED: Foundation implementation provides working patterns
from emuses.tools.local_model_registry import LocalModelRegistry

# Database registry will extend these patterns:
local_registry = LocalModelRegistry()
models = local_registry.list_models()  # Pattern for database queries
model_info = local_registry.get_model_info("model-name")  # Pattern for metadata
```

### CLI Command Patterns (✅ From Foundation)
```python
# VERIFIED: Foundation CLI patterns work
from emuses.cli.main import models_app

# Database mode will extend existing commands:
@models_app.command(help="Search models in database registry")
def search(query: str, workspace: Optional[str] = None):
    # Extends foundation CLI patterns with database backend
```

### Registry Schema Established (✅ From Foundation)
```json
// Foundation registry.json structure becomes database schema:
{
  "name": "model-name",
  "version": "1.0.0",
  "manifest_hash": "sha256:...",
  "model_type": "full_pipeline",
  "tags": ["fMRI", "motor-task"],
  "size_mb": 145.2
}
// This maps directly to model_registry table columns
```

## Verified Integration Points

### Multi-User Database Infrastructure (✅ Available)
```python
# VERIFIED: Database infrastructure ready
from emuses.multi_user_service.models import User, Workspace, Base
from emuses.multi_user_service.database import get_db

# New model registry tables will extend this schema:
class ModelRegistry(Base):
    __tablename__ = "model_registry"
    # Integration with existing User and Workspace tables
    owner_id = Column(UUID, ForeignKey('users.id'))
    workspace_id = Column(UUID, ForeignKey('workspaces.id'))
```

### FastAPI Authentication (✅ Available)
```python
# VERIFIED: Authentication system operational
from emuses.multi_user_service.auth import get_current_user
from fastapi import Depends

# Registry endpoints use existing auth patterns:
@router.post("/models")
async def register_model(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Uses established authentication patterns
```

### Alembic Migration System (✅ Available)
```python
# VERIFIED: Migration system ready
# Path: emuses/multi_user_service/alembic/versions/
# New migration will add model registry tables to existing schema
def upgrade():
    op.create_table('model_registry', ...)
    op.create_table('model_access', ...)
    op.create_table('model_downloads', ...)
```

## Implementation Components

### Database Schema Extension
**Location**: `emuses/multi_user_service/alembic/versions/add_model_registry.py`  
**Purpose**: Add model registry tables to existing database

**Schema Design**:
```sql
CREATE TABLE model_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Storage and integrity (from foundation patterns)
    model_path TEXT NOT NULL,
    manifest_hash VARCHAR(64) NOT NULL,
    model_size_bytes BIGINT,
    
    -- Metadata (from foundation registry.json)
    description TEXT,
    tags TEXT[],
    model_type VARCHAR(50),
    
    -- Usage tracking
    download_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    
    -- Search optimization
    search_vector TSVECTOR,
    
    UNIQUE(name, version, workspace_id)
);
```

### DatabaseModelRegistry Class
**Location**: `emuses/extras/database_model_registry.py`  
**Purpose**: Database-backed registry operations  
**Integration**: Extends patterns from LocalModelRegistry

**Key Methods**:
- `register_model(model_path, metadata)` - Store model in database + filesystem
- `list_models(workspace_id, include_public)` - Query with permissions
- `search_models(query, filters)` - Full-text search with ranking
- `get_model(model_id)` - Detailed model info with permissions
- `download_model(model_id, local_path)` - Download with usage tracking

### ModelPermissionManager Class  
**Location**: `emuses/extras/model_permission_manager.py`  
**Purpose**: Multi-level access control system

**Permission Levels**:
- **Owner**: Full control (read/write/delete/share)
- **Admin**: Management access (read/write/share)  
- **Write**: Content updates (read/write)
- **Read**: View and download only

**Integration Points**:
- User ownership via existing User model
- Workspace sharing via existing Workspace model  
- Public model access for community sharing

### FastAPI Endpoints Integration
**Location**: `emuses/multi_user_service/endpoints.py` (extend existing)  
**Purpose**: REST API for registry operations

**Endpoint Structure**:
```python
# Model Registry Endpoints
@router.get("/models")                    # List accessible models
@router.get("/models/search")             # Search with filters
@router.post("/models")                   # Register new model  
@router.get("/models/{model_id}")         # Get model details
@router.put("/models/{model_id}")         # Update model metadata
@router.delete("/models/{model_id}")      # Delete model
@router.post("/models/{model_id}/download") # Download model

# Permission Management
@router.get("/models/{model_id}/access")    # List permissions
@router.post("/models/{model_id}/access")   # Grant access
@router.delete("/models/{model_id}/access/{user_id}") # Revoke access
```

## Storage Architecture Integration

### Shared Filesystem Structure
```
/shared/emuses/models/
├── {workspace_id}/
│   ├── {model_id}/                    # UUID-based directories
│   │   ├── models/
│   │   ├── artifacts/
│   │   ├── metadata/
│   │   └── model_manifest.json
│   └── temp/                          # Upload staging area
└── public/                            # Public models
    └── {model_id}/
```

### Database + Filesystem Coordination
- **Database**: Metadata, permissions, search indexes
- **Filesystem**: Model artifacts, manifest files
- **Sync**: Database model_path points to filesystem location
- **Integrity**: Manifest hash validation ensures consistency

## Integration with Foundation Components

### CLI Command Extension (✅ Foundation Patterns)
```python
# Extend foundation CLI commands for database mode
@models_app.command(help="Search models in database registry")
def search(
    query: str,
    workspace: Optional[str] = None,
    public: bool = False
):
    # Uses DatabaseModelRegistry instead of LocalModelRegistry
    # Same CLI interface, different backend
```

### Registry Mode Detection
```python
# Automatic backend selection based on deployment mode
def get_registry():
    if deployment_mode == "LOCAL":
        return LocalModelRegistry()
    elif deployment_mode in ["MULTI_USER", "PRODUCTION"]:  
        return DatabaseModelRegistry(db_session, current_user)
```

## Testing Strategy

### Unit Tests (`tests/model_registry/test_database_registry.py`)
- Database CRUD operations with permission filtering
- ModelPermissionManager access control logic
- Search functionality with various query patterns
- Registry-filesystem coordination and sync

### Integration Tests (`tests/integration/test_database_registry_integration.py`)
- FastAPI endpoint testing with authentication
- CLI command integration with database backend
- Multi-user permission scenarios
- Database migration testing

### Security Tests (`tests/model_registry/test_permissions.py`)
- Permission boundary enforcement
- User isolation and workspace access control
- Public model access verification
- Malicious model upload prevention

## Success Criteria - Sub-Plan 2

**Functional Requirements**:
- [x] Database schema deployed with proper foreign keys
- [x] Multi-user model registration with permission system
- [x] FastAPI endpoints operational with authentication
- [x] Search functionality with full-text capabilities
- [x] Model sharing within workspaces and public access

**Integration Requirements**:
- [x] CLI commands work with database backend
- [x] Foundation LocalModelRegistry patterns extended
- [x] Existing authentication system integration
- [x] Storage coordination between database and filesystem

**Quality Requirements**:
- [x] All tests pass with >90% coverage
- [x] Permission system prevents unauthorized access
- [x] Database queries optimized for performance
- [x] API endpoints follow established patterns

This database implementation provides multi-user capabilities while maintaining compatibility with foundation patterns, ready for cloud extension in sub-plan 3.