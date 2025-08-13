# EMUSES Model Registry API Reference

## Overview

The EMUSES Model Registry provides both command-line interface (CLI) and RESTful API access to model management functionality. This reference covers all available interfaces across the three deployment modes: Local, Database, and Cloud.

## CLI API Reference

### Core Commands

All CLI commands follow the pattern: `python -m emuses.cli models COMMAND [OPTIONS] [ARGS]`

#### `status` - Registry Status

Show registry status and statistics.

```bash
python -m emuses.cli models status [OPTIONS]
```

**Options:**
- `--registry, -r PATH`: Custom registry path

**Output:**
- Registry location and path
- Model count
- Registry version and status
- Creation and update timestamps

**Example:**
```bash
$ python -m emuses.cli models status
Model Registry Status
Location: Default Location
Path: /home/user/.emuses/model_registry
💡 Hidden directory - access with file manager or terminal

Version: 1.0.0
Model Count: 0
Created: 2025-08-07T12:15:36.609649
Last Updated: 2025-08-07T12:15:36.609655
✅ Registry index is valid
```

#### `list` - List Models

List all models in the registry.

```bash
python -m emuses.cli models list [OPTIONS]
```

**Options:**
- `--registry, -r PATH`: Custom registry path

**Output:**
- Table of models with ID, name, version, and type
- Empty registry message if no models found

**Example:**
```bash
$ python -m emuses.cli models list
┌─────────────┬──────────┬──────────────────┬──────────────────┐
│ Model ID    │ Name     │ Version          │ Type             │
├─────────────┼──────────┼──────────────────┼──────────────────┤
│ brain_001   │ Brain-v1 │ 1.0.0           │ classification   │
│ umap_002    │ UMAP-v2  │ 2.1.0           │ umap            │
└─────────────┴──────────┴──────────────────┴──────────────────┘
```

#### `search` - Search Models

Search for models by query string.

```bash
python -m emuses.cli models search QUERY [OPTIONS]
```

**Arguments:**
- `QUERY`: Search query string (required)

**Options:**
- `--registry, -r PATH`: Custom registry path

**Output:**
- Search results in table format
- No results message if query doesn't match any models

**Example:**
```bash
$ python -m emuses.cli models search "brain"
Search Results for: brain
┌─────────────┬──────────────┬─────────┬──────────────────┐
│ Model ID    │ Name         │ Version │ Type             │
├─────────────┼──────────────┼─────────┼──────────────────┤
│ brain_001   │ Brain-v1     │ 1.0.0   │ classification   │
└─────────────┴──────────────┴─────────┴──────────────────┘
```

#### `info` - Model Information

Get detailed information about a specific model.

```bash
python -m emuses.cli models info MODEL_NAME [OPTIONS]
```

**Arguments:**
- `MODEL_NAME`: Model name or ID (required)

**Options:**
- `--registry, -r PATH`: Custom registry path

**Output:**
- Detailed model information including metadata, paths, and statistics

**Example:**
```bash
$ python -m emuses.cli models info brain_001
Model Information: brain_001
Name: Brain-v1
Version: 1.0.0
Type: classification
Description: Brain classification model
Tags: ["brain", "fMRI", "classification"]
Path: /home/user/.emuses/model_registry/brain_001
Size: 125.3 MB
Created: 2025-08-07T10:30:45
Status: Available
```

#### `install` - Install Model

Install a model into the registry.

```bash
python -m emuses.cli models install MODEL_PATH [OPTIONS]
```

**Arguments:**
- `MODEL_PATH`: Path to model file or directory (required)

**Options:**
- `--registry, -r PATH`: Custom registry path

**Output:**
- Installation progress and status
- Model ID and location after successful installation

**Example:**
```bash
$ python -m emuses.cli models install ~/models/brain-classifier.zip
Installing model from: /home/user/models/brain-classifier.zip
Validating model manifest...
✅ Model manifest is valid
Extracting model files...
✅ Model installed successfully

Model ID: brain_classifier_20250807
Name: brain-classifier
Version: 1.0.0
Registry Path: /home/user/.emuses/model_registry/brain_classifier_20250807
```

#### `remove` - Remove Model

Remove a model from the registry.

```bash
python -m emuses.cli models remove MODEL_NAME [OPTIONS]
```

**Arguments:**
- `MODEL_NAME`: Model name or ID to remove (required)

**Options:**
- `--registry, -r PATH`: Custom registry path

**Output:**
- Confirmation of model removal

**Example:**
```bash
$ python -m emuses.cli models remove brain_001
Removing model: brain_001
✅ Model 'brain_001' removed successfully
```

#### `storage` - Storage Information

Show storage usage and threshold information.

```bash
python -m emuses.cli models storage [OPTIONS]
```

**Options:**
- `--registry, -r PATH`: Custom registry path

**Output:**
- Registry location and storage usage
- Storage threshold warnings if applicable
- Tips for managing hidden directories

**Example:**
```bash
$ python -m emuses.cli models storage
Registry Location: Default Location
Path: /home/user/.emuses/model_registry
💡 Hidden directory - access with file manager or terminal

Storage Usage: 256.8 MB / 10.0 GB (2.6%)
Models: 3
Free Space: 9.7 GB

Storage Breakdown by Model:
• brain_classifier_001: 125.3 MB (48.8%)
• umap_model_002: 89.2 MB (34.7%)
• test_model_003: 42.3 MB (16.5%)

✅ Storage usage is healthy
```

#### `cleanup` - Clean Up Registry

Clean up orphaned model directories and temporary files.

```bash
python -m emuses.cli models cleanup [OPTIONS]
```

**Options:**
- `--registry, -r PATH`: Custom registry path
- `--dry-run`: Show what would be removed without actually removing

**Output:**
- List of items to be cleaned up
- Confirmation of cleanup operations

**Example:**
```bash
$ python -m emuses.cli models cleanup --dry-run
Cleanup Preview (Dry Run)
Registry: /home/user/.emuses/model_registry

Items to be cleaned:
• Orphaned directory: incomplete_model_20250806/
• Temporary file: temp_upload_xyz123.zip
• Broken symlink: old_model_link

Total space to free: 45.2 MB

Run without --dry-run to perform cleanup.
```

#### `stats` - Registry Statistics

Show detailed registry statistics.

```bash
python -m emuses.cli models stats [OPTIONS]
```

**Options:**
- `--registry, -r PATH`: Custom registry path

**Output:**
- Comprehensive statistics about registry contents

**Example:**
```bash
$ python -m emuses.cli models stats
Detailed Registry Statistics
Registry Path: /home/user/.emuses/model_registry
Total Models: 3
Storage Usage: 256.8 MB

Model Types:
• classification: 2 models (66.7%)
• umap: 1 model (33.3%)

Size Distribution:
• < 50 MB: 1 model
• 50-100 MB: 1 model  
• > 100 MB: 1 model

Recent Activity:
• Last installed: 2 hours ago
• Last accessed: 30 minutes ago
```

#### `mode-info` - Deployment Mode Information

Show model registry mode configuration and status.

```bash
python -m emuses.cli models mode-info [OPTIONS]
```

**Output:**
- Current deployment mode and configuration
- Registry capabilities and requirements
- Available CLI parameters for current mode

**Example:**
```bash
$ python -m emuses.cli models mode-info
Model Registry Mode Configuration
Current Mode: LOCAL
Registry Type: LocalModelRegistry

Mode Configuration:
  Requires Authentication: False
  Requires Database: False
  Multi-User Support: False
  Cloud Storage Support: False

Registry Capabilities:
  list_models: ✓
  install_model: ✓
  get_model_info: ✓
  search_models: ✓
  remove_model: ✓
  get_model_file_path: ✓

Interface Validation: Valid
Mode Compatibility: Compatible

Available CLI Parameters:
  --registry, -r    Custom registry path (local mode)
  --workspace, -w   Workspace ID (database/cloud modes)
  --user, -u        User ID (database/cloud modes)
  --public/--no-public Include public models

Local Mode Usage:
  • Models stored in local filesystem
  • Use --registry to specify custom path
  • No authentication required
```

#### `api-info` - API Information

Show information about database mode and API usage.

```bash
python -m emuses.cli models api-info [OPTIONS]
```

**Output:**
- API endpoint information for database/cloud modes
- Authentication requirements
- Service status

**Example:**
```bash
$ python -m emuses.cli models api-info
ℹ️ Multi-user service is disabled. Using local registry mode.
✅ All CLI commands are available for local operations.

# In database/cloud mode:
# API Endpoints Available:
# • GET /api/v1/models - List models
# • POST /api/v1/models/register - Register model
# • GET /api/v1/models/{id} - Get model info
# • DELETE /api/v1/models/{id} - Remove model
# • GET /api/v1/models/search - Search models
# 
# Authentication: Bearer token required
# Service Status: Available
```

## REST API Reference (Database/Cloud Modes)

### Authentication

All API endpoints require authentication in Database and Cloud modes:

```bash
# Get authentication token (implementation depends on deployment)
curl -X POST "/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'

# Use token in subsequent requests
curl -H "Authorization: Bearer YOUR_TOKEN" "/api/v1/models"
```

### Model Registry Endpoints

#### List Models

**Endpoint:** `GET /api/v1/models`

**Query Parameters:**
- `workspace_id` (optional): Filter by workspace
- `user_id` (optional): Filter by user
- `include_public` (optional): Include public models
- `limit` (optional): Number of results
- `offset` (optional): Pagination offset

**Response:**
```json
[
  {
    "model_id": "uuid-string",
    "name": "model-name",
    "version": "1.0.0",
    "type": "classification",
    "description": "Model description",
    "tags": ["tag1", "tag2"],
    "is_public": false,
    "owner_id": "owner-uuid",
    "workspace_id": "workspace-uuid",
    "created_at": "2025-08-07T12:00:00Z",
    "updated_at": "2025-08-07T12:00:00Z",
    "download_count": 42,
    "size_mb": 125.3
  }
]
```

#### Register Model

**Endpoint:** `POST /api/v1/models/register`

**Request Body:**
```json
{
  "name": "custom-model-name",
  "workspace_id": "workspace-uuid",
  "is_public": false,
  "tags": ["brain", "fMRI"],
  "description": "Model description"
}
```

**Response:**
```json
{
  "status": "success",
  "model_id": "new-model-uuid",
  "message": "Model registered successfully"
}
```

#### Get Model Information

**Endpoint:** `GET /api/v1/models/{model_id}`

**Response:**
```json
{
  "model_id": "uuid-string",
  "name": "model-name",
  "version": "1.0.0",
  "type": "classification",
  "description": "Detailed model description",
  "tags": ["tag1", "tag2"],
  "is_public": false,
  "owner_id": "owner-uuid",
  "workspace_id": "workspace-uuid",
  "created_at": "2025-08-07T12:00:00Z",
  "updated_at": "2025-08-07T12:00:00Z",
  "download_count": 42,
  "size_mb": 125.3,
  "manifest": {
    "model_type": "classification",
    "version": "1.0.0",
    "requirements": ["scikit-learn>=1.0"],
    "performance": {
      "accuracy": 0.95
    }
  }
}
```

#### Search Models

**Endpoint:** `GET /api/v1/models/search`

**Query Parameters:**
- `q` (required): Search query
- `workspace_id` (optional): Filter by workspace
- `model_type` (optional): Filter by model type
- `limit` (optional): Number of results
- `offset` (optional): Pagination offset

**Response:**
```json
{
  "query": "brain classification",
  "total_results": 15,
  "models": [
    {
      "model_id": "uuid-string",
      "name": "brain-classifier",
      "version": "2.1.0",
      "type": "classification",
      "description": "Advanced brain classification model",
      "tags": ["brain", "fMRI", "classification"],
      "relevance_score": 0.95,
      "download_count": 156
    }
  ]
}
```

#### Download Model

**Endpoint:** `POST /api/v1/models/{model_id}/download`

**Response:**
```json
{
  "download_url": "https://storage.example.com/models/signed-url",
  "expires_at": "2025-08-07T13:00:00Z",
  "size_bytes": 131457280
}
```

#### Remove Model

**Endpoint:** `DELETE /api/v1/models/{model_id}`

**Response:**
```json
{
  "status": "success",
  "message": "Model removed successfully",
  "model_id": "uuid-string"
}
```

### Permission Management Endpoints

#### Get Model Permissions

**Endpoint:** `GET /api/v1/models/{model_id}/permissions`

**Response:**
```json
{
  "model_id": "uuid-string",
  "owner_id": "owner-uuid",
  "permissions": [
    {
      "user_id": "user-uuid",
      "permission": "read",
      "granted_by": "owner-uuid",
      "granted_at": "2025-08-07T12:00:00Z"
    }
  ],
  "is_public": false
}
```

#### Grant Model Permission

**Endpoint:** `POST /api/v1/models/{model_id}/permissions`

**Request Body:**
```json
{
  "user_id": "user-uuid",
  "permission": "read"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Permission granted successfully"
}
```

#### Revoke Model Permission

**Endpoint:** `DELETE /api/v1/models/{model_id}/permissions/{user_id}`

**Response:**
```json
{
  "status": "success", 
  "message": "Permission revoked successfully"
}
```

### Production Mode Endpoints (Cloud)

#### Get Popular Models

**Endpoint:** `GET /api/v1/models/popular`

**Query Parameters:**
- `timeframe` (optional): "7d", "30d", "90d"
- `limit` (optional): Number of results

**Response:**
```json
{
  "timeframe": "30d",
  "models": [
    {
      "model_id": "uuid-string",
      "name": "hcp-motor-baseline",
      "download_count": 1250,
      "unique_users": 89,
      "avg_rating": 4.8
    }
  ]
}
```

#### Get Model Analytics

**Endpoint:** `GET /api/v1/models/{model_id}/analytics`

**Response:**
```json
{
  "model_id": "uuid-string",
  "total_downloads": 1250,
  "unique_users": 89,
  "downloads_by_day": [
    {"date": "2025-08-01", "count": 45},
    {"date": "2025-08-02", "count": 52}
  ],
  "geographic_distribution": [
    {"country": "US", "count": 450},
    {"country": "UK", "count": 280}
  ]
}
```

## Python API Examples

### Using LocalModelRegistry

```python
from emuses.tools.local_model_registry import LocalModelRegistry
from pathlib import Path

# Initialize registry
registry = LocalModelRegistry()

# Install a model
result = registry.install_model("/path/to/model.zip")
print(f"Installed model: {result['model_id']}")

# List models
models = registry.list_models()
for model in models:
    print(f"Model: {model['name']} v{model['version']}")

# Search models
results = registry.search_models("brain classification")
print(f"Found {len(results)} models")

# Get model information
model_info = registry.get_model_info("model-name")
if model_info:
    print(f"Model path: {model_info['path']}")
    print(f"Model type: {model_info['type']}")

# Get model file path for inference
model_path = registry.get_model_file_path("model-name")
if model_path:
    print(f"Model files at: {model_path}")
```

### Using ModelRegistryFactory

```python
from emuses.tools.model_registry_factory import ModelRegistryFactory
from pathlib import Path

# Create appropriate registry for current deployment mode
factory = ModelRegistryFactory()

try:
    # Auto-detect mode and create registry
    registry = factory.create_registry(
        registry_path=Path("~/my-models"),  # For local mode
        user_id="user-123",                # For database/cloud modes
        fallback=True                      # Fall back to local if needed
    )
    
    # Use registry (same interface regardless of mode)
    models = registry.list_models()
    print(f"Found {len(models)} models in registry")
    
except Exception as e:
    print(f"Registry creation failed: {e}")
```

### Using DatabaseModelRegistry

```python
from emuses.tools.database_model_registry import DatabaseModelRegistry
from emuses.multi_user_service.database import get_db

# Database mode requires database session and user context
async def use_database_registry():
    # Get database session
    db = next(get_db())
    
    # Initialize registry with user context
    registry = DatabaseModelRegistry(db_session=db, user_id="user-123")
    
    # Register a model
    result = await registry.register_model(
        model_path="/path/to/model.zip",
        metadata={
            "name": "my-brain-model",
            "workspace_id": "workspace-123", 
            "is_public": False,
            "tags": ["brain", "fMRI"],
            "description": "Brain classification model"
        }
    )
    
    # Search with permissions
    models = await registry.search_models(
        query="brain classification",
        filters={"workspace_id": "workspace-123"}
    )
    
    # Get accessible models
    accessible = await registry.get_accessible_models("user-123")
    
    return models
```

### Integration with Inference Pipeline

```python
from emuses.tools.model_registry_factory import ModelRegistryFactory
from emuses.pipelines.inference_stage import InferenceStage
from pathlib import Path

# Get model from registry
factory = ModelRegistryFactory()
registry = factory.create_registry()

# Find model
models = registry.search_models("my-inference-model")
if models:
    model_info = models[0]
    model_path = registry.get_model_file_path(model_info['name'])
    
    # Use with inference pipeline
    if model_path and Path(model_path).exists():
        inference_stage = InferenceStage()
        
        # Run inference using registry model
        results = inference_stage.run(
            model_path=model_path,
            data_path="/path/to/input/data",
            output_path="/path/to/output"
        )
        
        print(f"Inference completed: {results}")
    else:
        print("Model files not accessible")
else:
    print("Model not found in registry")
```

## Error Handling

### Common Error Responses

**Model Not Found (404):**
```json
{
  "detail": "Model not found: model-name",
  "error_code": "MODEL_NOT_FOUND"
}
```

**Permission Denied (403):**
```json
{
  "detail": "Access denied for operation: download",
  "error_code": "PERMISSION_DENIED"
}
```

**Invalid Model (400):**
```json
{
  "detail": "Invalid model manifest: missing version",
  "error_code": "INVALID_MODEL_MANIFEST"
}
```

**Authentication Required (401):**
```json
{
  "detail": "Authentication required for database mode",
  "error_code": "AUTH_REQUIRED"
}
```

### Python Exception Handling

```python
from emuses.tools.model_registry_factory import (
    ModelRegistryFactory, 
    RegistryCreationError, 
    RegistryValidationError
)

factory = ModelRegistryFactory()

try:
    registry = factory.create_registry()
    models = registry.list_models()
    
except RegistryCreationError as e:
    print(f"Failed to create registry: {e}")
    # Handle registry creation failure
    
except RegistryValidationError as e:
    print(f"Registry validation failed: {e}")
    # Handle validation errors
    
except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle other errors
```

This API reference provides comprehensive documentation for all available interfaces in the EMUSES Model Registry system, covering CLI commands, REST APIs, and Python programming interfaces across all deployment modes.