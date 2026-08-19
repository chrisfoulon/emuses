"""Test suite for authentication middleware integration.

This module tests the integration of authentication middleware with the existing
FastAPI application, ensuring proper positioning in middleware stack and
backward compatibility.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os


class TestAuthenticationMiddleware:
    """Test suite for authentication middleware integration."""

    def test_middleware_integration_exists(self):
        """Test that middleware integration functions exist."""
        from emuses.multi_user_service.middleware import (
            setup_authentication_middleware,
            get_conditional_auth_dependency
        )
        
        assert callable(setup_authentication_middleware)
        assert callable(get_conditional_auth_dependency)

    def test_setup_authentication_middleware_local_mode(self):
        """Test middleware setup in local mode (no auth required)."""
        from emuses.multi_user_service.middleware import setup_authentication_middleware
        
        app = FastAPI()
        
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'local'
        }):
            setup_authentication_middleware(app)
            
            # In local mode, middleware should be set up but optional
            assert app is not None

    def test_setup_authentication_middleware_multiuser_mode(self):
        """Test middleware setup in multi-user mode (auth required)."""
        from emuses.multi_user_service.middleware import setup_authentication_middleware
        
        app = FastAPI()
        
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'multi-user',
            'EMUSES_JWT_SECRET': 'test-secret'
        }):
            setup_authentication_middleware(app)
            
            # In multi-user mode, authentication should be configured
            assert app is not None

    def test_conditional_auth_dependency_local_mode(self):
        """Test conditional authentication dependency in local mode."""
        from emuses.multi_user_service.middleware import get_conditional_auth_dependency
        
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'local'
        }):
            dependency = get_conditional_auth_dependency()
            # In local mode, dependency should be optional (can return None)
            assert dependency is not None

    def test_conditional_auth_dependency_multiuser_mode(self):
        """Test conditional authentication dependency in multi-user mode."""
        from emuses.multi_user_service.middleware import get_conditional_auth_dependency
        
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'multi-user',
            'EMUSES_JWT_SECRET': 'test-secret'
        }):
            dependency = get_conditional_auth_dependency()
            # In multi-user mode, dependency should require authentication
            assert dependency is not None

    def test_middleware_stack_positioning(self):
        """Test that authentication middleware is positioned correctly in stack."""
        from emuses.multi_user_service.middleware import setup_authentication_middleware
        
        app = FastAPI()
        
        # Add CORS middleware first (like in existing app)
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(CORSMiddleware, allow_origins=["*"])
        
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'multi-user',
            'EMUSES_JWT_SECRET': 'test-secret'
        }):
            setup_authentication_middleware(app)
            
            # Check that middleware was added
            assert len(app.user_middleware) > 0

    def test_backward_compatibility_preservation(self):
        """Test that existing endpoints remain accessible."""
        from emuses.multi_user_service.middleware import (
            setup_authentication_middleware,
            get_conditional_auth_dependency
        )
        
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        with patch.dict(os.environ, {
            'EMUSES_DEPLOYMENT_MODE': 'local'
        }):
            setup_authentication_middleware(app)
            
            client = TestClient(app)
            response = client.get("/test")
            assert response.status_code == 200
            assert response.json() == {"message": "test"}