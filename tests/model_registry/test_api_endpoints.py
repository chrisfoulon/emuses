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
    """Create test database with tables."""
    engine = create_engine("sqlite:///:memory:")
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
def authenticated_client(client, test_user):
    """Create authenticated test client."""
    # Mock authentication
    with patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users') as mock_users:
        mock_users.current_user.return_value = test_user
        yield client


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
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_list_models_empty(self, mock_users, mock_get_db, client, test_db, test_user):
        """Test listing models from empty registry."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.list_models.return_value = []
            
            response = client.get("/api/v1/models/")
        
        assert response.status_code == 200
        assert response.json() == []
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_list_models_with_data(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test listing models with data."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
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
            
            response = client.get("/api/v1/models/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["model_id"] == str(test_model.id)
        assert data[0]["name"] == test_model.name
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_list_models_with_filters(self, mock_users, mock_get_db, client, test_db, test_user):
        """Test listing models with query parameters."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.list_models.return_value = []
            
            response = client.get("/api/v1/models/?model_type=classification&include_public=false&limit=10")
        
        assert response.status_code == 200
        
        # Verify registry was called with correct parameters
        call_args = mock_instance.list_models.call_args
        assert call_args[1]["include_public"] == False
        assert call_args[1]["filters"]["type"] == "classification"
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_search_models(self, mock_users, mock_get_db, client, test_db, test_user):
        """Test searching models."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.search_models.return_value = []
            
            response = client.get("/api/v1/models/search?query=classification&include_public=true&limit=25")
        
        assert response.status_code == 200
        
        # Verify search was called with correct parameters
        call_args = mock_instance.search_models.call_args
        assert call_args[1]["query"] == "classification"
        assert call_args[1]["include_public"] == True


class TestModelInfoEndpoints:
    """Test individual model information endpoints."""
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_get_model_info_success(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test getting model info successfully."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
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
            
            response = client.get(f"/api/v1/models/{test_model.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == str(test_model.id)
        assert data["name"] == test_model.name
        assert "manifest" in data
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_get_model_info_not_found(self, mock_users, mock_get_db, client, test_db, test_user):
        """Test getting info for non-existent model."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.get_model_info.return_value = None
            
            fake_id = str(uuid.uuid4())
            response = client.get(f"/api/v1/models/{fake_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestModelManagementEndpoints:
    """Test model management endpoints."""
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_remove_model_success(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test successful model removal."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.remove_model.return_value = {
                "status": "success",
                "message": "Model removed successfully"
            }
            
            response = client.delete(f"/api/v1/models/{test_model.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_remove_model_not_found(self, mock_users, mock_get_db, client, test_db, test_user):
        """Test removing non-existent model."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.remove_model.return_value = {
                "status": "error",
                "message": "Model not found"
            }
            
            fake_id = str(uuid.uuid4())
            response = client.delete(f"/api/v1/models/{fake_id}")
        
        assert response.status_code == 404
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_track_download_success(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test successful download tracking."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_instance = Mock()
            mock_registry.return_value = mock_instance
            mock_instance.track_download.return_value = {
                "status": "success",
                "download_id": str(uuid.uuid4())
            }
            
            response = client.post(f"/api/v1/models/{test_model.id}/download?download_method=api")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "download_id" in data


class TestPermissionEndpoints:
    """Test permission management endpoints."""
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_list_permissions_success(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test listing model permissions."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
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
            
            response = client.get(f"/api/v1/models/{test_model.id}/permissions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["permissions"]) == 1
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_grant_permission_success(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test granting model permission."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
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
            
            response = client.post(f"/api/v1/models/{test_model.id}/permissions", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_grant_permission_invalid_level(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test granting invalid permission level."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        request_data = {
            "user_id": str(uuid.uuid4()),
            "access_level": "invalid_level"
        }
        
        response = client.post(f"/api/v1/models/{test_model.id}/permissions", json=request_data)
        
        # Should fail validation due to regex constraint
        assert response.status_code == 422
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_revoke_permission_success(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test revoking model permission."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.ModelPermissionManager') as mock_manager:
            mock_instance = Mock()
            mock_manager.return_value = mock_instance
            mock_instance.revoke_access.return_value = {
                "status": "success",
                "message": "Access revoked from other@example.com"
            }
            
            other_user_id = str(uuid.uuid4())
            response = client.delete(f"/api/v1/models/{test_model.id}/permissions/{other_user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_set_public_status_success(self, mock_users, mock_get_db, client, test_db, test_user, test_model):
        """Test setting model public status."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.ModelPermissionManager') as mock_manager:
            mock_instance = Mock()
            mock_manager.return_value = mock_instance
            mock_instance.make_public.return_value = {
                "status": "success",
                "message": "Model made public",
                "is_public": True
            }
            
            response = client.put(f"/api/v1/models/{test_model.id}/public?is_public=true")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["is_public"] == True


class TestModelRegistrationEndpoint:
    """Test model registration endpoint."""
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_register_model_success(self, mock_users, mock_get_db, client, test_db, test_user):
        """Test successful model registration."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
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
                
                response = client.post("/api/v1/models/register", files=files, data=data)
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "success"
        assert "model_id" in response_data
    
    def test_register_model_missing_file(self, client):
        """Test model registration without file."""
        data = {"name": "test_model"}
        response = client.post("/api/v1/models/register", data=data)
        
        # Should fail due to missing required file
        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling in endpoints."""
    
    @patch('emuses.multi_user_service.model_registry_endpoints.get_db')
    @patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users')
    def test_database_error_handling(self, mock_users, mock_get_db, client, test_db, test_user):
        """Test handling of database errors."""
        mock_get_db.return_value = test_db
        mock_users.current_user.return_value = test_user
        
        with patch('emuses.multi_user_service.model_registry_endpoints.DatabaseModelRegistry') as mock_registry:
            mock_registry.side_effect = Exception("Database connection failed")
            
            response = client.get("/api/v1/models/")
        
        assert response.status_code == 500
        assert "error" in response.json()["detail"].lower()
    
    def test_invalid_uuid_handling(self, client):
        """Test handling of invalid UUID parameters."""
        with patch('emuses.multi_user_service.model_registry_endpoints.get_db'):
            with patch('emuses.multi_user_service.model_registry_endpoints.fastapi_users'):
                response = client.get("/api/v1/models/invalid-uuid-format")
        
        # Should handle invalid UUID gracefully
        assert response.status_code in [400, 422, 500]