"""Tests for model registry FastAPI endpoints.

This module tests the REST API endpoints for model registry operations
including authentication, parameter validation, and response formats.
"""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emuses.multi_user_service.models import Base, ModelRegistry, User, Workspace
from emuses.multi_user_service.model_registry_endpoints import setup_model_registry_endpoints


@pytest.fixture
def test_db():
    """Create test database with tables configured for FastAPI TestClient threading."""
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def test_user(test_db):
    """Create test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed_password",
        organization="Test Org",
        role="researcher",
        storage_quota_gb=10.0,
        compute_quota_hours=100.0,
        is_active=True,
        is_superuser=False,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def test_workspace(test_db, test_user):
    """Create test workspace."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace",
        description="Test workspace for API testing",
        owner_id=test_user.id,
        storage_path="/tmp/test_workspace",
        is_active=True
    )
    test_db.add(workspace)
    test_db.commit()
    return workspace


@pytest.fixture
def test_model(test_db, test_user):
    """Create test model."""
    model = ModelRegistry(
        id=uuid.uuid4(),
        name="test_model",
        version="1.0.0",
        owner_id=test_user.id,
        model_path="/fake/path",
        manifest_hash="test_hash",
        model_type="classification",
        description="Test model for API testing",
        tags=["test", "api"],
        download_count=5,
        model_size_bytes=1024*1024  # 1MB
    )
    test_db.add(model)
    test_db.commit()
    return model


@pytest.fixture
def test_app():
    """Create test FastAPI app with model registry endpoints."""
    app = FastAPI(title="Test EMUSES API")
    setup_model_registry_endpoints(app)
    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def authenticated_client(test_user, test_db):
    """Create authenticated test client using dependency override."""
    from emuses.multi_user_service.auth import get_current_active_user
    from emuses.multi_user_service.database import get_db
    from emuses.multi_user_service.model_registry_endpoints import setup_model_registry_endpoints
    from fastapi import FastAPI
    
    # Create fresh app
    app = FastAPI(title="Test EMUSES API")
    
    # Override dependencies with our test values
    def override_get_current_active_user():
        return test_user
    
    def override_get_db():
        return test_db
    
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    app.dependency_overrides[get_db] = override_get_db
    
    # Set up endpoints with overridden dependencies
    setup_model_registry_endpoints(app)
    
    client = TestClient(app)
    yield client
    
    # Clean up
    app.dependency_overrides.clear()


class TestModelRegistryEndpointsAuthentication:
    """Test authentication requirements for endpoints."""
    
    def test_list_models_requires_authentication(self, client):
        """Test that listing models requires authentication."""
        response = client.get("/api/v1/models/")
        # Should return 422 or 401 depending on auth setup
        assert response.status_code in [401, 422]
    
    def test_search_models_requires_authentication(self, client):
        """Test that searching models requires authentication."""
        response = client.get("/api/v1/models/search?query=test")
        assert response.status_code in [401, 422]
    
    def test_get_model_info_requires_authentication(self, client):
        """Test that getting model info requires authentication."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/models/{fake_id}")
        assert response.status_code in [401, 422]


class TestModelListingEndpoints:
    """Test model listing and discovery endpoints."""
    
    def test_list_models_empty(self, authenticated_client, test_db, test_user):
        """Test listing models from empty registry."""
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.list_models.return_value = []
            
            response = authenticated_client.get("/api/v1/models/")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_list_models_with_data(self, authenticated_client, test_db, test_user, test_model):
        """Test listing models with data."""
        
        # Mock response data
        mock_model_data = {
            "model_id": str(test_model.id),
            "name": test_model.name,
            "version": test_model.version,
            "type": test_model.model_type,
            "description": test_model.description,
            "tags": test_model.tags or [],
            "is_public": test_model.is_public,
            "owner_id": str(test_model.owner_id),
            "workspace_id": None,
            "created_at": test_model.created_at.isoformat(),
            "updated_at": test_model.updated_at.isoformat(),
            "download_count": test_model.download_count,
            "size_mb": 1.0
        }
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.list_models.return_value = [mock_model_data]
            
            response = authenticated_client.get("/api/v1/models/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["model_id"] == str(test_model.id)
        assert data[0]["name"] == test_model.name
    
    def test_list_models_with_filters(self, authenticated_client, test_db, test_user):
        """Test listing models with query parameters."""
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.list_models.return_value = []
            
            response = authenticated_client.get("/api/v1/models/?model_type=classification&include_public=false&limit=10")
        
        assert response.status_code == 200
        
        # Verify registry was called with correct parameters
        call_args = mock_instance.list_models.call_args
        assert call_args[1]["include_public"] == False
        assert call_args[1]["filters"]["type"] == "classification"
    
    def test_search_models(self, authenticated_client, test_db, test_user):
        """Test searching models."""
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.search_models.return_value = []
            
            response = authenticated_client.get("/api/v1/models/search?query=classification&include_public=true&limit=25")
        
        assert response.status_code == 200
        
        # Verify search was called with correct parameters
        call_args = mock_instance.search_models.call_args
        assert call_args[1]["query"] == "classification"
        assert call_args[1]["include_public"] == True


class TestModelInfoEndpoints:
    """Test individual model information endpoints."""
    
    def test_get_model_info_success(self, authenticated_client, test_db, test_user, test_model):
        """Test getting model info successfully."""
        mock_model_info = {
            "model_id": str(test_model.id),
            "name": test_model.name,
            "version": test_model.version,
            "type": test_model.model_type,
            "description": test_model.description,
            "tags": test_model.tags or [],
            "manifest": {"test": "data"}
        }
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.get_model_info.return_value = mock_model_info
            
            response = authenticated_client.get(f"/api/v1/models/{test_model.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == str(test_model.id)
        assert data["name"] == test_model.name
        assert "manifest" in data
    
    def test_get_model_info_not_found(self, authenticated_client, test_db, test_user):
        """Test getting info for non-existent model."""
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.get_model_info.return_value = None
            
            fake_id = str(uuid.uuid4())
            response = authenticated_client.get(f"/api/v1/models/{fake_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestModelManagementEndpoints:
    """Test model management endpoints."""
    
    def test_remove_model_success(self, authenticated_client, test_db, test_user, test_model):
        """Test successful model removal."""
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.remove_model.return_value = {
                "status": "success",
                "message": "Model removed successfully"
            }
            
            response = authenticated_client.delete(f"/api/v1/models/{test_model.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_remove_model_not_found(self, authenticated_client, test_db, test_user):
        """Test removing non-existent model."""
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.remove_model.return_value = {
                "status": "error",
                "message": "Model not found"
            }
            
            fake_id = str(uuid.uuid4())
            response = authenticated_client.delete(f"/api/v1/models/{fake_id}")
        
        assert response.status_code == 404
    
    def test_track_download_success(self, authenticated_client, test_db, test_user, test_model):
        """Test successful download tracking."""
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.track_download.return_value = {
                "status": "success",
                "download_id": str(uuid.uuid4())
            }
            
            response = authenticated_client.post(f"/api/v1/models/{test_model.id}/download?download_method=api")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "download_id" in data


class TestPermissionEndpoints:
    """Test permission management endpoints."""
    
    def test_list_permissions_success(self, authenticated_client, test_db, test_user, test_model):
        """Test listing model permissions."""
        with patch('emuses.multi_user_service.model_registry_endpoints.ModelPermissionManager') as mock_manager:
            mock_instance = Mock()
            mock_manager.return_value = mock_instance
            mock_instance.list_permissions.return_value = {
                "status": "success",
                "model_id": str(test_model.id),
                "permissions": [{
                    "user_email": "test@example.com",
                    "access_level": "owner",
                    "is_owner": True
                }]
            }
            
            response = authenticated_client.get(f"/api/v1/models/{test_model.id}/permissions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["permissions"]) == 1
    
    def test_grant_permission_success(self, authenticated_client, test_db, test_user, test_model):
        """Test granting model permission."""
        with patch('emuses.multi_user_service.model_registry_endpoints.ModelPermissionManager') as mock_manager:
            mock_instance = Mock()
            mock_manager.return_value = mock_instance
            mock_instance.grant_access.return_value = {
                "status": "success",
                "message": "Write access granted to other@example.com",
                "action": "granted"
            }
            
            request_data = {
                "user_id": str(uuid.uuid4()),
                "access_level": "write"
            }
            
            response = authenticated_client.post(f"/api/v1/models/{test_model.id}/permissions", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_grant_permission_invalid_level(self, authenticated_client, test_db, test_user, test_model):
        """Test granting invalid permission level."""
        request_data = {
            "user_id": str(uuid.uuid4()),
            "access_level": "invalid_level"
        }
        
        response = authenticated_client.post(f"/api/v1/models/{test_model.id}/permissions", json=request_data)
        
        # Should fail validation due to regex constraint
        assert response.status_code == 422
    
    def test_revoke_permission_success(self, authenticated_client, test_db, test_user, test_model):
        """Test revoking model permission."""
        with patch('emuses.multi_user_service.model_registry_endpoints.ModelPermissionManager') as mock_manager:
            mock_instance = Mock()
            mock_manager.return_value = mock_instance
            mock_instance.revoke_access.return_value = {
                "status": "success",
                "message": "Access revoked from other@example.com"
            }
            
            other_user_id = str(uuid.uuid4())
            response = authenticated_client.delete(f"/api/v1/models/{test_model.id}/permissions/{other_user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_set_public_status_success(self, authenticated_client, test_db, test_user, test_model):
        """Test setting model public status."""
        with patch('emuses.multi_user_service.model_registry_endpoints.ModelPermissionManager') as mock_manager:
            mock_instance = Mock()
            mock_manager.return_value = mock_instance
            mock_instance.make_public.return_value = {
                "status": "success",
                "message": "Model made public",
                "is_public": True
            }
            
            response = authenticated_client.put(f"/api/v1/models/{test_model.id}/public?is_public=true")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["is_public"] == True


class TestModelRegistrationEndpoint:
    """Test model registration endpoint."""
    
    def test_register_model_success(self, authenticated_client, test_db, test_user):
        """Test successful model registration."""
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.register_model.return_value = {
                "status": "success",
                "model_id": str(uuid.uuid4()),
                "name": "test_model",
                "version": "1.0.0"
            }
            
            # Create test file
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
                tmp_file.write(b"fake model data")
                tmp_file.flush()
                
                files = {"model_file": ("test_model.zip", open(tmp_file.name, "rb"), "application/zip")}
                data = {
                    "name": "custom_model",
                    "description": "Test model upload",
                    "tags": "test,api",
                    "is_public": "false"
                }
                
                response = authenticated_client.post("/api/v1/models/register", files=files, data=data)
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert "model_id" in response_data
    
    def test_register_model_missing_file(self, authenticated_client):
        """Test model registration without file."""
        data = {"name": "test_model"}
        response = authenticated_client.post("/api/v1/models/register", data=data)
        
        # Should fail due to missing required file
        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling in endpoints."""
    
    def test_database_error_handling(self, authenticated_client, test_db, test_user):
        """Test handling of database errors."""
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_registry.side_effect = Exception("Database connection failed")
            
            response = authenticated_client.get("/api/v1/models/")
        
        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()
    
    def test_invalid_uuid_handling(self, authenticated_client):
        """Test that invalid UUID format in model_id parameter is handled gracefully.
        
        This test validates that the system properly handles malformed UUID inputs
        and returns appropriate error responses instead of crashing.
        """
        # Test with clearly invalid UUID format
        response = authenticated_client.get("/api/v1/models/not-a-uuid-at-all")
        
        # Should return 500 (internal server error) because UUID() conversion fails
        # This validates that the error handling in the endpoint catches the ValueError
        assert response.status_code == 500
        
        # Validate that error message indicates the failure was in model info retrieval
        response_data = response.json()
        assert "Failed to get model info" in response_data["detail"]
        
        # Test with partial UUID format (common user error)
        response2 = authenticated_client.get("/api/v1/models/123e4567")
        assert response2.status_code == 500
        assert "Failed to get model info" in response2.json()["detail"]