"""Test suite for multi-user service authentication endpoints.

This module tests the authentication endpoints including registration,
login, logout, and token management using FastAPI-Users routers.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os


class TestAuthenticationEndpoints:
    """Test suite for authentication endpoints."""

    def test_auth_router_creation(self):
        """Test that authentication routers can be created."""
        from emuses.multi_user_service.endpoints import (
            get_auth_router,
            get_register_router,
            get_users_router
        )
        
        with patch.dict(os.environ, {
            'EMUSES_JWT_SECRET': 'test-secret-key'
        }):
            auth_router = get_auth_router()
            register_router = get_register_router()
            users_router = get_users_router()
            
            assert auth_router is not None
            assert register_router is not None
            assert users_router is not None

    def test_auth_endpoints_registration(self):
        """Test that authentication endpoints can be registered with FastAPI app."""
        from emuses.multi_user_service.endpoints import setup_auth_endpoints
        
        app = FastAPI()
        
        with patch.dict(os.environ, {
            'EMUSES_JWT_SECRET': 'test-secret-key'
        }):
            setup_auth_endpoints(app)
            
            # Check that routes were added
            route_paths = [route.path for route in app.routes]
            
            # Should include auth endpoints
            auth_paths = [path for path in route_paths if path.startswith('/auth')]
            assert len(auth_paths) > 0

    def test_token_validation_endpoint(self):
        """Test token validation endpoint."""
        from emuses.multi_user_service.endpoints import setup_auth_endpoints
        
        app = FastAPI()
        
        with patch.dict(os.environ, {
            'EMUSES_JWT_SECRET': 'test-secret-key'
        }):
            setup_auth_endpoints(app)
            
            client = TestClient(app)
            
            # Test token validation endpoint exists (logout is typically POST)
            # This would normally require a valid token, but we're just testing the endpoint exists
            response = client.post("/auth/jwt/logout")
            # Expect 401 Unauthorized without token, not 404 Not Found
            assert response.status_code in [401, 422]  # 422 for missing token

    def test_user_profile_endpoints(self):
        """Test user profile management endpoints."""
        from emuses.multi_user_service.endpoints import setup_auth_endpoints
        
        app = FastAPI()
        
        with patch.dict(os.environ, {
            'EMUSES_JWT_SECRET': 'test-secret-key'
        }):
            setup_auth_endpoints(app)
            
            client = TestClient(app)
            
            # Test that user profile endpoints exist
            response = client.get("/users/me")
            # Expect 401 Unauthorized without token, not 404 Not Found
            assert response.status_code in [401, 422]  # 422 for missing token

    def test_registration_endpoint(self):
        """Test user registration endpoint exists."""
        from emuses.multi_user_service.endpoints import setup_auth_endpoints
        
        app = FastAPI()
        
        with patch.dict(os.environ, {
            'EMUSES_JWT_SECRET': 'test-secret-key'
        }):
            setup_auth_endpoints(app)
            
            # Check that registration route exists
            route_paths = [route.path for route in app.routes]
            
            # Should include registration endpoint
            auth_register_paths = [path for path in route_paths if path.startswith('/auth') and 'register' in str(app.routes)]
            assert len(route_paths) > 0  # Routes were added
            
            # Test that endpoint responds (even if with error due to no database)
            client = TestClient(app)
            
            # Test with invalid data to avoid database operations
            response = client.post("/auth/register", json={})
            # Expect 422 for validation error, not 404 for missing endpoint
            assert response.status_code == 422

    def test_login_endpoint(self):
        """Test user login endpoint exists."""
        from emuses.multi_user_service.endpoints import setup_auth_endpoints
        
        app = FastAPI()
        
        with patch.dict(os.environ, {
            'EMUSES_JWT_SECRET': 'test-secret-key'
        }):
            setup_auth_endpoints(app)
            
            client = TestClient(app)
            
            # Test with missing credentials to avoid database operations
            response = client.post("/auth/jwt/login", data={})
            # Expect 422 for validation error (missing username/password), not 404 for missing endpoint
            assert response.status_code == 422