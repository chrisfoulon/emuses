# EMUSES Model Registry Developer Integration Guide

## Overview

This guide provides comprehensive information for developers integrating with the EMUSES Model Registry system. It covers architecture patterns, API integration, custom registry implementations, and contribution guidelines.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start Integration](#quick-start-integration)
- [Registry Interface](#registry-interface)
- [Factory Pattern Usage](#factory-pattern-usage)
- [Custom Registry Implementation](#custom-registry-implementation)
- [Database Integration](#database-integration)
- [API Integration](#api-integration)
- [Testing Patterns](#testing-patterns)
- [Error Handling](#error-handling)
- [Performance Considerations](#performance-considerations)
- [Contribution Guidelines](#contribution-guidelines)

## Architecture Overview

### Registry Hierarchy

The EMUSES Model Registry follows a layered architecture:

```
┌─────────────────────────────┐
│     CLI Commands            │  ← User Interface Layer
├─────────────────────────────┤
│   ModelRegistryFactory      │  ← Factory Pattern Layer
├─────────────────────────────┤
│    BaseModelRegistry        │  ← Abstract Interface Layer
├─────────────────────────────┤
│ Local │ Database │ Cloud    │  ← Implementation Layer
├─────────────────────────────┤
│ Storage │ DB │ Cloud APIs   │  ← Backend Layer
└─────────────────────────────┘
```

### Core Components

1. **BaseModelRegistry**: Abstract interface defining standard operations
2. **ModelRegistryFactory**: Factory for creating appropriate registry instances
3. **LocalModelRegistry**: File-based implementation for single users
4. **DatabaseModelRegistry**: Database-backed implementation for teams
5. **CloudModelRegistry**: Cloud-integrated implementation for production

### Design Principles

- **Unified Interface**: Same methods work across all deployment modes
- **Automatic Mode Detection**: Factory selects appropriate implementation
- **Graceful Fallback**: Falls back to local mode when advanced modes unavailable
- **Flexible Parameters**: Methods support both simple and advanced use cases

## Quick Start Integration

### Basic Integration

```python
from emuses.tools.model_registry_factory import ModelRegistryFactory

# Create registry (auto-detects deployment mode)
factory = ModelRegistryFactory()
registry = factory.create_registry()

# Basic operations work across all modes
models = registry.list_models()
print(f"Found {len(models)} models")

# Install a model
result = registry.install_model(
    model_path="/path/to/model.zip",
    model_name="my-model",
    version="1.0.0",
    description="My ML model"
)
print(f"Installed: {result['model_id']}")
```

### Integration with Existing Applications

```python
from emuses.tools.model_registry_factory import ModelRegistryFactory
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ModelManager:
    """Example integration class for managing models in your application."""
    
    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize model manager with registry.
        
        Parameters
        ----------
        registry_path : Path, optional
            Custom registry path (local mode only)
        """
        self.factory = ModelRegistryFactory()
        self.registry = self.factory.create_registry(
            registry_path=registry_path,
            fallback=True  # Always fallback to ensure functionality
        )
        
    def get_model_for_task(self, task_type: str) -> Optional[Path]:
        """Get the best model for a specific task.
        
        Parameters
        ----------
        task_type : str
            Type of task (e.g., "classification", "umap")
            
        Returns
        -------
        Optional[Path]
            Path to model files if found
        """
        try:
            # Search for models of the right type
            models = self.registry.search_models(task_type)
            if not models:
                logger.warning(f"No models found for task type: {task_type}")
                return None
                
            # Get the most recent model
            latest_model = max(models, key=lambda x: x.get('created_at', ''))
            
            # Get model file path
            model_path = self.registry.get_model_file_path(
                latest_model['name'], 
                latest_model.get('version')
            )
            
            if model_path and Path(model_path).exists():
                return Path(model_path)
            else:
                logger.error(f"Model files not accessible: {latest_model['name']}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting model for task {task_type}: {e}")
            return None
    
    def register_trained_model(self, model_path: Path, metadata: Dict[str, Any]) -> bool:
        """Register a newly trained model.
        
        Parameters
        ----------
        model_path : Path
            Path to trained model directory or file
        metadata : Dict[str, Any]
            Model metadata including name, version, description
            
        Returns
        -------
        bool
            True if registration successful
        """
        try:
            result = self.registry.install_model(
                model_path=model_path,
                model_name=metadata['name'],
                version=metadata['version'],
                description=metadata.get('description', ''),
                tags=metadata.get('tags', [])
            )
            
            logger.info(f"Registered model: {result['model_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register model {metadata['name']}: {e}")
            return False

# Usage in your application
model_manager = ModelManager()

# Get a model for classification
classifier_path = model_manager.get_model_for_task("classification")
if classifier_path:
    # Use the model
    run_classification(classifier_path, input_data)

# Register a new model after training
model_manager.register_trained_model(
    Path("/path/to/trained/model"),
    {
        "name": "brain-classifier-v2",
        "version": "2.0.0",
        "description": "Improved brain classification model",
        "tags": ["brain", "fMRI", "classification"]
    }
)
```

## Registry Interface

### BaseModelRegistry Methods

All registry implementations follow this interface:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from uuid import UUID

class BaseModelRegistry(ABC):
    """Standard interface for all registry implementations."""
    
    @abstractmethod
    def list_models(self, user_id: Optional[Union[UUID, str]] = None,
                   workspace_id: Optional[Union[UUID, str]] = None,
                   include_public: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """List available models."""
        pass
    
    @abstractmethod 
    def install_model(self, model_path: Path, model_name: str, version: str,
                     description: str = "", tags: Optional[List[str]] = None,
                     user_id: Optional[Union[UUID, str]] = None,
                     workspace_id: Optional[Union[UUID, str]] = None,
                     **kwargs) -> Dict[str, Any]:
        """Install model into registry."""
        pass
    
    @abstractmethod
    def get_model_info(self, model_name: str, version: Optional[str] = None,
                      user_id: Optional[Union[UUID, str]] = None,
                      workspace_id: Optional[Union[UUID, str]] = None,
                      **kwargs) -> Optional[Dict[str, Any]]:
        """Get model information."""
        pass
    
    @abstractmethod
    def search_models(self, query: str,
                     user_id: Optional[Union[UUID, str]] = None,
                     workspace_id: Optional[Union[UUID, str]] = None,
                     include_public: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """Search models by query."""
        pass
    
    @abstractmethod
    def remove_model(self, model_name: str, version: Optional[str] = None,
                    user_id: Optional[Union[UUID, str]] = None,
                    **kwargs) -> bool:
        """Remove model from registry."""
        pass
    
    @abstractmethod
    def get_model_file_path(self, model_name: str, version: Optional[str] = None,
                           user_id: Optional[Union[UUID, str]] = None,
                           **kwargs) -> Optional[Path]:
        """Get filesystem path to model files."""
        pass
```

### Method Parameters

**Common Parameters:**
- `user_id`: User identifier for permission checking (database/cloud modes)
- `workspace_id`: Workspace identifier for filtering (database/cloud modes) 
- `include_public`: Include public models in results
- `**kwargs`: Mode-specific parameters

**Local Mode:** Only uses `model_path`, `model_name`, `version` parameters
**Database Mode:** Uses all parameters for permission management
**Cloud Mode:** Uses all parameters plus cloud-specific options

## Factory Pattern Usage

### Basic Factory Usage

```python
from emuses.tools.model_registry_factory import ModelRegistryFactory, RegistryMode

factory = ModelRegistryFactory()

# Automatic mode detection
registry = factory.create_registry()

# Explicit mode specification
registry = factory.create_registry(mode=RegistryMode.LOCAL)

# With fallback (recommended for applications)
registry = factory.create_registry(fallback=True)
```

### Advanced Factory Configuration

```python
from emuses.tools.model_registry_factory import ModelRegistryFactory
from pathlib import Path

factory = ModelRegistryFactory()

# Local mode with custom path
registry = factory.create_registry(
    mode=RegistryMode.LOCAL,
    registry_path=Path("/shared/models")
)

# Database mode with user context
registry = factory.create_registry(
    mode=RegistryMode.DATABASE,
    user_id="user-123",
    workspace_id="workspace-456"
)

# Cloud mode with configuration
registry = factory.create_registry(
    mode=RegistryMode.CLOUD,
    user_id="user-123",
    cloud_config={
        "storage_backend": "s3",
        "bucket": "my-models"
    }
)
```

### Mode Detection Logic

The factory detects deployment mode using this hierarchy:

1. **Explicit mode parameter** (if provided)
2. **Environment variables**:
   - `EMUSES_DEPLOYMENT_MODE`: "local", "multi-user", "production"
   - `DATABASE_URL`: Presence indicates database capability
3. **Service availability**: Multi-user service running
4. **Fallback**: Local mode (always available)

## Custom Registry Implementation

### Creating a Custom Registry

```python
from emuses.tools.base_model_registry import BaseModelRegistry
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

class CustomModelRegistry(BaseModelRegistry):
    """Example custom registry implementation."""
    
    def __init__(self, custom_config: Dict[str, Any]):
        """Initialize custom registry.
        
        Parameters
        ----------
        custom_config : Dict[str, Any]
            Custom configuration parameters
        """
        self.config = custom_config
        self.logger = logging.getLogger(__name__)
        
    def list_models(self, user_id: Optional[Union[UUID, str]] = None,
                   workspace_id: Optional[Union[UUID, str]] = None,
                   include_public: bool = True, **kwargs) -> List[Dict[str, Any]]:
        """List models using custom logic."""
        # Implement your custom model listing logic
        models = []
        
        # Example: Read from custom storage
        try:
            # Your custom implementation here
            models = self._fetch_models_from_custom_backend(
                user_id=user_id,
                workspace_id=workspace_id,
                include_public=include_public
            )
        except Exception as e:
            self.logger.error(f"Failed to list models: {e}")
            
        return models
    
    def install_model(self, model_path: Path, model_name: str, version: str,
                     description: str = "", tags: Optional[List[str]] = None,
                     user_id: Optional[Union[UUID, str]] = None,
                     workspace_id: Optional[Union[UUID, str]] = None,
                     **kwargs) -> Dict[str, Any]:
        """Install model using custom logic."""
        try:
            # Validate model
            if not model_path.exists():
                raise ValueError(f"Model path does not exist: {model_path}")
            
            # Your custom installation logic
            model_id = self._install_to_custom_backend(
                model_path=model_path,
                model_name=model_name,
                version=version,
                description=description,
                tags=tags or [],
                user_id=user_id,
                workspace_id=workspace_id
            )
            
            return {
                "model_id": model_id,
                "name": model_name,
                "version": version,
                "status": "installed"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to install model {model_name}: {e}")
            raise
    
    def _fetch_models_from_custom_backend(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetch models from your custom backend."""
        # Implement your custom model fetching logic
        # Return list of model dictionaries
        pass
    
    def _install_to_custom_backend(self, **kwargs) -> str:
        """Install model to your custom backend."""
        # Implement your custom model installation logic
        # Return model ID
        pass
    
    # Implement other required abstract methods...
```

### Registering Custom Registry with Factory

```python
from emuses.tools.model_registry_factory import ModelRegistryFactory, RegistryMode

# Extend the factory to support your custom registry
class ExtendedModelRegistryFactory(ModelRegistryFactory):
    """Factory with custom registry support."""
    
    def create_custom_registry(self, custom_config: Dict[str, Any]) -> BaseModelRegistry:
        """Create custom registry instance.
        
        Parameters
        ----------
        custom_config : Dict[str, Any]
            Configuration for custom registry
            
        Returns
        -------
        BaseModelRegistry
            Custom registry instance
        """
        registry = CustomModelRegistry(custom_config)
        
        # Validate interface
        if not self.validate_interface(registry):
            raise RegistryValidationError("Custom registry interface validation failed")
            
        return registry

# Usage
factory = ExtendedModelRegistryFactory()
custom_registry = factory.create_custom_registry({
    "backend_url": "https://my-model-service.com",
    "api_key": "my-api-key"
})
```

## Database Integration

### Database Registry Usage

```python
from emuses.tools.database_model_registry import DatabaseModelRegistry
from emuses.multi_user_service.database import get_db
from sqlalchemy.orm import Session

# Async usage (recommended)
async def use_database_registry():
    """Example async database registry usage."""
    # Get database session
    db: Session = next(get_db())
    
    try:
        # Initialize registry with user context
        registry = DatabaseModelRegistry(
            db_session=db, 
            user_id="user-123"
        )
        
        # Register model with workspace association
        result = await registry.register_model(
            model_path=Path("/path/to/model.zip"),
            metadata={
                "name": "team-classifier",
                "workspace_id": "workspace-456",
                "is_public": False,
                "tags": ["classification", "team"],
                "description": "Team collaboration model"
            }
        )
        
        # Search with permission filtering
        models = await registry.search_models(
            query="classification",
            filters={
                "workspace_id": "workspace-456",
                "include_public": True
            }
        )
        
        print(f"Found {len(models)} models")
        return models
        
    finally:
        db.close()

# Sync usage (if needed)
def sync_database_registry():
    """Example sync database registry usage."""
    db: Session = next(get_db())
    
    try:
        registry = DatabaseModelRegistry(db_session=db, user_id="user-123")
        
        # Most operations have both sync and async versions
        models = registry.list_models_sync(
            user_id="user-123",
            workspace_id="workspace-456"
        )
        
        return models
        
    finally:
        db.close()
```

### Database Schema Integration

When working with the database registry, you can extend the schema:

```python
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from emuses.multi_user_service.models import Base

class CustomModelMetadata(Base):
    """Extended model metadata table."""
    
    __tablename__ = "custom_model_metadata"
    
    id = Column(String, ForeignKey("model_registry.id"), primary_key=True)
    custom_field = Column(String(255))
    additional_info = Column(Text)
    
    # Relationship to main model record
    model = relationship("ModelRegistry", back_populates="custom_metadata")

# Add to model registry model
# (This would be done in the main model definition)
# ModelRegistry.custom_metadata = relationship("CustomModelMetadata", back_populates="model")
```

## API Integration

### REST API Client

```python
import httpx
from typing import Dict, List, Optional
import asyncio

class ModelRegistryAPIClient:
    """Client for EMUSES Model Registry REST API."""
    
    def __init__(self, base_url: str, auth_token: str):
        """Initialize API client.
        
        Parameters
        ----------
        base_url : str
            Base URL of EMUSES API service
        auth_token : str
            Bearer token for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
        
    async def list_models(self, workspace_id: Optional[str] = None,
                         include_public: bool = True) -> List[Dict]:
        """List models via API."""
        params = {"include_public": include_public}
        if workspace_id:
            params["workspace_id"] = workspace_id
            
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/models",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def register_model(self, model_data: Dict) -> Dict:
        """Register model via API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/models/register",
                headers=self.headers,
                json=model_data
            )
            response.raise_for_status()
            return response.json()
    
    async def search_models(self, query: str, **filters) -> Dict:
        """Search models via API."""
        params = {"q": query, **filters}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/models/search",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()

# Usage
async def main():
    client = ModelRegistryAPIClient(
        base_url="https://emuses-api.example.com",
        auth_token="your-auth-token"
    )
    
    # List models
    models = await client.list_models(workspace_id="workspace-123")
    print(f"Found {len(models)} models")
    
    # Search models
    results = await client.search_models("brain classification")
    print(f"Search found {results['total_results']} results")

# Run async
asyncio.run(main())
```

### FastAPI Integration

```python
from fastapi import FastAPI, Depends, HTTPException
from emuses.tools.model_registry_factory import ModelRegistryFactory
from emuses.multi_user_service.auth import get_current_user
from typing import List, Dict, Any

app = FastAPI(title="My Application with Model Registry")

# Global factory instance
registry_factory = ModelRegistryFactory()

def get_registry(current_user=Depends(get_current_user)):
    """Dependency to get registry for current user."""
    return registry_factory.create_registry(
        user_id=current_user.id,
        fallback=True
    )

@app.get("/my-app/models", response_model=List[Dict[str, Any]])
async def list_available_models(registry=Depends(get_registry)):
    """List models available to current user."""
    try:
        models = registry.list_models()
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {e}")

@app.post("/my-app/models/use/{model_name}")
async def use_model_for_task(
    model_name: str,
    task_data: Dict[str, Any],
    registry=Depends(get_registry)
):
    """Use a registry model for a task."""
    try:
        # Get model path
        model_path = registry.get_model_file_path(model_name)
        if not model_path:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Use model for task (your application logic)
        result = await run_model_task(model_path, task_data)
        
        return {"status": "success", "result": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task failed: {e}")

async def run_model_task(model_path: Path, task_data: Dict[str, Any]):
    """Your application-specific model usage logic."""
    # Implement your model usage logic here
    pass
```

## Testing Patterns

### Unit Testing Registry Implementations

```python
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
from emuses.tools.local_model_registry import LocalModelRegistry

class TestModelRegistry(unittest.TestCase):
    """Test cases for model registry implementations."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry_path = Path(self.temp_dir) / "test_registry"
        self.registry = LocalModelRegistry(registry_path=self.registry_path)
        
    def tearDown(self):
        """Clean up test environment."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_install_model_success(self):
        """Test successful model installation."""
        # Create mock model file
        model_path = Path(self.temp_dir) / "test_model.zip"
        model_path.write_text("mock model data")
        
        # Mock model manifest validation
        with patch.object(self.registry, '_validate_model_manifest', return_value=True), \
             patch.object(self.registry, '_extract_model_manifest') as mock_extract:
            
            mock_extract.return_value = {
                "name": "test-model",
                "version": "1.0.0",
                "type": "classification"
            }
            
            result = self.registry.install_model(
                model_path=model_path,
                model_name="test-model",
                version="1.0.0"
            )
            
            self.assertEqual(result["name"], "test-model")
            self.assertEqual(result["version"], "1.0.0")
    
    def test_list_models_empty(self):
        """Test listing models in empty registry."""
        models = self.registry.list_models()
        self.assertEqual(len(models), 0)
    
    def test_search_models(self):
        """Test model search functionality."""
        # Mock registry with test data
        with patch.object(self.registry, 'list_models') as mock_list:
            mock_list.return_value = [
                {
                    "name": "brain-classifier",
                    "version": "1.0.0",
                    "description": "Brain classification model",
                    "tags": ["brain", "classification"]
                },
                {
                    "name": "umap-model", 
                    "version": "2.0.0",
                    "description": "UMAP dimensionality reduction",
                    "tags": ["umap", "dim-reduction"]
                }
            ]
            
            # Test search
            results = self.registry.search_models("brain")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["name"], "brain-classifier")
            
            results = self.registry.search_models("model")
            self.assertEqual(len(results), 2)  # Should find both

class TestModelRegistryFactory(unittest.TestCase):
    """Test cases for model registry factory."""
    
    def test_factory_creates_local_registry(self):
        """Test factory creates local registry."""
        from emuses.tools.model_registry_factory import ModelRegistryFactory, RegistryMode
        from emuses.tools.local_model_registry import LocalModelRegistry
        
        factory = ModelRegistryFactory()
        
        with patch.object(factory, '_detect_deployment_mode', return_value=RegistryMode.LOCAL):
            registry = factory.create_registry()
            self.assertIsInstance(registry, LocalModelRegistry)
    
    def test_factory_fallback_behavior(self):
        """Test factory fallback to local mode."""
        from emuses.tools.model_registry_factory import ModelRegistryFactory, RegistryMode
        
        factory = ModelRegistryFactory()
        
        # Mock database mode detection but make validation fail
        with patch.object(factory, '_detect_deployment_mode', return_value=RegistryMode.DATABASE), \
             patch.object(factory, '_validate_mode_requirements', return_value=False):
            
            registry = factory.create_registry(fallback=True)
            # Should fall back to LocalModelRegistry
            self.assertIsInstance(registry, LocalModelRegistry)

# Integration tests
class TestRegistryIntegration(unittest.TestCase):
    """Integration tests for registry functionality."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up integration test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_end_to_end_model_workflow(self):
        """Test complete model workflow."""
        from emuses.tools.model_registry_factory import ModelRegistryFactory
        
        # Create test model
        model_dir = Path(self.temp_dir) / "test_model"
        model_dir.mkdir()
        (model_dir / "model_manifest.json").write_text('''{
            "name": "test-model",
            "version": "1.0.0",
            "type": "classification",
            "description": "Test model"
        }''')
        
        # Create registry
        factory = ModelRegistryFactory()
        registry = factory.create_registry(
            registry_path=Path(self.temp_dir) / "registry"
        )
        
        # Install model
        result = registry.install_model(
            model_path=model_dir,
            model_name="test-model",
            version="1.0.0"
        )
        
        # Verify installation
        self.assertIn("model_id", result)
        
        # List models
        models = registry.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["name"], "test-model")
        
        # Search models
        search_results = registry.search_models("test")
        self.assertEqual(len(search_results), 1)
        
        # Get model info
        model_info = registry.get_model_info("test-model")
        self.assertIsNotNone(model_info)
        self.assertEqual(model_info["name"], "test-model")

if __name__ == "__main__":
    unittest.main()
```

### Testing with pytest

```python
import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from emuses.tools.model_registry_factory import ModelRegistryFactory

@pytest.fixture
def temp_registry_dir():
    """Fixture for temporary registry directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_model_file(temp_registry_dir):
    """Fixture for mock model file."""
    model_file = temp_registry_dir / "test_model.zip"
    model_file.write_text("mock model data")
    return model_file

@pytest.fixture
def registry_factory():
    """Fixture for registry factory."""
    return ModelRegistryFactory()

def test_registry_creation(registry_factory, temp_registry_dir):
    """Test registry creation with custom path."""
    registry = registry_factory.create_registry(
        registry_path=temp_registry_dir / "registry"
    )
    
    assert registry is not None
    models = registry.list_models()
    assert isinstance(models, list)

def test_model_installation(registry_factory, temp_registry_dir, mock_model_file):
    """Test model installation workflow."""
    registry = registry_factory.create_registry(
        registry_path=temp_registry_dir / "registry"
    )
    
    with patch.object(registry, '_validate_model_manifest', return_value=True), \
         patch.object(registry, '_extract_model_manifest') as mock_extract:
        
        mock_extract.return_value = {
            "name": "test-model",
            "version": "1.0.0",
            "type": "test"
        }
        
        result = registry.install_model(
            model_path=mock_model_file,
            model_name="test-model",
            version="1.0.0"
        )
        
        assert "model_id" in result
        assert result["name"] == "test-model"

@pytest.mark.asyncio
async def test_database_registry_async():
    """Test database registry async operations."""
    from emuses.tools.database_model_registry import DatabaseModelRegistry
    
    # Mock database session
    mock_db = MagicMock()
    
    registry = DatabaseModelRegistry(
        db_session=mock_db,
        user_id="test-user"
    )
    
    # Test async operations
    with patch.object(registry, '_execute_query') as mock_query:
        mock_query.return_value = []
        
        models = await registry.search_models("test query")
        assert isinstance(models, list)

def test_factory_mode_detection(registry_factory):
    """Test factory mode detection logic."""
    with patch('emuses.multi_user_service.deployment_config.detect_deployment_mode') as mock_detect:
        mock_detect.return_value = "local"
        
        registry = registry_factory.create_registry()
        assert registry is not None

# Performance tests
@pytest.mark.performance
def test_large_registry_performance(registry_factory, temp_registry_dir):
    """Test performance with large number of models."""
    registry = registry_factory.create_registry(
        registry_path=temp_registry_dir / "registry"
    )
    
    # Mock large number of models
    with patch.object(registry, 'list_models') as mock_list:
        mock_list.return_value = [
            {"name": f"model-{i}", "version": "1.0.0"}
            for i in range(1000)
        ]
        
        import time
        start_time = time.time()
        models = registry.list_models()
        end_time = time.time()
        
        assert len(models) == 1000
        assert (end_time - start_time) < 1.0  # Should complete in under 1 second
```

## Error Handling

### Registry-Specific Exceptions

```python
from emuses.tools.model_registry_factory import (
    ModelRegistryError,
    RegistryCreationError,
    RegistryValidationError,
    RegistryModeError
)
from emuses.tools.base_model_registry import BaseModelRegistry

class RobustModelManager:
    """Example of robust error handling with registry."""
    
    def __init__(self):
        self.factory = ModelRegistryFactory()
        self.registry = None
        self.logger = logging.getLogger(__name__)
        
    def initialize_registry(self, **kwargs) -> bool:
        """Initialize registry with error handling.
        
        Returns
        -------
        bool
            True if registry initialized successfully
        """
        try:
            self.registry = self.factory.create_registry(
                fallback=True,  # Always enable fallback
                **kwargs
            )
            
            # Validate registry works
            self.registry.list_models()
            return True
            
        except RegistryCreationError as e:
            self.logger.error(f"Failed to create registry: {e}")
            return False
            
        except RegistryValidationError as e:
            self.logger.error(f"Registry validation failed: {e}")
            return False
            
        except Exception as e:
            self.logger.error(f"Unexpected registry error: {e}")
            return False
    
    def safe_model_operation(self, operation_func, *args, **kwargs):
        """Execute model operation with error handling.
        
        Parameters
        ----------
        operation_func : callable
            Registry operation function to execute
        *args, **kwargs
            Arguments for the operation
            
        Returns
        -------
        tuple
            (success: bool, result: Any, error: str)
        """
        if not self.registry:
            return False, None, "Registry not initialized"
            
        try:
            result = operation_func(*args, **kwargs)
            return True, result, None
            
        except FileNotFoundError as e:
            error_msg = f"Model file not found: {e}"
            self.logger.error(error_msg)
            return False, None, error_msg
            
        except PermissionError as e:
            error_msg = f"Permission denied: {e}"
            self.logger.error(error_msg)
            return False, None, error_msg
            
        except ValueError as e:
            error_msg = f"Invalid parameter: {e}"
            self.logger.error(error_msg)
            return False, None, error_msg
            
        except Exception as e:
            error_msg = f"Operation failed: {e}"
            self.logger.error(error_msg)
            return False, None, error_msg
    
    def install_model_safely(self, model_path: Path, **metadata) -> tuple:
        """Install model with comprehensive error handling."""
        return self.safe_model_operation(
            self.registry.install_model,
            model_path=model_path,
            **metadata
        )
    
    def get_model_safely(self, model_name: str, version: str = None) -> tuple:
        """Get model with error handling."""
        return self.safe_model_operation(
            self.registry.get_model_info,
            model_name=model_name,
            version=version
        )

# Usage
manager = RobustModelManager()

if manager.initialize_registry():
    success, result, error = manager.install_model_safely(
        model_path=Path("/path/to/model.zip"),
        model_name="my-model",
        version="1.0.0"
    )
    
    if success:
        print(f"Model installed: {result['model_id']}")
    else:
        print(f"Installation failed: {error}")
else:
    print("Failed to initialize registry")
```

## Performance Considerations

### Caching and Optimization

```python
from functools import lru_cache, wraps
import time
from typing import Dict, List, Any

class OptimizedRegistryWrapper:
    """Wrapper adding performance optimizations to registry."""
    
    def __init__(self, registry: BaseModelRegistry, cache_ttl: int = 300):
        """Initialize optimized wrapper.
        
        Parameters
        ----------
        registry : BaseModelRegistry
            Underlying registry instance
        cache_ttl : int, default=300
            Cache time-to-live in seconds
        """
        self.registry = registry
        self.cache_ttl = cache_ttl
        self._cache_timestamps = {}
        
    def _cache_key(self, method_name: str, *args, **kwargs) -> str:
        """Generate cache key for method call."""
        # Simple cache key generation
        key_parts = [method_name] + [str(arg) for arg in args]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        return "|".join(key_parts)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self._cache_timestamps:
            return False
            
        age = time.time() - self._cache_timestamps[cache_key]
        return age < self.cache_ttl
    
    @lru_cache(maxsize=128)
    def _cached_list_models(self, cache_key: str, **kwargs) -> List[Dict[str, Any]]:
        """Cached version of list_models."""
        self._cache_timestamps[cache_key] = time.time()
        return self.registry.list_models(**kwargs)
    
    def list_models(self, **kwargs) -> List[Dict[str, Any]]:
        """List models with caching."""
        cache_key = self._cache_key("list_models", **kwargs)
        
        if self._is_cache_valid(cache_key):
            return self._cached_list_models(cache_key, **kwargs)
        else:
            # Clear invalid cache entry
            self._cached_list_models.cache_clear()
            return self._cached_list_models(cache_key, **kwargs)
    
    def __getattr__(self, name):
        """Delegate other methods to underlying registry."""
        return getattr(self.registry, name)

# Usage
factory = ModelRegistryFactory()
base_registry = factory.create_registry()
optimized_registry = OptimizedRegistryWrapper(base_registry, cache_ttl=600)

# First call - hits registry
models = optimized_registry.list_models()

# Second call within TTL - uses cache
models = optimized_registry.list_models()  # Faster
```

### Batch Operations

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import asyncio

class BatchModelOperations:
    """Utility class for batch model operations."""
    
    def __init__(self, registry: BaseModelRegistry, max_workers: int = 4):
        """Initialize batch operations handler.
        
        Parameters
        ----------
        registry : BaseModelRegistry
            Registry instance for operations
        max_workers : int, default=4
            Maximum number of concurrent workers
        """
        self.registry = registry
        self.max_workers = max_workers
        
    def install_models_batch(self, model_specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Install multiple models concurrently.
        
        Parameters
        ----------
        model_specs : List[Dict[str, Any]]
            List of model specifications for installation
            
        Returns
        -------
        List[Dict[str, Any]]
            Results of installations
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all installation tasks
            future_to_spec = {
                executor.submit(
                    self._install_single_model, spec
                ): spec for spec in model_specs
            }
            
            # Collect results
            for future in as_completed(future_to_spec):
                spec = future_to_spec[future]
                try:
                    result = future.result()
                    results.append({
                        "spec": spec,
                        "status": "success",
                        "result": result
                    })
                except Exception as e:
                    results.append({
                        "spec": spec,
                        "status": "error",
                        "error": str(e)
                    })
                    
        return results
    
    def _install_single_model(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Install single model from specification."""
        return self.registry.install_model(**spec)
    
    async def install_models_batch_async(self, model_specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Install multiple models asynchronously."""
        tasks = []
        
        for spec in model_specs:
            task = asyncio.create_task(
                self._install_single_model_async(spec)
            )
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Format results
        formatted_results = []
        for spec, result in zip(model_specs, results):
            if isinstance(result, Exception):
                formatted_results.append({
                    "spec": spec,
                    "status": "error", 
                    "error": str(result)
                })
            else:
                formatted_results.append({
                    "spec": spec,
                    "status": "success",
                    "result": result
                })
                
        return formatted_results
    
    async def _install_single_model_async(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Install single model asynchronously."""
        # For registries that support async operations
        if hasattr(self.registry, 'install_model_async'):
            return await self.registry.install_model_async(**spec)
        else:
            # Run sync operation in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._install_single_model, spec
            )

# Usage
batch_ops = BatchModelOperations(registry)

model_specs = [
    {
        "model_path": Path("/models/model1.zip"),
        "model_name": "model-1",
        "version": "1.0.0"
    },
    {
        "model_path": Path("/models/model2.zip"),
        "model_name": "model-2", 
        "version": "1.0.0"
    }
]

# Sync batch installation
results = batch_ops.install_models_batch(model_specs)

# Async batch installation
# results = await batch_ops.install_models_batch_async(model_specs)
```

## Contribution Guidelines

### Development Setup

```bash
# Clone repository
git clone https://github.com/your-org/emuses.git
cd emuses

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/model_registry/
```

### Code Style

**Follow these conventions:**
- **Docstrings**: NumPy-style docstrings for all functions and classes
- **Type hints**: Use type hints for all function parameters and return values
- **Linting**: Code must pass flake8 with max-complexity 10
- **Formatting**: Use consistent formatting (consider using black)

**Example function:**
```python
from typing import Dict, List, Optional, Any
from pathlib import Path

def example_registry_function(
    model_path: Path,
    model_name: str,
    tags: Optional[List[str]] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """Example function following code style guidelines.
    
    Parameters
    ----------
    model_path : Path
        Path to model file or directory
    model_name : str
        Name of the model
    tags : List[str], optional
        Optional tags for model categorization
    **kwargs : Any
        Additional keyword arguments
        
    Returns
    -------
    Dict[str, Any]
        Operation result with status and metadata
        
    Raises
    ------
    ValueError
        If model_path does not exist
    RegistryError
        If model registration fails
    """
    if not model_path.exists():
        raise ValueError(f"Model path does not exist: {model_path}")
        
    # Implementation here
    return {"status": "success", "model_name": model_name}
```

### Testing Requirements

**Test categories:**
- **Unit tests**: Test individual functions/classes in isolation
- **Integration tests**: Test component interactions
- **Performance tests**: Test scalability and response times
- **Security tests**: Test permission boundaries and input validation

**Test structure:**
```python
import pytest
from unittest.mock import Mock, patch
from emuses.tools.your_module import YourClass

class TestYourClass:
    """Test suite for YourClass."""
    
    @pytest.fixture
    def mock_instance(self):
        """Fixture for mock instance."""
        return YourClass(test_config)
    
    def test_success_case(self, mock_instance):
        """Test successful operation."""
        result = mock_instance.method("valid_input")
        assert result["status"] == "success"
    
    def test_error_case(self, mock_instance):
        """Test error handling."""
        with pytest.raises(ValueError):
            mock_instance.method("invalid_input")
    
    @patch('emuses.tools.your_module.external_dependency')
    def test_with_mocks(self, mock_external, mock_instance):
        """Test with external dependencies mocked."""
        mock_external.return_value = "mocked_result"
        result = mock_instance.method_using_external()
        assert "mocked_result" in result
```

### Pull Request Process

1. **Create Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Implement Changes**:
   - Follow code style guidelines
   - Add comprehensive tests
   - Update documentation

3. **Test Changes**:
   ```bash
   # Run full test suite
   pytest
   
   # Run specific tests
   pytest tests/model_registry/
   
   # Check coverage
   pytest --cov=emuses --cov-report=html
   
   # Lint code
   flake8 emuses/
   ```

4. **Commit Changes**:
   ```bash
   git add .
   git commit -m "feat: add new registry feature
   
   - Implement CustomModelRegistry class
   - Add comprehensive tests
   - Update documentation"
   ```

5. **Push and Create PR**:
   ```bash
   git push origin feature/your-feature-name
   # Create pull request via GitHub
   ```

### Documentation Standards

**Include documentation for:**
- All public functions and classes (NumPy-style docstrings)
- Integration examples for new features
- API changes and migration guides
- Performance implications of changes

**Documentation example:**
```python
class NewRegistryFeature:
    """New registry feature for advanced model management.
    
    This feature provides advanced capabilities for model organization
    and discovery in large-scale deployments.
    
    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary for feature initialization
    enable_advanced : bool, default=True
        Whether to enable advanced features
        
    Examples
    --------
    Basic usage:
    
    >>> feature = NewRegistryFeature({"setting": "value"})
    >>> result = feature.advanced_operation()
    >>> print(result["status"])
    'success'
    
    Advanced usage with custom configuration:
    
    >>> config = {
    ...     "advanced_setting": True,
    ...     "cache_size": 1000
    ... }
    >>> feature = NewRegistryFeature(config, enable_advanced=True)
    >>> models = feature.discover_models(complex_query)
    """
```

### Security Considerations

**When contributing registry features:**
- **Input Validation**: Validate all user inputs, especially file paths
- **Permission Checks**: Ensure proper access control in multi-user modes
- **SQL Injection**: Use parameterized queries for database operations
- **Path Traversal**: Validate file paths to prevent directory traversal
- **Resource Limits**: Implement appropriate resource limits and timeouts

**Security checklist:**
```python
def secure_model_operation(self, user_input: str, user_id: str) -> Any:
    """Example of secure implementation patterns."""
    
    # 1. Input validation
    if not isinstance(user_input, str) or len(user_input.strip()) == 0:
        raise ValueError("Invalid input parameter")
    
    # 2. Sanitize input
    sanitized_input = self._sanitize_input(user_input)
    
    # 3. Check permissions
    if not self._check_user_permission(user_id, "model_operation"):
        raise PermissionError("User not authorized for this operation")
    
    # 4. Use parameterized queries
    result = self.db.execute(
        "SELECT * FROM models WHERE name = %s AND owner_id = %s",
        (sanitized_input, user_id)
    )
    
    return result
```

This developer guide provides comprehensive information for integrating with and extending the EMUSES Model Registry system. Follow these patterns and guidelines to build robust, secure, and performant applications.