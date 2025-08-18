# Model Registry Implementation - Context

## Current State Analysis

### Deployment Mode Architecture

EMUSES supports three distinct deployment modes that require different registry approaches:

#### 1. Local Mode
**Current State**: Single-user filesystem-based operation
**Registry Requirements**: 
- Simple model discovery in user home directory
- File-based model installation and management
- No authentication or permission system needed
- Symlink support for shared storage scenarios

#### 2. Multi-User Mode  
**Current State**: Database-backed multi-user system with authentication
**Registry Requirements**:
- Database-stored model metadata with file storage
- User-based permissions and organizational sharing
- Lab-internal model discovery and collaboration
- Integration with existing user authentication system

#### 3. Production Mode
**Current State**: Containerized deployment with full infrastructure
**Registry Requirements**:
- Cloud storage integration with metadata database
- Public community models plus private organizational models
- Advanced search and filtering capabilities
- Performance analytics and usage tracking

### Existing Infrastructure Assessment

**Authentication System** (emuses/multi_user_service/):
- Complete user management with JWT tokens
- Role-based access control (admin, user, readonly)  
- Database models for users and workspaces
- API endpoints for user management and authentication

**Database Infrastructure**:
- PostgreSQL database with Alembic migrations
- Existing tables: users, workspaces, user_workspaces
- Migration system for schema evolution
- Connection pooling and transaction management

**File Storage Capabilities**:
- Local filesystem storage for model artifacts
- Docker volume mounting for persistent data
- Preparation for cloud storage integration (S3, Azure Blob)
- File upload/download endpoint patterns in FastAPI service

## Technical Architecture Analysis

### Database Schema Requirements

**Model Registry Tables**:
```sql
CREATE TABLE model_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    owner_id UUID REFERENCES users(id),
    workspace_id UUID REFERENCES workspaces(id),
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Model storage and integrity
    model_path TEXT NOT NULL,
    manifest_hash VARCHAR(64) NOT NULL,
    model_size_bytes BIGINT,
    
    -- Metadata and search
    description TEXT,
    tags TEXT[],
    model_type VARCHAR(50), -- 'umap', 'prediction', 'full_pipeline'
    
    -- Usage tracking
    download_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    
    -- Search and discovery
    search_vector TSVECTOR,
    
    UNIQUE(name, version, workspace_id)
);

CREATE TABLE model_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID REFERENCES model_registry(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    permission VARCHAR(10) CHECK (permission IN ('read', 'write', 'admin')),
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(model_id, user_id)
);

CREATE TABLE model_downloads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
    model_id UUID REFERENCES model_registry(id),
    user_id UUID REFERENCES users(id),
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    client_info JSONB
);

-- Performance indexes
CREATE INDEX idx_model_registry_owner ON model_registry(owner_id);
CREATE INDEX idx_model_registry_workspace ON model_registry(workspace_id);
CREATE INDEX idx_model_registry_public ON model_registry(is_public) WHERE is_public = true;
CREATE INDEX idx_model_registry_search ON model_registry USING GIN(search_vector);
CREATE INDEX idx_model_registry_tags ON model_registry USING GIN(tags);
```

**Integration with Existing Tables**:
- Leverage existing `users` table for ownership and permissions
- Integrate with `workspaces` for organizational model sharing
- Extend workspace permissions to include model access rights

### File Storage Architecture

**Local Mode Storage Structure**:
```
~/.emuses/
├── models/
│   ├── model-name-v1.0.0/
│   │   ├── models/
│   │   ├── artifacts/  
│   │   ├── metadata/
│   │   └── model_manifest.json
│   └── registry.json              # Local model index
└── config/
    └── local_registry.yaml
```

**Multi-User Mode Storage**:
```
/shared/emuses/models/
├── {workspace_id}/
│   ├── {model_id}/
│   │   ├── models/
│   │   ├── artifacts/
│   │   ├── metadata/
│   │   └── model_manifest.json
│   └── temp/                      # Upload staging area
└── public/                        # Public models
```

**Production Mode Storage** (Cloud Integration):
```
Cloud Storage Bucket:
├── models/
│   ├── {organization_id}/
│   │   └── {model_id}/
│   └── public/
│       └── {model_id}/
├── indexes/                       # Search indexes
└── analytics/                     # Usage data
```

### API Endpoint Architecture

**Model Registry Endpoints**:
```python
# Model discovery and search
GET    /api/v1/models                    # List available models
GET    /api/v1/models/search             # Search models with filters
GET    /api/v1/models/{model_id}         # Get model details
GET    /api/v1/models/{model_id}/download # Download model bundle

# Model management
POST   /api/v1/models                    # Register new model
PUT    /api/v1/models/{model_id}         # Update model metadata
DELETE /api/v1/models/{model_id}         # Delete model (owner only)

# Model access and permissions
GET    /api/v1/models/{model_id}/access  # List model permissions
POST   /api/v1/models/{model_id}/access  # Grant access to user/workspace
DELETE /api/v1/models/{model_id}/access/{user_id} # Revoke access

# Usage and analytics
GET    /api/v1/models/{model_id}/stats   # Usage statistics
POST   /api/v1/models/{model_id}/inference # Run inference (from inference-pipeline)

# Administrative endpoints (admin only)
GET    /api/v1/admin/models/stats        # Global model statistics  
POST   /api/v1/admin/models/migrate      # Model migration utilities
DELETE /api/v1/admin/models/cleanup      # Cleanup orphaned models
```

## Implementation Strategy by Deployment Mode

### Local Mode Implementation

**File-Based Registry**:
```python
class LocalModelRegistry:
    def __init__(self):
        self.models_dir = Path.home() / ".emuses" / "models"
        self.registry_file = Path.home() / ".emuses" / "registry.json"
        
    def install_model(self, source_path, name=None):
        """Install model from filesystem path"""
        # Verify model manifest
        # Copy to local registry directory
        # Update registry.json index
        
    def list_models(self, filters=None):
        """List installed models with filtering"""
        # Read registry.json
        # Apply filters (name, version, tags)
        # Return model metadata list
        
    def get_model_path(self, name, version="latest"):
        """Get filesystem path for model"""
        # Resolve version (latest, specific)
        # Return absolute path to model directory
```

**CLI Commands**:
```bash
# Local model management
emuses models install /path/to/model --name custom-name
emuses models list
emuses models info model-name
emuses models remove model-name
emuses models update-index  # Rescan model directory
```

### Multi-User Mode Implementation

**Database-Backed Registry**:
```python
class DatabaseModelRegistry:
    def __init__(self, db_session, current_user):
        self.db = db_session
        self.user = current_user
        
    async def register_model(self, model_path, metadata):
        """Register model in database with permissions"""
        # Verify model manifest and integrity
        # Store model metadata in database
        # Set up default permissions
        # Move model files to shared storage
        
    async def search_models(self, query, filters=None):
        """Search models with text and filter criteria"""
        # Use PostgreSQL full-text search
        # Apply permission filtering
        # Return paginated results with relevance scoring
        
    async def get_accessible_models(self, user_id):
        """Get models accessible to user"""
        # Query public models
        # Query user's private models  
        # Query workspace-shared models
        # Combine with permissions
```

**Permission System Integration**:
```python
class ModelPermissionManager:
    def check_access(self, model_id, user_id, permission):
        """Check if user has specific permission on model"""
        # Check model ownership
        # Check explicit permissions in model_access table
        # Check workspace-level permissions
        # Check public model access
        
    def grant_access(self, model_id, user_id, permission, granted_by):
        """Grant specific permission to user"""
        # Validate granter has admin permission
        # Create model_access record
        # Log permission grant
        
    def list_model_permissions(self, model_id):
        """List all users with access to model"""
        # Query model_access table
        # Include ownership information
        # Return formatted permission list
```

### Production Mode Implementation

**Cloud Storage Integration**:
```python
class CloudModelRegistry:
    def __init__(self, storage_backend, db_session):
        self.storage = storage_backend  # S3, Azure Blob, etc.
        self.db = db_session
        self.cache = RedisCache()  # Optional caching layer
        
    async def upload_model(self, model_bundle, metadata):
        """Upload model to cloud storage with metadata"""
        # Upload model bundle to cloud storage
        # Generate signed URLs for download
        # Store metadata in database
        # Update search indexes
        
    async def download_model(self, model_id, user_id):
        """Generate secure download URL for model"""
        # Verify user permissions
        # Generate time-limited signed URL
        # Log download activity
        # Update usage statistics
```

**Advanced Search and Analytics**:
```python
class ModelSearchEngine:
    def __init__(self, db_session):
        self.db = db_session
        
    async def advanced_search(self, query, filters):
        """Advanced search with multiple criteria"""
        # Full-text search on description and tags
        # Filter by model type, version, author
        # Sort by relevance, popularity, date
        # Support faceted search results
        
    async def get_popular_models(self, timeframe="30d"):
        """Get most downloaded/used models"""
        # Query download statistics
        # Apply time filtering
        # Return ranked results
        
    async def get_model_analytics(self, model_id):
        """Get detailed analytics for model"""
        # Download statistics over time
        # User demographics (if permitted)
        # Usage patterns and trends
        # Performance metrics if available
```

## Integration with Inference Pipeline

### Model Format Compatibility

**Universal Model Format Dependency**:
- All registry operations require models with valid manifest.json
- Registry validates manifest integrity before model acceptance
- Model versioning uses manifest version information
- Search indexes include manifest metadata for discovery

**Inference Integration**:
```python
# Enhanced inference command with registry support
emuses inference --model registry:model-name --data /path/to/data

# Registry-aware model resolution
emuses inference --model workspace:lab-fmri-v2.1 --data /path/to/data

# Public model usage
emuses inference --model public:hcp-motor-task --data /path/to/data
```

### Registry-Aware CLI Commands

**Model Installation and Discovery**:
```bash
# Install from registry
emuses models install registry:model-name --local-name custom-name

# Search registry
emuses models search "fMRI motor task" --type umap --min-accuracy 0.85

# Model information with registry metadata
emuses info registry:model-name
# Output: Local model info + registry metadata + usage stats
```

## Context Files for Implementation

### Database and Authentication
```bash
# Existing multi-user infrastructure
emuses/multi_user_service/models.py          # User and workspace models
emuses/multi_user_service/database.py        # Database configuration
emuses/multi_user_service/auth.py            # Authentication system
emuses/multi_user_service/endpoints.py       # API endpoint patterns

# Migration system
emuses/multi_user_service/alembic/           # Database migrations
alembic.ini                                  # Alembic configuration
```

### Model Management Infrastructure  
```bash
# Model persistence (from inference-pipeline)
emuses/tools/model_io.py                     # Enhanced ModelIOManager
emuses/pipelines/inference_stage.py          # Inference capabilities

# API service framework
emuses/foundation_fastapi_service/app.py     # FastAPI application
emuses/foundation_fastapi_service/models.py  # Pydantic models
```

### CLI and Configuration
```bash
# CLI framework
emuses/cli/main.py                           # Command registration
emuses/cli/commands.py                       # Command implementations

# Configuration management
emuses/multi_user_service/deployment_config.py # Deployment modes
```

## Success Metrics

### Technical Performance
- **Model Discovery**: Search response time <200ms for 10,000+ models
- **Installation Speed**: Model installation <2 minutes for 100MB models
- **Scalability**: Support 1000+ concurrent users in production mode
- **Storage Efficiency**: Deduplication for identical model versions

### User Experience  
- **Ease of Discovery**: Users find relevant models in <30 seconds
- **Installation Success**: 95%+ successful model installations
- **Permission Clarity**: Clear understanding of access rights
- **Error Recovery**: Helpful error messages with resolution guidance

### Security and Compliance
- **Access Control**: 100% enforcement of permission boundaries
- **Data Isolation**: Zero cross-user data leakage
- **Audit Trail**: Complete logging of all model access and modifications
- **Vulnerability Management**: Regular security scanning of model uploads

This context provides the foundation for implementing a scalable, secure model registry that supports EMUSES' transition from single-user tool to collaborative platform while maintaining scientific rigor and reproducibility standards.